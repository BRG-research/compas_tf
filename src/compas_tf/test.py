from session_py.nurbssurface import NurbsSurface
from session_py.point import Point
from compas_viewer import Viewer
from compas.datastructures import Mesh
from compas.geometry import Point as CompasPoint, Polyline

# Create a NURBS surface (3D, order 4, 5x5 control points)
srf = NurbsSurface(3, False, 4, 4, 5, 5)

# Setup knot vectors
srf.make_clamped_uniform_knot_vector(0, 1.0)
srf.make_clamped_uniform_knot_vector(1, 1.0)

# Set control points (hardcoded 5x5 grid)
srf.set_cv(0, 0, Point(0.0, 0.0, 2.5*-1))
srf.set_cv(0, 1, Point(0.0, 1.0, 0.0))
srf.set_cv(0, 2, Point(0.0, 2.0, 0.0))
srf.set_cv(0, 3, Point(0.0, 3.0, 0.0))
srf.set_cv(0, 4, Point(0.0, 4.0, 2.5*-1))

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

srf.set_cv(4, 0, Point(4.0, 0.0, 2.5*-1))
srf.set_cv(4, 1, Point(4.0, 1.0, 0.0))
srf.set_cv(4, 2, Point(4.0, 2.0, 0.0))
srf.set_cv(4, 3, Point(4.0, 3.0, 0.0))
srf.set_cv(4, 4, Point(4.0, 4.0, 2.5*-1))

print("NURBS Surface Grid Evaluation\n")

u_min, u_max = srf.domain(0)
v_min, v_max = srf.domain(1)
u_param = 0.5 * (u_min + u_max)
v_param = 0.5 * (v_min + v_max)
divisions = 50

# Build a quad mesh from a regular parameter grid on the surface
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

# Build two polylines: one iso-u (v varies), one iso-v (u varies)
print("Polyline v")
iso_u_pts = []
for j in range(divisions):
    v = v_min + (v_max - v_min) * j / (divisions - 1)
    pt = srf.point_at(u_param, v)
    print(pt)
    iso_u_pts.append(CompasPoint(pt.x, pt.y, pt.z))
print("Polyline u")
iso_v_pts = []
for i in range(divisions):
    u = u_min + (u_max - u_min) * i / (divisions - 1)
    pt = srf.point_at(u, v_param)
    print(pt)
    iso_v_pts.append(CompasPoint(pt.x, pt.y, pt.z))

iso_u_poly = Polyline(iso_u_pts)
iso_v_poly = Polyline(iso_v_pts)

viewer = Viewer()
viewer.scene.add(mesh, show_vertices=False, show_edges=True, show_faces=True, opacity=0.7)
viewer.scene.add(iso_u_poly, linewidth=3, linecolor=(1, 0, 0))
viewer.scene.add(iso_v_poly, linewidth=3, linecolor=(0, 0, 1))
viewer.show()

print("\n✅ Done!")