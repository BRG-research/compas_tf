from typing import Optional

from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Plane
from compas.geometry import Transformation
from compas_model.elements.element import Element



class SliceElement(Element):
    """Class representing a slice element.

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
            "width": self.box.xsize,
            "depth": self.box.ysize,
            "length": self.box.zsize,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        frame: Frame = Frame.worldXY(),
        transformation: Optional[Transformation] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=[], name=name)
        self._frame = frame

    @property
    def frame(self) -> Frame:
        return self._frame

    @property
    def plane(self) -> Plane:
        return Plane.from_frame(self.frame)

    def compute_elementgeometry(self, include_features=False) -> Frame:
        """Compute the frame of the slice.

        Returns
        -------
        :class:`compas.geometry.Frame`
        """
        return self.plane

    def compute_point(self) -> Point:
        """Compute the reference point of the beam from the centroid of its geometry.

        Returns
        -------
        :class:`compas.geometry.Point`

        """
        return self.frame.point

