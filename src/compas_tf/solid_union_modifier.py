from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.modifiers import Modifier

_UNION_BACKEND = None
_CHAIN_BACKEND = None


def _union_backend():
    """Resolve the pairwise boolean-union backend (cached after first call).

    Prefers ``compas_manifold`` over ``compas_cgal`` for the same robustness and
    speed reasons as the difference modifier (manifold is ~2-14x faster on the
    cutter-sized meshes used here and does not stall on near-degenerate input).
    Falls back to ``compas_cgal`` when ``compas_manifold`` is not installed.

    Both backends share the same signature::

        boolean_union_mesh_mesh(target_vf, source_vf) -> (V, F)

    Returns
    -------
    tuple[callable, str]
        The ``boolean_union_mesh_mesh`` function and the backend name.
    """
    global _UNION_BACKEND
    if _UNION_BACKEND is None:
        try:
            from compas_manifold.booleans import boolean_union_mesh_mesh

            _UNION_BACKEND = (boolean_union_mesh_mesh, "manifold")
        except ImportError:
            from compas_cgal.booleans import boolean_union_mesh_mesh

            _UNION_BACKEND = (boolean_union_mesh_mesh, "cgal")
    return _UNION_BACKEND


def _chain_backend():
    """Resolve the batched boolean-chain backend (cached after first call).

    Prefers ``compas_manifold`` over ``compas_cgal``. Both expose::

        boolean_chain(meshes, operations) -> (V, F)

    Returns
    -------
    tuple[callable, str]
        The ``boolean_chain`` function and the backend name.
    """
    global _CHAIN_BACKEND
    if _CHAIN_BACKEND is None:
        try:
            from compas_manifold.booleans import boolean_chain

            _CHAIN_BACKEND = (boolean_chain, "manifold")
        except ImportError:
            from compas_cgal.booleans import boolean_chain

            _CHAIN_BACKEND = (boolean_chain, "cgal")
    return _CHAIN_BACKEND


class SolidUnionModifier(Modifier):
    @staticmethod
    def apply_batch(sources: list, targetgeometry: Mesh) -> Mesh:
        """Apply all union sources in a single boolean_chain call (one C++ round-trip).

        Parameters
        ----------
        sources : list of :class:`compas.datastructures.Mesh`
            Meshes to union into the target.
        targetgeometry : :class:`compas.datastructures.Mesh`
            The base mesh.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            Result mesh, or original if the operation fails or produces no geometry.

        """
        from compas.geometry import Polyhedron

        boolean_chain, backend = _chain_backend()

        meshes = [targetgeometry.to_vertices_and_faces(triangulated=True)]
        for src in sources:
            meshes.append(src.to_vertices_and_faces(triangulated=True))
        operations = ["union"] * len(sources)
        print(f"[batch-union] boolean_chain ({backend}): target + {len(sources)} source(s)")
        try:
            V, F = boolean_chain(meshes, operations)
        except Exception as exc:
            print(f"[batch-union] boolean_chain failed: {exc}")
            return targetgeometry
        if not V.size or not F.size:
            print("[batch-union] empty result, keeping original")
            return targetgeometry
        print(f"[batch-union] OK -> V/F={len(V)}/{len(F)}")
        return Polyhedron(V.tolist(), F.tolist()).to_mesh()

    """Modifier for boolean union between two geometries.

    Parameters
    ----------
    name : str
        The name of the modifier.

    """

    @property
    def __data__(self) -> dict:
        return {}

    def apply(
        self,
        source,
        targetgeometry: Union[Brep, Mesh],
    ) -> Union[Brep, Mesh]:
        """Apply the boolean union to the target geometry.

        Skips the operation if source or target geometry is not a Mesh.

        Parameters
        ----------
        source : Element
            The source element whose geometry is merged into the target.
        targetgeometry : :class:`compas.geometry.Brep` | :class:`compas.datastructures.Mesh`
            The target of the modification.

        Returns
        -------
        Brep | Mesh
            The modified target geometry, or original if operation skipped.

        """
        from compas.geometry import Polyhedron

        boolean_union_mesh_mesh, _ = _union_backend()

        # Get source geometry
        source_geom = source.modelgeometry

        # Skip if source or target is not a Mesh
        if not isinstance(source_geom, Mesh):
            return targetgeometry
        if not isinstance(targetgeometry, Mesh):
            return targetgeometry

        SOURCE = source_geom.to_vertices_and_faces(triangulated=True)
        TARGET = targetgeometry.to_vertices_and_faces(triangulated=True)

        V, F = boolean_union_mesh_mesh(TARGET, SOURCE)
        shape = Polyhedron(V.tolist(), F.tolist())
        shape = shape.to_mesh()

        return shape
