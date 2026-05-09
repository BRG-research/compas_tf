from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas_model.elements import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineLoft


class DowelFeature(Feature):
    pass


class DowelElement(Element):
    """Class representing a rectangular dowel connector element.

    Simple extruded rectangle along Z axis.
    The element geometry is represented as a line (axis) for visualization.

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
    axis : :class:`compas.geometry.Line`
        The center axis of the dowel (with transformation applied).
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
        self._axis = Line([0, 0, 0], [0, 0, height])

    @property
    def axis(self) -> Line:
        """Get the axis line with transformation applied."""
        if self.transformation:
            return self._axis.transformed(self.transformation)
        return self._axis

    def compute_mesh(self) -> Mesh:
        """Compute the detailed mesh geometry for boolean operations."""
        import math
        n = 8
        r = self.width / 2
        pts = [Point(r * math.cos(2 * math.pi * k / n), r * math.sin(2 * math.pi * k / n), 0) for k in range(n)]
        circle_bottom = Polyline(pts + [pts[0]])
        circle_top = circle_bottom.translated([0, 0, self.height])
        return PolylineLoft.to_mesh(circle_bottom, circle_top)

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self.compute_mesh()

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        line = self.axis
        midpoint = line.midpoint
        size = max(self.width, self.depth)
        box = Box(size * inflate, size * inflate, self.height * inflate, frame=Frame(midpoint))
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        return self.compute_aabb(inflate)

    def compute_point(self) -> Point:
        return Point(*self.axis.midpoint)
