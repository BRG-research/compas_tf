from compas.geometry import Point, Line, Polyline, Vector, Parabola, Frame, Bezier
from compas.geometry import Plane
import math
from compas_viewer import Viewer

class Quarter:
    """Quarter of a timber floor."""
    def __init__(self, x_size=3000, y_size=3000, z_size=600, rise=453, angles=[33.69]):
        self.x_size = x_size
        self.y_size = y_size
        self.z_size = z_size
        self.rise = rise
        self.angles = angles

    def plan(self):
        """Return the half axes of the quarter."""

        line = Line([0,0,0], [self.x_size, 0, 0])
        lines = [line]
        y_projections = []  # Store y-direction lines
        
        for angle in self.angles:
            # Calculate new line length to keep endpoint at same x coordinate
            angle_rad = math.radians(angle)
            new_length = self.x_size / math.cos(angle_rad)
            
            # Create rotated line with adjusted length
            # Endpoint will be at (x_size, x_size * tan(angle), 0)
            end_point = Point(self.x_size, self.x_size * math.tan(angle_rad), 0)
            rotated_line = Line([0, 0, 0], end_point)
            lines.append(rotated_line)
            
        return lines, y_projections

    def elevation(self):
        """Return the elevation of the quarter as a parabolic arc through three points."""
        # Define three points: start (p0), middle (p1), end (p2)
        p0 = Point(0, 0, -self.z_size)
        p1 = Point(self.x_size*0.5, 0, -self.z_size+self.rise)
        p2 = Point(self.x_size, 0, -self.z_size+self.rise)

        bezier = Bezier([p0, p1, p2])
        polyline = bezier.to_polyline(6)
        
        plane = Plane(Point(0, 0, 0), Vector(0, 0, 1))
        intersection_points, _ = self.intersect_bezier_plane_exact(bezier, plane)
        
        return polyline, Polyline(intersection_points)

    def intersect_bezier_plane_exact(self, bezier, plane, value_tol=1e-7, param_tol=1e-6, max_depth=30):
        n = plane.normal
        q = plane.point
        vals = [n.dot(p - q) for p in bezier.points]

        def f(t):
            p = bezier.point_at(t)
            return n.dot(p - q)

        def subdivide_scalar(vs):
            levels = [list(vs)]
            while len(levels[-1]) > 1:
                prev = levels[-1]
                levels.append([(prev[i] + prev[i + 1]) * 0.5 for i in range(len(prev) - 1)])
            left = [levels[i][0] for i in range(len(vs))]
            right = [levels[len(vs) - 1 - i][i] for i in range(len(vs))]
            return left, right

        roots = []

        def recurse(vs, t0, t1, d):
            mn = min(vs)
            mx = max(vs)
            if mn > value_tol or mx < -value_tol:
                return
            f0 = f(t0)
            if abs(f0) <= value_tol:
                roots.append(t0)
                return
            f1 = f(t1)
            if abs(f1) <= value_tol:
                roots.append(t1)
                return
            if (t1 - t0) <= param_tol or d <= 0 or (mx - mn) <= value_tol:
                if f0 * f1 <= 0:
                    a, b = t0, t1
                    fa, fb = f0, f1
                    for _ in range(50):
                        m = 0.5 * (a + b)
                        fm = f(m)
                        if abs(fm) <= value_tol or (b - a) <= param_tol:
                            roots.append(m)
                            return
                        if fa * fm <= 0:
                            b, fb = m, fm
                        else:
                            a, fa = m, fm
                    roots.append(0.5 * (a + b))
                else:
                    m = 0.5 * (t0 + t1)
                    fm = f(m)
                    if abs(fm) <= value_tol:
                        roots.append(m)
                return
            left, right = subdivide_scalar(vs)
            tm = 0.5 * (t0 + t1)
            if min(left) <= value_tol and max(left) >= -value_tol:
                recurse(left, t0, tm, d - 1)
            if min(right) <= value_tol and max(right) >= -value_tol:
                recurse(right, tm, t1, d - 1)

        if not (min(vals) > value_tol or max(vals) < -value_tol):
            recurse(vals, 0.0, 1.0, max_depth)

        roots.sort()
        pruned = []
        for t in roots:
            if not pruned or abs(t - pruned[-1]) > param_tol:
                pruned.append(t)
        points = [bezier.point_at(t) for t in pruned]
        return points, pruned

if __name__ == "__main__":
    quarter = Quarter()
    lines, y_projections = quarter.plan()
    parabola, polyline = quarter.elevation()
    viewer = Viewer()
    for line in lines:
        viewer.scene.add(line)
    for line in y_projections:
        viewer.scene.add(line)
    viewer.scene.add(parabola)
    viewer.scene.add(polyline)
    viewer.show()

