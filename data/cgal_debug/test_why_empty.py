"""Understand WHY dirty vertices cause CGAL to return empty.
The cutter is a valid closed mesh. The target is a valid closed mesh.
Both have consistent normals. The difference should produce a non-empty result.
Let's check what CGAL actually does."""
import numpy as np
from compas.datastructures import Mesh
from compas_cgal.booleans import boolean_difference_mesh_mesh, boolean_union_mesh_mesh, boolean_intersection_mesh_mesh

# Dirty target (exact runtime values from the failing case)
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

# Load cutter from OBJ (this is the clean version that works individually but fails in chain)
cutter = Mesh.from_obj(r"C:\brg\code_python\compas_tf\data\cgal_debug\fail_cutter_0_contact_wedge_0.obj")
C = cutter.to_vertices_and_faces(triangulated=True)

# This was shown to fail earlier - but let me double check
print("=== dirty target - clean cutter ===")
V, F = boolean_difference_mesh_mesh((dirty_verts, faces), C)
print(f"  difference: V={V.shape[0]} F={F.shape[0]}")

# Hmm that actually worked in test_epeck_dirty.py. The REAL failing case
# was dirty target + dirty cutter (both transformed at runtime).
# Let me reconstruct the dirty cutter.

import pathlib, sys, math
from compas.geometry import Point, Rotation, Translation, Vector, Frame, Transformation
from compas.geometry import Polygon as GeomPolygon

sys.path.insert(0, str(pathlib.Path(r"C:\brg\code_python\compas_tf\examples")))
import compas_tf
from compas_tf.wedge import WedgeElement
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel, merge_collinear_points

builder = FloorBuilder(
    size=3000, height=650, rise=453, oculus=1000, beam_w=40,
    column_head_offset=50, inner_thick=60, outer_thick=100,
    column_head_scale=250, column_head_inclination=0,
    head_h=500, head_b=100, head_o=141,
)
guide = FloorGuide(
    size_grid_x=3000, size_grid_y=3000, size_column_head=220,
    size_column_head_chamfer=120, size_outer_ribs=100, size_inner_ribs=60,
    size_inner_beams=60, height=650, rise=453, size_oculus=1000, size_wedge=120,
)
floor_model = FloorModel(builder=builder)
floor_model.add_support(column_size=220)
floor_model.add_column(column_size=220)
floor_level = Translation.from_vector(Vector(0, 0, floor_model.story_height))
floor_model.add_floor_guide(guide, column_index=0, transformation=floor_level, include_oculus=True)
for i in range(1, 4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    floor_model.add_floor_guide(guide, column_index=i, transformation=floor_level * rot, include_oculus=False)
floor_model.precompute_boolean_modifiers()
floor_model.compute_contacts_inner_beams(tolerance=1.0, minimum_area=1.0, wedge_spacing=0)

# Get first contact and create wedge
edge_contacts = []
for edge in floor_model.graph.edges():
    contacts = floor_model.graph.edge_attribute(edge, name="contacts")
    if contacts:
        u, v = edge
        el_a = floor_model.graph.node_element(u)
        el_b = floor_model.graph.node_element(v)
        for contact in contacts:
            edge_contacts.append((el_a, el_b, contact))

el_a, el_b, contact = edge_contacts[0]
pts = list(contact.polygon.points)
pts = merge_collinear_points(pts, angle_tol=1e-3, closed=True)
contact_normal = GeomPolygon(pts).normal
centroid_z = sum(p[2] for p in pts) / len(pts)
scored = []
for i in range(len(pts)):
    a, b = pts[i], pts[(i + 1) % len(pts)]
    mid_z = (a[2] + b[2]) / 2
    length = (b - a).length
    is_top = mid_z >= centroid_z
    scored.append((is_top, length, a, b))
scored.sort(key=lambda e: (not e[0], -e[1]))
_, length, start, end = scored[0]
direction = (end - start).unitized()
n = round(length / (700 / 2))
n = n if n % 2 == 0 else n + 1
new_spacing = length / n
pt = start + direction * (new_spacing * 1)
frame = Frame(pt, direction, contact_normal)

wedge = WedgeElement(transformation=Transformation.from_frame(frame))
dirty_cutter = wedge.boolean_geometry

target_el = el_a
xform = target_el.modeltransformation
dirty_target = target_el.elementgeometry.transformed(xform)

# Get triangulated data
DT = dirty_target.to_vertices_and_faces(triangulated=True)
DC = dirty_cutter.to_vertices_and_faces(triangulated=True)

print("\n=== dirty target + dirty cutter ===")
V, F = boolean_difference_mesh_mesh(DT, DC)
print(f"  difference: V={V.shape[0]} F={F.shape[0]}")

V, F = boolean_union_mesh_mesh(DT, DC)
print(f"  union: V={V.shape[0]} F={F.shape[0]}")

V, F = boolean_intersection_mesh_mesh(DT, DC)
print(f"  intersection: V={V.shape[0]} F={F.shape[0]}")

# Check: is the target mesh valid?
print(f"\n=== Target mesh checks ===")
print(f"  closed: {dirty_target.is_closed()}")
print(f"  V={dirty_target.number_of_vertices()} F={dirty_target.number_of_faces()}")

print(f"\n=== Cutter mesh checks ===")
print(f"  closed: {dirty_cutter.is_closed()}")
print(f"  V={dirty_cutter.number_of_vertices()} F={dirty_cutter.number_of_faces()}")

# The big clue: union and intersection work, but difference is empty.
# CGAL's corefine_and_compute_difference returns false = can't classify inside/outside.
# This happens when the face classification is ambiguous.
#
# Check: does swapping A and B help? (B - A instead of A - B)
print(f"\n=== Swap operands: cutter - target ===")
V, F = boolean_difference_mesh_mesh(DC, DT)
print(f"  difference (B-A): V={V.shape[0]} F={F.shape[0]}")

# Check: does the EPECK chain also fail for just these two?
from compas_cgal.booleans import boolean_chain
print(f"\n=== EPECK chain: dirty target - dirty cutter ===")
V, F = boolean_chain([DT, DC], ["difference"])
print(f"  EPECK difference: V={V.shape[0]} F={F.shape[0]}")

# Check: clean both and try
clean_target = dirty_target.copy()
for vk in clean_target.vertices():
    x, y, z = clean_target.vertex_coordinates(vk)
    clean_target.vertex_attributes(vk, names="xyz", values=[round(x, 10), round(y, 10), round(z, 10)])
CT = clean_target.to_vertices_and_faces(triangulated=True)

clean_cutter = dirty_cutter.copy()
for vk in clean_cutter.vertices():
    x, y, z = clean_cutter.vertex_coordinates(vk)
    clean_cutter.vertex_attributes(vk, names="xyz", values=[round(x, 10), round(y, 10), round(z, 10)])
CC = clean_cutter.to_vertices_and_faces(triangulated=True)

print(f"\n=== Clean both (round 10): target - cutter ===")
V, F = boolean_difference_mesh_mesh(CT, CC)
print(f"  difference: V={V.shape[0]} F={F.shape[0]}")

# Clean only target
print(f"\n=== Clean target only (round 10) + dirty cutter ===")
V, F = boolean_difference_mesh_mesh(CT, DC)
print(f"  difference: V={V.shape[0]} F={F.shape[0]}")

# Clean only cutter
print(f"\n=== Dirty target + clean cutter only (round 10) ===")
V, F = boolean_difference_mesh_mesh(DT, CC)
print(f"  difference: V={V.shape[0]} F={F.shape[0]}")

# Check if boolean_difference returns False (CGAL returns bool for success)
# Actually the Python wrapper doesn't expose this. Let's check via _booleans directly.
import compas_cgal._booleans as _b

VA = np.asarray(DT[0], dtype=np.float64)
FA = np.asarray(DT[1], dtype=np.int32)
VB = np.asarray(DC[0], dtype=np.float64)
FB = np.asarray(DC[1], dtype=np.int32)

print(f"\n=== Raw C++ call ===")
print(f"  VA shape: {VA.shape}, FA shape: {FA.shape}")
print(f"  VB shape: {VB.shape}, FB shape: {FB.shape}")
result = _b.boolean_difference(VA, FA, VB, FB)
print(f"  result V: {result[0].shape}, result F: {result[1].shape}")

# Now check: does the target have any degenerate triangles?
print(f"\n=== Degenerate triangle check (target) ===")
for i, f in enumerate(DT[1]):
    v0, v1, v2 = [DT[0][j] for j in f]
    e1 = [v1[k] - v0[k] for k in range(3)]
    e2 = [v2[k] - v0[k] for k in range(3)]
    cross = [e1[1]*e2[2]-e1[2]*e2[1], e1[2]*e2[0]-e1[0]*e2[2], e1[0]*e2[1]-e1[1]*e2[0]]
    area = (cross[0]**2 + cross[1]**2 + cross[2]**2)**0.5 / 2
    if area < 1e-10:
        print(f"  DEGENERATE face {i}: area={area:.2e}")
        print(f"    v0={v0}, v1={v1}, v2={v2}")

# Check if any target faces have flipped normals
print(f"\n=== Target face normals vs centroid ===")
cx, cy, cz = dirty_target.centroid()
flipped = 0
for i, f in enumerate(DT[1]):
    v0, v1, v2 = [np.array(DT[0][j]) for j in f]
    e1 = v1 - v0
    e2 = v2 - v0
    n = np.cross(e1, e2)
    fc = (v0 + v1 + v2) / 3
    to_face = fc - np.array([cx, cy, cz])
    if np.dot(n, to_face) < 0:
        flipped += 1
        print(f"  face {i} INWARD: verts={f}")
print(f"  {flipped} flipped out of {len(DT[1])}")
