from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Polygon
from compas.geometry import Plane
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineLoft
from compas_tf.geometry import PolylineOffset
from compas_tf.geometry import LineOffset
import math


def _closed_polyline(points: list) -> Polyline:
    """Create a closed polyline from points."""
    return Polyline(list(points) + [points[0]])


def _rect_outline(p0, p1, z0, z1) -> Polyline:
    """Create rectangular outline from two points at two heights."""
    return Polyline([
        p0.translated([0, 0, z0]),
        p1.translated([0, 0, z0]),
        p1.translated([0, 0, z1]),
        p0.translated([0, 0, z1]),
        p0.translated([0, 0, z0]),
    ])


def _create_lofted_walls(poly, z_top, z_bot) -> list:
    """Create two lofted wall meshes from a 4-point polygon at two heights."""
    top = _closed_polyline(poly.points)
    bot = top.translated([0, 0, z_bot - z_top])
    if z_top != 0:
        top = _closed_polyline(poly.points).translated([0, 0, z_top])
        bot = top.translated([0, 0, z_bot - z_top])

    wall0 = Polyline([top.points[0], top.points[1], bot.points[1], bot.points[0], top.points[0]])
    wall1 = Polyline([top.points[3], top.points[2], bot.points[2], bot.points[3], top.points[3]])
    return PolylineLoft.to_mesh(wall0, wall1)


class OculusFeature(Feature):
    pass


class OculusElement(Element):
    """Central oculus beam element."""

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
            features: Optional[list[OculusFeature]] = None,
            name: Optional[str] = None,
        ):
            super().__init__(transformation=transformation, features=features, name=name)
            self.mesh = mesh if mesh else Mesh()

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self.mesh

    def _inflate_box(self, box: Box, inflate: float) -> Box:
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        return box

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        self._aabb = self._inflate_box(self.modelgeometry.aabb, inflate)
        return self._aabb

    def compute_obb(self, inflate: float = 1.0) -> Box:
        self._obb = self._inflate_box(self.modelgeometry.obb, inflate)
        return self._obb

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())



    @staticmethod
    def build(builder):
        """Build oculus beam geometry from FloorBuilder data.

        Parameters
        ----------
        builder : FloorBuilder
            The floor builder containing base geometry parameters.

        Returns
        -------
        list[OculusElement]
            The oculus beam elements.
        """
        elements = []
        base_depth = -builder.height + builder.rise
        oculus_poly = Polygon(builder.oculus_points)

        # Top walls (z=0 to z=base_depth)
        for poly in PolylineOffset.offset_polygon_reciprocally(oculus_poly, builder.thick):
            elements.append(OculusElement(mesh=_create_lofted_walls(poly, 0, base_depth)))

        # Stepped walls (z=base_depth to z=base_depth+thick)
        oculus_tsection = PolylineOffset.offset_polygon(oculus_poly, builder.thick)
        for poly in PolylineOffset.offset_polygon_reciprocally(Polygon(oculus_tsection), builder.thick):
            elements.append(OculusElement(mesh=_create_lofted_walls(poly, base_depth, base_depth + builder.thick)))

        # Center panel (z=base_depth+thick to z=base_depth+2*thick), subdivided into 3 segments
        z0, z1 = base_depth + builder.thick, base_depth + builder.thick * 2
        wall0 = oculus_tsection.translated([0, 0, z0])
        wall1 = oculus_tsection.translated([0, 0, z1])

        def sample_line(p0, p1, n=4):
            line = Line(p0, p1)
            return [line.point_at(i / (n - 1)) for i in range(n)]

        pts0_edge0 = sample_line(wall0.points[0], wall0.points[1])
        pts0_edge1 = sample_line(wall0.points[3], wall0.points[2])
        pts1_edge0 = sample_line(wall1.points[0], wall1.points[1])
        pts1_edge1 = sample_line(wall1.points[3], wall1.points[2])

        for i in range(3):
            seg0 = Polyline([pts0_edge0[i], pts0_edge0[i+1], pts0_edge1[i+1], pts0_edge1[i], pts0_edge0[i]])
            seg1 = Polyline([pts1_edge0[i], pts1_edge0[i+1], pts1_edge1[i+1], pts1_edge1[i], pts1_edge0[i]])
            elements.append(OculusElement(mesh=PolylineLoft.to_mesh(seg0, seg1)))

        # Edges screws on one corner only, then rotate 4 times

        from compas_tf.joint_screw import ScrewElement
        from compas_tf.joint_dowel import DowelElement
        from compas_tf.joint_strip import AlignmentStripElement

        height_offset = 20
        divisions = 4
        height = (builder.height-builder.rise-height_offset*2) / (divisions-1)
        height_center = (builder.height-builder.rise)/2

        offset_polygon = PolylineOffset.offset_polygon(oculus_poly, builder.thick * 0.5)
        line = Line(offset_polygon.points[0], offset_polygon.points[1])
        direction = line.direction
        basepoint = offset_polygon.points[0]- direction*builder.thick*0.5

        for i in range(divisions):
            screwpoint = basepoint + Vector(0, 0, height *-i - height_offset)
            line = Line(screwpoint, screwpoint+direction*builder.thick)
            xform_screw = Transformation.from_frame(frame=Frame(screwpoint, Vector.Zaxis().cross(direction), Vector.Zaxis()))

            for i in range(4):
                xform_rotation = Rotation.from_axis_and_angle([0,0,1], math.radians(90)*i, point=Point(0,0,0))
                screw = ScrewElement(height=line.length, transformation=xform_rotation*xform_screw)
                elements.append(screw)

        # Alignment strips
        aligmentstrip_point = basepoint + direction*builder.thick - Vector(0,0,height_center)
        line = Line(aligmentstrip_point, aligmentstrip_point+direction*builder.thick*2)
        xform_alignmentstrip = Transformation.from_frame(frame=Frame(aligmentstrip_point, Vector.Zaxis().cross(direction), direction))

        for i in range(4):
            xform_rotation = Rotation.from_axis_and_angle([0,0,1], math.radians(90)*i, point=Point(0,0,0))
            alignment_strip = AlignmentStripElement(transformation=xform_rotation*xform_alignmentstrip)
            elements.append(alignment_strip)
    
        # Screws and dowels one one side only
        divisions = 8
        height_middle = (builder.height-builder.rise) * 0.5

        for i in range(4):
            line = Line(oculus_poly.points[i], oculus_poly.points[(i+1)%4]).translated(Vector.Zaxis() * -height_middle)

            direction = Vector.Zaxis().cross(line.direction).unitized() * -builder.thick
            points = LineOffset.divide(line, divisions)

            for idx, pt in enumerate(points):
                if idx == 0 or idx == len(points)-1:
                    continue

                screw_line = Line(pt, pt+direction)
                plane = Plane(pt-direction, direction)
                xform = Transformation.from_frame(Frame.from_plane(plane))

                if (idx % 3 == 1):
                    dowel = DowelElement(height=screw_line.length, transformation=xform)
                    elements.append(dowel)

                if (idx % 3 == 0) or (idx % 3 == 2):
                    screw = ScrewElement(height=screw_line.length, transformation=xform)
                    elements.append(screw)

        return elements
