"""Dump exact runtime cutter vertices and test the combination."""
import pathlib
import sys
import math
import numpy as np

from compas.geometry import Point, Rotation, Translation, Vector, Frame, Transformation
from compas.datastructures import Mesh

sys.path.insert(0, str(pathlib.Path(r"C:\brg\code_python\compas_tf\examples")))
import compas_tf
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel, merge_collinear_points
from compas_tf.solid_difference_modifier import _triangulate_mesh
from compas_tf.wedge import WedgeElement
from compas.geometry import Polygon as GeomPolygon
from compas_cgal.booleans import boolean_difference_mesh_mesh, boolean_chain

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

# Find first contact and create a wedge manually
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
n = round(length / (wedge_spacing / 2))
n = n if n % 2 == 0 else n + 1
new_spacing = length / n

k = 1  # first wedge position
pt = start + direction * (new_spacing * k)
frame = Frame(pt, direction, contact_normal)

print(f"Wedge frame origin: {pt}")
print(f"Wedge frame xaxis: {direction}")
print(f"Wedge frame yaxis: {contact_normal}")

wedge = WedgeElement(transformation=Transformation.from_frame(frame))
cutter_geom = wedge.boolean_geometry

# Get target geometry
target_el = el_a
target_name = getattr(target_el, "name", "?")
xform = target_el.modeltransformation
target_geom = target_el.elementgeometry.transformed(xform)

print(f"\nTarget: {target_name}")
print(f"Target closed={target_geom.is_closed()} V={target_geom.number_of_vertices()} F={target_geom.number_of_faces()}")
print(f"Cutter closed={cutter_geom.is_closed()} V={cutter_geom.number_of_vertices()} F={cutter_geom.number_of_faces()}")

# Get the triangulated data as apply_batch would
tv, tt, _ = _triangulate_mesh(target_geom)
cv, ct, _ = _triangulate_mesh(cutter_geom)

print(f"\n=== Test via _triangulate_mesh (apply_batch path) ===")
print(f"target: {len(tv)} verts, {len(tt)} tris")
print(f"cutter: {len(cv)} verts, {len(ct)} tris")

# EPECK chain (what apply_batch actually calls)
V, F = boolean_chain([(tv, tt), (cv, ct)], ["difference"])
print(f"EPECK chain: V={V.shape[0]} F={F.shape[0]}")

# EPICK
V2, F2 = boolean_difference_mesh_mesh((tv, tt), (cv, ct))
print(f"EPICK: V={V2.shape[0]} F={F2.shape[0]}")

# Now try with to_vertices_and_faces (different triangulation path)
print(f"\n=== Test via to_vertices_and_faces ===")
T = target_geom.to_vertices_and_faces(triangulated=True)
C = cutter_geom.to_vertices_and_faces(triangulated=True)
V3, F3 = boolean_difference_mesh_mesh(T, C)
print(f"EPICK: V={V3.shape[0]} F={F3.shape[0]}")
V4, F4 = boolean_chain([T, C], ["difference"])
print(f"EPECK chain: V={V4.shape[0]} F={F4.shape[0]}")

# Check: are the cutter vertices clean or dirty?
cv_arr = np.array(cv)
print(f"\nCutter vertex stats:")
print(f"  x range: [{cv_arr[:,0].min():.15f}, {cv_arr[:,0].max():.15f}]")
print(f"  y range: [{cv_arr[:,1].min():.15f}, {cv_arr[:,1].max():.15f}]")
print(f"  z range: [{cv_arr[:,2].min():.15f}, {cv_arr[:,2].max():.15f}]")

# Compare cutter vertices with OBJ-loaded version
cutter_geom.to_obj("debug_rt_cutter2.obj")
c_clean = Mesh.from_obj("debug_rt_cutter2.obj")
cv_clean, ct_clean, _ = _triangulate_mesh(c_clean)
cv_clean_arr = np.array(cv_clean)
cv_arr2 = np.array(cv)
diff = np.abs(cv_arr2 - cv_clean_arr)
print(f"\nCutter vertex diff after OBJ roundtrip: max={diff.max():.15e}")
print(f"  x max diff: {diff[:,0].max():.15e}")
print(f"  y max diff: {diff[:,1].max():.15e}")
print(f"  z max diff: {diff[:,2].max():.15e}")

# Try: runtime target + clean cutter
print(f"\n=== Mixed: dirty target + clean (roundtripped) cutter ===")
V5, F5 = boolean_difference_mesh_mesh((tv, tt), (cv_clean, ct_clean))
print(f"EPICK: V={V5.shape[0]} F={F5.shape[0]}")

# Try: clean target + runtime cutter
tv_clean, tt_clean, _ = _triangulate_mesh(Mesh.from_obj("debug_rt_target.obj") if False else target_geom)
target_geom.to_obj("debug_rt_target2.obj")
t_clean = Mesh.from_obj("debug_rt_target2.obj")
tv_clean, tt_clean, _ = _triangulate_mesh(t_clean)
print(f"\n=== Mixed: clean target + dirty cutter ===")
V6, F6 = boolean_difference_mesh_mesh((tv_clean, tt_clean), (cv, ct))
print(f"EPICK: V={V6.shape[0]} F={F6.shape[0]}")
