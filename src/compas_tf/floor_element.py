import math
from dataclasses import dataclass
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Projection
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Vector
from compas.geometry import intersection_line_line
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import LineOffset
from compas_tf.geometry import PlaneIntersect
from compas_tf.geometry import PolylineCut
from compas_tf.geometry import PolylineLoft
from compas_tf.geometry import PolylineOffset
from compas_tf.joint_dowel import DowelElement
from compas_tf.joint_hilti import HiltiElement
from compas_tf.joint_screw import ScrewElement
from compas_tf.joint_strip import AlignmentStripElement
from compas_tf.plate import PlateElement
from compas_tf.solid_difference_modifier import SolidDifferenceModifier

# ==========================================================================
# Element Classes
# ==========================================================================


class QuarterFloorFeature(Feature):
    pass


class QuarterFloorElement(Element):
    """Quarter floor element containing rib, t-section, surface, and boundary geometry."""

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
        mesh: Mesh = None,
        transformation: Optional[Transformation] =  None,
        features: Optional[list[QuarterFloorFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.mesh = mesh if mesh else Mesh()

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