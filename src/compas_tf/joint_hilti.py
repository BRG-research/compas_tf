from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Transformation
from compas.geometry import earclip_polygon
from compas_model.elements import Element

# Polyline coordinates parsed from hilti.txt (one side only, the other is symmetrical)
# CW winding when viewed from +Z.
# _PROFILE_POINTS = [
#     (-10.0, 20.0, 0),
#     (13.925, 20.0, 0),
#     (44.10267, 32.5, 0),
#     (89.925044, 32.5, 0),
#     (89.925044, -32.500014, 0),
#     (44.10267, -32.500014, 0),
#     (13.925, -20, 0),
#     (-10.0, -20.0, 0),
# ]
_PROFILE_POINTS = [
    #     (-96.075, 32.5, 0),
    #     (-44.25, 32.5, 0),
    #     (-13.925, 20.0, 0),
    #     (10, 20.0, 0),
    #     (10.0, -20.0, 0),
    #     (-13.925, -20.0, 0),
    #     (-44.25, -32.5, 0),
    #     (-96.075, -32.5000, 0)
    (-96.075, 32.5, 0),
    (-44.25267, 32.5, 0),
    (-13.925, 20.0, 0),
    (10, 20.0, 0),
    (10, -20.0, 0),
    (-13.925, -20.0, 0),
    (-44.25267, -32.5, 0),
    (-96.075, -32.500014, 0),
]


class HiltiElement(Element):
    """Class representing a Hilti joint element.

    The joint is built from a single predefined polyline profile,
    extruded along local Z by a given height into a closed lofted mesh.
    The other side of the connector is symmetrical and handled by
    the placement transformation.

    The profile polyline lives in the local XY plane. The transformation
    parameter positions and orients the element in world space (local Z
    becomes the extrusion direction after transformation).

    Parameters
    ----------
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
            "height": self._height,
            "transformation": self.transformation,
            "name": self.name,
        }

    def __init__(
        self,
        height: float = 80.0,
        transformation: Optional[Transformation] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=None, name=name)
        self._height = height

    @property
    def height(self) -> float:
        return self._height

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Build a closed mesh with consistent outward normals.

        The mesh is constructed manually (not via PolylineLoft) to guarantee
        correct face winding for CGAL boolean difference operations.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        half_h = self._height / 2.0
        bottom = [Point(p[0], p[1], -half_h) for p in _PROFILE_POINTS]
        top = [Point(p[0], p[1], half_h) for p in _PROFILE_POINTS]
        n = len(bottom)

        vertices = bottom + top  # 0..n-1 = bottom, n..2n-1 = top
        faces = []

        # Side quads: winding [i, i+n, j+n, j] gives outward normals for CW profile
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, i + n, j + n, j])

        # Bottom cap: CW earclip gives -Z normal (outward for bottom)
        for tri in earclip_polygon(Polygon(bottom)):
            faces.append([tri[0], tri[1], tri[2]])

        # Top cap: reversed CW earclip gives +Z normal (outward for top)
        for tri in earclip_polygon(Polygon(top)):
            faces.append([tri[2] + n, tri[1] + n, tri[0] + n])

        return Mesh.from_vertices_and_faces(vertices, faces)

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
