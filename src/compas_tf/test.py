from session_py.nurbssurface import NurbsSurface
from session_py.nurbscurve import NurbsCurve
from session_py.point import Point
from session_py.vector import Vector

from compas_viewer import Viewer
from compas.datastructures import Mesh
from compas.geometry import Point as CompasPoint, Polyline, Line

# Helpers
def normalize(v: Vector, eps=1e-12) -> Vector:
    m = v.magnitude()
    return v / m if m > eps else Vector(0, 0, 0)

def small_plane_square(center: CompasPoint, e1: Vector, e2: Vector, size=0.2) -> Polyline:
    # Build a small oriented square in the e1/e2 plane around center
    p0 = CompasPoint(center.x + size * ( e1.x + e2.x), center.y + size * ( e1.y + e2.y), center.z + size * ( e1.z + e2.z))
    p1 = CompasPoint(center.x + size * (-e1.x + e2.x), center.y + size * (-e1.y + e2.y), center.z + size * (-e1.z + e2.z))
    p2 = CompasPoint(center.x + size * (-e1.x - e2.x), center.y + size * (-e1.y - e2.y), center.z + size * (-e1.z - e2.z))
    p3 = CompasPoint(center.x + size * ( e1.x - e2.x), center.y + size * ( e1.y - e2.y), center.z + size * ( e1.z - e2.z))
    return Polyline([p0, p1, p2, p3, p0])

def axis_triad(center: CompasPoint, e1: Vector, e2: Vector, n: Vector, scale=0.35):
    # Return pairs of points for Line geometry (x, y, z axes)
    p = center
    x_end = CompasPoint(p.x + scale*e1.x, p.y + scale*e1.y, p.z + scale*e1.z)
    y_end = CompasPoint(p.x + scale*e2.x, p.y + scale*e2.y, p.z + scale*e2.z)
    z_end = CompasPoint(p.x + scale*n.x,  p.y + scale*n.y,  p.z + scale*n.z)
    return (p, x_end), (p, y_end), (p, z_end)

# =============================================================================
# Surface (unchanged from your setup)
# =============================================================================
srf = NurbsSurface(3, False, 4, 4, 5, 5)
srf.make_clamped_uniform_knot_vector(0, 1.0)
srf.make_clamped_uniform_knot_vector(1, 1.0)

srf.set_cv(0, 0, Point(0.0, 0.0, -2.5))
srf.set_cv(0, 1, Point(0.0, 1.0,  0.0))
srf.set_cv(0, 2, Point(0.0, 2.0,  0.0))
srf.set_cv(0, 3, Point(0.0, 3.0,  0.0))
srf.set_cv(0, 4, Point(0.0, 4.0, -2.5))

srf.set_cv(1, 0, Point(1.0, 0.0, 0.0))
srf.set_cv(1, 1, Point(1.0, 1.0, 0.0))
srf.set_cv(1, 2, Point(1.0, 2.0, 5.0))
srf.set_cv(1, 3, Point(1.0, 3.0, 0.0))
srf.set_cv(1, 4, Point(1.0, 4.0, 0.0))

srf.set_cv(2, 0, Point(2.0, 0.0, 0.0))
srf.set_cv(2, 1, Point(2.0, 1.0, 0.0))
srf.set_cv(2, 2, Point(2.0, 2.0, 0.0))
srf.set_cv(2, 3, Point(2.0, 3.0, 0.0))
srf.set_cv(2, 4, Point(2.0, 4.0, 0.0))

srf.set_cv(3, 0, Point(3.0, 0.0, 0.0))
srf.set_cv(3, 1, Point(3.0, 1.0, 0.0))
srf.set_cv(3, 2, Point(3.0, 2.0, 0.0))
srf.set_cv(3, 3, Point(3.0, 3.0, 0.0))
srf.set_cv(3, 4, Point(3.0, 4.0, 0.0))

srf.set_cv(4, 0, Point(4.0, 0.0, -2.5))
srf.set_cv(4, 1, Point(4.0, 1.0,  0.0))
srf.set_cv(4, 2, Point(4.0, 2.0,  0.0))
srf.set_cv(4, 3, Point(4.0, 3.0,  0.0))
srf.set_cv(4, 4, Point(4.0, 4.0, -2.5))

u_min, u_max = srf.domain(0)
v_min, v_max = srf.domain(1)
u_param = 0.5 * (u_min + u_max)
v_param = 0.5 * (v_min + v_max)
divisions = 50

grid_size = 20
points_grid = []
for i in range(grid_size):
    row = []
    for j in range(grid_size):
        u = u_min + (u_max - u_min) * i / (grid_size - 1)
        v = v_min + (v_max - v_min) * j / (grid_size - 1)
        pt = srf.point_at(u, v)
        row.append(CompasPoint(pt.x, pt.y, pt.z))
    points_grid.append(row)

mesh = Mesh()
vertex_keys = []
for i in range(grid_size):
    row_keys = []
    for j in range(grid_size):
        pt = points_grid[i][j]
        key = mesh.add_vertex(x=pt.x, y=pt.y, z=pt.z)
        row_keys.append(key)
    vertex_keys.append(row_keys)

for i in range(grid_size - 1):
    for j in range(grid_size - 1):
        v0 = vertex_keys[i][j]
        v1 = vertex_keys[i+1][j]
        v2 = vertex_keys[i+1][j+1]
        v3 = vertex_keys[i][j+1]
        mesh.add_face([v0, v1, v2, v3])

iso_u_pts = []
for j in range(divisions):
    v = v_min + (v_max - v_min) * j / (divisions - 1)
    pt = srf.point_at(u_param, v)
    iso_u_pts.append(CompasPoint(pt.x, pt.y, pt.z))

iso_v_pts = []
for i in range(divisions):
    u = u_min + (u_max - u_min) * i / (divisions - 1)
    pt = srf.point_at(u, v_param)
    iso_v_pts.append(CompasPoint(pt.x, pt.y, pt.z))

iso_u_poly = Polyline(iso_u_pts)
iso_v_poly = Polyline(iso_v_pts)

# Surface frame at center (u_param, v_param)
pt_s = srf.point_at(u_param, v_param)
derivs = srf.evaluate(u_param, v_param, 1)  # [point, du, dv]
du = derivs[1]
dv = derivs[2]
n_s = normalize(du.cross(dv))
e1_s = normalize(du) if du.magnitude() > 1e-12 else normalize(dv.cross(n_s))
e2_s = n_s.cross(e1_s)
surf_center = CompasPoint(pt_s.x, pt_s.y, pt_s.z)
surf_square = small_plane_square(surf_center, e1_s, e2_s, size=0.25)
sx, sy, sz = axis_triad(surf_center, e1_s, e2_s, n_s, scale=0.35)

# =============================================================================
# 3D NURBS curve (non-planar) and frames
# =============================================================================
# Create a clearly 3D curve from 8 control points (wavy helix)
import math
ctrl = []
for k in range(8):
    t = k / 7.0 * 2.0 * math.pi
    r = 1.5 + 0.3 * math.cos(3.0 * t)
    x = r * math.cos(t)
    y = r * math.sin(t)
    z = 0.6 * t  # rises along the curve -> non-planar
    ctrl.append(Point(x, y, z))

crv3d = NurbsCurve.create(False, 3, ctrl)   # clamped degree-3 3D curve

# Sample the curve for display
t0, t1 = crv3d.domain()
curve_pts = []
for i in range(100):
    tt = t0 + (t1 - t0) * i / 99.0
    p = crv3d.point_at(tt)
    curve_pts.append(CompasPoint(p.x, p.y, p.z))
curve_poly = Polyline(curve_pts)

# Compute frames at mid-parameter on the 3D curve
tmid = 0.99 * (t0 + t1)
pt_c = crv3d.point_at(tmid)
T = normalize(crv3d.tangent_at(tmid))
curve_center = CompasPoint(pt_c.x, pt_c.y, pt_c.z)

# Normal plane (plane normal = T)
fallback = Vector(0, 0, 1) if abs(T.z) < 0.9 else Vector(0, 1, 0)
e1_np = normalize(T.cross(fallback))
e2_np = T.cross(e1_np)
n_np  = T
curve_np_square = small_plane_square(curve_center, e1_np, e2_np, size=0.25)
nx, ny, nz = axis_triad(curve_center, e1_np, e2_np, n_np, scale=0.35)

# Frenet plane (plane normal = binormal B)
ders = crv3d.evaluate(tmid, 2)  # [P, d1, d2]
d1 = ders[1]; d2 = ders[2]
T_f = normalize(d1)
proj = d2.dot(T_f)
N_raw = Vector(d2.x - T_f.x * proj, d2.y - T_f.y * proj, d2.z - T_f.z * proj)
N_f = normalize(N_raw) if N_raw.magnitude() > 1e-12 else e2_np
B_f = T_f.cross(N_f)
frenet_square = small_plane_square(curve_center, T_f, N_f, size=0.25)
fx, fy, fz = axis_triad(curve_center, T_f, N_f, B_f, scale=0.35)

# =============================================================================
# Viewer
# =============================================================================
viewer = Viewer()
viewer.scene.add(mesh, show_vertices=False, show_edges=True, show_faces=True, opacity=0.7)
viewer.scene.add(iso_u_poly, linewidth=3, linecolor=(1, 0, 0))
viewer.scene.add(iso_v_poly, linewidth=3, linecolor=(0, 0, 1))
print(iso_u_poly)
print(iso_v_poly)

# Surface frame (green plane, RGB axes)
print(surf_center)
print(sx[0], sx[1])
print(sy[0], sy[1])
print(sz[0], sz[1])
viewer.scene.add(surf_square, linewidth=2, linecolor=(0.0, 0.6, 0.0))
viewer.scene.add(Line(sx[0], sx[1]), linewidth=3, linecolor=(255, 0, 0))
viewer.scene.add(Line(sy[0], sy[1]), linewidth=3, linecolor=(0, 255, 0))
viewer.scene.add(Line(sz[0], sz[1]), linewidth=3, linecolor=(0, 0, 255))

# 3D curve and its frames
viewer.scene.add(curve_poly, linewidth=3, linecolor=(0.9, 0.2, 0.2))
print(curve_poly)


# Curve normal plane (magenta plane, RGB axes)
viewer.scene.add(curve_np_square, linewidth=2, linecolor=(0.6, 0.0, 0.6))
viewer.scene.add(Line(nx[0], nx[1]), linewidth=3, linecolor=(255, 0, 0))
viewer.scene.add(Line(ny[0], ny[1]), linewidth=3, linecolor=(0, 255, 0))
viewer.scene.add(Line(nz[0], nz[1]), linewidth=3, linecolor=(0, 0, 255))
print(curve_np_square)
print(nx[0], nx[1])
print(ny[0], ny[1])
print(nz[0], nz[1])


# Curve Frenet plane (orange plane, RGB axes)
viewer.scene.add(frenet_square, linewidth=2, linecolor=(0.9, 0.5, 0.0))
viewer.scene.add(Line(fx[0], fx[1]), linewidth=3, linecolor=(255, 0, 0))
viewer.scene.add(Line(fy[0], fy[1]), linewidth=3, linecolor=(0, 255, 0))
viewer.scene.add(Line(fz[0], fz[1]), linewidth=3, linecolor=(0, 0, 255))
print(frenet_square)
print(fx[0], fx[1])
print(fy[0], fy[1])
print(fz[0], fz[1])

viewer.show()