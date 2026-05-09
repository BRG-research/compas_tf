from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.modifiers import Modifier


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
        from compas_cgal.booleans import boolean_chain

        meshes = [targetgeometry.to_vertices_and_faces(triangulated=True)]
        for src in sources:
            meshes.append(src.to_vertices_and_faces(triangulated=True))
        operations = ["union"] * len(sources)
        print(f"[batch-union] boolean_chain: target + {len(sources)} source(s)")
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
        from compas_cgal.booleans import boolean_union_mesh_mesh

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
