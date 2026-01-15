from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Transformation
from compas.geometry import Translation
from compas_model.elements import Element
from compas_model.elements.element import Feature
from compas.geometry import Polygon
from compas_tf.geometry import PolylineLoft

# from compas_model.interactions import BooleanModifier
# from compas_model.interactions import Modifier


class ScrewFeature(Feature):
    pass


class ScrewElement(Element):
    """Class representing a beam element with a square section, constructed from the WorldXY Frame.
    The column is defined in its local frame, where the height corresponds to the Z-Axis, the depth to the Y-Axis, and the width to the X-Axis.
    By default, the local frame is set to WorldXY frame.

    Parameters
    ----------
    width : float
        The width of the column.
    depth : float
        The depth of the column.
    height : float
        The height of the column.
    transformation : Optional[:class:`compas.geometry.Transformation`]
        Transformation applied to the column.
    features : Optional[list[:class:`compas_model.features.ColumnFeature`]]
        Features of the column.
    name : Optional[str]
        If no name is defined, the class name is given.

    Attributes
    ----------
    width : float
        The width of the column.
    depth : float
        The depth of the column.
    height : float
        The height of the column.
    center_line : :class:`compas.geometry.Line`
        Line axis of the column.
    """

    @property
    def __data__(self) -> dict:
        return {
            "width": self.box.xsize,
            "depth": self.box.ysize,
            "height": self.box.zsize,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        diameter: float = 80.0,
        diameter_head: float = 250.0,
        height: float = 320.0,
        transformation: Optional[Transformation] = None,
        features: Optional[list[ScrewFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
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