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
# Connector Helper Functions
# ==========================================================================


def _line_to_screw(line: Line) -> ScrewElement:
    """Create a ScrewElement from a line."""
    plane = Plane(line.start, line.direction)
    xform = Transformation.from_frame(Frame.from_plane(plane))
    return ScrewElement(8, 25, line.length, transformation=xform)

def _line_to_dowel(line: Line) -> DowelElement:
    """Create a DowelElement from a line."""
    plane = Plane(line.start, line.direction)
    xform = Transformation.from_frame(Frame.from_plane(plane))
    return DowelElement(20, 20, line.length, transformation=xform)

def _line_to_strip(line: Line, height: float) -> AlignmentStripElement:
    """Create an AlignmentStripElement from a line."""
    frame = Frame(line.start, Vector.Zaxis().cross(line.direction), line.direction)
    xform = Transformation.from_frame(frame)
    return AlignmentStripElement(height=height, transformation=xform)

def _create_hilti(origin: Point, rib_dir: Vector, boundary_dir: Vector, height: float = 120.0) -> HiltiElement:
    """Create a HiltiElement positioned at the rib-boundary interface.

    Parameters
    ----------
    origin : :class:`compas.geometry.Point`
        Placement point (edge midpoint at mid-height of the rib).
    rib_dir : :class:`compas.geometry.Vector`
        Direction along the rib (maps to local X of the profile).
    boundary_dir : :class:`compas.geometry.Vector`
        Direction along the boundary beam (maps to local Z / extrusion).
    height : float
        Extrusion depth of the connector plate.
    """
    xaxis = rib_dir.unitized()
    yaxis = Vector(0, 0, 1)
    # zaxis is computed by Frame as xaxis x yaxis -> points along boundary
    frame = Frame(origin, xaxis, yaxis)
    xform = Transformation.from_frame(frame)
    return HiltiElement(height=height, transformation=xform)


# ==========================================================================
# Result Container
# ==========================================================================


@dataclass
class QuarterResult:
    """Container for quarter floor build results.

    axis_elements is a dict keyed by axis index containing all main elements:
    - axis_elements[0]: rib at axis 0 (bottom boundary)
    - axis_elements[1]: rib at axis 1 (diagonal 1)
    - axis_elements[2]: rib at axis 2 (diagonal 2)
    - axis_elements[3]: boundary at axis 3 (edge-oculus)
    - axis_elements[4]: boundary at axis 4 (oculus-oculus)
    - axis_elements[5]: boundary at axis 5 (oculus-edge)
    - axis_elements[6]: rib at axis 6 (left boundary)
    - axis_elements[7]: boundary at axis 7 (diagonal cut at column head)
    """

    axis_elements: dict  # {axis_idx: PlateElement}
    axis_polys: dict[int, list[Polyline]]
    tsection_elements: list
    surface_elements: list
    corner_block_elements: list
    surface_edge_polys: list
    screws: list
    dowels: list
    strips: list
    hilti_joints: list
    interactions: list  # List of (connector, element) tuples for model.add_interaction()
    modifiers: list  # List of (source, target, modifier) tuples for model.add_modifier()


# ==========================================================================
# Internal Helper Functions
# ==========================================================================


def _compute_axis_boundary_planes(builder):
    """Axis boundary planes for Q1 (from slab.py:233-242)."""
    axes = builder.axes
    return [Plane(axes[j].midpoint, Vector.Zaxis().cross(axes[j].direction)) for j in range(3, len(axes) - 1)]

def _compute_axis_planes(builder):
    """Axis planes for T-sections (from slab.py:244-255)."""
    axes = builder.axes
    planes = [Plane(axes[j].start, Vector.Zaxis().cross(axes[j].direction)) for j in range(3)]
    planes.append(Plane(axes[-1].start, -Vector.Zaxis().cross(axes[-1].direction)))
    return planes

def _compute_offset_axes(builder):
    """Offset axes for surface lofting (from slab.py:296-324)."""
    rib_parabolas = builder.rib_parabolas
    target_planes = builder.target_planes
    axes = builder.axes
    thick = builder.thick

    offset_0_bottom = PolylineOffset.offset_polyline(rib_parabolas[0], thick)
    offset_0_top = PolylineOffset.offset_polyline(rib_parabolas[0], thick * 2)
    offset_3_bottom = PolylineOffset.offset_polyline(rib_parabolas[3], thick)
    offset_3_top = PolylineOffset.offset_polyline(rib_parabolas[3], thick * 2)

    proj_dir0 = Vector.Zaxis().cross(axes[0].direction)
    proj_dir3 = Vector.Zaxis().cross(axes[3].direction)
    xform10 = Projection.from_plane_and_direction(target_planes[1], proj_dir0)
    xform20 = Projection.from_plane_and_direction(target_planes[2], proj_dir3)

    return [
        [offset_0_bottom, offset_0_top],
        [offset_0_bottom.transformed(xform10), offset_0_top.transformed(xform10)],
        [offset_3_bottom.transformed(xform20), offset_3_top.transformed(xform20)],
        [offset_3_bottom, offset_3_top],
    ]

def _compute_lofted_lines(builder, offset_axes):
    """Lofted lines between offset axes (from slab.py:326-342)."""
    rib_parabolas = builder.rib_parabolas
    lofted_bottom = []
    lofted_top = []

    for i in range(len(rib_parabolas) - 1):
        lofted_bottom.append(PolylineLoft.to_lines(offset_axes[i][0], offset_axes[i + 1][0]))
        lofted_top.append(PolylineLoft.to_lines(offset_axes[i][1], offset_axes[i + 1][1]))

    return [lofted_bottom, lofted_top]

def _build_ribs(builder):
    """Compute rib meshes and polyline pairs for quarter 1 (from slab.py:393-442).

    Ribs are keyed by axis index to follow builder.axes order:
    - rib[0] -> axes[0] (bottom boundary)
    - rib[1] -> axes[1] (diagonal 1)
    - rib[2] -> axes[2] (diagonal 2)
    - rib[6] -> axes[6] (left boundary)

    Returns
    -------
    tuple[dict, dict, dict]
        (meshes, flat_polylines, polyline_pairs) all keyed by axis index
    """
    # Rib configuration: (axis_idx, parabola_idx, target_plane_idx, boundary_cut_idx, rib_cut_idx)
    rib_configs = [
        (0, 0, 0, 0, 0, 0),  # axis 0: parabola[0], target[0], boundary_cut[0], rib_cut[0+3], end_plane[0]
        (1, 1, 1, 0, 1, 1),  # axis 1: parabola[1], target[1], boundary_cut[0], rib_cut[1+3], end_plane[1]
        (2, 2, 2, 2, 1, 1),  # axis 2: parabola[2], target[2], boundary_cut[2], rib_cut[1+3], end_plane[1]
        (6, 3, 3, 2, 2, 2),  # axis 6: parabola[3], target[3], boundary_cut[2], rib_cut[2+3], end_plane[2]
    ]



    rib_parabolas = builder.rib_parabolas
    target_planes = builder.target_planes
    cut_planes = builder.cut_planes
    thick = builder.thick
    head_h = builder.head_h

    end_planes = builder.compute_cut_planes(scale=builder.head_o, inclination=0)[3:6]


    quarter_meshes = {}
    list_rib_polylines = {}
    polyline_pairs = {}

    for axis_idx, parabola_idx, target_idx, boundary_cut_idx, rib_cut_idx, end_plane_idx in rib_configs:
        # Boundary ribs (axis 0 and 6) are double thick, extended outward
        if axis_idx == 0:
            offset0, offset1 = 0.5, -1.5  # outward is negative (outward_sign=-1)
        elif axis_idx == 6:
            offset0, offset1 = 1.5, -0.5  # outward is positive (outward_sign=+1)
        else:
            offset0, offset1 = 0.5, -0.5
        # end_plane = builder.end_diagonal_plane.offset(-builder.thick)
        end_plane = Plane(end_planes[end_plane_idx].point, -end_planes[end_plane_idx].normal)

        cut_boundary = cut_planes[boundary_cut_idx]
        cut_rib = cut_planes[rib_cut_idx + 3]

        # Extend boundary cut plane for double-thick boundary ribs
        if axis_idx in (0, 6):
            cut_boundary = cut_boundary.offset(-thick)

        proj0 = rib_parabolas[parabola_idx].translated(target_planes[target_idx].normal * thick * offset0)
        proj1 = rib_parabolas[parabola_idx].translated(target_planes[target_idx].normal * thick * offset1)

        cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj0, cut_rib), cut_boundary)
        cut1 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj1, cut_rib), cut_boundary)

        extension = 600
        line0 = PolylineCut.cut_by_plane(Polyline([cut0[0], cut0[-1]]).extended([extension, 0]), end_plane, flip=True)
        line1 = PolylineCut.cut_by_plane(Polyline([cut1[0], cut1[-1]]).extended([extension, 0]), end_plane, flip=True)

        xy_proj = Projection.from_plane_and_direction(Plane.worldXY(), Vector.Zaxis())
        mid_proj = Projection.from_plane_and_direction(Plane([0, 0, -head_h], [0, 0, 1]), Vector.Zaxis())

        top0, top1 = line0.transformed(xy_proj), line1.transformed(xy_proj)
        mid0 = PolylineCut.cut_by_plane(line0.transformed(mid_proj), cut_rib, flip=True)
        mid1 = PolylineCut.cut_by_plane(line1.transformed(mid_proj), cut_rib, flip=True)

        joined0 = Polyline(list(reversed(top0.points)) + mid0.points + cut0.points)
        joined1 = Polyline(list(reversed(top1.points)) + mid1.points + cut1.points)
        joined0.append(joined0.points[0])
        joined1.append(joined1.points[0])

        quarter_meshes[axis_idx] = PolylineLoft.to_mesh(joined0, joined1)
        list_rib_polylines[axis_idx] = [joined0, joined1]
        polyline_pairs[axis_idx] = (joined0, joined1)

    return quarter_meshes, list_rib_polylines, polyline_pairs

def _build_tsections(builder, axis_planes, lofted_lines):
    """Compute T-section meshes and polyline pairs for quarter 1 (from slab.py:444-485).

    Returns
    -------
    tuple[list[Mesh], list[tuple[Polyline, Polyline]]]
        (meshes, polyline_pairs) where polyline_pairs is [(top, bottom), ...]
    """
    lofted_bottom = lofted_lines[0]
    cut_planes = builder.cut_planes
    rib_parabolas = builder.rib_parabolas
    thick = builder.thick

    offsets = [[1], [-1, 1], [-1, 1], [-1]]
    offsets_ids = [[0], [0, 1], [1, 2], [2]]
    quarter_meshes = []
    polyline_pairs = []

    for i in range(len(rib_parabolas)):
        for j in range(len(offsets[i])):
            ap = axis_planes[i]
            plane0 = Plane(ap.point + ap.normal * thick * 0.5 * offsets[i][j], ap.normal)
            plane1 = Plane(ap.point + ap.normal * thick * 1.5 * offsets[i][j], ap.normal)

            proj0 = Polyline([plane0.closest_point(pt) for pt in rib_parabolas[i].points])
            proj1 = Polyline([plane1.closest_point(pt) for pt in rib_parabolas[i].points])

            cut0 = PolylineCut.cut_lines_by_plane(lofted_bottom[offsets_ids[i][j]], plane0)
            cut1 = PolylineCut.cut_lines_by_plane(lofted_bottom[offsets_ids[i][j]], plane1)

            cut_boundary = cut_planes[offsets_ids[i][j]]
            cut_rib = cut_planes[offsets_ids[i][j] + 3]

            for plane in [cut_boundary, cut_rib]:
                proj0 = PolylineCut.cut_by_plane(proj0, plane)
                proj1 = PolylineCut.cut_by_plane(proj1, plane)
                cut0 = PolylineCut.cut_by_plane(cut0, plane)
                cut1 = PolylineCut.cut_by_plane(cut1, plane)

            merged0 = Polyline(proj0.points + list(reversed(cut0.points)))
            merged1 = Polyline(proj1.points + list(reversed(cut1.points)))
            quarter_meshes.append(PolylineLoft.to_mesh(merged0, merged1, True))
            polyline_pairs.append((merged0, merged1))

    return quarter_meshes, polyline_pairs

def _build_surfaces(builder, axis_planes, lofted_lines, continuous=False):
    """Compute surface meshes, edge polylines, and polyline pairs for quarter 1.

    Returns
    -------
    tuple[list[Mesh], list, list[tuple[Polyline, Polyline]]]
        (meshes, edge_polylines, polyline_pairs) where polyline_pairs is [(top, bottom), ...]
    """
    lofted_bottom = lofted_lines[0]
    lofted_top = lofted_lines[1]
    cut_planes = builder.cut_planes
    rib_parabolas = builder.rib_parabolas
    thick = builder.thick

    offsets = [[1], [-1, 1], [-1, 1], [-1]]
    offsets_ids = [[0], [0, 1], [1, 2], [2]]
    surface_edges = []

    for i in range(len(rib_parabolas)):
        for j in range(len(offsets[i])):
            ap = axis_planes[i]
            plane0 = Plane(ap.point + ap.normal * thick * 0.5 * offsets[i][j], ap.normal)

            cut0 = PolylineCut.cut_lines_by_plane(lofted_bottom[offsets_ids[i][j]], plane0)
            cut1 = PolylineCut.cut_lines_by_plane(lofted_top[offsets_ids[i][j]], plane0)

            for plane in [cut_planes[offsets_ids[i][j]], cut_planes[offsets_ids[i][j] + 3]]:
                cut0 = PolylineCut.cut_by_plane(cut0, plane)
                cut1 = PolylineCut.cut_by_plane(cut1, plane)

            surface_edges.extend([cut0, cut1])

    quarter_meshes = []
    quarter_edge_polylines = []
    polyline_pairs = []
    for pair in [surface_edges[i : i + 4] for i in range(0, len(surface_edges), 4)]:
        bl, br, tl, tr = pair[0], pair[1], pair[2], pair[3]
        poly0 = Polyline(bl.points + list(reversed(br.points)))
        poly1 = Polyline(tl.points + list(reversed(tr.points)))

        quarter_edge_polylines.append([tl, bl, tr, br])

        if continuous:
            quarter_meshes.append(PolylineLoft.to_mesh(poly0, poly1)) # this
            polyline_pairs.append((poly0, poly1)) # this
        else:
            # Individual plates
            for j in range(len(bl.points) - 1):
                poly_t = Polyline([bl[j], bl[j + 1], tl[j + 1], tl[j], bl[j]])
                poly_b = Polyline([br[j], br[j + 1], tr[j + 1], tr[j], br[j]])
                quarter_meshes.append(PolylineLoft.to_mesh(poly_t, poly_b))
                # quarter_edge_polylines.append([poly_t, poly_b, poly_t, poly_b])
                polyline_pairs.append((poly_t, poly_b))

    return quarter_meshes, quarter_edge_polylines, polyline_pairs

def _build_corners_blocks(builder, axis_planes, offset_axes):
    """Build 3 corner blocks filling the gap between ribs at the column head.

    Each block is a vertical quad extruded from z=0 to z=-head_h,
    using the XY footprint of the trimmed lofted lines between adjacent ribs.

    Returns
    -------
    tuple[list[Mesh], list[tuple[Polyline, Polyline]]]
        (meshes, polyline_pairs) where polyline_pairs is [(top, bottom), ...]
    """
    _rib_parabolas = builder.rib_parabolas  # noqa: F841
    cut_planes0 = builder.compute_cut_planes(scale=builder.head_o, inclination=0)[3:6]
    cut_planes1 = builder.compute_cut_planes()[3:6]
    cut_planes1 = [Plane(cp.point, -cp.normal) for cp in cut_planes1]
    thick = builder.thick

    meshes = []
    polyline_pairs = []

    for k in range(3):
        # Loft lines between adjacent ribs
        bottom_lines = PolylineLoft.to_lines(offset_axes[k][0], offset_axes[k + 1][0])
        top_lines = PolylineLoft.to_lines(offset_axes[k][1], offset_axes[k + 1][1])

        # Rib offset planes
        left_plane = Plane(axis_planes[k].point + axis_planes[k].normal * thick * 0.5, axis_planes[k].normal)
        right_plane = Plane(axis_planes[k + 1].point - axis_planes[k + 1].normal * thick * 0.5, axis_planes[k + 1].normal)

        # Cut lofted lines by rib planes
        bl = PolylineCut.cut_lines_by_plane(bottom_lines, left_plane)
        tl = PolylineCut.cut_lines_by_plane(top_lines, left_plane)
        br = PolylineCut.cut_lines_by_plane(bottom_lines, right_plane)
        tr = PolylineCut.cut_lines_by_plane(top_lines, right_plane)

        # Trim by column head cut planes
        for tp in [cut_planes0[k], cut_planes1[k]]:
            bl = PolylineCut.cut_by_plane(bl, tp)
            tl = PolylineCut.cut_by_plane(tl, tp)
            br = PolylineCut.cut_by_plane(br, tp)
            tr = PolylineCut.cut_by_plane(tr, tp)

        # Project XY footprint to z=0 (top) and z=-head_h (bottom)
        top = Polyline([Point(p.x, p.y, 0) for p in [bl[0], bl[1], br[1], br[0], bl[0]]])
        bottom = Polyline([Point(p.x, p.y, -builder.head_h) for p in [tl[0], tl[1], tr[1], tr[0], tl[0]]])

        meshes.append(PolylineLoft.to_mesh(top, bottom, True))
        polyline_pairs.append((top, bottom))

    return meshes, polyline_pairs

def _build_boundaries(builder, surface_edge_polys):
    """Compute boundary beam meshes and polyline pairs for quarter 1.

    Boundaries are keyed by axis index to follow builder.axes order:
    - boundary[3] -> axes[3] (edge-oculus)
    - boundary[4] -> axes[4] (oculus-oculus)
    - boundary[5] -> axes[5] (oculus-edge)
    - boundary[7] -> diagonal cut at column head

    Returns
    -------
    tuple[dict, dict]
        (meshes, polyline_pairs) all keyed by axis index
    """
    q1 = builder.quarter_polygon
    thick = builder.thick
    height = builder.height
    rise = builder.rise

    poly0 = Polyline([q1[i] for i in [1, 2, 3, 4]])  # edge -> oculus -> oculus -> edge
    poly1 = PolylineOffset.offset_polyline_xy(poly0, thick)
    poly2 = PolylineOffset.offset_polyline_xy(poly0, thick * 1.5)
    poly1_r_list = PolylineOffset.offset_quarter_reciprocally(poly0, thick)

    meshes = {}
    polyline_pairs = {}
    edge_midpoints = {}  # {axis_idx: midpoint of contracted edge}
    dist = height - rise

    # j=0 -> axis 3, j=1 -> axis 4, j=2 -> axis 5
    for j in range(len(poly0) - 1):
        axis_idx = j + 3  # Map j to axis index
        # Main beam - use vertical sides (inner and outer faces)
        # s0: inner vertical face, s1: outer vertical face
        inner_pts = list(poly1_r_list[j].points)

        # Contract boundary plates on the side meeting double-thick ribs
        if j == 0:
            # axis 3 meets axis 0: contract the start side (pts 0,3) by thick
            dir03 = Vector.from_start_end(inner_pts[0], inner_pts[1]).unitized() * thick
            inner_pts[0] = inner_pts[0] + dir03
            dir30 = Vector.from_start_end(inner_pts[3], inner_pts[2]).unitized() * thick
            inner_pts[3] = inner_pts[3] + dir30
            edge_midpoints[3] = (inner_pts[0] + inner_pts[3]) * 0.5
        elif j == 2:
            # axis 5 meets axis 6: contract the start side (pts 0,3) by thick
            dir01 = Vector.from_start_end(inner_pts[0], inner_pts[1]).unitized() * thick
            inner_pts[0] = inner_pts[0] + dir01
            dir32 = Vector.from_start_end(inner_pts[3], inner_pts[2]).unitized() * thick
            inner_pts[3] = inner_pts[3] + dir32
            edge_midpoints[5] = (inner_pts[0] + inner_pts[3]) * 0.5
        # First two boundaries (j=0,1) need reversed winding
        if j < 2:
            s0 = Polyline([inner_pts[0], inner_pts[0] + Vector(0, 0, -dist), inner_pts[1] + Vector(0, 0, -dist), inner_pts[1], inner_pts[0]])
            s1 = Polyline([inner_pts[3], inner_pts[3] + Vector(0, 0, -dist), inner_pts[2] + Vector(0, 0, -dist), inner_pts[2], inner_pts[3]])
        else:
            s0 = Polyline([inner_pts[0], inner_pts[1], inner_pts[1] + Vector(0, 0, -dist), inner_pts[0] + Vector(0, 0, -dist), inner_pts[0]])
            s1 = Polyline([inner_pts[3], inner_pts[2], inner_pts[2] + Vector(0, 0, -dist), inner_pts[3] + Vector(0, 0, -dist), inner_pts[3]])
        meshes[axis_idx] = PolylineLoft.to_mesh(s1, s0)
        polyline_pairs[axis_idx] = (s1, s0)

        # T-section
        tl, bl, tr, br = surface_edge_polys[j]
        _p0off = Plane(tl[-2], -Vector(0, 0, 1).cross(tl.lines[0].direction)).offset(thick)  # noqa: F841
        _p1off = Plane(bl[-2], Vector(0, 0, 1).cross(bl.lines[0].direction)).offset(thick)  # noqa: F841

        mid0 = (poly1[j] + poly1[j + 1]) * 0.5
        mid1 = (poly2[j] + poly2[j + 1]) * 0.5
        p0 = Plane(mid0, Vector(0, 0, 1).cross(poly1[j + 1] - poly1[j]))
        p1 = Plane(mid1, -Vector(0, 0, 1).cross(poly2[j + 1] - poly2[j]))

        tl = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(tl, p0), p1)
        bl = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(bl, p0), p1)

        # s2 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(Polyline([tl[0], bl[0]]), p0off), p1off)
        # s3 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(Polyline([tl[1], bl[1]]), p0off), p1off)

        # OPTIONS: for the boundary faces
        # s2 = Polyline([s2[0], s2[1], [s2[1][0], s2[1][1], -dist], [s2[0][0], s2[0][1], -dist], s2[0]])
        # s3 = Polyline([s3[0], s3[1], [s3[1][0], s3[1][1], -dist], [s3[0][0], s3[0][1], -dist], s3[0]])
        # meshes.append(PolylineLoft.to_mesh(s2, s3))

    # Column head boundary (diagonal cut) -> axis 7
    plane_cut_1 = builder.end_planes[1]
    plane_cut_0 = builder.end_planes[1].offset(-builder.thick)
    plane0 = Plane.worldXY()
    plane1 = Plane(builder.axes[0].midpoint, Vector.Zaxis().cross(builder.axes[0].direction)).offset(-builder.thick * 0.5)
    plane2 = Plane.worldXY().offset(-builder.head_h)
    plane3 = Plane(builder.axes[-1].midpoint, Vector.Zaxis().cross(builder.axes[-1].direction)).offset(-builder.thick * 0.5)
    _result0 = Polyline(PlaneIntersect.intersect_consecutive_planes([plane0, plane1, plane2, plane3, plane0, plane1], plane_cut_0))  # noqa: F841
    _result1 = Polyline(PlaneIntersect.intersect_consecutive_planes([plane0, plane1, plane2, plane3, plane0, plane1], plane_cut_1))  # noqa: F841

    # meshes[7] = PolylineLoft.to_mesh(result0, result1)
    # polyline_pairs[7] = (result0, result1)

    return meshes, polyline_pairs, edge_midpoints


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
        transformation: Optional[Transformation] = None,
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

    @staticmethod
    def build(builder, angle: float = 0) -> QuarterResult:
        """Build quarter floor geometry from FloorBuilder.

        Parameters
        ----------
        builder : FloorBuilder
            The floor builder containing base geometry parameters.
        angle : float
            Rotation angle in degrees around Z-axis at origin (0, 0, 0).
            Valid values: 0, 90, 180, 270.

        Returns
        -------
        QuarterResult
            Container with rib_elements, rib_polys, tsection_elements,
            surface_elements, surface_edge_polys, boundary_beam_elements,
            screws, dowels, strips, and interactions.
        """
        # Create rotation transformation around Z-axis at origin
        rotation_xform = Rotation.from_axis_and_angle(
            [0, 0, 1], math.radians(angle), point=[0, 0, 0]
        ) if angle != 0 else None

        # Compute internal helper geometry (only used by quarter floor)
        axis_planes = _compute_axis_planes(builder)
        offset_axes = _compute_offset_axes(builder)
        lofted_lines = _compute_lofted_lines(builder, offset_axes)

        # Build components with polyline pairs
        rib_meshes, rib_polys, rib_polyline_pairs = _build_ribs(builder)
        tsection_meshes, tsection_polyline_pairs = _build_tsections(builder, axis_planes, lofted_lines)
        surface_meshes, surface_edge_polys, surface_polyline_pairs = _build_surfaces(builder, axis_planes, lofted_lines)
        boundary_beam_meshes, boundary_polyline_pairs, boundary_edge_midpoints = _build_boundaries(builder, surface_edge_polys)
        corner_block_meshes, corner_block_polyline_pairs = _build_corners_blocks(builder, axis_planes, offset_axes)

        # Apply rotation to polylines if needed (dicts for ribs/boundaries, lists for others)
        if rotation_xform:
            rib_polys = {axis_idx: [p.transformed(rotation_xform) for p in polys] for axis_idx, polys in rib_polys.items()}
            surface_edge_polys = [
                [poly.transformed(rotation_xform) for poly in edge_group]
                for edge_group in surface_edge_polys
            ]
            rib_polyline_pairs = {axis_idx: (p0.transformed(rotation_xform), p1.transformed(rotation_xform)) for axis_idx, (p0, p1) in rib_polyline_pairs.items()}
            tsection_polyline_pairs = [(p0.transformed(rotation_xform), p1.transformed(rotation_xform)) for p0, p1 in tsection_polyline_pairs]
            surface_polyline_pairs = [(p0.transformed(rotation_xform), p1.transformed(rotation_xform)) for p0, p1 in surface_polyline_pairs]
            boundary_polyline_pairs = {axis_idx: (p0.transformed(rotation_xform), p1.transformed(rotation_xform)) for axis_idx, (p0, p1) in boundary_polyline_pairs.items()}
            corner_block_polyline_pairs = [(p0.transformed(rotation_xform), p1.transformed(rotation_xform)) for p0, p1 in corner_block_polyline_pairs]
        # Create PlateElements with polylines - unified axis_elements dict
        axis_elements = {}
        axis_polys = {}

        # Add rib elements (axes 0, 1, 2, 6)
        for axis_idx, m in rib_meshes.items():
            axis_elements[axis_idx] = PlateElement(
                top_polyline=rib_polyline_pairs[axis_idx][0],
                bottom_polyline=rib_polyline_pairs[axis_idx][1],
                mesh=m.transformed(rotation_xform) if rotation_xform else m,
                name=f"axis_{axis_idx}"
            )
            axis_polys[axis_idx] = rib_polys[axis_idx]

        # Add boundary elements (axes 3, 4, 5, 7)
        for axis_idx, m in boundary_beam_meshes.items():
            axis_elements[axis_idx] = PlateElement(
                top_polyline=boundary_polyline_pairs[axis_idx][0],
                bottom_polyline=boundary_polyline_pairs[axis_idx][1],
                mesh=m.transformed(rotation_xform) if rotation_xform else m,
                name=f"axis_{axis_idx}"
            )
            axis_polys[axis_idx] = [boundary_polyline_pairs[axis_idx][0], boundary_polyline_pairs[axis_idx][1]]

        tsection_elements = [
            PlateElement(top_polyline=tsection_polyline_pairs[i][0], bottom_polyline=tsection_polyline_pairs[i][1],
                        name=f"tsection_{i}")
            for i in range(len(tsection_polyline_pairs))
        ]
        surface_elements = [
            PlateElement(top_polyline=surface_polyline_pairs[i][0], bottom_polyline=surface_polyline_pairs[i][1],
                        mesh=m.transformed(rotation_xform) if rotation_xform else m, name=f"surface_{i}")
            for i, m in enumerate(surface_meshes)
        ]

        corner_block_elements = [
            PlateElement(
                top_polyline=corner_block_polyline_pairs[i][0],
                bottom_polyline=corner_block_polyline_pairs[i][1],
                mesh=m.transformed(rotation_xform) if rotation_xform else m,
                name=f"corner_block_{i}",
            )
            for i, m in enumerate(corner_block_meshes)
        ]

        # =======================================================================
        # Build connectors directly referencing elements
        # =======================================================================
        screws = []
        dowels = []
        strips = []
        interactions = []

        height_offset = 20
        divisions = 4
        height0 = (builder.height - builder.rise - height_offset * 2) / (divisions - 1)
        _height1 = (builder.head_h - height_offset * 2) / (divisions * 2 - 1)  # noqa: F841
        height_middle = (builder.height - builder.rise) * 0.5

        # Helper to apply rotation to connector
        def apply_rotation(connector):
            if rotation_xform and connector.transformation:
                connector.transformation = rotation_xform * connector.transformation
            elif rotation_xform:
                connector.transformation = rotation_xform
            return connector

        # -----------------------------------------------------------------------
        # Corner screws - axes 0, 1, 2, 6 corners
        # -----------------------------------------------------------------------
        axis_pairs_02_to_boundary = {
            (3, 0): (axis_elements[3], axis_elements[0]),  # boundary axis 3, rib axis 0
            (3, 1): (axis_elements[3], axis_elements[1]),  # boundary axis 3, rib axis 1
            (5, 6): (axis_elements[5], axis_elements[6]),  # boundary axis 5, rib axis 6
            (5, 2): (axis_elements[5], axis_elements[2]),  # boundary axis 5, rib axis 2
        }
        for (offset_axis, intersect_axis), (boundary_element, rib_element) in axis_pairs_02_to_boundary.items():
            if intersect_axis in (0, 6):
                # Double-thick ribs: swap axes to rotate screw 90°, half thick longer on both sides
                line = LineOffset.offset_intersect(builder.axes[intersect_axis], builder.axes[offset_axis], builder.thick * 1.5)
            else:
                line = LineOffset.offset_intersect(builder.axes[offset_axis], builder.axes[intersect_axis], builder.thick * 0.5)
            for j in range(0, divisions):
                if j % 2 == 0:
                    continue
                translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height0 * j)
                screw = apply_rotation(_line_to_screw(translated_line))
                screws.append(screw)
                interactions.append((screw, boundary_element))
                interactions.append((screw, rib_element))

        # -----------------------------------------------------------------------
        # Strips between diagonal axes (axis[1] and axis[2])
        # -----------------------------------------------------------------------
        # axis_pairs_strips = [(3, 4), (4, 5)]
        # for offset_axis, intersect_axis in axis_pairs_strips:
        #     strip_point = Point(*intersection_line_line(builder.axes[offset_axis], builder.axes[intersect_axis])[0])
        #     strip_line = Line(strip_point, strip_point + builder.axes[offset_axis].direction +  # noqa: E501
        #         builder.axes[intersect_axis].direction).translated(Vector.Zaxis() * -height_middle)
        #     strip = apply_rotation(_line_to_strip(strip_line, height_middle * 2))
            # strips.append(strip)
            # interactions.append((strip, axis_elements[offset_axis]))
            # interactions.append((strip, axis_elements[intersect_axis]))
        axis_pairs_strips = [(3, 4), (5, 4)]
        for offset_axis, intersect_axis in axis_pairs_strips:
            offset_line = LineOffset.offset_xy(builder.axes[offset_axis], builder.thick * -0.5)
            strip_point = Point(*intersection_line_line(offset_line, builder.axes[intersect_axis])[0])

            strip_line = Line(strip_point, strip_point + Vector.Zaxis().cross(builder.axes[offset_axis].direction)).translated(Vector.Zaxis() * -height_middle)
            strip = apply_rotation(_line_to_strip(strip_line, height_middle * 2))
            strips.append(strip)
            interactions.append((strip, axis_elements[offset_axis]))
            interactions.append((strip, axis_elements[intersect_axis]))

        # -----------------------------------------------------------------------
        # Strips at axis corners
        # -----------------------------------------------------------------------
        # Double-thick boundary rib strips from contracted edge midpoints
        boundary_strip_configs = [
            (3, [axis_elements[0], axis_elements[3]]),
            (5, [axis_elements[6], axis_elements[5]]),
        ]
        for boundary_axis, connected_elements in boundary_strip_configs:
            strip_point = Point(*boundary_edge_midpoints[boundary_axis])
            strip_dir = builder.axes[boundary_axis].direction
            strip_line = Line(strip_point, strip_point + strip_dir).translated(Vector.Zaxis() * -height_middle)
            strip = apply_rotation(_line_to_strip(strip_line, height_middle * 2))
            strips.append(strip)
            for element in connected_elements:
                interactions.append((strip, element))

        # Single-thick rib strips
        axis_strip_single = {
            (1, 3): [axis_elements[1], axis_elements[3]],
            (2, 5): [axis_elements[2], axis_elements[5]],
        }
        for (offset_axis, intersect_axis), connected_elements in axis_strip_single.items():
            intersect_line = LineOffset.offset_xy(builder.axes[intersect_axis], builder.thick * -0.5)
            strip_point = Point(*intersection_line_line(builder.axes[offset_axis], intersect_line)[0])
            strip_dir = builder.axes[offset_axis].direction
            strip_line = Line(strip_point, strip_point + strip_dir).translated(Vector.Zaxis() * -height_middle)
            strip = apply_rotation(_line_to_strip(strip_line, height_middle * 2))
            strips.append(strip)
            for element in connected_elements:
                interactions.append((strip, element))

        # -----------------------------------------------------------------------
        # Corner block strips at column head - from wedge edges
        # -----------------------------------------------------------------------
        # Each corner block k: left rib axis [0,1,2], right rib axis [1,2,6]
        # top_poly = [bl0, bl1, br1, br0, bl0]
        # Left rib face edge: top[0]→top[1] (bl side), Right rib face edge: top[3]→top[2] (br side)
        corner_rib_axes = [(0, 1), (1, 2), (2, 6)]
        for k in range(len(corner_block_elements)):
            top_poly = corner_block_polyline_pairs[k][0]
            left_axis, right_axis = corner_rib_axes[k]

            # Left rib face: edge top[0]→top[1], strip at midpoint, rotated 90°, normal flipped
            # Positions from corner_block_polyline_pairs are already rotated, no apply_rotation needed
            left_mid = (top_poly[0] + top_poly[1]) * 0.5
            left_dir = -Vector.Zaxis().cross(Vector.from_start_end(top_poly[0], top_poly[1]))
            left_point = Point(left_mid.x, left_mid.y, -builder.head_h * 0.5)
            left_line = Line(left_point, left_point + left_dir)
            left_strip = _line_to_strip(left_line, builder.head_h)
            strips.append(left_strip)
            interactions.append((left_strip, corner_block_elements[k]))
            interactions.append((left_strip, axis_elements[left_axis]))

            # Right rib face: edge top[3]→top[2], strip at midpoint, rotated 90°, normal flipped
            # Positions from corner_block_polyline_pairs are already rotated, no apply_rotation needed
            right_mid = (top_poly[3] + top_poly[2]) * 0.5
            right_dir = -Vector.Zaxis().cross(Vector.from_start_end(top_poly[3], top_poly[2]))
            right_point = Point(right_mid.x, right_mid.y, -builder.head_h * 0.5)
            right_line = Line(right_point, right_point + right_dir)
            right_strip = _line_to_strip(right_line, builder.head_h)
            strips.append(right_strip)
            interactions.append((right_strip, corner_block_elements[k]))
            interactions.append((right_strip, axis_elements[right_axis]))

        # -----------------------------------------------------------------------
        # Hilti joints at 2x-thick rib / boundary interfaces
        # -----------------------------------------------------------------------
        # Only one side is needed (the other is symmetrical via placement).
        # Origin is at the rib-boundary axis intersection (rib end).
        # rib_dir_sign flips the profile direction so it extends into the rib.
        hilti_joints = []
        modifiers = []
        hilti_configs = [
            (3, 0, 1),   # boundary axis 3, rib axis 0, +rib_dir
            (5, 6, -1),  # boundary axis 5, rib axis 6, -rib_dir
        ]
        for boundary_axis, rib_axis, rib_dir_sign in hilti_configs:
            # Origin at rib-boundary axis intersection, offset by 0.5*thick along boundary normal
            pt = Point(*intersection_line_line(builder.axes[rib_axis], builder.axes[boundary_axis])[0])
            boundary_normal = builder.axes[boundary_axis].direction.unitized()
            boundary_normal_ortho = Vector.Zaxis().cross(boundary_normal).unitized()
            origin = Point(pt.x + boundary_normal.x * 0.5 * builder.thick + boundary_normal_ortho.x * -0.5 * builder.thick,
                           pt.y + boundary_normal.y * -0.5 * builder.thick + boundary_normal_ortho.y * -0.5 * builder.thick,
                           -height_middle)
            rib_dir = builder.axes[rib_axis].direction * rib_dir_sign
            boundary_dir = builder.axes[boundary_axis].direction
            hilti = _create_hilti(origin, rib_dir, boundary_dir, height=builder.thick * 2.1)
            hilti = apply_rotation(hilti)
            hilti_joints.append(hilti)
            interactions.append((hilti, axis_elements[rib_axis]))
            # Boolean difference: cut hilti shape from boundary rib only
            modifiers.append((hilti, axis_elements[rib_axis], SolidDifferenceModifier()))

        # -----------------------------------------------------------------------
        # Corner screws - near oculus (belong to axis[4])
        # -----------------------------------------------------------------------
        axis_pairs_1 = [(3, 4), (5, 4)]
        for offset_axis, intersect_axis in axis_pairs_1:
            line = LineOffset.offset_intersect(builder.axes[offset_axis], builder.axes[intersect_axis], builder.thick * 0.5)
            for j in range(0, divisions):
                if j % 2 == 1:
                    continue
                translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height0 * j)
                screw = apply_rotation(_line_to_screw(translated_line))
                screws.append(screw)
                interactions.append((screw, axis_elements[offset_axis]))

        # -----------------------------------------------------------------------
        # Back corner screws - belong to axis[7]
        # -----------------------------------------------------------------------
        # rib_axes = [0, 1, 2, 6]
        # for i in rib_axes:
        #     axis_plane = Plane(builder.axes[i].midpoint, Vector.Zaxis().cross(builder.axes[i].direction))
        #     p0 = intersection_plane_plane_plane(axis_plane, builder.end_diagonal_plane, Plane.worldXY())
        #     p1 = intersection_plane_plane_plane(axis_plane, builder.end_diagonal_plane.offset(-builder.thick * 1.0), Plane.worldXY())
        #     line = Line(p0, p1)

        #     if i == 0 or i == 6:
        #         for j in range(divisions * 2):
        #             if j % 2 == 0:
        #                 continue
        #             translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height1 * j)
        #             screw = apply_rotation(_line_to_screw(translated_line))
        #             screws.append(screw)
        #             interactions.append((screw, axis_elements[7]))
        #     else:
        #         for j in range(divisions * 2):
        #             if j % 2 == 1:
        #                 continue
        #             translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height1 * j)
        #             screw = apply_rotation(_line_to_screw(translated_line))
        #             screws.append(screw)
        #             interactions.append((screw, axis_elements[7]))

        # -----------------------------------------------------------------------
        # Boundary connectors - connect to axis_elements[3, 4, 5]
        # -----------------------------------------------------------------------
        boundary_configs = [(3, 12), (4, 8), (5, 12)]  # (axis_idx, divisions)
        for i, (axis_idx, num_divisions) in enumerate(boundary_configs):
            line = Line(builder.quarter_polygon[1 + i], builder.quarter_polygon[2 + i])
            direction = Vector.Zaxis().cross(line.direction).unitized() * builder.thick

            if axis_idx == 5:
                line = Line(line.end, line.start)
            points = LineOffset.divide(line, num_divisions)

            for idx, pt in enumerate(points):
                if idx == 0 or idx == len(points) - 1:
                    continue

                p_start = pt + direction - height_middle * Vector.Zaxis()
                p_end = pt + direction * 0 - height_middle * Vector.Zaxis()
                connector_line = Line(p_start, p_end)

                if idx % 3 == 1:
                    dowel = apply_rotation(_line_to_dowel(connector_line))
                    dowels.append(dowel)
                    interactions.append((dowel, axis_elements[axis_idx]))
                else:
                    screw = apply_rotation(_line_to_screw(connector_line))
                    screws.append(screw)
                    interactions.append((screw, axis_elements[axis_idx]))

        return QuarterResult(
            axis_elements=axis_elements,
            axis_polys=axis_polys,
            tsection_elements=tsection_elements,
            surface_elements=surface_elements,
            corner_block_elements=corner_block_elements,
            surface_edge_polys=surface_edge_polys,
            screws=screws,
            dowels=dowels,
            strips=strips,
            hilti_joints=hilti_joints,
            interactions=interactions,
            modifiers=modifiers,
        )
