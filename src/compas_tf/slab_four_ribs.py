from compas.geometry import Point, Vector, Line, Polygon, Polyline, Rotation, Scale, Frame, Plane, Transformation, Box
from compas.datastructures import Mesh
from compas.geometry import intersection_line_line, intersection_line_plane, intersection_plane_plane_plane, 
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


class SlabFourRibs:

    def __init__(self, xysize = 6000, zsize = 600, rise = 453, oculus_size = 2000):
        self.xysize = xysize
        self.zsize = zsize
        self.rise = rise
        self.oculus_size = oculus_size
        self._points = None
        self._oculus_lines = None
        
        self.parabolas = None
        self.planes = None
        self.offset_polylines = []

        self._boundary_lines = None
        self._ribs_lines = None
        
        self.model = Model()

    @property
    def points(self):

        if self._points is None:
            # Oculus square
            length = self.oculus_size*0.5
            p0 = Point(0+self.half_xysize, -length+self.half_xysize, 0)
            p1 = Point(length+self.half_xysize, 0+self.half_xysize, 0)
            p2 = Point(0+self.half_xysize, length+self.half_xysize, 0)
            p3 = Point(-length+self.half_xysize, 0+self.half_xysize, 0)

            # Bottom left quarter
            p4 = Point(0, 0, 0)
            p5 = Point(self.half_xysize, 0, 0)
            p6 = Point(0, self.half_xysize, 0)

            # Parabola points
            p7 = Point(0, 0, -self.rise)
            p8 = Point(self.half_xysize*0.5, 0, -self.zsize+self.rise)
            p9 = Point(self.half_xysize, 0, -self.zsize+self.rise)

            self._points = [p0, p1, p2, p3, p4, p5, p6, p7, p8, p9]

        return self._points

        # Key geometrical attributes
        


    @property
    def half_xysize(self):
        return self.xysize * 0.5

    @property
    def points(self):

        if self._points is None:
            # Oculus square
            length = self.oculus_size*0.5
            p0 = Point(0+self.half_xysize, -length+self.half_xysize, 0)
            p1 = Point(length+self.half_xysize, 0+self.half_xysize, 0)
            p2 = Point(0+self.half_xysize, length+self.half_xysize, 0)
            p3 = Point(-length+self.half_xysize, 0+self.half_xysize, 0)

            # Bottom left quarter
            p4 = Point(0, 0, 0)
            p5 = Point(self.half_xysize, 0, 0)
            p6 = Point(0, self.half_xysize, 0)

            # Parabola points
            p7 = Point(0, 0, -self.rise)
            p8 = Point(self.half_xysize*0.5, 0, -self.zsize+self.rise)
            p9 = Point(self.half_xysize, 0, -self.zsize+self.rise)

            self._points = [p0, p1, p2, p3, p4, p5, p6, p7, p8, p9]

        return self._points

    def set_point(self, point, index):
        self._points[index] = point

    @property
    def oculus_lines(self):
        if self._oculus_lines is None:
            self._oculus_lines = [
            Line(self.points[0], self.points[1]), 
            Line(self.points[1], self.points[2]), 
            Line(self.points[2], self.points[3]), 
            Line(self.points[3], self.points[0])
        ]
        

        return self._oculus_lines

    @property
    def ribs_lines(self):
        if self._ribs_lines is None:
            self._ribs_lines = [
            Line(self.points[4], self.points[5]), 
            Line(self.points[4], self.points[6]), 
            Line(self.points[4], self.points[0]), 
            Line(self.points[4], self.points[3])
        ]
        
        return self._ribs_lines

    def set_rib_line(self, line, index):
        self._ribs_lines[index] = line

    @property
    def boundary_lines(self):
        if self._boundary_lines is None:
            self._boundary_lines = [
            Line(self.points[5], self.points[0]), 
            Line(self.points[0], self.points[3]), 
            Line(self.points[3], self.points[6]), 
        ]
        
        return self._boundary_lines

    def get_boundary_beams(self, thickness =100, shorten_ribs = 300):

        zaxis = Vector(0,0,1)
        
        # Offset boundary lines inwards
        line0 = Line(self.points[5], self.points[0])
        line1 = Line(self.points[0], self.points[3])
        line2 = Line(self.points[3], self.points[6])

        # Translate half-way to get the axes
        axis0 = line0.translated(zaxis.cross(line0.direction).unitized() * thickness*0.5 - Vector(0,0,(self.zsize-self.rise)*0.5))
        axis1 = line1.translated(zaxis.cross(line1.direction).unitized() * thickness*0.5 - Vector(0,0,(self.zsize-self.rise)*0.5))
        axis2 = line2.translated(zaxis.cross(line2.direction).unitized() * thickness*0.5 - Vector(0,0,(self.zsize-self.rise)*0.5))

        # Transformations
        frame0 = Frame(axis0.start, -axis0.direction.cross(zaxis), zaxis)
        frame1 = Frame(axis1.start, -axis1.direction.cross(zaxis), zaxis)
        frame2 = Frame(axis2.start, -axis2.direction.cross(zaxis), zaxis)

        # Create beams
        beam0 = BeamElement(width=thickness, depth=self.zsize-self.rise, length=line0.length, transformation=Transformation.from_frame(frame0))
        beam1 = BeamElement(width=thickness, depth=self.zsize-self.rise, length=line1.length, transformation=Transformation.from_frame(frame1))
        beam2 = BeamElement(width=thickness, depth=self.zsize-self.rise, length=line2.length, transformation=Transformation.from_frame(frame2))



        # Perform line-line intersection to get axes points
        # These intersection points will be end points for the ribs too
        lines0 = beam0.get_long_lines()
        lines1 = beam1.get_long_lines()
        lines2 = beam2.get_long_lines()

        line0=lines0[0]
        line1=lines1[0]
        line2=lines2[0]

        line0_offset=lines0[1]
        line1_offset=lines1[1]
        line2_offset=lines2[1]
        lines_offset = [line0_offset, line1_offset, line2_offset]


        p0, _ = intersection_line_line(line0, line1)
        p1, _ = intersection_line_line(line1, line2)

        p0_offset, _ = intersection_line_line(line0_offset, line1_offset)
        p1_offset, _ = intersection_line_line(line1_offset, line2_offset)

        x_axis1 = Point(*p0)-Point(*p0_offset)
        x_axis2 = Point(*p1)-Point(*p1_offset)

        frame0= Frame(p0_offset, x_axis1, zaxis)
        frame1= Frame(p1_offset, x_axis2, zaxis)


        beam0.extend(100)
        beam1.extend(100)
        beam2.extend(100)

        self.model.add_element(beam0)
        self.model.add_element(beam1)
        self.model.add_element(beam2)


        frame00 = Frame(line0.start, [1,0,0], zaxis)
        frame01 = Frame(p0_offset, x_axis1, zaxis)
        frame10 = Frame(p0_offset, -x_axis1, zaxis)
        frame11 = Frame(p1_offset, x_axis2, zaxis)
        frame20 = Frame(p1_offset, -x_axis2, zaxis)
        frame21 = Frame(line2.end, [0,-1,0], zaxis)
        
        slice00 = SliceElement(transformation=Transformation.from_frame(frame00))
        slice01 = SliceElement(transformation=Transformation.from_frame(frame01))
        slice10 = SliceElement(transformation=Transformation.from_frame(frame10))
        slice11 = SliceElement(transformation=Transformation.from_frame(frame11))
        slice20 = SliceElement(transformation=Transformation.from_frame(frame20))
        slice21 = SliceElement(transformation=Transformation.from_frame(frame21))

        self.model.add_element(slice00)
        self.model.add_element(slice01)
        self.model.add_element(slice10)
        self.model.add_element(slice11)
        self.model.add_element(slice20)
        self.model.add_element(slice21)
        
        self.model.add_modifier(slice00, beam0, SliceModifier())
        self.model.add_modifier(slice01, beam0, SliceModifier())
        self.model.add_modifier(slice10, beam1, SliceModifier())
        self.model.add_modifier(slice11, beam1, SliceModifier())
        self.model.add_modifier(slice20, beam2, SliceModifier())
        self.model.add_modifier(slice21, beam2, SliceModifier())

        #############################################################################################
        # Axes
        #############################################################################################

        # Update axes
        new_corner = Vector(thickness*0.5,thickness*0.5,0)
        
        self.ribs_lines[0] = Line(new_corner+self.points[4], line0_offset.start+Vector(0, thickness*0.5, 0))
        self.ribs_lines[1] = Line(new_corner+self.points[4], p0)
        self.ribs_lines[2] = Line(new_corner+self.points[4], p1)
        self.ribs_lines[3] = Line(new_corner+self.points[4], line2_offset.end+Vector(thickness*0.5, 0, 0))
        # self.points[5] = Point(*(line0_offset.start+Vector(0, thickness*0.5, 0)))
        # self.points[0] = Point(*p0)
        # self.points[3] = Point(*p1)
        # self.points[6] = Point(*(line2_offset.end+Vector(thickness*0.5, 0, 0)))


        rib_element0 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[0].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[0].start, -self.ribs_lines[0].direction.cross(zaxis), zaxis)))    
        rib_element1 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[1].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[1].start, -self.ribs_lines[1].direction.cross(zaxis), zaxis)))    
        rib_element2 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[2].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[2].start, -self.ribs_lines[2].direction.cross(zaxis), zaxis)))    
        rib_element3 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[3].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[3].start, -self.ribs_lines[3].direction.cross(zaxis), zaxis)))
        rib_element1.extend(thickness*0.5)
        rib_element2.extend(thickness*0.5)
        rib_element3.extend(thickness*0.5)
        rib_element0.extend(thickness*0.5)   

        self.model.add_element(rib_element0)
        self.model.add_element(rib_element1)
        self.model.add_element(rib_element2)
        self.model.add_element(rib_element3)

        # Cut frames
        cut_frame0_front = Frame(line0.midpoint, line0.direction, zaxis)
        cut_frame1_front = Frame(line1.midpoint, line1.direction, zaxis)
        cut_frame2_front = Frame(line2.midpoint, line2.direction, zaxis)
        slice_rib_end0 = SliceElement(transformation=Transformation.from_frame(cut_frame0_front))
        slice_rib_end1 = SliceElement(transformation=Transformation.from_frame(cut_frame1_front))
        slice_rib_end2 = SliceElement(transformation=Transformation.from_frame(cut_frame2_front))
        self.model.add_element(slice_rib_end0)
        self.model.add_element(slice_rib_end1)
        self.model.add_element(slice_rib_end2)
        self.model.add_modifier(slice_rib_end0, rib_element0, SliceModifier())
        self.model.add_modifier(slice_rib_end0, rib_element1, SliceModifier())
        self.model.add_modifier(slice_rib_end1, rib_element1, SliceModifier())
        self.model.add_modifier(slice_rib_end1, rib_element2, SliceModifier())
        self.model.add_modifier(slice_rib_end2, rib_element2, SliceModifier())
        self.model.add_modifier(slice_rib_end2, rib_element3, SliceModifier())

        
        cut_frame0_back = Frame(self.ribs_lines[0].start, self.ribs_lines[0].direction.cross(zaxis), zaxis)
        cut_frame1_back = Frame(self.ribs_lines[0].start, (self.ribs_lines[1].direction+self.ribs_lines[2].direction).cross(zaxis), zaxis)
        cut_frame2_back = Frame(self.ribs_lines[0].start, self.ribs_lines[3].direction.cross(zaxis), zaxis)
    

        cut_frame0_back.translate(cut_frame0_back.zaxis*-shorten_ribs)
        cut_frame1_back.translate(cut_frame1_back.zaxis*-shorten_ribs)
        cut_frame2_back.translate(cut_frame2_back.zaxis*-shorten_ribs)
        slice_rib_end0 = SliceElement(transformation=Transformation.from_frame(cut_frame0_back))
        slice_rib_end1 = SliceElement(transformation=Transformation.from_frame(cut_frame1_back))
        slice_rib_end2 = SliceElement(transformation=Transformation.from_frame(cut_frame2_back))
        self.model.add_element(slice_rib_end0)
        self.model.add_element(slice_rib_end1)
        self.model.add_element(slice_rib_end2)
        self.model.add_modifier(slice_rib_end0, rib_element0, SliceModifier())
        self.model.add_modifier(slice_rib_end1, rib_element1, SliceModifier())
        self.model.add_modifier(slice_rib_end1, rib_element2, SliceModifier())
        self.model.add_modifier(slice_rib_end2, rib_element3, SliceModifier())


        # Create parabolic boolean from below
        self.ribs_lines[0] = Line(self.ribs_lines[0].start, intersection_line_plane(self.ribs_lines[0], Plane(line0_offset.start, line0_offset.direction.cross(zaxis))))
        self.ribs_lines[1] = Line(self.ribs_lines[1].start, intersection_line_plane(self.ribs_lines[1], Plane(line0_offset.start, line0_offset.direction.cross(zaxis))))
        self.ribs_lines[2] = Line(self.ribs_lines[2].start, intersection_line_plane(self.ribs_lines[2], Plane(line2_offset.start, line2_offset.direction.cross(zaxis))))
        self.ribs_lines[3] = Line(self.ribs_lines[3].start, intersection_line_plane(self.ribs_lines[3], Plane(line2_offset.start, line2_offset.direction.cross(zaxis))))

        parabola0, planes0 = self.compute_parabola(self.ribs_lines[0].start, self.ribs_lines[0].end, Vector(1,0,0), 7, thickness)
        parabola1, planes1 = self.compute_parabola(self.ribs_lines[1].start, self.ribs_lines[1].end, Vector(1,0,0), 7, thickness)
        parabola2, planes2 = self.compute_parabola(self.ribs_lines[2].start, self.ribs_lines[2].end, Vector(0,1,0), 7, thickness)
        parabola3, planes3 = self.compute_parabola(self.ribs_lines[3].start, self.ribs_lines[3].end, Vector(0,1,0), 7, thickness)
        self.parabolas = [parabola0, parabola1, parabola2, parabola3]
        self.planes = planes0 + planes1 + planes2 + planes3

        solid0 = self.create_solid(parabola0, 10, thickness)
        solid1 = self.create_solid(parabola1, 10, thickness)
        solid2 = self.create_solid(parabola2, 10, thickness)
        solid3 = self.create_solid(parabola3, 10, thickness)

        solid_element0 = self.model.add_element(Solid(solid0))
        solid_element1 = self.model.add_element(Solid(solid1))
        solid_element2 = self.model.add_element(Solid(solid2))
        solid_element3 = self.model.add_element(Solid(solid3))

        self.model.add_modifier(solid_element0, rib_element0, SolidDifferenceModifier())
        self.model.add_modifier(solid_element1, rib_element1, SolidDifferenceModifier())
        self.model.add_modifier(solid_element2, rib_element2, SolidDifferenceModifier())
        self.model.add_modifier(solid_element3, rib_element3, SolidDifferenceModifier())
   
        # Triangle parts

        # Triangle one 
        plane0 = Plane(self.ribs_lines[0].start, self.ribs_lines[0].direction.cross(zaxis)) # These will be offset inwards
        plane1 = Plane(self.ribs_lines[1].start, self.ribs_lines[1].direction.cross(zaxis)) # These will be offset inwards


        parabola0_offset = self.offset_polyline(
            parabola0, 
            thickness, 
            plane0, 
            Plane.from_frame(cut_frame0_back), 
            Plane.from_frame(cut_frame0_front))

        parabola1_offset = self.project_polyline(parabola0_offset, plane1)

        self.offset_polylines = [parabola0_offset, parabola1_offset]


    def compute_parabola(
        self,
        start_point,
        end_point,
        axis_for_plane_intersection=Vector(1,0,0),
        divisions=7,
        thickness = 10):

        import session_py

        points = [
            session_py.Point(start_point.x, start_point.y, start_point.z-self.zsize),
            session_py.Point((start_point.x+end_point.x)*0.5, (start_point.y+end_point.y)*0.5, (start_point.z+end_point.z)*0.5-self.zsize+self.rise),
            session_py.Point(end_point.x, end_point.y, end_point.z-self.zsize+self.rise),
        ]

        curve = session_py.NurbsCurve.create(periodic=False, degree=len(points)-1, points=points)
        
        # Create planes perpendicular to X-axis at regular intervals
        planes = []
        planes_compas = []
        print(thickness)
        step = (self.half_xysize-thickness*1.5) / (divisions-1)
        start_point = points[0]
        for i in range(divisions):
            translation = axis_for_plane_intersection*step*i

            planes.append(session_py.Plane.from_point_normal(translation+start_point, axis_for_plane_intersection))
            planes_compas.append(Plane(translation+start_point, axis_for_plane_intersection))
        

        # Intersect curve with each plane
        sampled_points = []
        for plane in planes:
            intersection_points = curve.intersect_plane_points(plane)
            if intersection_points:
                sampled_points.append(intersection_points[0])

        # Convert session_py points to compas points
        compas_points = [Point(p.x, p.y, p.z) for p in sampled_points]
        print("number of points of original parabola:", len(compas_points))
        parabola = Polyline(compas_points)
        subdivided_parabola = Polyline(curve.divide_by_count(10)[0])

        return parabola, planes_compas

    
    def offset_polyline(
        self,
        polyline,
        distance = 10,
        base_plane = None,
        start_plane = None,
        end_plane = None):

        # Create offset planes from lines
        lines = polyline.lines
        planes = [start_plane]
        for line in lines:
            plane = Plane(line.midpoint, -line.direction.cross(base_plane.normal))
            plane = plane.offset(distance)
            planes.append(plane)
        planes.append(end_plane)

        # Intersect the planes
        points = []
        for i in range(len(planes)-1):
            intersection = intersection_plane_plane_plane(planes[i], planes[i+1], base_plane)
            if not intersection:
                raise Exception("Intersection failed in offset_polyline")
            else:
                points.append(intersection)
        return Polyline(points)
    
    def project_polyline(
        self,
        polyline,
        plane_source,
        plane_target):

        projected_points = []
        for point in polyline.points:
            projected_points.append(intersection_line_plane(Line(point, point+plane.normal), plane))
        
        return Polyline(projected_points)
    
  
        

    def create_solid(
        self, 
        parabola,
        extend = 10,
        thickness = 10):

        closed_polygon = Polyline(parabola.points)
        closed_polygon.extend((extend, extend))

        closed_polygon.insert(0, Point(closed_polygon[0][0], closed_polygon[0][1], -self.zsize-extend))
        closed_polygon.append(Point(closed_polygon[-1][0], closed_polygon[-1][1], -self.zsize-extend))
        closed_polygon = Polygon(closed_polygon)


        # Translate the polyline
        closed_polygon_translated = closed_polygon.translated(closed_polygon.normal*thickness)
        closed_polygon.translate(closed_polygon.normal*-1.0*thickness)

        # Loft the polyline
        vertices = closed_polygon.points + closed_polygon_translated.points
        print("number of vertices:", len(closed_polygon.points))
        print("number of vertices:", len(vertices))
        faces = []
        for i in range(len(closed_polygon.points)):
            n = len(closed_polygon.points)
            a = i
            b = (i+1) if i < n-1 else 0
            c = i + n
            d = (i+1) + n if i < n-1 else n
            faces.append([a, b, d, c])

        v0, f0 = closed_polygon.to_vertices_and_faces()
        f0 = f0[0]

        f1 = []
        for i in range(len(f0)):
            f1.append(f0[i]+len(f0))
        f0.reverse()
        faces.append(f0)
        faces.append(f1)

        mesh = Mesh.from_vertices_and_faces(vertices, faces)

        return mesh




    def polar_array(self, geometries):
        
        polar_arrays = []
        for i in range(4):
            angle = math.pi/2 * i
            transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), angle, Point(self.half_xysize, self.half_xysize, 0))
            polar_array = []
            for g in geometries:
                polar_array.append(g.transformed(transformation))
            polar_arrays.append(polar_array)
        return polar_arrays

slab = SlabFourRibs()
result = slab.get_boundary_beams()





config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "wireframe"  # "lighted", "wireframe", "shaded", "ghosted"
scale = 1e-3
xform = Scale.from_factors([scale, scale, scale])
    
beams = viewer.scene.add_group("beams")
cuts = viewer.scene.add_group("cuts")
parabolas = viewer.scene.add_group("parabolas")
offset_parabolas = viewer.scene.add_group("offset_parabolas")
other = viewer.scene.add_group("other")
cut_planes = viewer.scene.add_group("cut_planes")
axes = viewer.scene.add_group("axes")

# for p in result[2]:
#     if isinstance(p, Mesh):
#         mesh = p.scaled(scale)
#         cuts.add(mesh, hide_coplanaredges=True)
#     else:
#         parabolas.add(p.scaled(scale), color=[255,0,255])
        
# for p in result[4]:
#     point = p.origin
#     point.scale(scale)
#     normal = p.z_axis
#     cut_planes.add(Plane(point, normal))
    
# for p in result[3]:
#     parabolas.add(p.scaled(scale), color=[255,0,255])


for element in slab.model.elements():
    if isinstance(element, BeamElement):
        geometry = element.modelgeometry
        beams.add(geometry,hide_coplanaredges=True)
    elif isinstance(element, Solid):
        geometry = element.modelgeometry
        other.add(geometry,hide_coplanaredges=True)


for ribline in slab.ribs_lines:
    axes.add(ribline, color=[255,0,0])

for parabola in slab.parabolas:
    parabolas.add(parabola, color=[255,0,255])

# for plane in slab.planes:
#     polygon = Polygon.from_rectangle([0,0,0], 1000,1000)
#     polygon.transform(Transformation.from_frame(Frame.from_plane(plane)))
#     cut_planes.add(polygon)

for polyline in slab.offset_polylines:
    offset_parabolas.add(polyline, color=[255,0,0])

viewer.show()
