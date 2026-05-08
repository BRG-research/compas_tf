from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.elements import Element


class SherpaXL120Element(Element):
    """Class representing a Sherpa XL 120 connector element with a box geometry.

    Parameters
    ----------
    depth : float
        The depth of the connector (Y-axis).
    height : float
        The height of the connector (Z-axis).
    frame : :class:`compas.geometry.Frame`, optional
        Local frame of the box.
    transformation : :class:`compas.geometry.Transformation`, optional
        Transformation applied to the connector.
    name : str, optional
        Name of the element.
    """

    WIDTH = 18.0

    @property
    def __data__(self) -> dict:
        return {
            "depth": self._box.xsize,
            "height": self._box.zsize,
            "frame": self._box.frame,
            "transformation": self.transformation,
            "name": self.name,
        }

    def __init__(
        self,
        depth: float = 120.0,
        height: float = 410.0,
        frame: Optional[Frame] = None,
        transformation: Optional[Transformation] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=None, name=name)
        w = self.WIDTH
        self._box = Box.from_width_height_depth(depth, w, height)
        self._box.frame = Frame([0, 0, -w/2], [1, 0, 0], [0, 1, 0])
        if frame is not None:
            self._box.transform(Transformation.from_frame(frame))

    @property
    def box(self) -> Box:
        return self._box

    @property
    def width(self) -> float:
        return self._box.xsize

    @property
    def depth(self) -> float:
        return self._box.ysize

    @property
    def height(self) -> float:
        return self._box.zsize

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self._box.to_mesh()

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self._box.transformed(self.modeltransformation)
        box = Box.from_bounding_box(box.points)
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self._box.transformed(self.modeltransformation)
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_collision_mesh(self, inflate: float = 1.0) -> Mesh:
        raise NotImplementedError

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())
