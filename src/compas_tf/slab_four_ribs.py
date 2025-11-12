from compas.geometry import Point, Vector, Line, Polygon, Polyline, Rotation, Parabola, Bezier, NurbsCurve
import math
from compas_viewer import Viewer
from compas_viewer.config import Config



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
        self._parabola = None

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

    @property
    def boundary_lines(self):
        if self._boundary_lines is None:
            self._boundary_lines = [
            Line(self.points[5], self.points[0]), 
            Line(self.points[0], self.points[3]), 
            Line(self.points[3], self.points[6]), 
        ]
        
        return self._boundary_lines


    @property
    def parabola(self):
        if self._parabola is None:
            self._parabola = Polyline([self.points[7], self.points[8], self.points[9]])
        return self._parabola





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
config = Config()
config.camera.target = [2,2,0]
config.camera.position = [0,0,10]
viewer = Viewer(config)
scale = 1e-3

oculus_lines = slab.oculus_lines
ribs_lines = slab.ribs_lines
boundaries_lines = slab.boundary_lines

group = viewer.scene.add_group("oculus")
for i in oculus_lines:
    group.add(i.scaled(scale))

group = viewer.scene.add_group("parabola")
group.add(slab.parabola.scaled(scale))


polar_array = slab.polar_array(ribs_lines)
for i in range(len(polar_array)):
    group = viewer.scene.add_group("ribs " + str(i))
    for j in polar_array[i]:
        group.add(j.scaled(scale))
    break

polar_array = slab.polar_array(boundaries_lines)
for i in range(len(polar_array)):
    group = viewer.scene.add_group("boundaries " + str(i))
    for j in polar_array[i]:
        group.add(j.scaled(scale))
    break
viewer.show()
