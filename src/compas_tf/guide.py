from compas.datastructures import Mesh
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Projection
from compas.geometry import Vector
from compas.geometry import intersection_line_line
from compas.geometry import intersection_line_plane
from compas.geometry import intersection_segment_segment
from compas.geometry import midpoint_point_point
from compas_model.models import Model
from compas_viewer import Viewer
from compas_viewer.config import Config
from shapely import points
from compas_tf.geometry import PlaneIntersect

from compas_tf.geometry import PlaneIntersect
from compas_tf.geometry import PolylineCut
from compas_tf.geometry import PolylineLoft
from compas_tf.geometry import PolylineOffset
from compas import json_dump


class Guide:

    def __init__(self, xy=3000, z=650, r=453, o=1000, t=40, t_panels=40, bb=250):
        self.xy = xy  # Half size of the floor
        self.z = z  # Total height of the floor
        self.r = r  # Rise of the parabola
        self.s = z - r  # Static height above the the parabola
        self.o = o  # Half size of the central oculus from the top to bottom points
        self.bb = bb  # the width of the boundary beams
        self._pt = None  # Top points describind the whole floor
        self._ft = None  # Top points describind the whole floor
        self._pb = None  # Bottom points describind the whole floor
        self._fb = None  # Bottom points describind the whole floor
        self._fs = None  # Bottom points describind the whole floor
        self._mt = None  # Low poly representation of the top mesh for each triangle and quad
        self._ms = None  # Low poly representation of the top mesh for each slab outline
        self._axes = None  # Axes of the floor
        self.bm = 0  # Half of the column head, this is later derived from the parbola points
        self._bp = None  # Two parabolas at the boundary
        self.t = t  # Thickness of the beam elements
        self.t_panels = t_panels  # Thickness of the panel elements
        self._projected_parabolas = None  # Parabolas for each rib quarter (4 lists)
        self._target_planes = None
        self._axis_boundary_planes = None
        self._axis_planes = None
        self._cutplanes = None
        self._end_planes = None
        self._offset_axes = None
        self._lofted_lines = None
        self._boundary_beams = None
        self._column_centers = None  # Cache for column center points

        self.ribs_polylines = []
        self.ribs_tsections = []
        self.surfaces_polylines = []
        self.surfaces_lines = []
        self.surface_edge_polylines = []  # [quarter][surface_idx] = [top_left, bottom_left]
        self.tsection_edge_polylines = []  # [quarter][tsection_idx] = [outer_top, outer_bottom, inner_top, inner_bottom]

        # Mesh storage attributes
        self._rib_meshes = None  # List per quarter: [[mesh, mesh, ...], ...]
        self._tsection_meshes = None  # List per quarter: [[mesh, mesh, ...], ...]
        self._surface_meshes = None  # List per quarter: [[mesh, mesh, ...], ...]
        self._column_head_top_blocks = None
        self._column_head_gap_blocks = None

        self.model = Model()

    @property
    def pt(self):
        if self._pt is None:
            self._pt = [
                # Oculus points
                Point(0, -self.o, 0, name="pt_0"),
                Point(self.o, 0, 0, name="pt_1"),
                Point(0, self.o, 0, name="pt_2"),
                Point(-self.o, 0, 0, name="pt_3"),
                # Perimeter points
                Point(-self.xy, -self.xy, 0, name="pt_4"),
                Point(0, -self.xy, 0, name="pt_5"),
                Point(self.xy, -self.xy, 0, name="pt_6"),
                Point(self.xy, 0, 0, name="pt_7"),
                Point(self.xy, self.xy, 0, name="pt_8"),
                Point(0, self.xy, 0, name="pt_9"),
                Point(-self.xy, self.xy, 0, name="pt_10"),
                Point(-self.xy, 0, 0, name="pt_11"),
            ]

        return self._pt

    @property
    def ft(self):
        if self._ft is None:
            self._ft = [
                # Oculus face
                [0, 1, 2, 3],
                # Quarter 1 faces
                [4, 5, 0],
                [4, 0, 3],
                [4, 3, 11],
                # Quarter 2 faces
                [6, 7, 1],
                [6, 1, 0],
                [6, 0, 5],
                # Quarter 3 faces
                [8, 9, 2],
                [8, 2, 1],
                [8, 1, 7],
                # Quarter 4 faces
                [10, 11, 3],
                [10, 3, 2],
                [10, 2, 9],
            ]
        return self._ft

    @property
    def fs(self):
        if self._fs is None:
            self._fs = [
                # Oculus face
                [0, 1, 2, 3],
                # Quarter 1 faces
                [4, 5, 0, 3, 11],
                # Quarter 2 faces
                [6, 7, 1, 0, 5],
                # Quarter 3 faces
                [8, 9, 2, 1, 7],
                # Quarter 4 faces
                [10, 11, 3, 2, 9],
            ]
        return self._fs

    @property
    def mt(self):
        if self._mt is None:
            self._mt = Mesh.from_vertices_and_faces(self.pt, self.ft)
        return self._mt

    @property
    def ms(self):
        if self._ms is None:
            self._ms = Mesh.from_vertices_and_faces(self.pt, self.fs)
        return self._ms

    @property
    def pb(self):
        if self._pb is None:
            self._pb = [
                # Oculus points
                Point(0, -self.o, -self.s, name="pb_0"),
                Point(self.o, 0, -self.s, name="pb_1"),
                Point(0, self.o, -self.s, name="pb_2"),
                Point(-self.o, 0, -self.s, name="pb_3"),
                # Perimeter points
                Point(-self.xy, -self.xy, -self.z, name="pb_4"),
                Point(0, -self.xy, -self.s, name="pb_5"),
                Point(self.xy, -self.xy, -self.z, name="pb_6"),
                Point(self.xy, 0, -self.s, name="pb_7"),
                Point(self.xy, self.xy, -self.z, name="pb_8"),
                Point(0, self.xy, -self.s, name="pb_9"),
                Point(-self.xy, self.xy, -self.z, name="pb_10"),
                Point(-self.xy, 0, -self.s, name="pb_11"),
                # Mid points Quarter 1-2-3-4
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[4], self.pt[5])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[4], self.pt[0])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[4], self.pt[3])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[4], self.pt[11])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[6], self.pt[7])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[6], self.pt[1])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[6], self.pt[0])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[6], self.pt[5])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[8], self.pt[9])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[8], self.pt[2])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[8], self.pt[1])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[8], self.pt[7])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[10], self.pt[11])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[10], self.pt[3])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[10], self.pt[2])),
                Vector(0, 0, -self.s) + Point(*midpoint_point_point(self.pt[10], self.pt[9])),
            ]

        return self._pb

    @property
    def axes(self):
        if self._axes is None:
            # Central axis to position rectangle beams
            # Beams are mapped to mesh edges
            # Beams have planes at the longest faces

            # Offset polygons to get the axes of the beams

            offset_polygons_full = []
            offset_polygons_half = []
            polygons = self.ms.to_polygons()

            axes = []
            for polygon in polygons:
                offset_polygons_full.append(PolylineOffset.offset_polygon(polygon, self.t))
                offset_polygons_half.append(PolylineOffset.offset_polygon(polygon, self.t * 0.5))
                axes.append(offset_polygons_half[-1].lines)

            # Position diagonal at the offset outline vertices
            for i in range(len(offset_polygons_full)):
                if i == 0:
                    continue

                corner = offset_polygons_half[i].points[0]

                p2 = offset_polygons_full[i].points[2]
                p3 = offset_polygons_full[i].points[3]

                line2 = Line(corner, p2)
                line3 = Line(corner, p3)

                axes[i].insert(1, line2)
                axes[i].insert(2, line3)

            # Extend axes to intersect with the boundary
            extended_axes = []
            for i in range(len(axes)):
                extended_axes.append([])
                for j in range(len(axes[i])):
                    p0 = axes[i][j].start
                    p1 = axes[i][j].end
                    dir = (p1 - p0).unitized()
                    p0 = -dir * self.t * 4 + p0
                    p1 = dir * self.t * 4 + p1
                    line = Line(p1, p0)

                    intersection_points = []

                    for k in range(len(polygons[i])):
                        p0 = polygons[i][k]
                        p1 = polygons[i][(k + 1) % len(polygons[i])]
                        cd = Line(p0, p1)

                        pt = intersection_segment_segment(line, cd)

                        if pt[0] is not None:
                            intersection_points.append(pt[0])

                    if len(intersection_points) != 2:
                        raise Exception("Intersection points not 2", len(intersection_points))

                    line = Line(intersection_points[0], intersection_points[1])

                    # Check orientation
                    cp0, cpt0 = axes[i][j].closest_point(line.start, True)
                    cp1, cpt1 = axes[i][j].closest_point(line.end, True)

                    if cpt0 > cpt1:
                        line = Line(line.end, line.start)

                    extended_axes[i].append(line)

            self._axes = extended_axes

        return self._axes

    @property
    def boundary_parabolas(self):
        # Two boundary parabolas with a step for the column head
        # We skip the first list of axes because it is a key stone

        if self._bp is None:
            divisions = 7
            boundary_parabolas = []

            for i in range(len(self.axes)):
                boundary_parabolas.append([])
                if i == 0:
                    continue

                for j in range(len(self.axes[i])):
                    if j != 0 and j != len(self.axes[i]) - 1:
                        continue
                    elif j == 0:
                        p0 = Vector(0, 0, -self.z) + self.axes[i][j].start
                        p1 = Vector(0, 0, -self.s) + self.axes[i][j].midpoint
                        p2 = Vector(0, 0, -self.s) + self.axes[i][j].end
                        boundary_parabolas[i].append(Polyline([p0, p1, p2]))
                    elif j == len(self.axes[i]) - 1:
                        p0 = Vector(0, 0, -self.s) + self.axes[i][j].start
                        p1 = Vector(0, 0, -self.s) + self.axes[i][j].midpoint
                        p2 = Vector(0, 0, -self.z) + self.axes[i][j].end
                        boundary_parabolas[i].append(Polyline([p0, p1, p2]))

                    # Bezier curve: quadratic Bézier (parabola) formula
                    points = []
                    for k in range(divisions):  # e.g. divisions = 7  ->  7 points, 6 segments
                        t = k / (divisions - 1)  # t in [0, 1]
                        pt = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2
                        points.append(pt)

                    self.bm = abs(points[-2][2]) * 0.5 - 3.5
                    boundary_parabolas[i][-1] = Polyline(points)

            self._bp = boundary_parabolas

        return self._bp

    @property
    def target_planes(self):
        # Target planes for each rib quarter (4 planes per quarter)
        # These are the planes onto which parabolas are projected

        if self._target_planes is not None:
            return self._target_planes

        self._target_planes = []

        for i in range(len(self.boundary_parabolas)):
            if i == 0:
                self._target_planes.append([])  # Empty list for index 0
                continue

            target_plane00 = Plane(self.axes[i][0].start, Vector.Zaxis().cross(self.axes[i][0].direction))
            target_plane10 = Plane(self.axes[i][1].start, Vector.Zaxis().cross(self.axes[i][1].direction))
            target_plane20 = Plane(self.axes[i][2].start, Vector.Zaxis().cross(self.axes[i][2].direction))
            target_plane30 = Plane(self.axes[i][3].start, Vector.Zaxis().cross(self.axes[i][3].direction))
            self._target_planes.append([target_plane00, target_plane10, target_plane20, target_plane30])

        return self._target_planes


guide = Guide()

config = Config()
config.unit = "mm"
viewer = Viewer(config)

viewer.renderer.rendermode = "lighted"  # "lighted", "wireframe", "shaded", "ghosted"

pt = viewer.scene.add_group("pt")
for p in guide.pt:
    pt.add(p, name=p.name)

json_dump(guide.pt, "data/guide_points.json")

dict_serialization = {
    "pt": guide.pt,
    "pb": guide.pb,
    "ms": guide.ms,
    "mt": guide.mt,
    "axes": guide.axes,
    "boundary_parabolas": guide.boundary_parabolas,
    "target_planes": guide.target_planes,
}

pb = viewer.scene.add_group("pb")
for p in guide.pb:
    pb.add(p, name=p.name)

boundary_parabolas = viewer.scene.add_group("boundary_parabolas")
for quarter in guide.boundary_parabolas:
    for idx, polyline in enumerate(quarter):
        boundary_parabolas.add(polyline, name=f"quarter_{guide.boundary_parabolas.index(quarter)}_parabola_{idx}")

target_planes = viewer.scene.add_group("target_planes")
for quarter in guide.target_planes:
    for idx, plane in enumerate(quarter):

        target_planes.add(PlaneIntersect.plane_rectangle(plane)[0], name=f"quarter_{guide.target_planes.index(quarter)}_plane_{idx}")
        target_planes.add(PlaneIntersect.plane_rectangle(plane)[1], name=f"quarter_{guide.target_planes.index(quarter)}_plane_{idx}")

axes = viewer.scene.add_group("axes")
for quarter in guide.axes:
    for idx, line in enumerate(quarter):
        axes.add(line, name=f"quarter_{guide.axes.index(quarter)}_axis_{idx}")

viewer.scene.add(guide.ms, name="ms")
viewer.scene.add(guide.mt, name="mt")


# viewer.show()
