from compas.geometry import Point, Vector, Line, Polygon, Polyline, Plane, Projection
from compas.datastructures import Mesh
from compas.geometry import intersection_line_line, intersection_line_plane, midpoint_point_point, intersection_segment_segment
from compas_viewer import Viewer
from compas_viewer.config import Config
from compas_model.models import Model
from compas_tf.geometry import PolylineOffset, PolylineCut, PolylineLoft, PlaneIntersect


class FloorSkeleton:

    def __init__(self, xy = 3000, z = 650, r = 453, o = 1000, t = 40, t_panels = 40, bb = 250):
        self.xy = xy # Half size of the floor
        self.z = z # Total height of the floor
        self.r = r # Rise of the parabola
        self.s = z-r # Static height above the the parabola
        self.o = o # Half size of the central oculus from the top to bottom points
        self.bb = bb # the width of the boundary beams
        self._pt = None # Top points describind the whole floor
        self._ft = None # Top points describind the whole floor
        self._pb = None # Bottom points describind the whole floor
        self._fb = None # Bottom points describind the whole floor
        self._fs = None # Bottom points describind the whole floor
        self._mt = None # Low poly representation of the top mesh for each triangle and quad
        self._ms = None # Low poly representation of the top mesh for each slab outline
        self._axes = None # Axes of the floor
        self.bm = 0 # Half of the column head, this is later derived from the parbola points
        self._bp = None # Two parabolas at the boundary
        self.t = t # Thickness of the beam elements
        self.t_panels = t_panels # Thickness of the panel elements
        self._projected_parabolas = None # Parabolas for each rib quarter (4 lists)
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
                [0,1,2,3],
                # Quarter 1 faces
                [4,5,0],
                [4,0,3],
                [4,3,11],
                # Quarter 2 faces
                [6,7,1],
                [6,1,0],
                [6,0,5],
                # Quarter 3 faces
                [8,9,2],
                [8,2,1],
                [8,1,7],
                # Quarter 4 faces
                [10,11,3],
                [10,3,2],
                [10,2,9],
            ]
        return self._ft

    @property
    def fs(self):
        if self._fs is None:
            self._fs = [
                # Oculus face
                [0,1,2,3],
                # Quarter 1 faces
                [4,5,0,3,11],
                # Quarter 2 faces
                [6,7,1,0,5],
                # Quarter 3 faces
                [8,9,2,1,7],
                # Quarter 4 faces
                [10,11,3,2,9]
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
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[4], self.pt[5])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[4], self.pt[0])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[4], self.pt[3])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[4], self.pt[11])),

                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[6], self.pt[7])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[6], self.pt[1])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[6], self.pt[0])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[6], self.pt[5])),

                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[8], self.pt[9])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[8], self.pt[2])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[8], self.pt[1])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[8], self.pt[7])),

                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[10], self.pt[11])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[10], self.pt[3])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[10], self.pt[2])),
                Vector(0,0,-self.s)+Point(*midpoint_point_point(self.pt[10], self.pt[9])), 
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
                offset_polygons_half.append(PolylineOffset.offset_polygon(polygon, self.t*0.5))
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

                axes[i].insert(1,line2)
                axes[i].insert(2,line3)


            # Extend axes to intersect with the boundary
            extended_axes = []
            for i in range(len(axes)):
                extended_axes.append([])
                for j in range(len(axes[i])):

                    p0 = axes[i][j].start
                    p1 = axes[i][j].end
                    dir = (p1-p0).unitized()
                    p0 = -dir*self.t*4+p0
                    p1 = dir*self.t*4+p1
                    line = Line(p1,p0)
                    
                    intersection_points = []

                    for k in range(len(polygons[i])):
                        p0 = polygons[i][k]
                        p1 = polygons[i][(k+1)%len(polygons[i])]
                        cd = Line(p0,p1)
                        
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

                    if j != 0 and j != len(self.axes[i])-1:
                        continue
                    elif j == 0:
                        p0 = Vector(0,0,-self.z) + self.axes[i][j].start
                        p1 = Vector(0,0,-self.s) + self.axes[i][j].midpoint
                        p2 = Vector(0,0,-self.s) + self.axes[i][j].end
                        boundary_parabolas[i].append(Polyline([p0,p1,p2]))
                    elif j == len(self.axes[i])-1:
                        p0 = Vector(0,0,-self.s) + self.axes[i][j].start
                        p1 = Vector(0,0,-self.s) + self.axes[i][j].midpoint
                        p2 = Vector(0,0,-self.z) + self.axes[i][j].end
                        boundary_parabolas[i].append(Polyline([p0,p1,p2]))

                    # Bezier curve: quadratic Bézier (parabola) formula 
                    points = []
                    for k in range(divisions):          # e.g. divisions = 7  ->  7 points, 6 segments
                        t = k / (divisions - 1)         # t in [0, 1]
                        pt = (1 - t)**2 * p0 + 2*(1 - t)*t * p1 + t**2 * p2
                        points.append(pt)

                    self.bm = abs(points[-2][2])*0.5  -3.5
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

            target_plane00 = Plane(self.axes[i][0].start,  Vector.Zaxis().cross(self.axes[i][0].direction))
            target_plane10 = Plane(self.axes[i][1].start,  Vector.Zaxis().cross(self.axes[i][1].direction))
            target_plane20 = Plane(self.axes[i][2].start,  Vector.Zaxis().cross(self.axes[i][2].direction))
            target_plane30 = Plane(self.axes[i][3].start,  Vector.Zaxis().cross(self.axes[i][3].direction))
            self._target_planes.append([target_plane00, target_plane10, target_plane20, target_plane30])

        return self._target_planes

    @property
    def axis_boundary_planes(self):
        # 3 Axis boundary planes per quarter

        if self._axis_boundary_planes is not None:
            return self._axis_boundary_planes

        self._axis_boundary_planes = []

        for i in range(len(self.boundary_parabolas)):
            if i == 0:
                self._axis_boundary_planes.append([])  # Empty list for index 0
                continue

            planes = []
            for j in range(3, len(self.axes[i])-1):
                planes.append(Plane(self.axes[i][j].midpoint,  Vector.Zaxis().cross(self.axes[i][j].direction)))
            self._axis_boundary_planes.append(planes)

        return self._axis_boundary_planes

    @property
    def axis_planes(self):
        # 4 Axis planes per quarter

        if self._axis_planes is not None:
            return self._axis_planes

        self._axis_planes = []

        for i in range(len(self.boundary_parabolas)):
            if i == 0:
                self._axis_planes.append([])  # Empty list for index 0
                continue

            planes = []
            for j in range(3):
                planes.append(Plane(self.axes[i][j].start,  Vector.Zaxis().cross(self.axes[i][j].direction)))
            planes.append(Plane(self.axes[i][-1].start,  -Vector.Zaxis().cross(self.axes[i][-1].direction)))
            self._axis_planes.append(planes)

        return self._axis_planes

    @property
    def rib_parabolas(self):
        # These parabolas will be projected to beam long faces
        # Parabolas will be cut second direction beam long faces

        if self._projected_parabolas is not None:
            return self._projected_parabolas

        self._projected_parabolas = []

        for i in range(len(self.boundary_parabolas)):
            if i == 0:
                self._projected_parabolas.append([])  # Empty list for index 0
                continue

            # Projection vectors, for the three inner triangles
            projection_direction0 = Vector.Zaxis().cross(self.axes[i][0].direction)
            projection_direction3 = Vector.Zaxis().cross(self.axes[i][3].direction)

            # Get target planes for this quarter
            current_target_planes = self.target_planes[i]
            target_plane10 = current_target_planes[1]
            target_plane20 = current_target_planes[2]

            target_plane11 = target_plane10.offset(-self.t*0.5)
            target_plane21 = target_plane20.offset(self.t*0.5)

            xform10 = Projection.from_plane_and_direction(target_plane11, projection_direction0)
            xform20 = Projection.from_plane_and_direction(target_plane21, projection_direction3)



            boundary_parabola1 = self.boundary_parabolas[i][0].transformed(xform10)
            boundary_parabola2 = self.boundary_parabolas[i][1].transformed(xform20)

            # Axis parabolas
            boundary_parabola0 = self.boundary_parabolas[i][0]
            boundary_parabola3 = self.boundary_parabolas[i][1]
            boundary_parabola2.points.reverse()
            boundary_parabola3.points.reverse()

            current_projected_parabolas = [boundary_parabola0, boundary_parabola1, boundary_parabola2, boundary_parabola3]
            self._projected_parabolas.append(current_projected_parabolas)



        return self._projected_parabolas

    def _compute_corner_geometry(self, q):
        """Compute corner geometry data for cut planes and column heads.
        
        Returns:
            tuple: (points_for_planes, points_for_planes_offset, planes)
        """
        # Find intersection of first and last axes
        intersection = intersection_line_line(self.axes[q][0], self.axes[q][-1])[0]
        
        # Build 4 planes along the axes
        scale = 460
        angle_inclination = 180
        points = []
        planes = []
        for i in range(4):
            direction = self.axes[q][i].direction * scale + intersection
            point = Point(*direction)
            points.append(point)
            plane = Plane(point, self.axes[q][i].direction.cross(Vector.Zaxis()))
            offset_dir = self.t * -0.5 if i > 1 else self.t * 0.5
            plane = plane.offset(offset_dir)
            planes.append(plane)

        # Compute 4 key points for cut planes
        middle_line = Line(points[1], points[2])
        point1 = Point(*intersection_line_plane(middle_line, planes[1]))
        point2 = Point(*intersection_line_plane(middle_line, planes[2]))
        point0 = planes[0].closest_point(point1)
        point3 = planes[3].closest_point(point2)

        points_for_planes = [point0, point1, point2, point3]
        
        # Compute offset points along axis directions
        points_for_planes_offset = []
        for i in range(4):
            temp_pt = self.axes[q][i].direction * angle_inclination + points_for_planes[i]
            points_for_planes_offset.append(temp_pt)
        points_for_planes_offset[0] = planes[0].closest_point(points_for_planes_offset[1])
        points_for_planes_offset[3] = planes[3].closest_point(points_for_planes_offset[2])
        for i in range(4):
            points_for_planes_offset[i] = -Vector.Zaxis() * self.z + points_for_planes_offset[i]

        return points_for_planes, points_for_planes_offset, planes

    @property
    def cut_planes(self):
        if self._cutplanes is not None:
            return self._cutplanes

        # Cut the polylines using planes axis_boundary_planes
        self._cutplanes = []
        for q in range(len(self.axis_boundary_planes)):
            if q == 0:
                self._cutplanes.append([])  # Empty list for index 0
                continue

            l = []
            for plane in self.axis_boundary_planes[q]:
                l.append(plane.offset(self.t * 0.5))
            self._cutplanes.append(l)

        for q in range(len(self.axis_boundary_planes)):
            if q == 0:
                continue

            points_for_planes, points_for_planes_offset, planes = self._compute_corner_geometry(q)

            # Create 3 cut planes from the 4 points
            plane0 = Plane((points_for_planes[0] + points_for_planes[1]) * 0.5, -(points_for_planes[1] - points_for_planes[0]).cross(points_for_planes_offset[0] - points_for_planes[0]))
            plane1 = Plane((points_for_planes[1] + points_for_planes[2]) * 0.5, -(points_for_planes[2] - points_for_planes[1]).cross(points_for_planes_offset[1] - points_for_planes[1]))
            plane2 = Plane((points_for_planes[2] + points_for_planes[3]) * 0.5, -(points_for_planes[3] - points_for_planes[2]).cross(points_for_planes_offset[2] - points_for_planes[2]))

            self._cutplanes[q].append(plane0)
            self._cutplanes[q].append(plane1)
            self._cutplanes[q].append(plane2)

        return self._cutplanes

    @property
    def end_planes(self):
        """End planes for each rib, used for cutting beams and column heads.
        
        Returns:
            list: Nested list [q][i] where q is quarter index and i is rib index (0-3)
        """
        if self._end_planes is not None:
            return self._end_planes
        
        self._end_planes = [[]]  # Empty list for index 0
        
        for q in range(1, len(self.axis_boundary_planes)):
            quarter_planes = []
            for i in range(4):
                normal = Point(self.rib_parabolas[q][i][0][0], self.rib_parabolas[q][i][0][1], 0) - Point(self.rib_parabolas[q][i][-1][0], self.rib_parabolas[q][i][-1][1], 0)
                plane = Plane(Point(self.rib_parabolas[q][i][0][0], self.rib_parabolas[q][i][0][1], 0), normal)
                end_plane = plane.offset(-200)
                quarter_planes.append(end_plane)
            self._end_planes.append(quarter_planes)
        
        return self._end_planes

    @property
    def column_heads(self):
        """Generate column head geometry for each corner.
        
        Returns main column head meshes. Also populates:
        - _column_head_top_blocks: Top block meshes per corner
        - _column_head_gap_blocks: Gap block meshes per corner (3 per corner)
        """
        if not hasattr(self, '_column_heads') or self._column_heads is None:
            self._column_heads = []
            self._column_centers = []  # Store center points for columns
            self._column_head_top_blocks = []
            self._column_head_gap_blocks = []
            
            for q in range(len(self.axis_boundary_planes)):
                if q == 0:
                    continue

                points_for_planes, points_for_planes_offset, planes = self._compute_corner_geometry(q)

                # Create lines from the loft and cut them with the plane 
                plane_top = Plane([0, 0, -self.bm], Vector.Zaxis())
                plane_bottom = Plane([0, 0, -self.bm * 2], Vector.Zaxis())
                top_points = []
                bottom_points = []
                for i in range(4):
                    line = Line(points_for_planes[i], points_for_planes_offset[i])
                    result = intersection_line_plane(line, plane_top)
                    if result:
                        top_points.append(Point(*result))
                    result = intersection_line_plane(line, plane_bottom)
                    if result:
                        bottom_points.append(Point(*result))
                corner = self.pt[self.fs[q][0]]

                
                polyline_top = Polyline(top_points).extended([self.bb, self.bb])
                gap_blocks_polyline_front = Polyline(polyline_top.points)
                polyline_bottom = Polyline(bottom_points).extended([self.bb, self.bb])
                direction = -polyline_top.lines[0].direction * self.bb + polyline_bottom.lines[-1].direction * self.bb
                corner = direction + corner
                polyline_top.append(Vector(0, 0, -self.bm) + corner)
                polyline_bottom.append(Vector(0, 0, -self.bm * 2) + corner)
                polyline_top.points = polyline_top.points[-1:] + polyline_top.points[:-1]
                polyline_bottom.points = polyline_bottom.points[-1:] + polyline_bottom.points[:-1]
                polyline_top.append(polyline_top[0])
                polyline_bottom.append(polyline_bottom[0])
                polyline_taper = polyline_bottom.translated(Vector(0, 0, -(self.z - self.bm * 2)))
                xaxis = polyline_taper.lines[0].direction * self.bb
                yaxis = polyline_taper.lines[-1].direction * self.bb
                center = polyline_taper[0]
                # Cache actual center of square (not corner) for element_columns
                square_center = center + xaxis * 0.5 - yaxis * 0.5
                self._column_centers.append(square_center)
                polyline_taper = Polyline([
                    center,
                    center + xaxis,
                    center + xaxis - yaxis * 0.99,
                    center + xaxis * 0.99 - yaxis,
                    center - yaxis,
                    center,
                ])
                
                column_head_mesh = PolylineLoft.multiple_to_mesh([polyline_top, polyline_bottom, polyline_taper])
                self._column_heads.append(column_head_mesh)

                # Top part of column to take the tension
               
                stop_plane0 = Plane(self.pt[self.fs[q][0]], Vector.Zaxis().cross(self.pt[self.fs[q][1]] - self.pt[self.fs[q][0]]))
                stop_plane1 = Plane(self.pt[self.fs[q][0]], Vector.Zaxis().cross(self.pt[self.fs[q][-1]] - self.pt[self.fs[q][0]]))
                planes = [
                    stop_plane0,
                    self.end_planes[q][0],
                    self.end_planes[q][1],
                    self.end_planes[q][2],
                    self.end_planes[q][3],
                    stop_plane1,
                    ]
                ipoints =  PlaneIntersect.intersect_consecutive_planes(planes)

                top_block_polyline0 = Polyline(ipoints)
                gap_blocks_polyline = Polyline(ipoints)
                top_block_polyline0.extend((self.bb, self.bb))
                top_block_polyline0.insert(0, Point(center[0], center[1], 0))
                top_block_polyline0.append(top_block_polyline0[0])
                top_block_polyline1 = top_block_polyline0.translated(Vector(0, 0, -self.bm))

                # Store top block mesh
                top_block_mesh = PolylineLoft.to_mesh(top_block_polyline0, top_block_polyline1)
                self._column_head_top_blocks.append(top_block_mesh)

                # Diagonals blocks (gap blocks)
                corner_gap_blocks = []
                ids = [[0,2], [3, 5], [4,7]]
                for i in range(3):

                    a = ids[i][0]
                    b = ids[i][1]

                    cutplane0 = Polygon(list(reversed(self.ribs_polylines[q-1][a].points[:-1]))).plane
                    cutplane1 = Polygon(self.ribs_polylines[q-1][b].points[:-1]).plane

                    points = []

                    polyline = PolylineCut.cut_by_plane(gap_blocks_polyline, cutplane0)
                    polyline = PolylineCut.cut_by_plane(polyline, cutplane1)

                    for p in polyline:
                        points.append(Point(p[0],p[1],0))

                    polyline = PolylineCut.cut_by_plane(gap_blocks_polyline_front, cutplane0)
                    polyline = PolylineCut.cut_by_plane(polyline, cutplane1)

                    for p in list(reversed(polyline)):
                        points.append(Point(p[0],p[1],0))
                    
                    polygon0 = Polygon(points)
                    polygon1 = polygon0.translated(Vector(0, 0, -self.bm))
                    gap_block_mesh = PolylineLoft.to_mesh(Polyline(polygon0.points), Polyline(polygon1.points))
                    corner_gap_blocks.append(gap_block_mesh)

                self._column_head_gap_blocks.append(corner_gap_blocks)

        return self._column_heads

    @property
    def lofted_lines_from_parabolas(self):
        lofted_lines = []

        for q in range(len(self.boundary_parabolas)):
            if q == 0:
                continue
            lofted_lines_0 = PolylineLoft.to_lines(self.rib_parabolas[q][0], self.rib_parabolas[q][1])
            lofted_lines_1 = PolylineLoft.to_lines(self.rib_parabolas[q][1], self.rib_parabolas[q][2])
            lofted_lines_2 = PolylineLoft.to_lines(self.rib_parabolas[q][2], self.rib_parabolas[q][3])
            lofted_lines.append(lofted_lines_0)
            lofted_lines.append(lofted_lines_1)
            lofted_lines.append(lofted_lines_2)
        
        return lofted_lines

    @property
    def offset_axes(self):
        # Offset axes for surface lofting - cached per quarter

        if self._offset_axes is not None:
            return self._offset_axes

        self._offset_axes = []

        for q in range(len(self.boundary_parabolas)):
            if q == 0:
                self._offset_axes.append([])
                continue

            # Offset polylines 0 and 3
            offset_0_bottom = PolylineOffset.offset_polyline(self.rib_parabolas[q][0], self.t)
            offset_0_top = PolylineOffset.offset_polyline(self.rib_parabolas[q][0], self.t*2)
            offset_3_bottom = PolylineOffset.offset_polyline(self.rib_parabolas[q][3], self.t)
            offset_3_top = PolylineOffset.offset_polyline(self.rib_parabolas[q][3], self.t*2)

            # Get projection parameters
            current_target_planes = self.target_planes[q]
            target_plane10 = current_target_planes[1]
            target_plane20 = current_target_planes[2]

            projection_direction0 = Vector.Zaxis().cross(self.axes[q][0].direction)
            projection_direction3 = Vector.Zaxis().cross(self.axes[q][3].direction)

            xform10 = Projection.from_plane_and_direction(target_plane10, projection_direction0)
            xform20 = Projection.from_plane_and_direction(target_plane20, projection_direction3)

            # Project polylines 1 and 2 from 0 and 3
            offset_1_bottom = offset_0_bottom.transformed(xform10)
            offset_1_top = offset_0_top.transformed(xform10)
            offset_2_bottom = offset_3_bottom.transformed(xform20)
            offset_2_top = offset_3_top.transformed(xform20)

            quarter_offset_axes = [
                [offset_0_bottom, offset_0_top],
                [offset_1_bottom, offset_1_top],
                [offset_2_bottom, offset_2_top],
                [offset_3_bottom, offset_3_top]
            ]
            self._offset_axes.append(quarter_offset_axes)

        return self._offset_axes

    @property
    def lofted_lines(self):
        # Lofted lines between offset axes - cached per quarter
        # Returns list of [lofted_lines_bottom, lofted_lines_top] per quarter

        if self._lofted_lines is not None:
            return self._lofted_lines

        self._lofted_lines = []

        for q in range(len(self.boundary_parabolas)):
            if q == 0:
                self._lofted_lines.append([[], []])
                continue

            offset_axes = self.offset_axes[q]
            lofted_lines_bottom = []
            lofted_lines_top = []

            for i in range(len(self.rib_parabolas[q])-1):
                lofted_lines_0 = PolylineLoft.to_lines(offset_axes[i][0], offset_axes[i+1][0])
                lofted_lines_1 = PolylineLoft.to_lines(offset_axes[i][1], offset_axes[i+1][1])
                lofted_lines_bottom.append(lofted_lines_0)
                lofted_lines_top.append(lofted_lines_1)

            self._lofted_lines.append([lofted_lines_bottom, lofted_lines_top])

        return self._lofted_lines

    @property
    def rib_meshes(self):
        """Rib beam meshes per quarter.
        
        Returns:
            list: Nested list [quarter_idx][rib_idx] of meshes (4 ribs per quarter, 4 quarters)
        """
        if self._rib_meshes is None:
            self._rib_meshes = [[]]  # Empty list for index 0
            
            for q in range(len(self.boundary_parabolas)):
                if q == 0:
                    continue

                offsets_ids = [0, 1, 1, 2]
                list_rib_polylines = []
                quarter_meshes = []

                for i in range(len(self.rib_parabolas[q])):

                    offset0 = 0.0
                    offset1 = 0.0

                    if i == 0:
                        offset0 = 0.5
                        offset1 = -0.5
                    elif i == 1:
                        offset0 = 0.0
                        offset1 = 1.0
                    elif i == 2:
                        offset0 = 0.0
                        offset1 = -1.0
                    elif i == 3:
                        offset0 = 0.5
                        offset1 = -0.5

                    end_plane = self.end_planes[q][i]

                    projected_parabola_0 = self.rib_parabolas[q][i].translated(self.target_planes[q][i].normal * self.t*offset0)
                    projected_parabola_1 = self.rib_parabolas[q][i].translated(self.target_planes[q][i].normal * self.t*offset1)

                    current_cut_planes = self.cut_planes[q]
                    cut_plane_boundary = current_cut_planes[offsets_ids[i]]  # indices 0, 1, 2
                    cut_plane_rib = current_cut_planes[offsets_ids[i] + 3]   # indices 3, 4, 5

                    cut_parabola0 = PolylineCut.cut_by_plane(projected_parabola_0, cut_plane_rib, flip=False)
                    cut_parabola1 = PolylineCut.cut_by_plane(projected_parabola_1, cut_plane_rib, flip=False)
                    cut_parabola0 = PolylineCut.cut_by_plane(cut_parabola0, cut_plane_boundary, flip=False)
                    cut_parabola1 = PolylineCut.cut_by_plane(cut_parabola1, cut_plane_boundary, flip=False)



                    # Project polylines to xy planes
                    line0 = Polyline([cut_parabola0[0], cut_parabola0[-1]])
                    line1 = Polyline([cut_parabola1[0], cut_parabola1[-1]])
                    extension = 378 if i == 0 or i == 3 else 450
                    
                    line0.extend([extension,0])
                    line1.extend([extension,0])
                    line0 = PolylineCut.cut_by_plane(line0, end_plane, flip=True)
                    line1 = PolylineCut.cut_by_plane(line1, end_plane, flip=True)

                    top_parabola0 = line0.transformed(Projection.from_plane_and_direction(Plane.worldXY(), Vector.Zaxis()))
                    top_parabola1 = line1.transformed(Projection.from_plane_and_direction(Plane.worldXY(), Vector.Zaxis()))
                    mid_parabola0 = line0.transformed(Projection.from_plane_and_direction(Plane([0,0,-self.bm], [0,0,1]), Vector.Zaxis()))
                    mid_parabola1 = line1.transformed(Projection.from_plane_and_direction(Plane([0,0,-self.bm], [0,0,1]), Vector.Zaxis()))
                    mid_parabola0 = PolylineCut.cut_by_plane(mid_parabola0, cut_plane_rib, flip=True)
                    mid_parabola1 = PolylineCut.cut_by_plane(mid_parabola1, cut_plane_rib, flip=True)
                    
                    joined_parabola0 = Polyline(list(reversed(top_parabola0.points)) + mid_parabola0.points + cut_parabola0.points)
                    joined_parabola1 = Polyline(list(reversed(top_parabola1.points)) + mid_parabola1.points + cut_parabola1.points)
                    joined_parabola0.append(joined_parabola0.points[0])
                    joined_parabola1.append(joined_parabola1.points[0])

                    

                    rib_mesh = PolylineLoft.to_mesh(joined_parabola0, joined_parabola1)
                    quarter_meshes.append(rib_mesh)

                    list_rib_polylines.append(joined_parabola0)
                    list_rib_polylines.append(joined_parabola1)

                self.ribs_polylines.append(list_rib_polylines)
                self._rib_meshes.append(quarter_meshes)

        return self._rib_meshes

    @property
    def tsection_meshes(self):
        """T-section meshes per quarter.
        
        Returns:
            list: Nested list [quarter_idx][tsection_idx] of meshes (6 T-sections per quarter)
        """
        if self._tsection_meshes is None:
            self._tsection_meshes = [[]]  # Empty list for index 0
            self.tsection_edge_polylines = [[]]  # Empty list for index 0

            for q in range(len(self.boundary_parabolas)):
                if q == 0:
                    continue

                lofted_lines_bottom = self.lofted_lines[q][0]
                current_cut_planes = self.cut_planes[q]

                offsets = [[1], [-1, 1], [-1, 1], [-1]]
                offsets_ids = [[0], [0, 1], [1, 2], [2]]
                quarter_meshes = []
                quarter_tsection_polylines = []

                for i in range(len(self.rib_parabolas[q])):
                    for j in range(len(offsets[i])):

                        # Create planes first, then project rib_parabolas onto them
                        plane0 = Plane(self.axis_planes[q][i].point + self.axis_planes[q][i].normal * self.t*0.5 * offsets[i][j], self.axis_planes[q][i].normal)
                        plane1 = Plane(self.axis_planes[q][i].point + self.axis_planes[q][i].normal * self.t*1.5 * offsets[i][j], self.axis_planes[q][i].normal)

                        # Project rib_parabola points onto plane0 and plane1 (along plane normal)
                        projected_points_0 = []
                        projected_points_1 = []
                        for pt in self.rib_parabolas[q][i].points:
                            projected_points_0.append(plane0.closest_point(pt))
                            projected_points_1.append(plane1.closest_point(pt))
                        projected_parabola_0 = Polyline(projected_points_0)
                        projected_parabola_1 = Polyline(projected_points_1)

                        cut_parabola0 = PolylineCut.cut_lines_by_plane(lofted_lines_bottom[offsets_ids[i][j]], plane0)
                        cut_parabola1 = PolylineCut.cut_lines_by_plane(lofted_lines_bottom[offsets_ids[i][j]], plane1)

                        # Cut planes
                        cut_plane_boundary = current_cut_planes[offsets_ids[i][j]]  # indices 0, 1, 2
                        cut_plane_rib = current_cut_planes[offsets_ids[i][j] + 3]   # indices 3, 4, 5
                        
                        # Cut at boundary end (flip=False)
                        projected_parabola_0 = PolylineCut.cut_by_plane(projected_parabola_0, cut_plane_boundary, flip=False)
                        projected_parabola_1 = PolylineCut.cut_by_plane(projected_parabola_1, cut_plane_boundary, flip=False)
                        cut_parabola0 = PolylineCut.cut_by_plane(cut_parabola0, cut_plane_boundary, flip=False)
                        cut_parabola1 = PolylineCut.cut_by_plane(cut_parabola1, cut_plane_boundary, flip=False)
                        
                        # Cut at rib end
                        projected_parabola_0 = PolylineCut.cut_by_plane(projected_parabola_0, cut_plane_rib, flip=False)
                        projected_parabola_1 = PolylineCut.cut_by_plane(projected_parabola_1, cut_plane_rib, flip=False)
                        cut_parabola0 = PolylineCut.cut_by_plane(cut_parabola0, cut_plane_rib, flip=False)
                        cut_parabola1 = PolylineCut.cut_by_plane(cut_parabola1, cut_plane_rib, flip=False)

                        merged_polyline0 = Polyline(projected_parabola_0.points + list(reversed(cut_parabola0.points)))
                        merged_polyline1 = Polyline(projected_parabola_1.points + list(reversed(cut_parabola1.points)))
                        tsection_mesh = PolylineLoft.to_mesh(merged_polyline0, merged_polyline1, True)
                        quarter_meshes.append(tsection_mesh)

                        self.ribs_tsections.append(projected_parabola_0)
                        self.ribs_tsections.append(projected_parabola_1)
                        self.ribs_tsections.append(cut_parabola0)
                        self.ribs_tsections.append(cut_parabola1)
                        quarter_tsection_polylines.append([projected_parabola_0, cut_parabola0, projected_parabola_1, cut_parabola1])

                self._tsection_meshes.append(quarter_meshes)
                self.tsection_edge_polylines.append(quarter_tsection_polylines)

        return self._tsection_meshes

    @property
    def surface_meshes(self):
        """Surface meshes per quarter.
        
        Returns:
            list: Nested list [quarter_idx][surface_idx] of meshes (3 surfaces per quarter)
        """
        if self._surface_meshes is None:
            self._surface_meshes = [[]]  # Empty list for index 0
            self.surface_edge_polylines = [[]]  # Empty list for index 0

            for q in range(len(self.boundary_parabolas)):
                if q == 0:
                    continue

                lofted_lines_bottom = self.lofted_lines[q][0]
                lofted_lines_top = self.lofted_lines[q][1]
                current_cut_planes = self.cut_planes[q]

                offsets = [[1], [-1, 1], [-1, 1], [-1]]
                offsets_ids = [[0], [0, 1], [1, 2], [2]]

                surface_edges = []
                for i in range(len(self.rib_parabolas[q])):
                    for j in range(len(offsets[i])):

                        plane0 = Plane(self.axis_planes[q][i].point + self.axis_planes[q][i].normal * self.t*0.5 * offsets[i][j], self.axis_planes[q][i].normal)

                        cut_parabola0 = PolylineCut.cut_lines_by_plane(lofted_lines_bottom[offsets_ids[i][j]], plane0)
                        cut_parabola1 = PolylineCut.cut_lines_by_plane(lofted_lines_top[offsets_ids[i][j]], plane0)

                        # Cut planes
                        cut_plane_boundary = current_cut_planes[offsets_ids[i][j]]  # indices 0, 1, 2
                        cut_plane_rib = current_cut_planes[offsets_ids[i][j] + 3]   # indices 3, 4, 5

                        # Cut at boundary end
                        cut_parabola0 = PolylineCut.cut_by_plane(cut_parabola0, cut_plane_boundary, flip=False)
                        cut_parabola1 = PolylineCut.cut_by_plane(cut_parabola1, cut_plane_boundary, flip=False)

                        # Cut at rib end
                        cut_parabola0 = PolylineCut.cut_by_plane(cut_parabola0, cut_plane_rib, flip=False)
                        cut_parabola1 = PolylineCut.cut_by_plane(cut_parabola1, cut_plane_rib, flip=False)

                        self.surfaces_polylines.append(cut_parabola0)
                        self.surfaces_polylines.append(cut_parabola1)

                        surface_edges.extend([cut_parabola0, cut_parabola1])

                surface_pairs = [surface_edges[i:i+4] for i in range(0, len(surface_edges), 4)]
                quarter_meshes = []
                quarter_edge_polylines = []
                for idx, pair in enumerate(surface_pairs):

                    polyline_bottom_left = pair[0]
                    polyline_bottom_right = pair[1]
                    polyline_top_left = pair[2]
                    polyline_top_right = pair[3]

                    polyline0 = Polyline(polyline_bottom_left.points + list(reversed(polyline_bottom_right.points)))
                    polyline1 = Polyline(polyline_top_left.points + list(reversed(polyline_top_right.points)))

                    surface_mesh = PolylineLoft.to_mesh(polyline0, polyline1)
                    quarter_edge_polylines.append([polyline_top_left, polyline_bottom_left, polyline_top_right, polyline_bottom_right])
                    quarter_meshes.append(surface_mesh)

                self._surface_meshes.append(quarter_meshes)
                self.surface_edge_polylines.append(quarter_edge_polylines)

        return self._surface_meshes

    @property
    def element_boundary_beams(self):
        # Ensure dependencies are computed first
        _ = self.surface_meshes  # populates surface_edge_polylines
        _ = self.tsection_meshes  # populates tsection_edge_polylines

        if self._boundary_beams is None:
            self._boundary_beams = []

            for i in range(len(self.fs)):

                if i == 0:

                    side0 = Polyline([self.pt[self.fs[i][0]],self.pt[self.fs[i][1]],self.pt[self.fs[i][2]],self.pt[self.fs[i][3]], self.pt[self.fs[i][0]]])
                    side1 = side0.translated([0,0,-(self.z-self.r)])
                    mesh = PolylineLoft.to_mesh(side0, side1)
                    self._boundary_beams.append(mesh)

                else:

                    polyline0 = Polyline([self.pt[self.fs[i][1]],self.pt[self.fs[i][2]],self.pt[self.fs[i][3]], self.pt[self.fs[i][4]]])
                    polyline1 = PolylineOffset.offset_polyline_xy(polyline0, self.t)
                    polyline2 = PolylineOffset.offset_polyline_xy(polyline0, self.t * 1.5)

                    distance = self.z-self.r
                    for j in range(len(polyline0)-1):
                        side0 = Polyline([polyline0[j], polyline0[j+1], Vector(0,0,-distance)+polyline0[j+1], Vector(0,0,-distance)+polyline0[j], polyline0[j]])
                        side1 = Polyline([polyline1[j], polyline1[j+1], Vector(0,0,-distance)+polyline1[j+1], Vector(0,0,-distance)+polyline1[j], polyline1[j]])
                        mesh = PolylineLoft.to_mesh(side0, side1)
                        self._boundary_beams.append(mesh)

                        # t-section
                        top_left, bottom_left, top_right, bottom_right = self.surface_edge_polylines[i][j]
                        plane0offset = Plane(top_left[-2], -Vector(0, 0, 1).cross(top_left.lines[0].direction)).offset(self.t)
                        plane1offset = Plane(bottom_left[-2], Vector(0, 0, 1).cross(bottom_left.lines[0].direction)).offset(self.t)

                        side2 = Polyline([polyline1[j], polyline1[j + 1]])
                        side3 = Polyline([polyline2[j], polyline2[j + 1]])
                        p0 = (polyline1[j] + polyline1[j + 1]) * 0.5
                        p1 = (polyline2[j] + polyline2[j + 1]) * 0.5
                        plane0 = Plane(p0, Vector(0, 0, 1).cross(polyline1[j + 1] - polyline1[j]))
                        plane1 = Plane(p1, -Vector(0, 0, 1).cross(polyline2[j + 1] - polyline2[j]))

                        top_left = PolylineCut.cut_by_plane(top_left, plane0)
                        top_left = PolylineCut.cut_by_plane(top_left, plane1)
                        bottom_left = PolylineCut.cut_by_plane(bottom_left, plane0)
                        bottom_left = PolylineCut.cut_by_plane(bottom_left, plane1)
                        side2 = Polyline([top_left[0], bottom_left[0]])
                        side3 = Polyline([top_left[1], bottom_left[1]])

                        side2 = PolylineCut.cut_by_plane(side2, plane0offset)
                        side2 = PolylineCut.cut_by_plane(side2, plane1offset)
                        side3 = PolylineCut.cut_by_plane(side3, plane0offset)
                        side3 = PolylineCut.cut_by_plane(side3, plane1offset)
                        side2 = Polyline([side2[0], side2[1], [side2[1][0], side2[1][1], -(self.z-self.r)], [side2[0][0], side2[0][1], -(self.z-self.r)], side2[0]])
                        side3 = Polyline([side3[0], side3[1], [side3[1][0], side3[1][1], -(self.z-self.r)], [side3[0][0], side3[0][1], -(self.z-self.r)], side3[0]])
                        mesh = PolylineLoft.to_mesh(side2, side3)
                        self._boundary_beams.append(mesh)                   

        return self._boundary_beams

    @property
    def edge_beam_meshes(self):
        """Edge beam meshes connecting quarters.
        
        Returns:
            list: 4 edge beam meshes
        """
        if not hasattr(self, '_edge_beam_meshes') or self._edge_beam_meshes is None:
            self._edge_beam_meshes = []
            idx = [[0, 1], [1, 2], [2, 3], [3, 0]]
            idy = [[1, 6], [1, 6], [1, 6], [1, 6]]

            for i in range(4):
                a0 = idx[i][0]
                b0 = idy[i][0]
                a1 = idx[i][1]
                b1 = idy[i][1]

                polyline0 = self.ribs_polylines[a0][b0].copy().points[1:-1] 
                polyline1 = self.ribs_polylines[a1][b1].copy().points[1:-1] 

                merged0 = Polyline(polyline0 + list(reversed(polyline1)))
                merged0.points.append(merged0.points[0])
                polygon = Polygon(merged0.points)
                merged1 = merged0.translated(polygon.normal*self.bb)
                edge_beam_mesh = PolylineLoft.to_mesh(merged0, merged1)
                self._edge_beam_meshes.append(edge_beam_mesh)

        return self._edge_beam_meshes



floor_skeleton = FloorSkeleton()

config = Config()
config.unit = "mm"
viewer = Viewer(config)

viewer.renderer.rendermode = "lighted"  # "lighted", "wireframe", "shaded", "ghosted"

# Create viewer groups for organized display

# b) Boundary beams and edge beams
boundary_beams_group = viewer.scene.add_group("boundary_beams")
edge_beams_group = viewer.scene.add_group("edge_beams")

# c) Column heads with all parts
column_heads_main = viewer.scene.add_group("column_heads_main")
column_heads_top_blocks = viewer.scene.add_group("column_heads_top_blocks")
column_heads_gap_blocks = viewer.scene.add_group("column_heads_gap_blocks")

# d) Quarter slabs - create groups for each quarter
quarter_1_ribs = viewer.scene.add_group("quarter_1_ribs")
quarter_1_tsections = viewer.scene.add_group("quarter_1_tsections")
quarter_1_surfaces = viewer.scene.add_group("quarter_1_surfaces")

quarter_2_ribs = viewer.scene.add_group("quarter_2_ribs")
quarter_2_tsections = viewer.scene.add_group("quarter_2_tsections")
quarter_2_surfaces = viewer.scene.add_group("quarter_2_surfaces")

quarter_3_ribs = viewer.scene.add_group("quarter_3_ribs")
quarter_3_tsections = viewer.scene.add_group("quarter_3_tsections")
quarter_3_surfaces = viewer.scene.add_group("quarter_3_surfaces")

quarter_4_ribs = viewer.scene.add_group("quarter_4_ribs")
quarter_4_tsections = viewer.scene.add_group("quarter_4_tsections")
quarter_4_surfaces = viewer.scene.add_group("quarter_4_surfaces")

quarter_groups = [
    None,  # index 0 unused
    (quarter_1_ribs, quarter_1_tsections, quarter_1_surfaces),
    (quarter_2_ribs, quarter_2_tsections, quarter_2_surfaces),
    (quarter_3_ribs, quarter_3_tsections, quarter_3_surfaces),
    (quarter_4_ribs, quarter_4_tsections, quarter_4_surfaces),
]

# First compute rib_meshes (populates ribs_polylines needed by column_heads)
_ = floor_skeleton.rib_meshes

# Add boundary beams
print(f"Number of boundary beams: {len(floor_skeleton.element_boundary_beams)}")
for beam in floor_skeleton.element_boundary_beams:
    boundary_beams_group.add(beam, hide_coplanaredges=True)

# Add edge beams
print(f"Number of edge beams: {len(floor_skeleton.edge_beam_meshes)}")
for edge_beam in floor_skeleton.edge_beam_meshes:
    edge_beams_group.add(edge_beam, hide_coplanaredges=True)

# Add column heads with all parts
for column_head in floor_skeleton.column_heads:
    column_heads_main.add(column_head, hide_coplanaredges=True)

for top_block in floor_skeleton._column_head_top_blocks:
    column_heads_top_blocks.add(top_block, hide_coplanaredges=True)

for corner_gap_blocks in floor_skeleton._column_head_gap_blocks:
    for gap_block in corner_gap_blocks:
        column_heads_gap_blocks.add(gap_block, hide_coplanaredges=True)

# Add quarter slabs with ribs, T-sections, surfaces
for q in range(1, 5):
    ribs_group, tsections_group, surfaces_group = quarter_groups[q]

    for rib_mesh in floor_skeleton.rib_meshes[q]:
        ribs_group.add(rib_mesh, hide_coplanaredges=True)

    for tsection_mesh in floor_skeleton.tsection_meshes[q]:
        tsections_group.add(tsection_mesh, hide_coplanaredges=True)

    for surface_mesh in floor_skeleton.surface_meshes[q]:
        surfaces_group.add(surface_mesh, hide_coplanaredges=True)

viewer.show()