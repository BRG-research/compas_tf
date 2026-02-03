from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.modifiers import Modifier


class SolidDifferenceModifier(Modifier):
    """Modifier for boolean difference between two geometries.

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

        # Skip if source or target is not a Mesh
        if not isinstance(source_geom, Mesh):
            return targetgeometry
        if not isinstance(targetgeometry, Mesh):
            return targetgeometry

        SOURCE = source_geom.to_vertices_and_faces(triangulated=True)
        TARGET = targetgeometry.to_vertices_and_faces(triangulated=True)

        V, F = boolean_difference_mesh_mesh(TARGET, SOURCE)
        vertices = V.tolist()
        faces = F.tolist()

        if not vertices or not faces:
            print(f"WARNING: Boolean difference produced empty result, keeping original geometry")
            return targetgeometry

        shape = Polyhedron(vertices, faces)
        shape = shape.to_mesh()

        return shape
