"""Test the last remaining failure: boolean_chain_with_face_source vs boolean_chain."""
import pathlib, sys, math
import numpy as np

from compas.geometry import Point, Rotation, Translation, Vector, Frame, Transformation
from compas.datastructures import Mesh
from compas.geometry import Polygon as GeomPolygon

sys.path.insert(0, str(pathlib.Path(r"C:\brg\code_python\compas_tf\examples")))
import compas_tf
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel, merge_collinear_points
from compas_tf.solid_difference_modifier import _triangulate_mesh
from compas_tf.wedge import WedgeElement
from compas_cgal.booleans import (
    boolean_difference_mesh_mesh, boolean_chain, boolean_chain_with_face_source
)

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

# Find the last failing case: inner_beams_2 in 4th quarter with wedge_17,18,19
from compas_tf.solid_difference_modifier import SolidDifferenceModifier
from compas_model.elements.group import Group
from compas_tf.joint_dowel import DowelElement

# Rebuild all wedges
edge_contacts = []
for edge in floor_model.graph.edges():
    contacts = floor_model.graph.edge_attribute(edge, name="contacts")
    if contacts:
        u, v = edge
        el_a = floor_model.graph.node_element(u)
        el_b = floor_model.graph.node_element(v)
        for contact in contacts:
            edge_contacts.append((el_a, el_b, contact))

wedge_spacing = 700
all_wedges = []
for el_a, el_b, contact in edge_contacts:
    polygon = getattr(contact, "polygon", None)
    if polygon is None:
        continue
    pts = list(polygon.points)
    pts = merge_collinear_points(pts, angle_tol=1e-3, closed=True)
    if len(pts) < 3:
        continue
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
    if length < 1e-6:
        continue
    direction = (end - start).unitized()
    n = round(length / (wedge_spacing / 2))
    n = n if n % 2 == 0 else n + 1
    if n == 0:
        continue
    new_spacing = length / n
    for k in range(1, n):
        if k % 2 == 0:
            continue
        pt = start + direction * (new_spacing * k)
        frame = Frame(pt, direction, contact_normal)
        wedge = WedgeElement(transformation=Transformation.from_frame(frame))
        all_wedges.append((wedge, el_a, el_b))

# The 4th quarter inner_beams_2 uses wedges 17,18,19
# Let me find by testing all inner_beams_2 with 3 wedges
for target_el_outer in [ec[0] for ec in edge_contacts] + [ec[1] for ec in edge_contacts]:
    pass  # complex to find, let me just iterate

# Simpler: run the full precompute with wedges and catch the failure
from compas_tf.floor_model import FloorModel as FM

# Use a modified apply_batch to detect the failure
import compas_tf.solid_difference_modifier as sdm
original_triangulate = sdm._triangulate_mesh

fail_data = {}

def patched_apply_batch(sources, targetgeometry, operations=None):
    if operations is None:
        operations = ["difference"] * len(sources)

    all_vf = []
    for mesh in [targetgeometry] + list(sources):
        verts, tris, _ = original_triangulate(mesh)
        all_vf.append((verts, tris))

    # Test both variants
    V1, F1 = boolean_chain(all_vf, operations)
    try:
        V2, F2, S2 = boolean_chain_with_face_source(all_vf, operations)
    except:
        V2 = np.array([])
        F2 = np.array([])

    chain_ok = V1.size > 0
    face_source_ok = V2.size > 0

    if chain_ok and not face_source_ok:
        print(f"  ** DIVERGENCE: boolean_chain OK (V={V1.shape[0]}) but face_source EMPTY **")
        fail_data["all_vf"] = all_vf
        fail_data["operations"] = operations
    elif not chain_ok and not face_source_ok:
        print(f"  ** BOTH EMPTY **")

    if face_source_ok:
        return Mesh.from_vertices_and_faces(V2.tolist(), F2.tolist())
    if chain_ok:
        return Mesh.from_vertices_and_faces(V1.tolist(), F1.tolist())
    return targetgeometry

# Monkey-patch and re-run
sdm.SolidDifferenceModifier.apply_batch = staticmethod(patched_apply_batch)

floor_model2 = FloorModel(builder=builder)
floor_model2.add_support(column_size=220)
floor_model2.add_column(column_size=220)
floor_level = Translation.from_vector(Vector(0, 0, floor_model2.story_height))
floor_model2.add_floor_guide(guide, column_index=0, transformation=floor_level, include_oculus=True)
for i in range(1, 4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    floor_model2.add_floor_guide(guide, column_index=i, transformation=floor_level * rot, include_oculus=False)

print("=== Testing with fallback ===")
floor_model2.precompute_boolean_modifiers()
floor_model2.compute_contacts_inner_beams(tolerance=1.0, minimum_area=1.0)
print(f"\nfail_data captured: {'yes' if fail_data else 'no'}")

if fail_data:
    all_vf = fail_data["all_vf"]
    ops = fail_data["operations"]
    print(f"\nFailing case: {len(all_vf)} meshes, ops={ops}")
    for i, (v, f) in enumerate(all_vf):
        print(f"  mesh {i}: V={len(v)} F={len(f)}")

    # Test hybrid variant
    V_h, F_h = boolean_chain(all_vf, ops, hybrid=True)
    print(f"\nboolean_chain hybrid: V={V_h.shape[0]} F={F_h.shape[0]}")

    V_fsh, F_fsh, S_fsh = boolean_chain_with_face_source(all_vf, ops, hybrid=True)
    print(f"boolean_chain_with_face_source hybrid: V={V_fsh.shape[0]} F={F_fsh.shape[0]}")
