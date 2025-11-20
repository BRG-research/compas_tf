from compas.geometry import Point, Vector, Line, Polygon, Polyline, Rotation, Scale, Frame, Plane, Transformation, Box
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

    def __init__(self, xy = 3000, z = 600, r = 453, o = 1000, t = 100):
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
        self._par_b = None # Two parabolas at the boundary
        self.t = t # Thickness of the beam elements

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

                line2= Line(corner, p2)
                line3 = Line(corner, p3)

                axes[i].append(line2)
                axes[i].append(line3)


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
                    line = Line(p0,p1)
                    
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


                    extended_axes[i].append(line)
            
            self._axes = extended_axes

        return self._axes

    @property
    def boundary_parabolas(self, divisions = 7):
        # Two boundary parabolas with a step for the column head
        # We skip the first list of axes because it is a key stone


        if self._par_b is None:
            
            self._par_b = []

            for i in range(len(self.axes)):
                if not (i==1 or i==len(self.axes)-1):
                    p0 = self.axes[i][0].start
                    p1 = self.axes[i][0].midpoint
                    p2 = self.axes[i][0].end
                    length = self.axes[i][0].length
                    dir = self.axes[i][0].direction
                    

                    p0 = -Vector(0,0,self.z)+p0
                    p1 = -Vector(0,0,self.s)+p1
                    p2 = -Vector(0,0,self.s)+p2


                    import session_py

                    points = [
                        session_py.Point(p0[0], p0[1], p0[2]),
                        session_py.Point(p1[0], p1[1], p1[2]),
                        session_py.Point(p2[0], p2[1], p2[2]),
                    ]

                    curve = session_py.NurbsCurve.create(periodic=False, degree=len(points)-1, points=points)
                    
                    # Create planes perpendicular to X-axis at regular intervals
                    planes = []
                    step = length / (divisions-1)
                    start_point = points[0]
                    for i in range(divisions):
                        translation = dir*step*i
                        planes.append(session_py.Plane.from_point_normal(translation+start_point, axis_for_plane_intersection))
                    

                    # Intersect curve with each plane
                    sampled_points = []
                    for plane in planes:
                        intersection_points = curve.intersect_plane_points(plane)
                        if intersection_points:
                            sampled_points.append(intersection_points[0])

                    self._par_b.append(Polyline(sampled_points))

        return self._par_b
                    
                
        

        

    @property
    def projected_parabolas(self):
        # These parabolas will be projected to beam long faces
        # Parabolas will be cut second direction beam long faces
        pass

    @property
    def floor_surfaces(self):
        # From projected parabolas we make lofted mesh faces
        # We wound need to offset the outlines too
        pass

    @property
    def tsection(self):
        # Define little beem step to position the floor surfaces
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

viewer.renderer.rendermode = "shaded"  # "lighted", "wireframe", "shaded", "ghosted"

# for point in floor_skeleton.pt:
#     viewer.scene.add(Box(100,100,100, Frame(point=point), name=point.name))

# for point in floor_skeleton.pb:
#     viewer.scene.add(Box(100,100,100, Frame(point=point), name=point.name))


viewer.scene.add(floor_skeleton.mt)
# viewer.scene.add(floor_skeleton.ms)

for lines in floor_skeleton.axes:
    for line in lines:
        if isinstance(line, Line):
            viewer.scene.add(line, color=(255, 0, 0))
        else:
            viewer.scene.add(Polyline(line), color=(0, 255, 0))



# viewer.scene.add(floor.mb)

viewer.show()