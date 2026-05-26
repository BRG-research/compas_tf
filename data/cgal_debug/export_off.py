"""Export the exact dirty meshes as OFF files with full double precision."""
import pathlib, sys, math
from compas.geometry import Point, Rotation, Translation, Vector, Frame, Transformation
from compas.datastructures import Mesh
from compas.geometry import Polygon as GeomPolygon

sys.path.insert(0, str(pathlib.Path(r"C:\brg\code_python\compas_tf\examples")))
import compas_tf
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel, merge_collinear_points
from compas_tf.wedge import WedgeElement

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

DT = dirty_target.to_vertices_and_faces(triangulated=True)
DC = dirty_cutter.to_vertices_and_faces(triangulated=True)


def write_off(path, verts, faces):
    with open(path, "w") as f:
        f.write("OFF\n")
        f.write(f"{len(verts)} {len(faces)} 0\n")
        for v in verts:
            f.write(f"{v[0]:.18e} {v[1]:.18e} {v[2]:.18e}\n")
        for face in faces:
            f.write(f"3 {face[0]} {face[1]} {face[2]}\n")


out_dir = pathlib.Path(r"C:\brg\code_python\compas_tf\data\cgal_debug")
write_off(out_dir / "dirty_target.off", DT[0], DT[1])
write_off(out_dir / "dirty_cutter.off", DC[0], DC[1])
print(f"Exported dirty_target.off ({len(DT[0])}V {len(DT[1])}F)")
print(f"Exported dirty_cutter.off ({len(DC[0])}V {len(DC[1])}F)")
