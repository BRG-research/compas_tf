from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Projection
from compas.geometry import Reflection
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineCut
from compas_tf.geometry import PolylineLoft


class EdgeBeamFeature(Feature):
    pass


class EdgeBeamElement(Element):
    """Edge beam at floor perimeter connecting adjacent quarters."""

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
        transformation: Optional[Transformation] = None,
        features: Optional[list[EdgeBeamFeature]] = None,
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

    @staticmethod
    def build(builder):
        """Build single edge beam. Rotate the result yourself for other edges."""


        #############################################################################################
        # Transformation to origin
        #############################################################################################

        xform = Translation.from_vector([0, builder.size+builder.beam_w/2, 0])

        #############################################################################################
        # Builder
        #############################################################################################

        # Get builder data
        parabola = builder.boundary_parabolas[0]
        axis = builder.axes[0]
        cut_boundary = builder.cut_planes[0]
        cut_corner = builder.cut_planes[3]
        thick = builder.thick
        head_h = builder.head_h
        beam_w = builder.beam_w

        # Offset parabola
        normal = Vector.Zaxis().cross(axis.direction)
        proj = parabola.translated(normal * thick * -0.5)

        # Cut by planes
        cut = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj, cut_corner), cut_boundary)

        # Extend and cut by end plane
        line = PolylineCut.cut_by_plane(Polyline([cut[0], cut[-1]]).extended([1000, 0]), builder.top_end_planes[0], flip=True)

        # Build step profile: top (z=0) + mid (z=-head_h) + curve
        xy_proj = Projection.from_plane_and_direction(Plane.worldXY(), Vector.Zaxis())
        mid_proj = Projection.from_plane_and_direction(Plane([0, 0, -head_h], [0, 0, 1]), Vector.Zaxis())

        top = line.transformed(xy_proj)
        mid = PolylineCut.cut_by_plane(line.transformed(mid_proj), cut_corner, flip=True)

        poly = Polyline(list(reversed(top.points)) + mid.points + cut.points)
        poly.append(poly.points[0])

        # Merge with reflected copy
        pts0 = poly.points[1:-1]
        reflection = Reflection.from_plane(Plane.worldYZ())
        pts1 = Polyline(poly.transformed(reflection).points[1:-1])
        merged = Polyline(list(pts0) + list(reversed(pts1.points)))

        polygon = Polygon(merged.points)
        mesh = PolylineLoft.to_mesh(merged, merged.translated(polygon.normal * beam_w))
        mesh.transform(xform)

        return EdgeBeamElement(mesh=mesh, name="edge_beam")
