from session_py.nurbssurface import NurbsSurface
from session_py.point import Point
from compas_viewer import Viewer
from compas.datastructures import Mesh
from compas.geometry import Point as CompasPoint


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

# Evaluate surface at subdivided grid points
grid_size = 10  # Increase for finer mesh
u_min, u_max = srf.domain(0)
v_min, v_max = srf.domain(1)

# Store evaluated points in 2D grid
points_grid = []
for i in range(grid_size):
    row = []
    for j in range(grid_size):
        # Calculate parameters
        u = u_min + (u_max - u_min) * i / (grid_size - 1)
        v = v_min + (v_max - v_min) * j / (grid_size - 1)
        
        # Evaluate point
        pt = srf.point_at(u, v)
        print(pt)
        row.append(CompasPoint(pt.x, pt.y, pt.z))
    points_grid.append(row)

print(f"Evaluated {grid_size}x{grid_size} = {grid_size*grid_size} points")

# Create COMPAS Mesh
mesh = Mesh()

# Add vertices and store their keys in a 2D array
vertex_keys = []
for i in range(grid_size):
    row_keys = []
    for j in range(grid_size):
        pt = points_grid[i][j]
        key = mesh.add_vertex(x=pt.x, y=pt.y, z=pt.z)
        row_keys.append(key)
    vertex_keys.append(row_keys)

print(f"Added {mesh.number_of_vertices()} vertices")

# Create quad faces
face_count = 0
for i in range(grid_size - 1):
    for j in range(grid_size - 1):
        # Create quad face from 4 adjacent vertices
        v0 = vertex_keys[i][j]
        v1 = vertex_keys[i+1][j]
        v2 = vertex_keys[i+1][j+1]
        v3 = vertex_keys[i][j+1]
        mesh.add_face([v0, v1, v2, v3])
        face_count += 1

print(f"Added {face_count} quad faces")
print(f"Mesh: {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces, {mesh.number_of_edges()} edges")

# Visualize with COMPAS Viewer
viewer = Viewer()
viewer.scene.add(mesh, show_vertices=True, show_edges=True, show_faces=True)
viewer.show()

print("\n✅ Done!")