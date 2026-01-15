# from typing import Optional
from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.modifiers import Modifier


class SolidDifferenceModifier(Modifier):
    """Modifier for slicing a geometry with a frame.

    Parameters
    ----------
    name : str
        The name of the modifier.

    """

    @property
    def __data__(self) -> dict:
        return {"frame": self.frame}

    def apply(
        self,
        source,
        targetgeometry: Union[Brep, Mesh],
    ) -> Union[Brep, Mesh]:
        """Apply the interaction to the target geometry.

        Parameters
        ----------
        target : :class:`compas.geometry.Brep` | :class:`compas.datastructures.Mesh`
            The target of the modification.

        Returns
        -------
        Brep | Mesh
            The modified target geometry.

        """

        print("Applying SolidDifferenceModifier...")

        from compas.geometry import Polyhedron
        from compas_cgal.booleans import boolean_difference_mesh_mesh

        SOURCE = source.modelgeometry.to_vertices_and_faces(triangulated=True)
        TARGET = targetgeometry.to_vertices_and_faces(triangulated=True)

        V, F = boolean_difference_mesh_mesh(TARGET, SOURCE)
        shape = Polyhedron(V.tolist(), F.tolist())
        shape = shape.to_mesh()

        return shape
