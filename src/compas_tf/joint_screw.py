from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Transformation
from compas.geometry import Translation
from compas_model.elements import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineLoft


class ScrewFeature(Feature):
    pass


class ScrewElement(Element):
    """Class representing a screw connector element.

    The screw has a wider head at the base that tapers to a smaller diameter shaft.
    The element geometry is represented as a line (axis) for visualization.

    Parameters
    ----------
    diameter : float
        The diameter of the screw shaft.
    diameter_head : float
        The diameter of the screw head.
    height : float
        The total height of the screw.
    transformation : Optional[:class:`compas.geometry.Transformation`]
        Transformation applied to the screw.
    features : Optional[list[:class:`ScrewFeature`]]
        Features of the screw.
    name : Optional[str]
        If no name is defined, the class name is given.

    Attributes
    ----------
    diameter : float
        The diameter of the screw shaft.
    diameter_head : float
        The diameter of the screw head.
    height : float
        The total height of the screw.
    axis : :class:`compas.geometry.Line`
        The center axis of the screw (with transformation applied).
    """

    @property
    def __data__(self) -> dict:
        return {
            "diameter": self.diameter,
            "diameter_head": self.diameter_head,
            "height": self.height,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        diameter: float = 8.0,
        diameter_head: float = 25.0,
        height: float = 320.0,
        transformation: Optional[Transformation] = None,
        features: Optional[list[ScrewFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.diameter = diameter
        self.diameter_head = diameter_head
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
        rectangle0 = Polygon.from_sides_and_radius_xy(4, self.diameter / 2)
        rectangle1 = Polygon.from_sides_and_radius_xy(4, self.diameter_head / 2)
        xform_boolean_tolerance = Translation.from_vector([0, 0, -1])
        xform0 = Translation.from_vector([0, 0, self.diameter])
        xform1 = Translation.from_vector([0, 0, self.height])

        polylines = [rectangle1.transformed(xform_boolean_tolerance), rectangle1.transformed(xform0), rectangle0.transformed(xform0), rectangle0.transformed(xform1)]
        return PolylineLoft.multiple_to_mesh(polylines)

    def compute_elementgeometry(self, include_features=False) -> Line:
        return self._axis

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        line = self.axis
        midpoint = line.midpoint
        box = Box(self.diameter_head * inflate, self.diameter_head * inflate, self.height * inflate, frame=Frame(midpoint))
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        return self.compute_aabb(inflate)

    def compute_point(self) -> Point:
        return Point(*self.axis.midpoint)
