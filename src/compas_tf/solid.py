from typing import Optional

from compas.geometry import Frame
from compas.geometry import Point
from compas.datastructures import Mesh
from compas.geometry import Transformation
from compas_model.elements.element import Element



class Solid(Element):
    """Class representing a solid element.

    Parameters
    ----------
    frame : :class:`compas.geometry.Frame`
        The frame of the slice.
    transformation : Optional[:class:`compas.geometry.Transformation`]
        Transformation applied to the slice.
    name : Optional[str]
        If no name is defined, the class name is given.


    """

    @property
    def __data__(self) -> dict:
        return {
            "mesh": self.mesh,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        mesh: Mesh,
        transformation: Optional[Transformation] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=[], name=name)
        self._mesh = mesh

    @property
    def mesh(self) -> Frame:
        return self._mesh

    def compute_elementgeometry(self, include_features=False) -> Frame:
        """Compute the frame of the slice.

        Returns
        -------
        :class:`compas.geometry.Frame`
        """
        return self.mesh

    def compute_point(self) -> Point:
        """Compute the reference point of the beam from the centroid of its geometry.

        Returns
        -------
        :class:`compas.geometry.Point`

        """
        return self.mesh.centroid

