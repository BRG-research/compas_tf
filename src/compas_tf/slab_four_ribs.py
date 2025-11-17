from compas.geometry import Point, Vector, Line, Polygon, Polyline, Rotation, Scale, Frame, Plane, Transformation
from compas.geometry import intersection_line_line
import math
from compas_viewer import Viewer
from compas_viewer.config import Config
from compas_tf.beam import BeamElement
from compas_tf.plate import PlateElement
from compas_tf.slicer import SliceElement
from compas_tf.slicemodifier import SliceModifier
from compas_model.models import Model

class SlabFourRibs:

    def __init__(self, xysize = 6000, zsize = 600, rise = 453, oculus_size = 2000):
        self.xysize = xysize
        self.zsize = zsize
        self.rise = rise
        self.oculus_size = oculus_size
        self._points = None
        self._oculus_lines = None
        self._ribs_lines = None
        self._boundary_lines = None
        self.model = Model()

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

        boundary_beams = []
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
        self.ribs_lines[1] = Line(new_corner+self.points[4], line0_offset.end)
        self.ribs_lines[2] = Line(new_corner+self.points[4], line2_offset.start)
        self.ribs_lines[3] = Line(new_corner+self.points[4], line2_offset.end+Vector(thickness*0.5, 0, 0))

        # Shorted ribs
        # shorted_rib_lines = []
        # for idx, rib_line in enumerate(self.ribs_lines):
        #     direction = rib_line.direction.unitized()
        #     shorted_rib_line = Line(rib_line.start+direction*shorten_ribs, rib_line.end)
        #     shorted_rib_lines.append(shorted_rib_line)

        rib0 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[0].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[0].start, -self.ribs_lines[0].direction.cross(zaxis), zaxis)))    
        rib1 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[1].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[1].start, -self.ribs_lines[1].direction.cross(zaxis), zaxis)))    
        rib2 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[2].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[2].start, -self.ribs_lines[2].direction.cross(zaxis), zaxis)))    
        rib3 = BeamElement(width=thickness, depth=self.zsize, length=self.ribs_lines[3].length, transformation=Transformation.from_frame(Frame(-Vector(0,0,self.zsize*0.5)+self.ribs_lines[3].start, -self.ribs_lines[3].direction.cross(zaxis), zaxis)))    

        self.model.add_element(rib0)
        self.model.add_element(rib1)
        self.model.add_element(rib2)
        self.model.add_element(rib3)

        # Offset ribs to two sides
        # Two options
        # 1. Rib offsets intersected with the two boundary lines
        # 2. Ribs are rotated
        # rib_polygons = []
        # for idx, rib_line in enumerate(self.ribs_lines):

        #     rib_line_offset0 = rib_line.translated(zaxis.cross(rib_line.direction).unitized() * -thickness*0.5)
        #     rib_line_offset1 = rib_line.translated(zaxis.cross(rib_line.direction).unitized() * thickness*0.5)

        #     if idx > 0 and idx < len(self.ribs_lines)-1:
        #         print(idx)
        #         rib_p0, _ = intersection_line_line(rib_line_offset0, lines_offset[-1+idx])
        #         rib_p1, _ = intersection_line_line(rib_line_offset1, lines_offset[0+idx])
        #         polygon = Polygon([rib_line_offset0.start, rib_p0, rib_line.end, rib_p1, rib_line_offset1.start])
        #         rib_polygons.append(polygon)
        #     else:
        #         polygon = Polygon([rib_line_offset0.start, rib_line_offset0.end, rib_line_offset1.end, rib_line_offset1.start])
        #         rib_polygons.append(polygon)

          
        
    
        return [beam0, beam1, beam2], [Point(*p0),  Point(*p0_offset), Point(*p1), Point(*p1_offset)]


    def get_boundary_offset(self, thickness =100, shorten_ribs = 300):



        zaxis = Vector(0,0,1)

        # Offset boundary lines inwards
        line0 = Line(self.points[5], self.points[0])
        line1 = Line(self.points[0], self.points[3])
        line2 = Line(self.points[3], self.points[6])

        line0_offset = line0.translated(zaxis.cross(line0.direction).unitized() * thickness)
        line1_offset = line1.translated(zaxis.cross(line1.direction).unitized() * thickness)
        line2_offset = line2.translated(zaxis.cross(line2.direction).unitized() * thickness)
        axis0 = line0.translated(zaxis.cross(line0.direction).unitized() * thickness)
        axis1 = line1.translated(zaxis.cross(line1.direction).unitized() * thickness)
        axis2 = line2.translated(zaxis.cross(line2.direction).unitized() * thickness)

        p0, _ = intersection_line_line(line0_offset, line1_offset)
        p1, _ = intersection_line_line(line1_offset, line2_offset)
        line0_offset = Line(line0_offset.start, p0)
        line1_offset = Line(p0, p1)
        line2_offset = Line(p1, line2_offset.end)
        lines_offset = [line0_offset, line1_offset, line2_offset]

        # Boundary polygons
        boundary_polygons = []
        boundary_polygons.append(Polygon([line0.start, line0.end, line0_offset.end, line0_offset.start]))
        boundary_polygons.append(Polygon([line1.start, line1.end, line1_offset.end, line1_offset.start]))
        boundary_polygons.append(Polygon([line2.start, line2.end, line2_offset.end, line2_offset.start]))

        # Update axes
        new_corner = Vector(thickness*0.5,thickness*0.5,0)
        
        self.ribs_lines[0] = Line(new_corner+self.points[4], line0_offset.start+Vector(0, thickness*0.5, 0))
        self.ribs_lines[1] = Line(new_corner+self.points[4], line0_offset.end)
        self.ribs_lines[2] = Line(new_corner+self.points[4], line2_offset.start)
        self.ribs_lines[3] = Line(new_corner+self.points[4], line2_offset.end+Vector(thickness*0.5, 0, 0))

        # Shorted ribs
        shorted_rib_lines = []
        for idx, rib_line in enumerate(self.ribs_lines):
            direction = rib_line.direction.unitized()
            shorted_rib_line = Line(rib_line.start+direction*shorten_ribs, rib_line.end)
            shorted_rib_lines.append(shorted_rib_line)
    

        # Offset ribs to two sides
        # Two options
        # 1. Rib offsets intersected with the two boundary lines
        # 2. Ribs are rotated
        rib_polygons = []
        for idx, rib_line in enumerate(shorted_rib_lines):

            rib_line_offset0 = rib_line.translated(zaxis.cross(rib_line.direction).unitized() * -thickness*0.5)
            rib_line_offset1 = rib_line.translated(zaxis.cross(rib_line.direction).unitized() * thickness*0.5)

            if idx > 0 and idx < len(shorted_rib_lines)-1:
                print(idx)
                rib_p0, _ = intersection_line_line(rib_line_offset0, lines_offset[-1+idx])
                rib_p1, _ = intersection_line_line(rib_line_offset1, lines_offset[0+idx])
                polygon = Polygon([rib_line_offset0.start, rib_p0, rib_line.end, rib_p1, rib_line_offset1.start])
                rib_polygons.append(polygon)
            else:
                polygon = Polygon([rib_line_offset0.start, rib_line_offset0.end, rib_line_offset1.end, rib_line_offset1.start])
                rib_polygons.append(polygon)





        return boundary_polygons+rib_polygons

    def parabola(self, start_point, end_point, axis_for_plane_intersection=Vector(1,0,0), divisions=7):


        import session_py

        points = [
            session_py.Point(start_point.x, start_point.y, start_point.z-self.zsize),
            session_py.Point((start_point.x+end_point.x)*0.5, (start_point.y+end_point.y)*0.5, (start_point.z+end_point.z)*0.5-self.zsize+self.rise),
            session_py.Point(end_point.x, end_point.y, end_point.z-self.zsize+self.rise),
        ]

        curve = session_py.NurbsCurve.create(periodic=False, degree=len(points)-1, points=points)
        
        # Create planes perpendicular to X-axis at regular intervals
        planes = []
        divisions = 7
        step = self.half_xysize / (divisions-1)
        start_point = points[0]
        for i in range(divisions):
            translation = axis_for_plane_intersection*step*i
            planes.append(session_py.Plane.from_point_normal(translation+start_point, axis_for_plane_intersection))

        # Intersect curve with each plane
        sampled_points = []
        for plane in planes:
            intersection_points = curve.intersect_plane_points(plane)
            if intersection_points:
                sampled_points.append(intersection_points[0])
        print(sampled_points)

        # Convert session_py points to compas points
        compas_points = [Point(p.x, p.y, p.z) for p in sampled_points]
        parabola = Polyline(compas_points)
        # parabola = Polyline(points)
        return parabola, planes




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
slab.get_boundary_beams()





config = Config()

# config.camera.target = [2,2,0]
# config.camera.position = [0,0,10]
# config.camera.scale = 1000
viewer = Viewer(config)
scale = 1e-3
xform = Scale.from_factors([scale, scale, scale])
    
print(len(list(slab.model.elements())))
for element in slab.model.elements():
    # geometry = element.elementgeometry.transformed(xform)
    
    # print(geometry)
    # viewer.scene.add(geometry)
    geometry = element.modelgeometry.transformed(xform)
    print(geometry)
    viewer.scene.add(geometry)

for ribline in slab.ribs_lines:
    viewer.scene.add(ribline.scaled(scale))

    # lines = element.get_long_lines()
    # for line in lines:
    #     viewer.scene.add(line.scaled(scale))

# line0 = Line(points[0], points[1]).scaled(scale)
# line1 = Line(points[2], points[3]).scaled(scale)
# print(line0)
# viewer.scene.add(line0, name="a", color=[255,0,0])
# viewer.scene.add(line1, name="b", color=[0,255,0])


# oculus_lines = slab.oculus_lines
# ribs_lines = slab.ribs_lines
# boundaries_lines = slab.boundary_lines

# group = viewer.scene.add_group("oculus")
# for i in oculus_lines:
#     group.add(i.scaled(scale))

# group = viewer.scene.add_group("parabola")
# parabola0, planes0 = slab.parabola(slab.points[4], slab.points[5], Vector(1,0,0))
# parabola1, planes1 = slab.parabola(slab.points[4], slab.points[0], Vector(1,0,0))
# parabola2, planes2 = slab.parabola(slab.points[4], slab.points[6], Vector(0,1,0))
# parabola3, planes3 = slab.parabola(slab.points[4], slab.points[3], Vector(0,1,0))
# group.add(parabola0.scaled(scale))
# group.add(parabola1.scaled(scale))
# group.add(parabola2.scaled(scale))
# group.add(parabola3.scaled(scale))
# lines = slab.get_boundary_offset()
# for i in lines:
#     group.add(i.scaled(scale))


# for p in parabola0.points:
#     group.add(Box(0.1,0.1,0.1,Frame(p.scaled(scale))))

# for p in parabola1.points:
#     group.add(Box(0.1,0.1,0.1,Frame(p.scaled(scale))))

# for p in parabola2.points:
#     group.add(Box(0.1,0.1,0.1,Frame(p.scaled(scale))))

# for p in parabola3.points:
#     group.add(Box(0.1,0.1,0.1,Frame(p.scaled(scale))))

# polar_array = slab.polar_array(ribs_lines)
# for i in range(len(polar_array)):
#     group = viewer.scene.add_group("ribs " + str(i))
#     for j in polar_array[i]:
#         group.add(j.scaled(scale))
#     break

# polar_array = slab.polar_array(boundaries_lines)
# for i in range(len(polar_array)):
#     group = viewer.scene.add_group("boundaries " + str(i))
#     for j in polar_array[i]:
#         group.add(j.scaled(scale))
#     break
viewer.show()
