from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
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
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry of the screw.
    axis : :class:`compas.geometry.Line`
        The center axis of the screw.
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

        rectangle0 = Polygon.from_sides_and_radius_xy(4, diameter / 2)
        rectangle1 = Polygon.from_sides_and_radius_xy(4, diameter_head / 2)
        xform0 = Translation.from_vector([0, 0, diameter])
        xform1 = Translation.from_vector([0, 0, height])

        polylines = [rectangle1, rectangle1.transformed(xform0), rectangle0.transformed(xform0), rectangle0.transformed(xform1)]
        self.mesh = PolylineLoft.multiple_to_mesh(polylines)
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