import math

from compas.data import json_dump
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Projection
from compas.geometry import Rotation
from compas.geometry import Vector
from compas.geometry import intersection_line_line
from compas.geometry import intersection_line_plane
from compas.geometry import intersection_segment_segment
from compas_viewer import Viewer
from compas_viewer.config import Config

from compas_tf.geometry import BezierCurve
from compas_tf.geometry import PlaneIntersect
from compas_tf.geometry import PolylineCut
from compas_tf.geometry import PolylineLoft
from compas_tf.geometry import PolylineOffset


class FloorSkeleton:
    """Floor skeleton generator using polar array pattern.

    Phase 1: Computes all geometry for quarter 1
    Phase 2: Rotates Q1 geometry to create quarters 2, 3, 4
    """

    # ==========================================================================
    # Initialization
    # ==========================================================================

    def __init__(self, size=3000, height=650, rise=453, oculus=1000, thick=40, beam_w=250):
        self.size = size  # Half size of floor
        self.height = height  # Total height
        self.rise = rise  # Parabola rise
        self.static_h = height - rise  # Static height above parabola
        self.oculus = oculus  # Half size of central oculus
        self.beam_w = beam_w  # Boundary beam width
        self.thick = thick  # Beam element thickness
        self.head_h = 0  # Column head half height (derived)

        # Cached geometry (quarter 1 only)
        self._oculus_pts = None
        self._q1_poly = None
        self._axes = None
        self._bound_parabolas = None
        self._rib_parabolas = None
        self._target_planes = None
        self._bound_planes = None
        self._axis_planes = None
        self._cut_planes = None
        self._end_planes = None
        self._offset_axes = None
        self._loft_lines = None

        # Q1 mesh storage (computed in phase 1)
        self._q1_rib_meshes = None
        self._q1_rib_polys = None
        self._q1_tsection_meshes = None
        self._q1_surface_meshes = None
        self._q1_surface_edge_polys = None
        self._q1_column_head = None
        self._q1_head_top = None
        self._q1_head_gaps = None
        self._q1_boundary_beams = None
        self._oculus_mesh = None

        # All quarters storage (computed in phase 2 - rotation)
        self._rib_meshes = None
        self._rib_polys = None
        self._tsection_meshes = None
        self._surface_meshes = None
        self._surface_edge_polylines = None
        self._column_heads = None
        self._column_head_top_blocks = None
        self._column_head_gap_blocks = None
        self._boundary_beams = None
        self._edge_beams = None

        # Steps dictionary for serialization
        self.steps = {}

    # ==========================================================================
    # Base Geometry - Points (only oculus + quarter 1 perimeter needed)
    # ==========================================================================

    @property
    def oculus_points(self):
        if self._oculus_pts is None:
            self._oculus_pts = [
                Point(0, -self.oculus, 0),
                Point(self.oculus, 0, 0),
                Point(0, self.oculus, 0),
                Point(-self.oculus, 0, 0),
            ]
            self.steps["01_oculus_points"] = self._oculus_pts
        return self._oculus_pts

    @property
    def quarter_polygon(self):
        if self._q1_poly is None:
            self._q1_poly = Polygon([
                Point(-self.size, -self.size, 0),  # corner
                Point(0, -self.size, 0),  # edge midpoint
                self.oculus_points[0],  # oculus
                self.oculus_points[3],  # oculus
                Point(-self.size, 0, 0),  # edge midpoint
            ])
            self.steps["02_quarter_polygon"] = self._q1_poly
        return self._q1_poly

    # ==========================================================================
    # Axes - Beam Positioning Lines
    # ==========================================================================

    @property
    def axes(self):
        """Central axes for rib positioning"""
        if self._axes is None:
            polygon = self.quarter_polygon
            offset_polygon_full = PolylineOffset.offset_polygon(polygon, self.thick)
            offset_polygon_half = PolylineOffset.offset_polygon(polygon, self.thick * 0.5)
            axes_lines = list(offset_polygon_half.lines)

            # Add diagonal axes at corner
            corner = offset_polygon_half.points[0]
            axes_lines.insert(1, Line(corner, offset_polygon_full.points[2]))
            axes_lines.insert(2, Line(corner, offset_polygon_full.points[3]))

            # Extend axes to boundary
            extended_axes = []
            for j in range(len(axes_lines)):
                p0, p1 = axes_lines[j].start, axes_lines[j].end
                direction = (p1 - p0).unitized()
                line = Line(direction * self.thick * 4 + p1, -direction * self.thick * 4 + p0)

                intersection_points = []
                for k in range(len(polygon)):
                    seg = Line(polygon[k], polygon[(k + 1) % len(polygon)])
                    pt = intersection_segment_segment(line, seg)
                    if pt[0] is not None:
                        intersection_points.append(pt[0])

                if len(intersection_points) != 2:
                    raise Exception("Intersection points not 2", len(intersection_points))

                line = Line(intersection_points[0], intersection_points[1])
                _, cpt0 = axes_lines[j].closest_point(line.start, True)
                _, cpt1 = axes_lines[j].closest_point(line.end, True)
                if cpt0 > cpt1:
                    line = Line(line.end, line.start)
                extended_axes.append(line)

            self._axes = extended_axes
            self.steps["03_axes"] = self._axes
        return self._axes

    # ==========================================================================
    # Parabolas - Boundary and Rib Curves
    # ==========================================================================

    @property
    def boundary_parabolas(self):
        if self._bound_parabolas is None:
            divisions = 7
            q1_parabolas = []
            axes = self.axes

            for j in [0, len(axes) - 1]:
                if j == 0:
                    p0 = Vector(0, 0, -self.height) + axes[j].start
                    p1 = Vector(0, 0, -self.static_h) + axes[j].midpoint
                    p2 = Vector(0, 0, -self.static_h) + axes[j].end
                else:
                    p0 = Vector(0, 0, -self.static_h) + axes[j].start
                    p1 = Vector(0, 0, -self.static_h) + axes[j].midpoint
                    p2 = Vector(0, 0, -self.height) + axes[j].end

                bezier = BezierCurve.quadratic_points(p0, p1, p2, divisions)
                self.head_h = abs(bezier[-2][2]) * 0.5 - 3.5
                q1_parabolas.append(bezier)

            self._bound_parabolas = q1_parabolas
            self.steps["04_boundary_parabolas"] = q1_parabolas
        return self._bound_parabolas

    @property
    def rib_parabolas(self):
        """Projected parabolas for ribs (quarter 1 only)."""
        if self._rib_parabolas is not None:
            return self._rib_parabolas

        axes = self.axes
        proj_dir0 = Vector.Zaxis().cross(axes[0].direction)
        proj_dir3 = Vector.Zaxis().cross(axes[3].direction)

        target_planes = self.target_planes
        xform10 = Projection.from_plane_and_direction(target_planes[1], proj_dir0)
        xform20 = Projection.from_plane_and_direction(target_planes[2], proj_dir3)

        parabola0 = self.boundary_parabolas[0]
        parabola1 = parabola0.transformed(xform10)
        parabola3 = self.boundary_parabolas[1]
        parabola2 = parabola3.transformed(xform20)
        parabola2.points.reverse()
        parabola3.points.reverse()

        self._rib_parabolas = [parabola0, parabola1, parabola2, parabola3]
        self.steps["05_rib_parabolas"] = self._rib_parabolas
        return self._rib_parabolas

    # ==========================================================================
    # Planes - Target, Axis, Cut, and End Planes
    # ==========================================================================

    @property
    def target_planes(self):
        """Target planes for rib projection (quarter 1 only)."""
        if self._target_planes is not None:
            return self._target_planes

        axes = self.axes
        planes = [Plane(axes[i].midpoint, Vector.Zaxis().cross(axes[i].direction)) for i in range(4)]
        self._target_planes = planes
        self.steps["06_target_planes"] = planes
        return self._target_planes

    @property
    def axis_boundary_planes(self):
        """Axis boundary planes (quarter 1 only)."""
        if self._bound_planes is not None:
            return self._bound_planes

        axes = self.axes
        planes = [Plane(axes[j].midpoint, Vector.Zaxis().cross(axes[j].direction)) for j in range(3, len(axes) - 1)]
        self._bound_planes = planes
        self.steps["07_axis_boundary_planes"] = planes
        return self._bound_planes

    @property
    def axis_planes(self):
        """Axis planes for T-sections (quarter 1 only)."""
        if self._axis_planes is not None:
            return self._axis_planes

        axes = self.axes
        planes = [Plane(axes[j].start, Vector.Zaxis().cross(axes[j].direction)) for j in range(3)]
        planes.append(Plane(axes[-1].start, -Vector.Zaxis().cross(axes[-1].direction)))
        self._axis_planes = planes
        self.steps["08_axis_planes"] = planes
        return self._axis_planes

    @property
    def cut_planes(self):
        """Cut planes for trimming geometry (quarter 1 only)."""
        if self._cut_planes is not None:
            return self._cut_planes

        offset_planes = [plane.offset(self.thick * 0.5) for plane in self.axis_boundary_planes]
        pts, pts_offset, _ = self._compute_corner_geometry()

        normals = [-(pts[i + 1] - pts[i]).cross(pts_offset[i] - pts[i]) for i in range(3)]
        corner_planes = [Plane((pts[i] + pts[i + 1]) * 0.5, normals[i]) for i in range(3)]

        self._cut_planes = offset_planes + corner_planes
        self.steps["09_cut_planes"] = self._cut_planes
        return self._cut_planes

    @property
    def end_planes(self):
        """End planes for each rib (quarter 1 only)."""
        if self._end_planes is not None:
            return self._end_planes

        planes = []
        for i in range(4):
            id = i if i < 3 else -1
            p0 = Point(self.axes[id].start[0], self.axes[id].start[1], 0)
            p1 = Point(self.axes[id].end[0], self.axes[id].end[1], 0)
            if i == 3:
                p0, p1 = p1, p0
            planes.append(Plane(p0, p0 - p1).offset(-200))

        self._end_planes = planes
        self.steps["10_end_planes"] = planes
        return self._end_planes

    # ==========================================================================
    # Surface Lofting - Offset Axes and Lofted Lines
    # ==========================================================================

    @property
    def offset_axes(self):
        """Offset axes for surface lofting (quarter 1 only)."""
        if self._offset_axes is not None:
            return self._offset_axes

        rib_parabolas = self.rib_parabolas
        target_planes = self.target_planes
        axes = self.axes

        offset_0_bottom = PolylineOffset.offset_polyline(rib_parabolas[0], self.thick)
        offset_0_top = PolylineOffset.offset_polyline(rib_parabolas[0], self.thick * 2)
        offset_3_bottom = PolylineOffset.offset_polyline(rib_parabolas[3], self.thick)
        offset_3_top = PolylineOffset.offset_polyline(rib_parabolas[3], self.thick * 2)

        proj_dir0 = Vector.Zaxis().cross(axes[0].direction)
        proj_dir3 = Vector.Zaxis().cross(axes[3].direction)
        xform10 = Projection.from_plane_and_direction(target_planes[1], proj_dir0)
        xform20 = Projection.from_plane_and_direction(target_planes[2], proj_dir3)

        q1_offset_axes = [
            [offset_0_bottom, offset_0_top],
            [offset_0_bottom.transformed(xform10), offset_0_top.transformed(xform10)],
            [offset_3_bottom.transformed(xform20), offset_3_top.transformed(xform20)],
            [offset_3_bottom, offset_3_top],
        ]
        self._offset_axes = q1_offset_axes
        self.steps["11_offset_axes"] = q1_offset_axes
        return self._offset_axes

    @property
    def lofted_lines(self):
        """Lofted lines between offset axes (quarter 1 only)."""
        if self._loft_lines is not None:
            return self._loft_lines

        offset_axes = self.offset_axes
        lofted_bottom = []
        lofted_top = []

        for i in range(len(self.rib_parabolas) - 1):
            lofted_bottom.append(PolylineLoft.to_lines(offset_axes[i][0], offset_axes[i + 1][0]))
            lofted_top.append(PolylineLoft.to_lines(offset_axes[i][1], offset_axes[i + 1][1]))

        self._loft_lines = [lofted_bottom, lofted_top]
        self.steps["12_lofted_lines"] = {"bottom": lofted_bottom, "top": lofted_top}
        return self._loft_lines

    # ==========================================================================
    # Helper Methods - Geometry and Rotation
    # ==========================================================================

    def _compute_corner_geometry(self):
        """Compute corner geometry for cut planes and column heads (quarter 1)."""
        axes = self.axes
        intersection = intersection_line_line(axes[0], axes[-1])[0]

        scale, angle_inclination = 460, 180
        points, planes = [], []
        for i in range(4):
            point = Point(*(axes[i].direction * scale + intersection))
            points.append(point)
            plane = Plane(point, axes[i].direction.cross(Vector.Zaxis()))
            planes.append(plane.offset(self.thick * (-0.5 if i > 1 else 0.5)))

        middle_line = Line(points[1], points[2])
        pts = [
            planes[0].closest_point(Point(*intersection_line_plane(middle_line, planes[1]))),
            Point(*intersection_line_plane(middle_line, planes[1])),
            Point(*intersection_line_plane(middle_line, planes[2])),
            planes[3].closest_point(Point(*intersection_line_plane(middle_line, planes[2]))),
        ]

        pts_offset = [axes[i].direction * angle_inclination + pts[i] for i in range(4)]
        pts_offset[0] = planes[0].closest_point(pts_offset[1])
        pts_offset[3] = planes[3].closest_point(pts_offset[2])
        pts_offset = [-Vector.Zaxis() * self.height + p for p in pts_offset]

        return pts, pts_offset, planes

    def _get_rotation_transform(self, rotations_90):
        """Get rotation transformation for n * 90 degrees around Z-axis."""
        return Rotation.from_axis_and_angle([0, 0, 1], math.pi / 2 * rotations_90, point=[0, 0, 0])

    def _rotate_geometry(self, geometry, rotations_90):
        """Rotate geometry by n * 90 degrees around Z-axis."""
        if rotations_90 == 0:
            return geometry
        xform = self._get_rotation_transform(rotations_90)
        if isinstance(geometry, list):
            return [self._rotate_geometry(item, rotations_90) for item in geometry]
        return geometry.transformed(xform)

    # ==========================================================================
    # Phase 1: Q1 Mesh Computation
    # ==========================================================================

    def _compute_q1_rib_meshes(self):
        """Compute rib meshes and polylines for quarter 1."""
        if self._q1_rib_meshes is not None:
            return self._q1_rib_meshes, self._q1_rib_polys

        offsets_ids = [0, 1, 1, 2]
        offset_pairs = [(0.5, -0.5), (0.5, -0.5), (0.5, -0.5), (0.5, -0.5)]
        rib_parabolas = self.rib_parabolas
        target_planes = self.target_planes
        end_planes = self.end_planes
        cut_planes = self.cut_planes

        quarter_meshes, list_rib_polylines = [], []

        for i in range(len(rib_parabolas)):
            offset0, offset1 = offset_pairs[i]
            end_plane = end_planes[i]
            cut_boundary = cut_planes[offsets_ids[i]]
            cut_rib = cut_planes[offsets_ids[i] + 3]

            proj0 = rib_parabolas[i].translated(target_planes[i].normal * self.thick * offset0)
            proj1 = rib_parabolas[i].translated(target_planes[i].normal * self.thick * offset1)

            cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj0, cut_rib), cut_boundary)
            cut1 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj1, cut_rib), cut_boundary)

            extension = 378 if i in [0, 3] else 450
            line0 = PolylineCut.cut_by_plane(Polyline([cut0[0], cut0[-1]]).extended([extension, 0]), end_plane, flip=True)
            line1 = PolylineCut.cut_by_plane(Polyline([cut1[0], cut1[-1]]).extended([extension, 0]), end_plane, flip=True)

            xy_proj = Projection.from_plane_and_direction(Plane.worldXY(), Vector.Zaxis())
            mid_proj = Projection.from_plane_and_direction(Plane([0, 0, -self.head_h], [0, 0, 1]), Vector.Zaxis())

            top0, top1 = line0.transformed(xy_proj), line1.transformed(xy_proj)
            mid0 = PolylineCut.cut_by_plane(line0.transformed(mid_proj), cut_rib, flip=True)
            mid1 = PolylineCut.cut_by_plane(line1.transformed(mid_proj), cut_rib, flip=True)

            joined0 = Polyline(list(reversed(top0.points)) + mid0.points + cut0.points)
            joined1 = Polyline(list(reversed(top1.points)) + mid1.points + cut1.points)
            joined0.append(joined0.points[0])
            joined1.append(joined1.points[0])

            quarter_meshes.append(PolylineLoft.to_mesh(joined0, joined1))
            list_rib_polylines.extend([joined0, joined1])

        self._q1_rib_meshes = quarter_meshes
        self._q1_rib_polys = list_rib_polylines
        self.steps["13_q1_rib_meshes"] = quarter_meshes
        self.steps["14_q1_rib_polylines"] = list_rib_polylines
        return quarter_meshes, list_rib_polylines

    def _compute_q1_tsection_meshes(self):
        """Compute T-section meshes for quarter 1."""
        if self._q1_tsection_meshes is not None:
            return self._q1_tsection_meshes

        lofted_bottom = self.lofted_lines[0]
        cut_planes = self.cut_planes
        rib_parabolas = self.rib_parabolas
        axis_planes = self.axis_planes

        offsets = [[1], [-1, 1], [-1, 1], [-1]]
        offsets_ids = [[0], [0, 1], [1, 2], [2]]
        quarter_meshes = []

        for i in range(len(rib_parabolas)):
            for j in range(len(offsets[i])):
                ap = axis_planes[i]
                plane0 = Plane(ap.point + ap.normal * self.thick * 0.5 * offsets[i][j], ap.normal)
                plane1 = Plane(ap.point + ap.normal * self.thick * 1.5 * offsets[i][j], ap.normal)

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

        self._q1_tsection_meshes = quarter_meshes
        self.steps["15_q1_tsection_meshes"] = quarter_meshes
        return quarter_meshes

    def _compute_q1_surface_meshes(self):
        """Compute surface meshes and edge polylines for quarter 1."""
        if self._q1_surface_meshes is not None:
            return self._q1_surface_meshes, self._q1_surface_edge_polys

        lofted_bottom = self.lofted_lines[0]
        lofted_top = self.lofted_lines[1]
        cut_planes = self.cut_planes
        rib_parabolas = self.rib_parabolas
        axis_planes = self.axis_planes

        offsets = [[1], [-1, 1], [-1, 1], [-1]]
        offsets_ids = [[0], [0, 1], [1, 2], [2]]
        surface_edges = []

        for i in range(len(rib_parabolas)):
            for j in range(len(offsets[i])):
                ap = axis_planes[i]
                plane0 = Plane(ap.point + ap.normal * self.thick * 0.5 * offsets[i][j], ap.normal)

                cut0 = PolylineCut.cut_lines_by_plane(lofted_bottom[offsets_ids[i][j]], plane0)
                cut1 = PolylineCut.cut_lines_by_plane(lofted_top[offsets_ids[i][j]], plane0)

                for plane in [cut_planes[offsets_ids[i][j]], cut_planes[offsets_ids[i][j] + 3]]:
                    cut0 = PolylineCut.cut_by_plane(cut0, plane)
                    cut1 = PolylineCut.cut_by_plane(cut1, plane)

                surface_edges.extend([cut0, cut1])

        quarter_meshes, quarter_edge_polylines = [], []
        for pair in [surface_edges[i : i + 4] for i in range(0, len(surface_edges), 4)]:
            bl, br, tl, tr = pair[0], pair[1], pair[2], pair[3]
            poly0 = Polyline(bl.points + list(reversed(br.points)))
            poly1 = Polyline(tl.points + list(reversed(tr.points)))
            quarter_meshes.append(PolylineLoft.to_mesh(poly0, poly1))
            quarter_edge_polylines.append([tl, bl, tr, br])

        self._q1_surface_meshes = quarter_meshes
        self._q1_surface_edge_polys = quarter_edge_polylines
        self.steps["16_q1_surface_meshes"] = quarter_meshes
        self.steps["17_q1_surface_edge_polys"] = quarter_edge_polylines
        return quarter_meshes, quarter_edge_polylines

    def _compute_q1_column_head(self):
        """Compute column head geometry for quarter 1."""
        if self._q1_column_head is not None:
            return self._q1_column_head, self._q1_head_top, self._q1_head_gaps

        # Ensure rib polys computed
        self._compute_q1_rib_meshes()

        pts, pts_offset, _ = self._compute_corner_geometry()
        q1 = self.quarter_polygon
        end_planes = self.end_planes

        plane_top = Plane([0, 0, -self.head_h], Vector.Zaxis())
        plane_bottom = Plane([0, 0, -self.head_h * 2], Vector.Zaxis())

        top_pts = [Point(*intersection_line_plane(Line(pts[i], pts_offset[i]), plane_top)) for i in range(4)]
        bottom_pts = [Point(*intersection_line_plane(Line(pts[i], pts_offset[i]), plane_bottom)) for i in range(4)]

        corner = q1[0]  # corner point
        polyline_top = Polyline(top_pts).extended([self.beam_w, self.beam_w])
        gap_front = Polyline(polyline_top.points)
        polyline_bottom = Polyline(bottom_pts).extended([self.beam_w, self.beam_w])

        direction = -polyline_top.lines[0].direction * self.beam_w + polyline_bottom.lines[-1].direction * self.beam_w
        corner = direction + corner

        for poly, z_off in [(polyline_top, -self.head_h), (polyline_bottom, -self.head_h * 2)]:
            poly.append(Vector(0, 0, z_off) + corner)
            poly.points = poly.points[-1:] + poly.points[:-1]
            poly.append(poly[0])

        taper = polyline_bottom.translated(Vector(0, 0, -(self.height - self.head_h * 2)))
        xaxis = taper.lines[0].direction * self.beam_w
        yaxis = taper.lines[-1].direction * self.beam_w
        center = taper[0]
        taper = Polyline([center, center + xaxis, center + xaxis - yaxis * 0.99, center + xaxis * 0.99 - yaxis, center - yaxis, center])

        head_mesh = PolylineLoft.multiple_to_mesh([polyline_top, polyline_bottom, taper])

        # Top block
        stop0 = Plane(q1[0], Vector.Zaxis().cross(q1[1] - q1[0]))
        stop1 = Plane(q1[0], Vector.Zaxis().cross(q1[-1] - q1[0]))
        ipoints = PlaneIntersect.intersect_consecutive_planes([stop0] + list(end_planes) + [stop1])

        top_poly0 = Polyline(ipoints)
        gap_poly = Polyline(ipoints)
        top_poly0.extend((self.beam_w, self.beam_w))
        top_poly0.insert(0, Point(center[0], center[1], 0))
        top_poly0.append(top_poly0[0])
        top_poly1 = top_poly0.translated(Vector(0, 0, -self.head_h))
        top_mesh = PolylineLoft.to_mesh(top_poly0, top_poly1)

        # Gap blocks
        gap_blocks = []
        ribs = self._q1_rib_polys
        for a, b in [[0, 2], [3, 5], [4, 7]]:
            cut0 = Polygon(list(reversed(ribs[a].points[:-1]))).plane
            cut1 = Polygon(ribs[b].points[:-1]).plane

            points = []
            for poly in [gap_poly, gap_front]:
                cut = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(poly, cut0), cut1)
                pts_list = [Point(p[0], p[1], 0) for p in (cut if poly == gap_poly else reversed(cut))]
                points.extend(pts_list)

            poly0 = Polygon(points)
            poly1 = poly0.translated(Vector(0, 0, -self.head_h))
            gap_blocks.append(PolylineLoft.to_mesh(Polyline(poly0.points), Polyline(poly1.points)))

        self._q1_column_head = head_mesh
        self._q1_head_top = top_mesh
        self._q1_head_gaps = gap_blocks
        self.steps["18_q1_column_head"] = head_mesh
        self.steps["19_q1_head_top"] = top_mesh
        self.steps["20_q1_head_gaps"] = gap_blocks
        return head_mesh, top_mesh, gap_blocks

    def _compute_q1_boundary_beams(self):
        """Compute boundary beam meshes for quarter 1."""
        if self._q1_boundary_beams is not None:
            return self._q1_boundary_beams

        # Ensure surface edges computed
        self._compute_q1_surface_meshes()

        q1 = self.quarter_polygon
        surface_edges = self._q1_surface_edge_polys

        poly0 = Polyline([q1[i] for i in [1, 2, 3, 4]])  # edge -> oculus -> oculus -> edge
        poly1 = PolylineOffset.offset_polyline_xy(poly0, self.thick)
        poly2 = PolylineOffset.offset_polyline_xy(poly0, self.thick * 1.5)

        meshes = []
        dist = self.height - self.rise

        for j in range(len(poly0) - 1):
            # Main beam
            s0 = Polyline([poly0[j], poly0[j + 1], Vector(0, 0, -dist) + poly0[j + 1], Vector(0, 0, -dist) + poly0[j], poly0[j]])
            s1 = Polyline([poly1[j], poly1[j + 1], Vector(0, 0, -dist) + poly1[j + 1], Vector(0, 0, -dist) + poly1[j], poly1[j]])
            meshes.append(PolylineLoft.to_mesh(s0, s1))

            # T-section
            tl, bl, tr, br = surface_edges[j]
            p0off = Plane(tl[-2], -Vector(0, 0, 1).cross(tl.lines[0].direction)).offset(self.thick)
            p1off = Plane(bl[-2], Vector(0, 0, 1).cross(bl.lines[0].direction)).offset(self.thick)

            mid0 = (poly1[j] + poly1[j + 1]) * 0.5
            mid1 = (poly2[j] + poly2[j + 1]) * 0.5
            p0 = Plane(mid0, Vector(0, 0, 1).cross(poly1[j + 1] - poly1[j]))
            p1 = Plane(mid1, -Vector(0, 0, 1).cross(poly2[j + 1] - poly2[j]))

            tl = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(tl, p0), p1)
            bl = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(bl, p0), p1)

            s2 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(Polyline([tl[0], bl[0]]), p0off), p1off)
            s3 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(Polyline([tl[1], bl[1]]), p0off), p1off)

            s2 = Polyline([s2[0], s2[1], [s2[1][0], s2[1][1], -dist], [s2[0][0], s2[0][1], -dist], s2[0]])
            s3 = Polyline([s3[0], s3[1], [s3[1][0], s3[1][1], -dist], [s3[0][0], s3[0][1], -dist], s3[0]])
            meshes.append(PolylineLoft.to_mesh(s2, s3))

        self._q1_boundary_beams = meshes
        self.steps["21_q1_boundary_beams"] = meshes
        return meshes

    def _compute_oculus_mesh(self):
        """Compute oculus beam mesh."""
        if self._oculus_mesh is not None:
            return self._oculus_mesh

        op = self.oculus_points
        oculus = Polyline([op[0], op[1], op[2], op[3], op[0]])
        self._oculus_mesh = PolylineLoft.to_mesh(oculus, oculus.translated([0, 0, -(self.height - self.rise)]))
        self.steps["22_oculus_mesh"] = self._oculus_mesh
        return self._oculus_mesh

    # ==========================================================================
    # Phase 2: Rotation to All Quarters
    # ==========================================================================

    def rotate_all(self):
        """Rotate all Q1 geometry to create all 4 quarters."""
        # Ensure all Q1 computed
        self._compute_q1_rib_meshes()
        self._compute_q1_tsection_meshes()
        self._compute_q1_surface_meshes()
        self._compute_q1_column_head()
        self._compute_q1_boundary_beams()
        self._compute_oculus_mesh()

        # Rotate ribs
        self._rib_meshes = [self._q1_rib_meshes]
        self._rib_polys = [self._q1_rib_polys]
        for rotation in [1, 2, 3]:
            self._rib_meshes.append(self._rotate_geometry(self._q1_rib_meshes, rotation))
            self._rib_polys.append(self._rotate_geometry(self._q1_rib_polys, rotation))

        # Rotate tsections
        self._tsection_meshes = [self._q1_tsection_meshes]
        for rotation in [1, 2, 3]:
            self._tsection_meshes.append(self._rotate_geometry(self._q1_tsection_meshes, rotation))

        # Rotate surfaces
        self._surface_meshes = [self._q1_surface_meshes]
        self._surface_edge_polylines = [self._q1_surface_edge_polys]
        for rotation in [1, 2, 3]:
            self._surface_meshes.append(self._rotate_geometry(self._q1_surface_meshes, rotation))
            self._surface_edge_polylines.append([self._rotate_geometry(g, rotation) for g in self._q1_surface_edge_polys])

        # Rotate column heads
        self._column_heads = [self._q1_column_head]
        self._column_head_top_blocks = [self._q1_head_top]
        self._column_head_gap_blocks = [self._q1_head_gaps]
        for rotation in [1, 2, 3]:
            self._column_heads.append(self._rotate_geometry(self._q1_column_head, rotation))
            self._column_head_top_blocks.append(self._rotate_geometry(self._q1_head_top, rotation))
            self._column_head_gap_blocks.append(self._rotate_geometry(self._q1_head_gaps, rotation))

        # Rotate boundary beams
        self._boundary_beams = [self._oculus_mesh]
        self._boundary_beams.extend(self._q1_boundary_beams)
        for rotation in [1, 2, 3]:
            self._boundary_beams.extend(self._rotate_geometry(self._q1_boundary_beams, rotation))

        # Edge beams (computed from rotated rib polys)
        self._edge_beams = []
        idx = [[0, 1], [1, 2], [2, 3], [3, 0]]
        for i in range(4):
            pts0 = self._rib_polys[idx[i][0]][1].copy().points[1:-1]
            pts1 = self._rib_polys[idx[i][1]][6].copy().points[1:-1]

            merged = Polyline(pts0 + list(reversed(pts1)))
            merged.points.append(merged.points[0])
            polygon = Polygon(merged.points)
            self._edge_beams.append(PolylineLoft.to_mesh(merged, merged.translated(polygon.normal * self.beam_w)))

        # Record rotation step
        self.steps["23_rotated_rib_meshes"] = self._rib_meshes
        self.steps["24_rotated_tsection_meshes"] = self._tsection_meshes
        self.steps["25_rotated_surface_meshes"] = self._surface_meshes
        self.steps["26_rotated_column_heads"] = self._column_heads
        self.steps["27_rotated_boundary_beams"] = self._boundary_beams
        self.steps["28_edge_beams"] = self._edge_beams

    # ==========================================================================
    # Public Properties (trigger computation)
    # ==========================================================================

    @property
    def rib_meshes(self):
        """Rib beam meshes (all quarters)."""
        if self._rib_meshes is None:
            self.rotate_all()
        return self._rib_meshes

    @property
    def rib_polys(self):
        """Rib polylines (all quarters)."""
        if self._rib_polys is None:
            self.rotate_all()
        return self._rib_polys

    @property
    def tsection_meshes(self):
        """T-section meshes (all quarters)."""
        if self._tsection_meshes is None:
            self.rotate_all()
        return self._tsection_meshes

    @property
    def surface_meshes(self):
        """Surface meshes (all quarters)."""
        if self._surface_meshes is None:
            self.rotate_all()
        return self._surface_meshes

    @property
    def surface_edge_polylines(self):
        """Surface edge polylines (all quarters)."""
        if self._surface_edge_polylines is None:
            self.rotate_all()
        return self._surface_edge_polylines

    @property
    def column_heads(self):
        """Column head meshes (all corners)."""
        if self._column_heads is None:
            self.rotate_all()
        return self._column_heads

    @property
    def element_boundary_beams(self):
        """Boundary beam meshes (oculus + all quarters)."""
        if self._boundary_beams is None:
            self.rotate_all()
        return self._boundary_beams

    @property
    def edge_beam_meshes(self):
        """Edge beam meshes connecting quarters."""
        if self._edge_beams is None:
            self.rotate_all()
        return self._edge_beams

    # ==========================================================================
    # Serialization
    # ==========================================================================

    def save_steps(self, filepath):
        """Save all computation steps to JSON file."""
        json_dump(self.steps, filepath)


# ==========================================================================
# Viewer Script
# ==========================================================================

floor_skeleton = FloorSkeleton()

config = Config()
config.unit = "mm"
viewer = Viewer(config)

# Compute all geometry
_ = floor_skeleton.rib_meshes

# 1) Oculus group
oculus_group = viewer.scene.add_group("oculus")
oculus_group.add(floor_skeleton.element_boundary_beams[0], hide_coplanaredges=True)

# 2) Quarters parent group
quarters_group = viewer.scene.add_group("quarters")
beams_per_quarter = 6
for q in range(4):
    quarter_group = viewer.scene.add_group(f"quarter_{q + 1}", parent=quarters_group)
    ribs_group = viewer.scene.add_group("ribs", parent=quarter_group)
    tsections_group = viewer.scene.add_group("tsections", parent=quarter_group)
    surfaces_group = viewer.scene.add_group("surfaces", parent=quarter_group)
    boundary_group = viewer.scene.add_group("boundary", parent=quarter_group)
    gaps_group = viewer.scene.add_group("rib_gaps", parent=quarter_group)

    for mesh in floor_skeleton.rib_meshes[q]:
        ribs_group.add(mesh, hide_coplanaredges=True)
    for mesh in floor_skeleton.tsection_meshes[q]:
        tsections_group.add(mesh, hide_coplanaredges=True)
    for mesh in floor_skeleton.surface_meshes[q]:
        surfaces_group.add(mesh, hide_coplanaredges=True)

    start_idx = 1 + q * beams_per_quarter
    end_idx = start_idx + beams_per_quarter
    for mesh in floor_skeleton.element_boundary_beams[start_idx:end_idx]:
        boundary_group.add(mesh, hide_coplanaredges=True)

    for gap_block in floor_skeleton._column_head_gap_blocks[q]:
        gaps_group.add(gap_block, hide_coplanaredges=True)

    boundary_group.color = (0.2, 0.4, 0.8)

# 3) Corners parent group
corners_color = (0.5, 0.5, 0.5)
corners_group = viewer.scene.add_group("corners")
for i in range(4):
    corner_group = viewer.scene.add_group(f"corner_{i + 1}", parent=corners_group)
    head_group = viewer.scene.add_group("head", parent=corner_group)
    top_group = viewer.scene.add_group("top", parent=corner_group)

    head_group.add(floor_skeleton.column_heads[i], hide_coplanaredges=True, color=corners_color)
    top_group.add(floor_skeleton._column_head_top_blocks[i], hide_coplanaredges=True, color=corners_color)

# 4) Edge beams
edge_color = (0.9, 0.9, 0.9)
edge_beams_group = viewer.scene.add_group("edge_beams")
for edge_beam in floor_skeleton.edge_beam_meshes:
    edge_beams_group.add(edge_beam, hide_coplanaredges=True, color=edge_color)

viewer.show()
