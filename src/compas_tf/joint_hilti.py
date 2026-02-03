from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements import Element

from compas_tf.geometry import PolylineLoft


# Polyline coordinates parsed from hilti.txt
_POLYLINE_A_POINTS = [
    (-10.0, 20.0, 0),
    (13.925, 20.0, 0),
    (44.10267, 32.5, 0),
    (89.925044, 32.5, 0),
    (89.925044, -32.500014, 0),
    (44.10267, -32.500014, 0),
    (13.925, -20, 0),
    (-10.0, -20.0, 0),
    (-10.0, 20.0, 0),
]

_POLYLINE_B_POINTS = [
    (-96.075, 32.5, 0),
    (-44.25267, 32.5, 0),
    (-13.925, 20.0, 0),
    (10, 20.0, 0),
    (10.0, -20.0, 0),
    (-13.925, -20.0, 0),
    (-44.25267, -32.5, 0),
    (-96.075, -32.500014, 0),
    (-96.075, 32.5, 0),
]


class HiltiElement(Element):
    """Class representing a Hilti joint element.

    The joint is built from one of two predefined polyline profiles (A or B),
    extruded along local Z by a given height into a lofted mesh.

    The profile polyline lives in the local XY plane. The transformation
    parameter positions and orients the element in world space (local Z
    becomes the extrusion direction after transformation).

    Parameters
    ----------
    profile : str
        Which polyline profile to use: ``"A"`` or ``"B"``.
    height : float
        Extrusion height along local Z-axis.
    transformation : :class:`compas.geometry.Transformation`, optional
        Transformation applied to the element.
    name : str, optional
        Name of the element.
    """

    @property
    def __data__(self) -> dict:
        return {
            "profile": self._profile,
            "height": self._height,
            "transformation": self.transformation,
            "name": self.name,
        }

    def __init__(
        self,
        profile: str = "A",
        height: float = 80.0,
        transformation: Optional[Transformation] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=None, name=name)
        if profile not in ("A", "B"):
            raise ValueError("profile must be 'A' or 'B', got '{}'".format(profile))
        self._profile = profile
        self._height = height

    @property
    def profile(self) -> str:
        return self._profile

    @property
    def height(self) -> float:
        return self._height

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Loft the profile polyline along local Z by ``height`` to produce a mesh.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        pts = _POLYLINE_A_POINTS if self._profile == "A" else _POLYLINE_B_POINTS
        bottom = Polyline([Point(*p) for p in pts])
        up = Vector(0, 0, self._height)
        top = Polyline([Point(p.x + up.x, p.y + up.y, p.z + up.z) for p in bottom.points])
        return PolylineLoft.to_mesh(bottom, top, cap=True, close=False)

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        mesh = self.modelgeometry
        box = Box.from_bounding_box(mesh.vertices_attributes("xyz"))
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        return self.compute_aabb(inflate)

    def compute_collision_mesh(self, inflate: float = 1.0) -> Mesh:
        raise NotImplementedError

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())
