"""Test: does EPECK chain also fail with dirty vertices?"""
import numpy as np
from compas_cgal.booleans import boolean_difference_mesh_mesh, boolean_chain
from compas.datastructures import Mesh

# Load the cutter from OBJ (clean)
cutter = Mesh.from_obj(r"C:\brg\code_python\compas_tf\data\cgal_debug\fail_cutter_0_contact_wedge_0.obj")
C = cutter.to_vertices_and_faces(triangulated=True)

# Dirty target (exact runtime values)
dirty_verts = [
    [0.0, -2900.0, 3500.0],
    [-5.684341886080802e-14, -1000.0, 3500.0],
    [0.0, -975.625652061079, 3303.0],
    [0.0, -2900.0, 3303.0],
    [-60.0, -2900.0, 3500.0],
    [-60.0, -940.0, 3500.0],
    [-59.99999999999994, -915.6256520610791, 3303.0],
    [-60.0, -2900.0, 3303.0],
]
faces = [
    [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5],
    [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7],
    [0, 3, 2], [2, 1, 0], [7, 4, 5], [5, 6, 7],
]

# Clean target (rounded)
clean_verts = [
    [0.0, -2900.0, 3500.0],
    [0.0, -1000.0, 3500.0],
    [0.0, -975.626, 3303.0],
    [0.0, -2900.0, 3303.0],
    [-60.0, -2900.0, 3500.0],
    [-60.0, -940.0, 3500.0],
    [-60.0, -915.626, 3303.0],
    [-60.0, -2900.0, 3303.0],
]

print("=== EPICK with dirty vertices ===")
V, F = boolean_difference_mesh_mesh((dirty_verts, faces), C)
print(f"  Result: V={V.shape[0]} F={F.shape[0]}")

print("=== EPICK with clean vertices ===")
V, F = boolean_difference_mesh_mesh((clean_verts, faces), C)
print(f"  Result: V={V.shape[0]} F={F.shape[0]}")

print("=== EPECK chain with dirty vertices ===")
V, F = boolean_chain([(dirty_verts, faces), C], ["difference"])
print(f"  Result: V={V.shape[0]} F={F.shape[0]}")

print("=== EPECK chain with clean vertices ===")
V, F = boolean_chain([(clean_verts, faces), C], ["difference"])
print(f"  Result: V={V.shape[0]} F={F.shape[0]}")

# What about snapping just the near-zero x to exactly 0?
snapped_verts = [list(v) for v in dirty_verts]
snapped_verts[1][0] = 0.0
snapped_verts[6][0] = -60.0

print("=== EPICK with x-snapped vertices ===")
V, F = boolean_difference_mesh_mesh((snapped_verts, faces), C)
print(f"  Result: V={V.shape[0]} F={F.shape[0]}")

print("=== EPECK chain with x-snapped vertices ===")
V, F = boolean_chain([(snapped_verts, faces), C], ["difference"])
print(f"  Result: V={V.shape[0]} F={F.shape[0]}")
