from compas.geometry import Point, Vector, Line, Polygon, Polyline, Rotation, Scale, Frame, Plane, Transformation, Box, Projection
from compas.datastructures import Mesh
from compas.geometry import intersection_line_line, intersection_line_plane, intersection_plane_plane_plane, midpoint_point_point, intersection_segment_polyline, intersection_segment_segment
import math
from compas_viewer import Viewer
from compas_viewer.config import Config
from session_py.intersection import line_plane
from compas_tf.beam import BeamElement
from compas_tf.plate import PlateElement
from compas_tf.slicer import SliceElement
from compas_tf.solid import Solid
from compas_tf.slicemodifier import SliceModifier
from compas_tf.solid_difference_modifier import SolidDifferenceModifier
from compas_model.models import Model
from compas.itertools import pairwise

class FloorSkeleton:
    """
    [ ] - Create points representing the low poly geometry of the floor.
    [ ] - Create mesh
    [ ] - Create Beam elements and and map them to edges
    [ ] - From face representation extract beam long planes
    [ ] - Create parabolas for cuts
    [ ] - From parabolas make extrusion lines that later will cross by mesh face beam plaes
    
    """

    def __init__(self, xy = 3000, z = 600, r = 453, o = 1000, t = 40, t_panels = 27):
        self.xy = xy # Half size of the floor
        self.z = z # Total height of the floor
        self.r = r # Rise of the parabola
        self.s = z-r # Static height above the the parabola
        self.o = o # Half size of the central oculus from the top to bottom points
        self._pt = None # Top points describind the whole floor
        self._ft = None # Top points describind the whole floor
        self._pb = None # Bottom points describind the whole floor
        self._fb = None # Bottom points describind the whole floor
        self._fs = None # Bottom points describind the whole floor
        self._mt = None # Low poly representation of the top mesh for each triangle and quad
        self._ms = None # Low poly representation of the top mesh for each slab outline
        self._axes = None # Axes of the floor
        self._bp = None # Two parabolas at the boundary
        self.t = t # Thickness of the beam elements
        self.t_panels = t_panels # Thickness of the panel elements

        self.ribs_polylines = []
        self.ribs_tsections = []
        self.surfaces_polylines = []
        self.temp = []

        self.model = Model() # Model with discrete elements



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

    def offset_polygon(self, polygon, distance, baseplane = Plane.worldXY()):

        planes = []
        for l in Polygon(polygon).lines:
            zaxis = Vector.Zaxis().cross(l.direction)
            zaxis.unitize()
            planes.append(Plane(zaxis*distance+l.midpoint, zaxis))

        points = []
        for i in range(len(planes)):
            a = planes[(len(planes)+i-1)%len(planes)]
            b = planes[i]
            c = baseplane
            result = intersection_plane_plane_plane(a,b,c)
            if not result:
                raise Exception("No intersection at offset_polygon. Index: ", i)
            points.append(result)

        polygon = Polygon(points)
        return polygon


    def offset_polyline(self, polyline, distance, baseplane = Plane.worldXY()):

        # End planes
        start_plane = Plane(polyline[0], polyline[1]- polyline[0])
        end_plane = Plane(polyline[-1], polyline[-2]- polyline[-1])
        
        # Planes for intersection
        planes = [start_plane]
        for line in polyline.lines:
            xaxis = line.direction
            yaxis = Vector.Zaxis().cross(xaxis)
            zaxis = xaxis.cross(yaxis)

            planes.append(Plane(line.midpoint, zaxis).offset(distance))
        planes.append(end_plane)

        # Base plane
        baseplane = Plane(polyline[0], Vector.Zaxis().cross(polyline[-1]-polyline[0]))

        # Perform offset by plane intersection
        points = []
        for i in range(len(planes)-1):
            a = planes[i]
            b = planes[(i+1)]
            c = baseplane
            result = intersection_plane_plane_plane(a,b,c)
            if not result:
                raise Exception("No intersection at offset_polygon. Index: ", i)
            points.append(result)

        offset_polyline = Polyline(points)
        return offset_polyline            

    @property
    def axes(self):

        if self._axes is None:
           
            # Central axis to position recangle beams
            # Beams are mapped to mesh edges
            # Beams have planes at the longest faces

            # Offset polygons to get the axes of the beams

            offset_polygons_full = []
            offset_polygons_half = []
            polygons = self.ms.to_polygons()

            axes = []
            for polygon in polygons:
                offset_polygons_full.append(self.offset_polygon(polygon, self.t))
                offset_polygons_half.append(self.offset_polygon(polygon, self.t*0.5))
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

                    # print(cpt0, cpt1)
                    if cpt0 > cpt1:
                        line = Line(line.end, line.start)


                    extended_axes[i].append(line)
            
            self._axes = extended_axes
            # self._axes = axes

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

                    boundary_parabolas[i][-1] = Polyline(points)

            self._bp = boundary_parabolas

        return self._bp 

    def average_polyline(self, polyline0, polyline1):

        points = []
        for i in range(len(polyline0)):
            points.append((polyline0[i] + polyline1[i]) / 2)
        
        return Polyline(points)

    def loft_polylines(self, polyline0, polyline1):
        vertices = polyline0.points + polyline1.points
        faces = []
        for i in range(len(polyline0)-1):
            faces.append([i, i+1, i+len(polyline0)+1, i+len(polyline0)])
        return Mesh.from_vertices_and_faces(vertices, faces)

    @property
    def projected_parabolas(self):
        # These parabolas will be projected to beam long faces
        # Parabolas will be cut second direction beam long faces

        projected_parabolas = []
        projected_parabolas_offset = []


        for i in range(len(self.boundary_parabolas)):
            if i == 0:
                continue

            # 4 Axis planes
            axis_planes = []
            for j in range(len(self.axes[i])):
                axis_planes.append(Plane(self.axes[i][j].start,  Vector.Zaxis().cross(self.axes[i][j].direction)))

            # 8 Surface planes, stored 2n pairs
            surface_planes_a = []
            surface_planes_b = []
            step_planes_a = []
            step_planes_b = []
            for j in range(len(self.axes[i])):
                surface_planes_a.append(Plane(self.axes[i][j].start,  Vector.Zaxis().cross(self.axes[i][j].direction)).offset(self.t*0.5))
                surface_planes_b.append(Plane(self.axes[i][j].start,  Vector.Zaxis().cross(self.axes[i][j].direction)).offset(-self.t*0.5))
                step_planes_a.append(Plane(self.axes[i][j].start,  Vector.Zaxis().cross(self.axes[i][j].direction)).offset(self.t*1.0))
                step_planes_b.append(Plane(self.axes[i][j].start,  Vector.Zaxis().cross(self.axes[i][j].direction)).offset(-self.t*1.0))

            # Projection vectors, for the three inner triangles
            # Usage_ xform = Projection.from_plane_and_direction(target_plane, projection_direction0)
            projection_direction0 = Vector.Zaxis().cross(self.axes[i][0].direction)
            projection_direction1 = Vector.Zaxis().cross(self.axes[i][1].direction) + Vector.Zaxis().cross(self.axes[i][2].direction)
            projection_direction3 = Vector.Zaxis().cross(self.axes[i][3].direction)



            # Projected parabolas
            target_plane00 = Plane(self.axes[i][0].start,  Vector.Zaxis().cross(self.axes[i][0].direction))
            target_plane10 = Plane(self.axes[i][1].start,  Vector.Zaxis().cross(self.axes[i][1].direction))
            target_plane20 = Plane(self.axes[i][2].start,  Vector.Zaxis().cross(self.axes[i][2].direction))
            target_plane30 = Plane(self.axes[i][3].start,  Vector.Zaxis().cross(self.axes[i][3].direction))
            target_planes = [target_plane00, target_plane10, target_plane20, target_plane30]
            
            target_plane11 = target_plane10.offset(-self.t*0.5)
            target_plane21 = target_plane20.offset(self.t*0.5)

            xform10 = Projection.from_plane_and_direction(target_plane11, projection_direction0)
            xform20 = Projection.from_plane_and_direction(target_plane21, projection_direction3)
            xform11 = Projection.from_plane(target_plane10)
            xform21 = Projection.from_plane(target_plane20)

            # Axis parabolas
            boundary_parabola0 = self.boundary_parabolas[i][0]
            boundary_parabola1 = self.boundary_parabolas[i][0].transformed(xform10)
            boundary_parabola2 = self.boundary_parabolas[i][1].transformed(xform20)
            
            boundary_parabola1.translate(target_plane11.normal * self.t*0.5)
            boundary_parabola2.translate(target_plane21.normal * -self.t*0.5)
            boundary_parabola3 = self.boundary_parabolas[i][1]
            boundary_parabola2.points.reverse()
            boundary_parabola3.points.reverse()

            current_projected_parabolas = [boundary_parabola0, boundary_parabola1, boundary_parabola2, boundary_parabola3]
            projected_parabolas += current_projected_parabolas


            # Beams - translation to two sides
            beams = []

            for i in range(len(current_projected_parabolas)):
                projected_parabola_0 = current_projected_parabolas[i].translated(target_planes[i].normal * self.t*0.5)
                projected_parabola_1 = current_projected_parabolas[i].translated(target_planes[i].normal * -self.t*0.5)
                self.ribs_polylines.append(projected_parabola_0)
                self.ribs_polylines.append(projected_parabola_1)
                mesh = self.loft_polylines(projected_parabola_0, projected_parabola_1)
                self.temp.append(mesh)
            
            idx = len(self.ribs_polylines) - 1 - 7
            self.temp.append(self.loft_polylines(self.ribs_polylines[idx+0], self.ribs_polylines[idx+3]))
            self.temp.append(self.loft_polylines(self.ribs_polylines[idx+2], self.ribs_polylines[idx+5]))
            self.temp.append(self.loft_polylines(self.ribs_polylines[idx+4], self.ribs_polylines[idx+6]))


            # T-section - bottom translation to two sides, top projection from one side

            # Surface * projection from one side

            # Cut all the bottom profiles the 3 boundary beams
            # Meaning the two inner beams are cut by one and the same plane



        print(len(projected_parabolas))
        return projected_parabolas

    @property
    def floor_surfaces_polylines(self):
        # From projected parabolas we make lofted mesh faces
        # We wound need to offset the outlines too
        pass

    @property
    def tsection(self):
        # Define little beem step to position the floor surfaces_polylines
        pass

    @property
    def column_heads(self):
        # Column heads are the intersection of the projected parabolas
        pass



floor_skeleton = FloorSkeleton()
floor_skeleton.axes


config = Config()
config.unit = "mm"
viewer = Viewer(config)

viewer.renderer.rendermode = "wireframe"  # "lighted", "wireframe", "shaded", "ghosted"

# for point in floor_skeleton.pt:
#     viewer.scene.add(Box(100,100,100, Frame(point=point), name=point.name))

# for point in floor_skeleton.pb:
#     viewer.scene.add(Box(100,100,100, Frame(point=point), name=point.name))

geometry = viewer.scene.add_group("geometry")

geometry.add(floor_skeleton.mt)
# viewer.scene.add(floor_skeleton.ms)

for lines in floor_skeleton.axes:
    for line in lines:
        if isinstance(line, Line):
            geometry.add(line, color=(255, 0, 0))
        else:
            geometry.add(Polyline(line), color=(0, 255, 0))


for parabola in floor_skeleton.boundary_parabolas:
    for polyline in parabola:
        geometry.add(polyline, color=(0, 0, 255))

floor_skeleton.projected_parabolas

rib_polylines = viewer.scene.add_group("rib_polylines")
ribs_tsections = viewer.scene.add_group("ribs_tsections")
surfaces_polylines = viewer.scene.add_group("surfaces_polylines")
temp = viewer.scene.add_group("temp")

for polyline in floor_skeleton.ribs_polylines:
    rib_polylines.add(polyline)

for polyline in floor_skeleton.ribs_tsections:
    ribs_tsections.add(polyline)

for polyline in floor_skeleton.surfaces_polylines:
    surfaces_polylines.add(polyline)

for mesh in floor_skeleton.temp:
    temp.add(mesh)



# viewer.scene.add(floor.mb)

viewer.show()