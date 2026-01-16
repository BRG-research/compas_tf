from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas.geometry import Translation
from compas_model.elements import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineLoft


class DowelFeature(Feature):
    pass


class DowelElement(Element):
    """Class representing a rectangular dowel connector element.

    Simple extruded rectangle along Z axis.

    Parameters
    ----------
    width : float
        The width of the dowel (X direction).
    depth : float
        The depth of the dowel (Y direction).
    height : float
        The height/length of the dowel (Z direction).
    transformation : Optional[:class:`compas.geometry.Transformation`]
        Transformation applied to the dowel.
    features : Optional[list[:class:`DowelFeature`]]
        Features of the dowel.
    name : Optional[str]
        If no name is defined, the class name is given.

    Attributes
    ----------
    width : float
        The width of the dowel.
    depth : float
        The depth of the dowel.
    height : float
        The height of the dowel.
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry of the dowel.
    axis : :class:`compas.geometry.Line`
        The center axis of the dowel.
    """

    @property
    def __data__(self) -> dict:
        return {
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        width: float = 20.0,
        depth: float = 20.0,
        height: float = 100.0,
        transformation: Optional[Transformation] = None,
        features: Optional[list[DowelFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.width = width
        self.depth = depth
        self.height = height

        # Create rectangle centered at origin
        w, d = width / 2, depth / 2
        rect_bottom = Polyline([
            Point(-w, -d, 0),
            Point(w, -d, 0),
            Point(w, d, 0),
            Point(-w, d, 0),
            Point(-w, -d, 0),
        ])
        rect_top = rect_bottom.translated([0, 0, height])

        self.mesh = PolylineLoft.to_mesh(rect_bottom, rect_top)
        self.axis = Line([0, 0, 0], [0, 0, height])

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self.mesh

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.aabb
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.obb
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())
