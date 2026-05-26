import pathlib
import sys
import math

import compas
from compas.geometry import Point, Rotation, Translation, Vector

sys.path.insert(0, str(pathlib.Path(r"C:\brg\code_python\compas_tf\examples")))
import compas_tf
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel
from compas.datastructures import Mesh
from compas_tf.solid_difference_modifier import SolidDifferenceModifier
from compas_model.elements.group import Group
from compas_tf.joint_dowel import DowelElement
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
floor_model.compute_contacts_inner_beams(tolerance=1.0, minimum_area=1.0)

def bbox(mesh):
    xs = [mesh.vertex_coordinates(v)[0] for v in mesh.vertices()]
    ys = [mesh.vertex_coordinates(v)[1] for v in mesh.vertices()]
    zs = [mesh.vertex_coordinates(v)[2] for v in mesh.vertices()]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

# Find the first failing case and dump geometry
found = False
for element in floor_model.elements():
    if isinstance(element, (Group, DowelElement, WedgeElement)):
        continue

    bool_sources = []
    for nbr in floor_model.graph.neighbors_in(element.graphnode):
        modifiers = floor_model.graph.edge_attribute((nbr, element.graphnode), name="modifiers") or []
        source = floor_model.graph.node_element(nbr)
        for modifier in modifiers:
            if isinstance(modifier, SolidDifferenceModifier):
                src_geom = getattr(source, "boolean_geometry", None) or source.modelgeometry
                if isinstance(src_geom, Mesh) and src_geom.is_closed():
                    bool_sources.append((src_geom, getattr(source, "name", "?")))

    if len(bool_sources) < 2:
        continue

    xform = element.modeltransformation
    geometry = element.elementgeometry.transformed(xform)
    if not isinstance(geometry, Mesh) or not geometry.is_closed():
        continue

    from compas_cgal.booleans import boolean_difference_mesh_mesh
    T = geometry.to_vertices_and_faces(triangulated=True)
    C = bool_sources[0][0].to_vertices_and_faces(triangulated=True)
    Vr, Fr = boolean_difference_mesh_mesh(T, C)
    if Vr.size == 0:
        name = getattr(element, "name", "?")
        print(f"\nFailing element: {name}")
        bmin, bmax = bbox(geometry)
        print(f"  target bbox: ({bmin[0]:.1f}, {bmin[1]:.1f}, {bmin[2]:.1f}) -> ({bmax[0]:.1f}, {bmax[1]:.1f}, {bmax[2]:.1f})")
        size = (bmax[0]-bmin[0], bmax[1]-bmin[1], bmax[2]-bmin[2])
        print(f"  target size: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f}")

        for src_geom, src_name in bool_sources:
            bmin, bmax = bbox(src_geom)
            print(f"  cutter '{src_name}' bbox: ({bmin[0]:.1f}, {bmin[1]:.1f}, {bmin[2]:.1f}) -> ({bmax[0]:.1f}, {bmax[1]:.1f}, {bmax[2]:.1f})")
            size = (bmax[0]-bmin[0], bmax[1]-bmin[1], bmax[2]-bmin[2])
            print(f"  cutter size: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.1f}")

        # Export to OBJ for visual inspection
        data_dir = pathlib.Path(r"C:\brg\code_python\compas_tf\data\cgal_debug")
        geometry.to_obj(str(data_dir / "fail_target.obj"))
        for i, (src_geom, src_name) in enumerate(bool_sources):
            src_geom.to_obj(str(data_dir / f"fail_cutter_{i}_{src_name}.obj"))
        print(f"\n  Exported to cgal_debug/fail_target.obj and fail_cutter_*.obj")
        found = True
        break

if not found:
    print("No failures found")
