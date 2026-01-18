from dataclasses import dataclass
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Line
from compas.geometry import Projection
from compas.geometry import Transformation
from compas.geometry import Vector
from compas.geometry import Frame
from compas.geometry import intersection_plane_plane_plane
from compas.geometry import intersection_line_line
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import LineOffset
from compas_tf.geometry import PlaneIntersect
from compas_tf.geometry import PolylineCut
from compas_tf.geometry import PolylineLoft
from compas_tf.geometry import PolylineOffset
from compas_tf.joint_screw import ScrewElement
from compas_tf.joint_dowel import DowelElement
from compas_tf.joint_strip import AlignmentStripElement

# ==========================================================================
# Result Container
# ==========================================================================


@dataclass
class QuarterResult:
    """Container for quarter floor build results."""

    rib_elements: list
    rib_polys: list[Polyline]
    tsection_elements: list
    surface_elements: list
    surface_edge_polys: list
    boundary_beam_elements: list
    screws: list
    dowels: list
    strips: list


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
    """Compute rib meshes and polylines for quarter 1 (from slab.py:393-442)."""
    offsets_ids_boundary = [0, 0, 2, 2]  # Front: diagonal ribs (1,2) use planes 0 and 2
    offsets_ids_rib = [0, 1, 1, 2]       # Back: original values
    offset_pairs = [(0.5, -0.5), (0.5, -0.5), (0.5, -0.5), (0.5, -0.5)]
    rib_parabolas = builder.rib_parabolas
    target_planes = builder.target_planes
    cut_planes = builder.cut_planes
    thick = builder.thick
    head_h = builder.head_h

    quarter_meshes = []
    list_rib_polylines = []

    for i in range(len(rib_parabolas)):
        offset0, offset1 = offset_pairs[i]
        # end_plane = cut_planes[1]
        # end_plane = Plane(builder.end_planes[1].point, builder.cut_planes[1].normal).offset(-30)
        end_plane = builder.end_diagonal_plane.offset(-builder.thick)

        cut_boundary = cut_planes[offsets_ids_boundary[i]]
        cut_rib = cut_planes[offsets_ids_rib[i] + 3]

        proj0 = rib_parabolas[i].translated(target_planes[i].normal * thick * offset0)
        proj1 = rib_parabolas[i].translated(target_planes[i].normal * thick * offset1)

        cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj0, cut_rib), cut_boundary)
        cut1 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj1, cut_rib), cut_boundary)

        extension = 378 if i in [0, 3] else 498
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

        quarter_meshes.append(PolylineLoft.to_mesh(joined0, joined1))
        list_rib_polylines.extend([joined0, joined1])

    return quarter_meshes, list_rib_polylines


def _build_tsections(builder, axis_planes, lofted_lines):
    """Compute T-section meshes for quarter 1 (from slab.py:444-485)."""
    lofted_bottom = lofted_lines[0]
    cut_planes = builder.cut_planes
    rib_parabolas = builder.rib_parabolas
    thick = builder.thick

    offsets = [[1], [-1, 1], [-1, 1], [-1]]
    offsets_ids = [[0], [0, 1], [1, 2], [2]]
    quarter_meshes = []

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

    return quarter_meshes


def _build_surfaces(builder, axis_planes, lofted_lines):
    """Compute surface meshes and edge polylines for quarter 1 (from slab.py:487-528)."""
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
    for pair in [surface_edges[i : i + 4] for i in range(0, len(surface_edges), 4)]:
        bl, br, tl, tr = pair[0], pair[1], pair[2], pair[3]
        poly0 = Polyline(bl.points + list(reversed(br.points)))
        poly1 = Polyline(tl.points + list(reversed(tr.points)))
        quarter_meshes.append(PolylineLoft.to_mesh(poly0, poly1))
        quarter_edge_polylines.append([tl, bl, tr, br])

    return quarter_meshes, quarter_edge_polylines


def _build_boundaries(builder, surface_edge_polys):
    """Compute boundary beam meshes for quarter 1 (from slab.py:607-653)."""
    q1 = builder.quarter_polygon
    thick = builder.thick
    height = builder.height
    rise = builder.rise

    poly0 = Polyline([q1[i] for i in [1, 2, 3, 4]])  # edge -> oculus -> oculus -> edge
    poly1 = PolylineOffset.offset_polyline_xy(poly0, thick)
    poly2 = PolylineOffset.offset_polyline_xy(poly0, thick * 1.5)

    meshes = []
    dist = height - rise

    for j in range(len(poly0) - 1):
        # Main beam
        s0 = Polyline([poly0[j], poly0[j + 1], Vector(0, 0, -dist) + poly0[j + 1], Vector(0, 0, -dist) + poly0[j], poly0[j]])
        s1 = Polyline([poly1[j], poly1[j + 1], Vector(0, 0, -dist) + poly1[j + 1], Vector(0, 0, -dist) + poly1[j], poly1[j]])
        meshes.append(PolylineLoft.to_mesh(s0, s1))

        # T-section
        tl, bl, tr, br = surface_edge_polys[j]
        p0off = Plane(tl[-2], -Vector(0, 0, 1).cross(tl.lines[0].direction)).offset(thick)
        p1off = Plane(bl[-2], Vector(0, 0, 1).cross(bl.lines[0].direction)).offset(thick)

        mid0 = (poly1[j] + poly1[j + 1]) * 0.5
        mid1 = (poly2[j] + poly2[j + 1]) * 0.5
        p0 = Plane(mid0, Vector(0, 0, 1).cross(poly1[j + 1] - poly1[j]))
        p1 = Plane(mid1, -Vector(0, 0, 1).cross(poly2[j + 1] - poly2[j]))

        tl = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(tl, p0), p1)
        bl = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(bl, p0), p1)

        s2 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(Polyline([tl[0], bl[0]]), p0off), p1off)
        s3 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(Polyline([tl[1], bl[1]]), p0off), p1off)

        # OPTIONS: for the boundary faces
        # s2 = Polyline([s2[0], s2[1], [s2[1][0], s2[1][1], -dist], [s2[0][0], s2[0][1], -dist], s2[0]])
        # s3 = Polyline([s3[0], s3[1], [s3[1][0], s3[1][1], -dist], [s3[0][0], s3[0][1], -dist], s3[0]])
        # meshes.append(PolylineLoft.to_mesh(s2, s3))

    # Column head boundary
    plane_cut_0 = builder.end_diagonal_plane
    plane_cut_1 = builder.end_diagonal_plane.offset(-builder.thick)
    plane0 = Plane.worldXY()
    plane1 = Plane(builder.axes[0].midpoint, Vector.Zaxis().cross(builder.axes[0].direction)).offset(-builder.thick*0.5)
    plane2 = Plane.worldXY().offset(-builder.head_h)
    plane3 = Plane(builder.axes[-1].midpoint, Vector.Zaxis().cross(builder.axes[-1].direction)).offset(-builder.thick*0.5)
    result0 = Polyline(PlaneIntersect.intersect_consecutive_planes([plane0, plane1, plane2, plane3, plane0, plane1], plane_cut_0))
    result1 = Polyline(PlaneIntersect.intersect_consecutive_planes([plane0, plane1, plane2, plane3, plane0, plane1], plane_cut_1))

    meshes.append(PolylineLoft.to_mesh(result0, result1))


    return meshes




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
    
    def _build_screw_lines(self, builder) -> tuple[list[ScrewElement], list[DowelElement]]:
        """Build screw and dowel elements for quarter floor connections.

        Returns
        -------
        tuple[list[ScrewElement], list[DowelElement]]
            Lists of screw and dowel elements.
        """

        def _line_to_screw(line: Line) -> ScrewElement:
            plane = Plane(line.start, line.direction)
            xform = Transformation.from_frame(Frame.from_plane(plane))
            return ScrewElement(8, 25, line.length, transformation=xform)

        def _line_to_dowel(line: Line) -> DowelElement:
            plane = Plane(line.start, line.direction)
            xform = Transformation.from_frame(Frame.from_plane(plane))
            return DowelElement(20, 20, line.length, transformation=xform)
        
        def _line_to_strip(frame: Line, height) -> AlignmentStripElement:
            frame = Frame(frame.start, Vector.Zaxis().cross(frame.direction), frame.direction)
            xform = Transformation.from_frame(frame)
            return AlignmentStripElement(height=height, transformation=xform)

        screws = []
        dowels = []
        strips = []

        height_offset = 20
        divisions = 4
        height0 = (builder.height-builder.rise-height_offset*2) / (divisions-1)
        height1 = (builder.head_h-height_offset*2) / (divisions*2-1)
        height_middle = (builder.height-builder.rise) * 0.5

        # Corner screws - 0 and 2 axis (boundary ribs)
        axis_pairs_02 = [(3, 0), (3, 1), (5, 6), (5, 2)]
        for offset_axis, intersect_axis in axis_pairs_02:
            line = LineOffset.offset_intersect(builder.axes[offset_axis], builder.axes[intersect_axis], builder.thick * 0.5)
            for j in range(0, divisions):
                if j % 2 == 0:
                    continue
                translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height0 * j)
                screws.append(_line_to_screw(translated_line))


        # Strips
        axis_pairs_strips = [(3, 4), (4, 5)]
        for offset_axis, intersect_axis in axis_pairs_strips:
            strip_point = Point(*intersection_line_line(builder.axes[offset_axis], builder.axes[intersect_axis])[0])   
            strip_line = Line(strip_point, strip_point + builder.axes[offset_axis].direction+ builder.axes[intersect_axis].direction).translated(Vector.Zaxis() * -height_middle)
            strips.append(_line_to_strip(strip_line, height_middle*2))

        axis_pairs_strips = [(0,3), (6, 5),(1,3), (2,5)]
        for offset_axis, intersect_axis in axis_pairs_strips:
            intersect_axis = LineOffset.offset_xy(builder.axes[intersect_axis],builder.thick*-0.5)
            strip_point = Point(*intersection_line_line(builder.axes[offset_axis], intersect_axis)[0])
            
            strip_line = Line(strip_point, strip_point + builder.axes[offset_axis].direction).translated(Vector.Zaxis() * -height_middle*0.5)
            strips.append(_line_to_strip(strip_line, height_middle*2))


        axis_corner = Line(builder.end_diagonal_plane.point, builder.end_diagonal_plane.point + Vector.Zaxis().cross(builder.end_diagonal_plane.normal))
        axes = [0, 6, 1, 2]
        for axis in axes:
            intersect_axis = LineOffset.offset_xy(axis_corner,builder.thick*-1)
            strip_point = Point(*intersection_line_line(builder.axes[axis], intersect_axis)[0])
            
            strip_line = Line(strip_point, strip_point + builder.axes[axis].direction).translated(Vector.Zaxis() * -builder.head_h*0.5)
            strips.append(_line_to_strip(strip_line, builder.head_h))




        # Corner screws - 1 axis (diagonal)
        axis_pairs_1 = [(3, 4), (5, 4)]
        for offset_axis, intersect_axis in axis_pairs_1:
            line = LineOffset.offset_intersect(builder.axes[offset_axis], builder.axes[intersect_axis], builder.thick * 0.5)
            for j in range(0, divisions):
                if j % 2 == 1:
                    continue
                translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height0 * j)
                screws.append(_line_to_screw(translated_line))


        # Back corner
        rib_axes = [0, 1, 2, 6]
        for i in rib_axes:
            axis_plane = Plane(builder.axes[i].midpoint, Vector.Zaxis().cross(builder.axes[i].direction))
            p0 = intersection_plane_plane_plane(axis_plane, builder.end_diagonal_plane, Plane.worldXY())
            p1 = intersection_plane_plane_plane(axis_plane, builder.end_diagonal_plane.offset(-builder.thick * 0.5), Plane.worldXY())
            line = Line(p0, p1)

            if i == 0 or i == 6:
                for j in range(divisions * 2):
                    if j % 2 == 0:
                        continue
                    translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height1 * j)
                    screws.append(_line_to_screw(translated_line))
            else:
                for j in range(divisions * 2):
                    if j % 2 == 1:
                        continue
                    translated_line = line.translated(-Vector.Zaxis() * height_offset - Vector.Zaxis() * height1 * j)
                    screws.append(_line_to_screw(translated_line))

        # Connectors
        divisions = [12, 8, 12]

        for i in range(3):
            line = Line(builder.quarter_polygon[1 + i], builder.quarter_polygon[2 + i])
            direction = Vector.Zaxis().cross(line.direction).unitized() * builder.thick

            if i == 2:
                line = Line(line.end, line.start)
            points = LineOffset.divide(line, divisions[i])

            for idx, pt in enumerate(points):
                if idx == 0 or idx == len(points) - 1:
                    continue

                p_start = pt + direction - height_middle * Vector.Zaxis()
                p_end = pt + direction * 0 - height_middle * Vector.Zaxis()
                connector_line = Line(p_start, p_end)

                if idx % 3 == 1:
                    dowels.append(_line_to_dowel(connector_line))
                else:
                    screws.append(_line_to_screw(connector_line))

        return screws, dowels, strips

    @staticmethod
    def build(builder) -> QuarterResult:
        """Build quarter floor geometry from FloorBuilder.

        Parameters
        ----------
        builder : FloorBuilder
            The floor builder containing base geometry parameters.

        Returns
        -------
        QuarterResult
            Container with rib_elements, rib_polys, tsection_elements,
            surface_elements, surface_edge_polys, boundary_beam_elements.
        """
        # Compute internal helper geometry (only used by quarter floor)
        axis_planes = _compute_axis_planes(builder)
        offset_axes = _compute_offset_axes(builder)
        lofted_lines = _compute_lofted_lines(builder, offset_axes)

        # Build components
        rib_meshes, rib_polys = _build_ribs(builder)
        tsection_meshes = _build_tsections(builder, axis_planes, lofted_lines)
        surface_meshes, surface_edge_polys = _build_surfaces(builder, axis_planes, lofted_lines)
        boundary_beam_meshes = _build_boundaries(builder, surface_edge_polys)

        # Screws and connectors
        screws, dowels, strips = QuarterFloorElement()._build_screw_lines(builder)

        # Wrap meshes in elements
        rib_elements = [QuarterFloorElement(mesh=m, name=f"rib_{i}") for i, m in enumerate(rib_meshes)]
        tsection_elements = [QuarterFloorElement(mesh=m, name=f"tsection_{i}") for i, m in enumerate(tsection_meshes)]
        surface_elements = [QuarterFloorElement(mesh=m, name=f"surface_{i}") for i, m in enumerate(surface_meshes)]
        boundary_beam_elements = [QuarterFloorElement(mesh=m, name=f"boundary_{i}") for i, m in enumerate(boundary_beam_meshes)]

        return QuarterResult(
            rib_elements=rib_elements,
            rib_polys=rib_polys,
            tsection_elements=tsection_elements,
            surface_elements=surface_elements,
            surface_edge_polys=surface_edge_polys,
            boundary_beam_elements=boundary_beam_elements,
            screws=screws,
            dowels=dowels,
            strips=strips
        )
