from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas.geometry import Vector
from compas.geometry import intersection_line_plane
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PlaneIntersect
from compas_tf.geometry import PolylineLoft


class ColumnHeadFeature(Feature):
    pass


class ColumnHeadElement(Element):
    """Class representing a column head element.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry of the column head.
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the column head.
    features : list[:class:`ColumnHeadFeature`], optional
        The features of the column head.
    name : str, optional
        The name of the column head.

    Attributes
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry.
    """

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
        features: Optional[list[ColumnHeadFeature]] = None,
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
        """Build column head geometry from FloorBuilder data.

        Returns: (head_element, top_element)
        """
        pts, pts_offset = builder.corner_points
        corner = builder.corner_point
        end_planes = builder.end_planes
        head_h = builder.head_h
        beam_w = builder.beam_w
        height = builder.height

        plane_top = Plane([0, 0, -head_h], Vector.Zaxis())
        plane_bottom = Plane([0, 0, -head_h * 2], Vector.Zaxis())

        top_pts = [Point(*intersection_line_plane(Line(pts[i], pts_offset[i]), plane_top)) for i in range(4)]
        bottom_pts = [Point(*intersection_line_plane(Line(pts[i], pts_offset[i]), plane_bottom)) for i in range(4)]

        polyline_top = Polyline(top_pts).extended([beam_w, beam_w])
        polyline_bottom = Polyline(bottom_pts).extended([beam_w, beam_w])

        direction = -polyline_top.lines[0].direction * beam_w + polyline_bottom.lines[-1].direction * beam_w
        corner = direction + corner

        for poly, z_off in [(polyline_top, -head_h), (polyline_bottom, -head_h * 2)]:
            poly.append(Vector(0, 0, z_off) + corner)
            poly.points = poly.points[-1:] + poly.points[:-1]
            poly.append(poly[0])

        taper = polyline_bottom.translated(Vector(0, 0, -(height - head_h * 2)))
        xaxis = taper.lines[0].direction * beam_w
        yaxis = taper.lines[-1].direction * beam_w
        center = taper[0]
        taper = Polyline([center, center + xaxis, center + xaxis - yaxis * 0.99, center + xaxis * 0.99 - yaxis, center - yaxis, center])

        head_mesh = PolylineLoft.multiple_to_mesh([polyline_top, polyline_bottom, taper])

        # Top block
        bp = builder.boundary_points
        stop0 = Plane(builder.corner_point, Vector.Zaxis().cross(bp[0] - builder.corner_point))
        stop1 = Plane(builder.corner_point, Vector.Zaxis().cross(bp[3] - builder.corner_point))
        ipoints = PlaneIntersect.intersect_consecutive_planes([stop0] + list(end_planes) + [stop1])

        top_poly0 = Polyline(ipoints)
        top_poly0.extend((beam_w, beam_w))
        top_poly0.insert(0, Point(center[0], center[1], 0))
        top_poly0.append(top_poly0[0])
        top_poly1 = top_poly0.translated(Vector(0, 0, -head_h))
        top_mesh = PolylineLoft.to_mesh(top_poly0, top_poly1)

        head_element = ColumnHeadElement(mesh=head_mesh, name="column_head")
        top_element = ColumnHeadElement(mesh=top_mesh, name="column_head_top")

        return head_element, top_element