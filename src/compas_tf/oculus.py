import math
from dataclasses import dataclass
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
from compas_tf.plate import PlateElement


@dataclass
class OculusResult:
    """Container for oculus build results."""

    oculus_elements: list  # PlateElement mesh elements
    screws: list  # ScrewElement connectors
    dowels: list  # DowelElement connectors
    strips: list  # AlignmentStripElement connectors
    interactions: list  # List of (connector, element) tuples for model.add_interaction()


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


def _create_lofted_walls(poly, z_top, z_bot) -> tuple[Polyline, Polyline, Mesh]:
    """Create two lofted wall meshes from a 4-point polygon at two heights.

    Returns
    -------
    tuple[Polyline, Polyline, Mesh]
        (top_polyline, bottom_polyline, lofted_mesh)
    """
    top = _closed_polyline(poly.points)
    bot = top.translated([0, 0, z_bot - z_top])
    if z_top != 0:
        top = _closed_polyline(poly.points).translated([0, 0, z_top])
        bot = top.translated([0, 0, z_bot - z_top])

    wall0 = Polyline([top.points[0], top.points[1], bot.points[1], bot.points[0], top.points[0]])
    wall1 = Polyline([top.points[3], top.points[2], bot.points[2], bot.points[3], top.points[3]])
    mesh = PolylineLoft.to_mesh(wall0, wall1)
    return wall0, wall1, mesh


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
    def build(builder) -> OculusResult:
        """Build oculus beam geometry from FloorBuilder data.

        Parameters
        ----------
        builder : FloorBuilder
            The floor builder containing base geometry parameters.

        Returns
        -------
        OculusResult
            Container with oculus_elements, screws, dowels, strips, and interactions.
        """
        from compas_tf.joint_screw import ScrewElement
        from compas_tf.joint_dowel import DowelElement
        from compas_tf.joint_strip import AlignmentStripElement

        oculus_elements = []
        screws = []
        dowels = []
        strips = []
        interactions = []

        base_depth = -builder.height + builder.rise
        oculus_poly = Polygon(builder.oculus_points)

        # Top walls (z=0 to z=base_depth) - 2 elements (inner and outer)
        for poly in PolylineOffset.offset_polygon_reciprocally(oculus_poly, builder.thick):
            top_poly, bot_poly, mesh = _create_lofted_walls(poly, 0, base_depth)
            oculus_elements.append(PlateElement(top_polyline=top_poly, bottom_polyline=bot_poly, mesh=mesh, name="oculus_top_wall"))

        # Stepped walls (z=base_depth to z=base_depth+thick) - 2 elements
        oculus_tsection = PolylineOffset.offset_polygon(oculus_poly, builder.thick)
        for poly in PolylineOffset.offset_polygon_reciprocally(Polygon(oculus_tsection), builder.thick):
            top_poly, bot_poly, mesh = _create_lofted_walls(poly, base_depth, base_depth + builder.thick)
            oculus_elements.append(PlateElement(top_polyline=top_poly, bottom_polyline=bot_poly, mesh=mesh, name="oculus_stepped_wall"))

        # TODO: It is not clear: should it be 3 panels or 1 panels?
        # Center panel (z=base_depth+thick to z=base_depth+2*thick)
        z0, z1 = base_depth + builder.thick, base_depth + builder.thick * 2
        wall0 = oculus_tsection.translated([0, 0, z0])
        wall1 = oculus_tsection.translated([0, 0, z1])

        line00 = Line(wall0.points[0], wall0.points[1])
        line01 = Line(wall0.points[3], wall0.points[2])
        line10 = Line(wall1.points[1], wall1.points[0])
        line11 = Line(wall1.points[2], wall1.points[3])

        points00 = LineOffset.divide(line00, 3)
        points01 = LineOffset.divide(line01, 3)
        points10 = LineOffset.divide(line10, 3)
        points11 = LineOffset.divide(line11, 3)

        polyline_top = Polyline(points00 + points10 + [points00[0]])
        polyline_bot = Polyline(points01 + points11 + [points01[0]])
        oculus_elements.append(PlateElement(top_polyline=polyline_top, bottom_polyline=polyline_bot, name="oculus_center_panel"))

        # Corner screws - connect adjacent oculus walls at each corner
        # These screws connect the oculus wall elements to each other
        height_offset = 20
        divisions = 4
        height = (builder.height-builder.rise-height_offset*2) / (divisions-1)
        height_center = (builder.height-builder.rise)/2

        offset_polygon = PolylineOffset.offset_polygon(oculus_poly, builder.thick * 0.5)
        line = Line(offset_polygon.points[0], offset_polygon.points[1])
        direction = line.direction
        basepoint = offset_polygon.points[0] - direction*builder.thick*0.5

        for div_idx in range(divisions):
            screwpoint = basepoint + Vector(0, 0, height * -div_idx - height_offset)
            screw_line = Line(screwpoint, screwpoint + direction * builder.thick)
            xform_screw = Transformation.from_frame(frame=Frame(screwpoint, Vector.Zaxis().cross(direction), Vector.Zaxis()))

            for rot_idx in range(4):
                xform_rotation = Rotation.from_axis_and_angle([0, 0, 1], math.radians(90) * rot_idx, point=Point(0, 0, 0))
                screw = ScrewElement(height=screw_line.length, transformation=xform_rotation * xform_screw, name=f"oculus_corner_screw_{div_idx}_{rot_idx}")
                screws.append(screw)
                # Corner screws connect to both top walls (elements 0 and 1)
                interactions.append((screw, oculus_elements[(rot_idx-1)%4]))

        # Alignment strips at corners
        alignmentstrip_point = basepoint + direction * builder.thick - Vector(0, 0, height_center)
        xform_alignmentstrip = Transformation.from_frame(frame=Frame(alignmentstrip_point, Vector.Zaxis().cross(direction), direction))

        for rot_idx in range(4):
            xform_rotation = Rotation.from_axis_and_angle([0, 0, 1], math.radians(90) * rot_idx, point=Point(0, 0, 0))
            strip = AlignmentStripElement(transformation=xform_rotation * xform_alignmentstrip, name=f"oculus_corner_strip_{rot_idx}")
            strips.append(strip)
            # Strips connect to both top walls
            interactions.append((strip, oculus_elements[rot_idx]))
            interactions.append((strip, oculus_elements[(rot_idx-1)%4]))

        # Boundary screws and dowels - connect oculus to quarter boundary beams
        # These are "external" connections - the boundary_beam is not an oculus element
        # They will need to be connected to quarter_floor boundary elements externally
        divisions = 8
        height_middle = (builder.height-builder.rise) * 0.5

        for edge_idx in range(4):
            line = Line(oculus_poly.points[edge_idx], oculus_poly.points[(edge_idx + 1) % 4]).translated(Vector.Zaxis() * -height_middle)
            direction = Vector.Zaxis().cross(line.direction).unitized() * -builder.thick
            points = LineOffset.divide(line, divisions)

            for idx, pt in enumerate(points):
                if idx == 0 or idx == len(points) - 1:
                    continue

                screw_line = Line(pt, pt + direction)
                plane = Plane(pt - direction, direction)
                xform = Transformation.from_frame(Frame.from_plane(plane))

                if idx % 3 == 1:
                    dowel = DowelElement(height=screw_line.length, transformation=xform, name=f"oculus_boundary_dowel_{edge_idx}_{idx}")
                    dowels.append(dowel)
                    # Boundary dowels connect to top walls (external to quarter boundary)
                    interactions.append((dowel, oculus_elements[edge_idx]))
                else:
                    screw = ScrewElement(height=screw_line.length, transformation=xform, name=f"oculus_boundary_screw_{edge_idx}_{idx}")
                    screws.append(screw)
                    # Boundary screws connect to top walls (external to quarter boundary)
                    interactions.append((screw, oculus_elements[edge_idx]))

        return OculusResult(
            oculus_elements=oculus_elements,
            screws=screws,
            dowels=dowels,
            strips=strips,
            interactions=interactions,
        )
