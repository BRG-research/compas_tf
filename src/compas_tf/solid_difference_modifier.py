from collections import defaultdict
from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.modifiers import Modifier


def _triangulate_mesh(mesh, precision=12):
    """Fan-triangulate a compas Mesh, returning (vertices, triangles, tri_to_orig).

    ``tri_to_orig[i]`` is the original face index that produced output triangle ``i``.
    This lets us remap CGAL's per-triangle face_id back to the original polygon face.

    Vertex coordinates are rounded to ``precision`` decimal places to eliminate
    sub-ULP floating-point noise from chained transformations that can cause
    CGAL corefinement to fail on near-coplanar faces.
    """
    vkeys = list(mesh.vertices())
    vindex = {vk: i for i, vk in enumerate(vkeys)}
    vertices = [[round(c, precision) for c in mesh.vertex_coordinates(vk)] for vk in vkeys]

    triangles = []
    tri_to_orig = {}
    for orig_idx, fkey in enumerate(mesh.faces()):
        fverts = [vindex[vk] for vk in mesh.face_vertices(fkey)]
        n = len(fverts)
        if n == 3:
            triangles.append(fverts)
            tri_to_orig[len(triangles) - 1] = orig_idx
        else:
            v0 = fverts[0]
            for k in range(1, n - 1):
                triangles.append([v0, fverts[k], fverts[k + 1]])
                tri_to_orig[len(triangles) - 1] = orig_idx

    return vertices, triangles, tri_to_orig


def _polygonal_mesh_from_face_source(V, F, S, tri_to_orig_per_mesh):
    """Reconstruct a polygonal mesh from boolean_chain_with_face_source output.

    Each output triangle in F carries a source tag S[i] = [mesh_id, face_id]
    where face_id is the index in the *triangulated* input mesh.
    ``tri_to_orig_per_mesh[mesh_id]`` maps that triangulated face_id back to
    the original polygon face index, so triangles that came from the same
    polygon (but were split during triangulation) are grouped together.

    Parameters
    ----------
    V : ndarray (N, 3)
    F : ndarray (M, 3)  — triangle soup from CGAL
    S : ndarray (M, 2)  — [mesh_id, face_id] per triangle
    tri_to_orig_per_mesh : list[dict]
        One dict per input mesh: ``tri_to_orig_per_mesh[mesh_id][tri_face_id]``
        gives the original polygon face index.

    Returns
    -------
    :class:`compas.datastructures.Mesh`
        Polygonal mesh with one face per original input face.
    """
    vertices = V.tolist()
    tris = F.tolist()

    # Remap triangulated face_id → original polygon face_id
    tags = []
    for mesh_id, tri_fid in S.tolist():
        orig_fid = tri_to_orig_per_mesh[mesh_id].get(tri_fid, tri_fid)
        tags.append((mesh_id, orig_fid))

    # Group triangle indices by (mesh_id, face_id)
    groups = defaultdict(list)
    for i, tag in enumerate(tags):
        groups[tag].append(i)

    new_faces = []
    for tri_indices in groups.values():
        if len(tri_indices) == 1:
            new_faces.append(tris[tri_indices[0]])
            continue

        # Collect all directed half-edges for this group
        half_edges = set()
        for ti in tri_indices:
            t = tris[ti]
            half_edges.add((t[0], t[1]))
            half_edges.add((t[1], t[2]))
            half_edges.add((t[2], t[0]))

        # Boundary: half-edges whose reverse is absent → outer polygon edges
        adj = {a: b for (a, b) in half_edges if (b, a) not in half_edges}

        if not adj:
            for ti in tri_indices:
                new_faces.append(tris[ti])
            continue

        # Trace one (or more) boundary loops
        visited = set()
        for start in list(adj):
            if start in visited:
                continue
            loop = [start]
            visited.add(start)
            nxt = adj[start]
            while nxt != start and nxt not in visited:
                loop.append(nxt)
                visited.add(nxt)
                nxt = adj.get(nxt, start)
            if len(loop) >= 3:
                new_faces.append(loop)

    return Mesh.from_vertices_and_faces(vertices, new_faces)


class SolidDifferenceModifier(Modifier):
    SUPPORTED_WITH_FACE_SOURCE = {"union", "difference", "intersection"}

    def __init__(self, operation: str = "difference", name: str = None):
        """Boolean modifier with a configurable operation type.

        Parameters
        ----------
        operation : str
            One of ``"difference"``, ``"union"``, ``"intersection"``, ``"xor"``.
            ``"xor"`` falls back to ``boolean_chain`` (no face-source tracking).
        """
        super().__init__(name=name)
        if operation not in ("difference", "union", "intersection", "xor"):
            raise ValueError(f"Unknown boolean operation '{operation}'. Use difference/union/intersection/xor.")
        self.operation = operation

    @property
    def __data__(self) -> dict:
        return {"operation": self.operation}

    @classmethod
    def __from_data__(cls, data: dict) -> "SolidDifferenceModifier":
        return cls(operation=data.get("operation", "difference"))

    @staticmethod
    def apply_batch(sources: list, targetgeometry: Mesh, operations: list = None) -> Mesh:
        """Apply a sequence of boolean operations in a single CGAL call.

        Each entry in ``sources`` corresponds to the operation at the same index
        in ``operations``.  Supported values: ``"difference"``, ``"union"``,
        ``"intersection"``.  If any operation is ``"xor"``, the method falls
        back to ``boolean_chain`` (no face-source tracking, triangle output).

        Parameters
        ----------
        sources : list of :class:`compas.datastructures.Mesh`
        targetgeometry : :class:`compas.datastructures.Mesh`
        operations : list of str, optional
            Per-source operation strings.  Defaults to ``["difference"] * n``.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        if operations is None:
            operations = ["difference"] * len(sources)

        has_xor = any(op == "xor" for op in operations)

        op_summary = "+".join(sorted(set(operations)))
        print(f"[batch-bool] boolean_chain ({op_summary}): target + {len(sources)} mesh(es)")

        if has_xor:
            from compas_cgal.booleans import boolean_chain

            all_vf = []
            for mesh in [targetgeometry] + list(sources):
                verts, tris, _ = _triangulate_mesh(mesh)
                all_vf.append((verts, tris))

            try:
                V, F = boolean_chain(all_vf, operations)
            except Exception as exc:
                print(f"[batch-bool] boolean_chain failed: {exc}")
                return targetgeometry
            if not V.size or not F.size:
                print("[batch-bool] empty result, keeping original")
                return targetgeometry
            print(f"[batch-bool] OK -> V/F={len(V)}/{len(F)}")
            return Mesh.from_vertices_and_faces(V.tolist(), F.tolist())

        from compas_cgal.booleans import boolean_chain_with_face_source

        all_vf = []
        for mesh in [targetgeometry] + list(sources):
            verts, tris, _ = _triangulate_mesh(mesh)
            all_vf.append((verts, tris))

        try:
            V, F, S = boolean_chain_with_face_source(all_vf, operations)
        except Exception as exc:
            print(f"[batch-bool] boolean_chain_with_face_source failed: {exc}")
            V, F = None, None
        else:
            if not V.size or not F.size:
                V, F = None, None

        if V is not None:
            print(f"[batch-bool] OK -> V/F={len(V)}/{len(F)}")
            return Mesh.from_vertices_and_faces(V.tolist(), F.tolist())

        from compas_cgal.booleans import boolean_difference_mesh_mesh

        print("[batch-bool] chain returned empty, falling back to sequential")
        result_mesh = targetgeometry
        for i, src in enumerate(sources):
            T = result_mesh.to_vertices_and_faces(triangulated=True)
            C = src.to_vertices_and_faces(triangulated=True)
            try:
                V, F = boolean_difference_mesh_mesh(T, C)
            except Exception as exc:
                print(f"[batch-bool] sequential step {i} failed: {exc}")
                return targetgeometry
            if not V.size or not F.size:
                print(f"[batch-bool] sequential step {i} empty, keeping original")
                return targetgeometry
            result_mesh = Mesh.from_vertices_and_faces(V.tolist(), F.tolist())
        print(f"[batch-bool] sequential OK -> V/F={result_mesh.number_of_vertices()}/{result_mesh.number_of_faces()}")
        return result_mesh

    """Modifier for boolean difference between two geometries.

    Parameters
    ----------
    name : str
        The name of the modifier.

    """

    def apply(
        self,
        source,
        targetgeometry: Union[Brep, Mesh],
    ) -> Union[Brep, Mesh]:
        """Apply the boolean difference to the target geometry.

        Skips the operation if source or target geometry is not a Mesh.

        Parameters
        ----------
        source : Element
            The source element (cutter).
        targetgeometry : :class:`compas.geometry.Brep` | :class:`compas.datastructures.Mesh`
            The target of the modification.

        Returns
        -------
        Brep | Mesh
            The modified target geometry, or original if operation skipped.

        """
        from compas.geometry import Polyhedron
        from compas_cgal.booleans import boolean_difference_mesh_mesh

        # Get source geometry
        source_geom = source.modelgeometry
        source_name = getattr(source, "name", "<unnamed>")

        # Skip if source or target is not a Mesh
        if not isinstance(source_geom, Mesh):
            print(f"[diff] skip '{source_name}': source is {type(source_geom).__name__}, not Mesh")
            return targetgeometry
        if not isinstance(targetgeometry, Mesh):
            print(f"[diff] skip '{source_name}': target is {type(targetgeometry).__name__}, not Mesh")
            return targetgeometry

        # Watertight inputs are required; an open mesh will abort CGAL hard.
        src_closed = source_geom.is_closed()
        tgt_closed = targetgeometry.is_closed()
        print(
            f"[diff] '{source_name}' -> target  "
            f"src V/F/closed={source_geom.number_of_vertices()}/{source_geom.number_of_faces()}/{src_closed}  "
            f"tgt V/F/closed={targetgeometry.number_of_vertices()}/{targetgeometry.number_of_faces()}/{tgt_closed}"
        )
        if not src_closed:
            print(f"[diff] skip '{source_name}': cutter not closed")
            return targetgeometry
        if not tgt_closed:
            print(f"[diff] skip '{source_name}': target not closed")
            return targetgeometry

        SOURCE = source_geom.to_vertices_and_faces(triangulated=True)
        TARGET = targetgeometry.to_vertices_and_faces(triangulated=True)

        try:
            V, F = boolean_difference_mesh_mesh(TARGET, SOURCE)
        except Exception as exc:
            print(f"[diff] CGAL raised for '{source_name}': {exc}")
            return targetgeometry

        vertices = V.tolist()
        faces = F.tolist()

        if not vertices or not faces:
            print(f"[diff] empty result for '{source_name}', keeping original")
            return targetgeometry

        shape = Polyhedron(vertices, faces)
        shape = shape.to_mesh()
        print(f"[diff] '{source_name}' OK  -> result V/F={len(vertices)}/{len(faces)}")
        return shape
