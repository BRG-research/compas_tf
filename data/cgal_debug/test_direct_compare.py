"""Compare: load the exported failing meshes in Python vs what the C++ test loaded from OBJ."""
import numpy as np
from compas.datastructures import Mesh
from compas_cgal.booleans import boolean_difference_mesh_mesh, boolean_chain

# 1) Load the exported fail OBJs back
target = Mesh.from_obj(r"C:\brg\code_python\compas_tf\data\cgal_debug\fail_target.obj")
cutter = Mesh.from_obj(r"C:\brg\code_python\compas_tf\data\cgal_debug\fail_cutter_0_contact_wedge_0.obj")

print("=== Loaded from exported OBJ ===")
print(f"target: V={target.number_of_vertices()} F={target.number_of_faces()} closed={target.is_closed()}")
print(f"cutter: V={cutter.number_of_vertices()} F={cutter.number_of_faces()} closed={cutter.is_closed()}")

# Check face winding consistency
from compas.geometry import normal_polygon, centroid_points
print("\n=== Target face normals ===")
centroid = target.centroid()
outward_count = 0
inward_count = 0
for fkey in target.faces():
    pts = target.face_coordinates(fkey)
    fn = normal_polygon(pts, unitized=True)
    fc = centroid_points(pts)
    # direction from mesh centroid to face centroid
    to_face = [fc[i] - centroid[i] for i in range(3)]
    dot = sum(fn[i] * to_face[i] for i in range(3))
    if dot > 0:
        outward_count += 1
    else:
        inward_count += 1
        print(f"  face {fkey} INWARD normal: n={[round(x,3) for x in fn]} fc={[round(x,1) for x in fc]}")
print(f"  {outward_count} outward, {inward_count} inward")

# 2) Try boolean with fan triangulation (what apply_batch does)
print("\n=== Test: fan-triangulated (Python path) ===")
T = target.to_vertices_and_faces(triangulated=True)
C = cutter.to_vertices_and_faces(triangulated=True)
print(f"target tris: V={len(T[0])} F={len(T[1])}")
print(f"cutter tris: V={len(C[0])} F={len(C[1])}")

V, F = boolean_difference_mesh_mesh(T, C)
print(f"EPICK result: V={V.shape[0] if V.size else 0} F={F.shape[0] if F.size else 0}")

# 3) Try with boolean_chain (EPECK)
print("\n=== Test: EPECK chain ===")
V2, F2 = boolean_chain([T, C], ["difference"])
print(f"EPECK result: V={V2.shape[0] if V2.size else 0} F={F2.shape[0] if F2.size else 0}")

# 4) Now load the original OBJ files that the C++ test used successfully
print("\n=== Test: original OBJ files from cgal_debug ===")
target_orig = Mesh.from_obj(r"C:\brg\code_python\compas_tf\data\cgal_debug\target.obj")
cutter_orig = Mesh.from_obj(r"C:\brg\code_python\compas_tf\data\cgal_debug\cutter_0_wedgeelement.obj")
print(f"orig target: V={target_orig.number_of_vertices()} F={target_orig.number_of_faces()} closed={target_orig.is_closed()}")
print(f"orig cutter: V={cutter_orig.number_of_vertices()} F={cutter_orig.number_of_faces()} closed={cutter_orig.is_closed()}")

T2 = target_orig.to_vertices_and_faces(triangulated=True)
C2 = cutter_orig.to_vertices_and_faces(triangulated=True)
V3, F3 = boolean_difference_mesh_mesh(T2, C2)
print(f"EPICK result: V={V3.shape[0] if V3.size else 0} F={F3.shape[0] if F3.size else 0}")

V4, F4 = boolean_chain([T2, C2], ["difference"])
print(f"EPECK result: V={V4.shape[0] if V4.size else 0} F={F4.shape[0] if F4.size else 0}")

# 5) Print actual vertex/face data for comparison
print("\n=== fail_target vertices ===")
verts = T[0]
for i, v in enumerate(verts):
    print(f"  v{i}: {v}")
print("=== fail_target faces ===")
for i, f in enumerate(T[1]):
    print(f"  f{i}: {f}")

print("\n=== orig target.obj vertices ===")
verts2 = T2[0]
for i, v in enumerate(verts2):
    print(f"  v{i}: {v}")
print("=== orig target.obj faces ===")
for i, f in enumerate(T2[1]):
    print(f"  f{i}: {f}")
