from collections import defaultdict
from typing import Optional
from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.elements.element import Feature
from compas_model.modifiers import Modifier


def _bbox_center(meshes: list) -> tuple:
    """The centre of the combined axis-aligned bounding box of ``meshes``."""
    xs, ys, zs = [], [], []
    for mesh in meshes:
        for vertex in mesh.vertices():
            x, y, z = mesh.vertex_coordinates(vertex)
            xs.append(x)
            ys.append(y)
            zs.append(z)
    if not xs:
        return (0.0, 0.0, 0.0)
    return (0.5 * (min(xs) + max(xs)), 0.5 * (min(ys) + max(ys)), 0.5 * (min(zs) + max(zs)))


def heal_mesh(mesh: Mesh, precision: Optional[int] = None) -> Mesh:
    """Scrub a boolean result: weld coincident vertices, drop collapsed faces.

    Manifold already returns a watertight, welded mesh, so on a good result this
    is effectively a no-op. Its job is to remove the occasional zero-area sliver
    face or duplicated vertex a near-degenerate cut can leave behind - the "thin
    leftover" / barely-valid faces - WITHOUT changing the solid the mesh bounds:
    it only welds exactly-coincident points and deletes faces that have collapsed
    to fewer than three distinct vertices.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
    precision : int, optional
        Decimal precision for the vertex weld (defaults to ``compas.PRECISION``).

    Returns
    -------
    :class:`compas.datastructures.Mesh`
    """
    if not isinstance(mesh, Mesh):
        return mesh
    healed = mesh.copy()
    try:
        healed.weld(precision)
    except Exception:
        pass
    for face in list(healed.faces()):
        if len(set(healed.face_vertices(face))) < 3:  # collapsed after the weld
            try:
                healed.delete_face(face)
            except Exception:
                pass
    try:
        healed.remove_unused_vertices()
    except Exception:
        pass
    return healed


class MeshCutFeature(Feature):
    """Feature that boolean-differences cutter solids out of a host element.

    Stored on the host element (in its local frame), so the cut travels with
    copy/serialization and the cutter solids stay available for fabrication. The
    cutters are unioned into a single solid first (so shared/coplanar faces are
    not re-processed) and the largest connected piece of the result is kept.

    Parameters
    ----------
    meshes : list[:class:`compas.datastructures.Mesh`]
        Closed cutter solids to subtract, in the host element's local frame.
    name : str, optional
    """

    @property
    def __data__(self) -> dict:
        return {"meshes": self.meshes, "name": self.name}

    def __init__(self, meshes: list = None, name: Optional[str] = None):
        super().__init__(name=name)
        self.meshes = [mesh.copy() for mesh in (meshes or [])]

    def apply(self, shape: Mesh) -> Mesh:
        if not self.meshes:
            return shape

        from compas.geometry import Translation
        from compas_manifold.booleans import boolean_chain

        # Run the boolean with the operands shifted to the origin and shift the
        # result back: Manifold's merge tolerance scales with the bounding-box
        # magnitude, so working near (0,0,0) instead of out at the model's world
        # coordinates keeps it as precise as possible. Pure translation - the
        # carved solid is identical, just temporarily re-centred.
        cx, cy, cz = _bbox_center([shape] + self.meshes)
        to_origin = Translation.from_vector([-cx, -cy, -cz])
        from_origin = Translation.from_vector([cx, cy, cz])

        cutters = [mesh.transformed(to_origin).to_vertices_and_faces(True) for mesh in self.meshes]
        if len(cutters) > 1:
            unioned = boolean_chain(cutters, ["union"] * (len(cutters) - 1))
            cutters = [unioned]

        result = boolean_chain([shape.transformed(to_origin).to_vertices_and_faces(True), cutters[0]], ["difference"])
        carved = Mesh.from_vertices_and_faces(result[0], result[1]).transformed(from_origin)
        carved = SolidDifferenceModifier.largest_piece(carved)
        return heal_mesh(carved)  # scrub any zero-area sliver faces the cut left

    # A generic mesh cut has no parametric ("minimal") form; the typed subclasses
    # below override this to return their defining line / polylines.
    minimal = None

    def placed(self, transformation) -> "MeshCutFeature":
        """Return an independent copy with the cutter geometry moved by ``transformation``.

        Used to bring a stored (local-frame) feature into model space without
        mutating the original. Subclasses that are parametric override this to
        move their defining geometry instead of the (derived) meshes.
        """
        feature = self.copy()
        feature.meshes = [mesh.transformed(transformation) for mesh in feature.meshes]
        return feature


class CylinderCutFeature(MeshCutFeature):
    """A cylindrical cut defined parametrically by an axis ``line`` + ``radius``.

    The ``(line, radius, sides)`` is the source of truth; the closed boolean
    cutter mesh is derived from it on demand (so it is never serialized). Use
    :attr:`minimal` (the axis line) for fabrication / inspection, and
    :attr:`meshes` for the boolean difference.

    Parameters
    ----------
    line : :class:`compas.geometry.Line`
        The cylinder axis, in the host element's local frame.
    radius : float
        The cylinder radius.
    sides : int, optional
        Polygon resolution of the derived cutter mesh.
    name : str, optional
    """

    @property
    def __data__(self) -> dict:
        return {"line": self.line, "radius": self.radius, "sides": self.sides, "name": self.name}

    def __init__(self, line=None, radius: float = 10.0, sides: int = 8, name: Optional[str] = None):
        Feature.__init__(self, name=name)
        self.line = line
        self.radius = radius
        self.sides = sides

    @property
    def meshes(self) -> list:
        """The cylinder cutter as a one-item list of closed meshes (for booleans)."""
        from compas_tf.connectors import ConnectorCylinderElement

        return [ConnectorCylinderElement(line=self.line, radius=self.radius, sides=self.sides).compute_mesh()]

    @property
    def minimal(self):
        """The axis line - the minimal representation of a cylinder cut."""
        return self.line

    def placed(self, transformation) -> "CylinderCutFeature":
        feature = self.copy()
        feature.line = self.line.transformed(transformation)
        return feature


class PrismCutFeature(MeshCutFeature):
    """A prism cut (box, wedge, ... any extrusion) defined by co-wound ``bottom``
    and ``top`` boundary polylines, lofted exactly like a plate.

    The two polylines are the source of truth; the closed boolean cutter mesh is
    the loft between them, derived on demand. Use :attr:`minimal`
    (``(bottom, top)``) for fabrication / inspection - the same top/bottom
    representation a :class:`compas_tf.plate.PlateElement` uses.

    Parameters
    ----------
    bottom, top : :class:`compas.geometry.Polyline`
        Co-wound boundary polylines (vertex *i* of ``bottom`` matches vertex *i*
        of ``top``), in the host element's local frame.
    name : str, optional
    """

    @property
    def __data__(self) -> dict:
        return {"bottom": self.bottom, "top": self.top, "name": self.name}

    def __init__(self, bottom=None, top=None, name: Optional[str] = None):
        Feature.__init__(self, name=name)
        self.bottom = bottom
        self.top = top

    @property
    def meshes(self) -> list:
        """The prism cutter as a one-item list of closed meshes (for booleans)."""
        from compas_tf.plate import PlateElement

        return [PlateElement.loft(self.bottom, self.top, cap=True, close=True)]

    @property
    def minimal(self):
        """``(bottom, top)`` polylines - the minimal representation of a prism cut."""
        return (self.bottom, self.top)

    def placed(self, transformation) -> "PrismCutFeature":
        feature = self.copy()
        feature.bottom = self.bottom.transformed(transformation)
        feature.top = self.top.transformed(transformation)
        return feature


def _difference_backend():
    """Return the pairwise boolean-difference backend (compas_manifold).

    Manifold's ``boolean_difference_mesh_mesh`` always returns watertight,
    oriented 2-manifold output and does not hang on the near-degenerate /
    self-intersecting cutters that make other corefinement kernels stall::

        boolean_difference_mesh_mesh(target_vf, cutter_vf) -> (V, F)

    where the inputs are ``(vertices, faces)`` tuples and the result is a pair
    of numpy arrays (triangulated faces).

    Returns
    -------
    tuple[callable, str]
        The ``boolean_difference_mesh_mesh`` function and the backend name.
    """
    from compas_manifold.booleans import boolean_difference_mesh_mesh

    return (boolean_difference_mesh_mesh, "manifold")


def _chain_backend():
    """Return the batched boolean-chain backend (compas_manifold).

    ::

        boolean_chain(meshes, operations) -> (V, F)
        boolean_chain_with_face_source(meshes, operations) -> (V, F, S)

    where ``meshes`` is an iterable of ``(vertices, faces)`` tuples and ``S`` is
    an ``[N, 2]`` array of ``[mesh_id, face_id]`` tags.

    Returns
    -------
    tuple[callable, callable, str]
        ``(boolean_chain, boolean_chain_with_face_source, backend_name)``.
    """
    from compas_manifold.booleans import boolean_chain
    from compas_manifold.booleans import boolean_chain_with_face_source

    return (boolean_chain, boolean_chain_with_face_source, "manifold")


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


def merge_coplanar_faces(mesh: Mesh, normal_tol: float = 1e-3, offset_tol: float = 1e-3) -> Mesh:
    """Merge groups of adjacent coplanar faces into single polygon faces.

    Boolean kernels (and the capitel union) emit triangle soup; face-face
    contact detection needs one polygon per flat region or it fragments/misses
    contacts. This welds the mesh, groups adjacent faces that share a common
    plane (matching unit normal and plane offset within tolerance), and re-traces
    each group's outer boundary into a single polygon face.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh to clean (typically a triangulated boolean result).
    normal_tol : float
        Max ``|n_a x n_b|`` (sine of the angle) for two normals to count as parallel.
    offset_tol : float
        Max difference in plane offset (distance along the normal) for two faces
        to count as co-planar.

    Returns
    -------
    :class:`compas.datastructures.Mesh`
        A mesh with maximal planar polygon faces. Returns a copy unchanged if it
        has a single face.
    """
    from compas.geometry import cross_vectors
    from compas.geometry import dot_vectors
    from compas.geometry import length_vector

    work = mesh.copy()
    try:
        work.weld()  # boolean output has coincident-but-distinct vertices at seams
    except Exception:
        pass

    faces = list(work.faces())
    if len(faces) <= 1:
        return work

    planes = {}
    for face in faces:
        normal = work.face_normal(face)
        if length_vector(normal) == 0:
            planes[face] = None
        else:
            planes[face] = (normal, dot_vectors(normal, work.face_centroid(face)))

    # Union-find: union adjacent faces that lie on the same plane.
    parent = {face: face for face in faces}

    def find(x):
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    for face in faces:
        plane = planes[face]
        if plane is None:
            continue
        normal, offset = plane
        for nbr in work.face_neighbors(face):
            other = planes.get(nbr)
            if other is None:
                continue
            n2, d2 = other
            if dot_vectors(normal, n2) > 0 and length_vector(cross_vectors(normal, n2)) < normal_tol and abs(offset - d2) < offset_tol:
                parent[find(face)] = find(nbr)

    groups = defaultdict(list)
    for face in faces:
        groups[find(face)].append(face)

    new_faces = []
    for grp in groups.values():
        if len(grp) == 1:
            new_faces.append(work.face_vertices(grp[0]))
            continue

        # Boundary half-edges of the merged region are those with no reverse twin.
        half_edges = set()
        for face in grp:
            verts = work.face_vertices(face)
            for i in range(len(verts)):
                half_edges.add((verts[i], verts[(i + 1) % len(verts)]))
        nxt = {a: b for (a, b) in half_edges if (b, a) not in half_edges}

        loops = []
        visited = set()
        for start in list(nxt):
            if start in visited:
                continue
            loop = [start]
            visited.add(start)
            step = nxt.get(start)
            while step is not None and step != start and step not in visited:
                loop.append(step)
                visited.add(step)
                step = nxt.get(step)
            if len(loop) >= 3:
                loops.append(loop)

        if len(loops) == 1:
            new_faces.append(loops[0])  # single outer boundary -> one polygon face
        else:
            # Region with hole(s) (e.g. a dowel hole on a face) or an untraceable
            # boundary: a single polygon face cannot carry a hole, so keep the
            # original (already-manifold) boolean faces for this group rather than
            # merging - merging would orphan the hole and open the mesh.
            new_faces.extend(work.face_vertices(face) for face in grp)

    vkeys = list(work.vertices())
    vindex = {vk: i for i, vk in enumerate(vkeys)}
    vertices = [work.vertex_coordinates(vk) for vk in vkeys]
    faces_idx = [[vindex[vk] for vk in fverts] for fverts in new_faces]
    merged = Mesh.from_vertices_and_faces(vertices, faces_idx)

    # Safety net: coplanar merging is a cleanup for contact detection, not a
    # correctness requirement. On complex cuts it can introduce non-manifold
    # edges, so never downgrade a manifold input to a non-manifold output -
    # fall back to the (manifold) welded mesh.
    try:
        if not merged.is_manifold():
            return work
    except Exception:
        return work
    return merged


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
    def largest_piece(mesh: Mesh) -> Mesh:
        """Return the largest connected component of a (possibly disjoint) mesh.

        A boolean difference can split the target into several disconnected
        solids (e.g. a cut that lops a chunk off the column head); we keep only
        the main body. "Largest" is measured by absolute volume, falling back to
        face count for any component whose volume cannot be evaluated.

        Parameters
        ----------
        mesh : :class:`compas.datastructures.Mesh`

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            The largest component, or ``mesh`` unchanged if it is already a
            single connected piece.
        """
        if not isinstance(mesh, Mesh):
            return mesh
        try:
            if mesh.is_connected():
                return mesh
        except Exception:
            pass
        parts = mesh.exploded()
        if len(parts) <= 1:
            return mesh

        def _volume(part):
            try:
                vol = abs(part.volume())
                return vol if vol > 0 else None
            except Exception:
                return None

        volumes = [_volume(part) for part in parts]

        def _score(index):
            return volumes[index] if volumes[index] is not None else float(parts[index].number_of_faces())

        best = max(range(len(parts)), key=_score)
        largest = parts[best]

        # Dropping a tiny sliver is normal; dropping a NON-trivial piece means the
        # cut fragmented the host solid (almost always a coplanar / degenerate
        # cutter) and real geometry is being thrown away - make that loud instead
        # of silent, so it can be fixed at the source rather than masked here.
        kept = volumes[best]
        discarded = sum(v for i, v in enumerate(volumes) if i != best and v)
        if kept and discarded > 0.01 * kept:
            import warnings

            warnings.warn(
                f"largest_piece kept 1 of {len(parts)} solids and discarded {discarded:.4g} mm^3 "
                f"(~{100 * discarded / kept:.0f}% of the kept volume) - the cut is fragmenting the host; "
                f"check for coplanar/degenerate cutters",
                stacklevel=2,
            )
        return largest

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

        # A pure-difference result may be split into disjoint solids; keep only
        # the largest piece. Skipped when a union/intersection is in the mix,
        # where multiple disconnected pieces can be intentional.
        only_difference = all(op == "difference" for op in operations)

        def _finish(mesh):
            return SolidDifferenceModifier.largest_piece(mesh) if only_difference else mesh

        boolean_chain, boolean_chain_with_face_source, backend = _chain_backend()

        op_summary = "+".join(sorted(set(operations)))
        print(f"[batch-bool] {backend} boolean_chain ({op_summary}): target + {len(sources)} mesh(es)")

        if has_xor:
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
            return _finish(Mesh.from_vertices_and_faces(V.tolist(), F.tolist()))

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
            return _finish(Mesh.from_vertices_and_faces(V.tolist(), F.tolist()))

        boolean_difference_mesh_mesh, _ = _difference_backend()

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
        return _finish(result_mesh)

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

        boolean_difference_mesh_mesh, backend = _difference_backend()

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
            print(f"[diff] {backend} raised for '{source_name}': {exc}")
            return targetgeometry

        vertices = V.tolist()
        faces = F.tolist()

        if not vertices or not faces:
            print(f"[diff] empty result for '{source_name}', keeping original")
            return targetgeometry

        shape = Polyhedron(vertices, faces)
        shape = shape.to_mesh()
        print(f"[diff] '{source_name}' OK  -> result V/F={len(vertices)}/{len(faces)}")
        # A difference can split the target into disjoint solids; keep the main body.
        return SolidDifferenceModifier.largest_piece(shape)
