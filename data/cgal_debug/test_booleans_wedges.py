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

print("=== First precompute (sherpa cutters on columns) ===")
floor_model.precompute_boolean_modifiers()

print("\n=== Contact detection + wedge placement ===")
floor_model.compute_contacts_inner_beams(tolerance=1.0, minimum_area=1.0)
contacts = list(floor_model.contacts())
print(f"[contact] {len(contacts)} contact(s) found")

print("\n=== Diagnosing empty boolean results ===")
from compas.datastructures import Mesh
from compas_tf.solid_difference_modifier import SolidDifferenceModifier, _triangulate_mesh
from compas_tf.solid_union_modifier import SolidUnionModifier
from compas_model.elements.group import Group
from compas_tf.joint_dowel import DowelElement
from compas_tf.wedge import WedgeElement
import numpy as np

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
                op = getattr(modifier, "operation", "difference")
                if isinstance(src_geom, Mesh) and (op == "union" or src_geom.is_closed()):
                    bool_sources.append((src_geom, op, getattr(source, "name", "?")))

    if not bool_sources:
        continue

    xform = element.modeltransformation
    geometry = element.elementgeometry.transformed(xform)
    if not isinstance(geometry, Mesh) or not geometry.is_closed():
        continue

    name = getattr(element, "name", "?")
    n_cutters = len(bool_sources)
    if n_cutters < 2:
        continue

    print(f"\n  Element: {name} (V={geometry.number_of_vertices()} F={geometry.number_of_faces()} closed={geometry.is_closed()})")
    for src_geom, op, src_name in bool_sources:
        print(f"    cutter: {src_name} op={op} V={src_geom.number_of_vertices()} F={src_geom.number_of_faces()} closed={src_geom.is_closed()}")

    # Try the chain
    from compas_cgal.booleans import boolean_chain_with_face_source
    all_vf = []
    for mesh in [geometry] + [s for s, _, _ in bool_sources]:
        verts, tris, _ = _triangulate_mesh(mesh)
        all_vf.append((verts, tris))
    operations = [op for _, op, _ in bool_sources]
    try:
        V, F, S = boolean_chain_with_face_source(all_vf, operations)
        if not V.size or not F.size:
            print(f"    RESULT: EMPTY!")
            # Try one-by-one
            print(f"    Testing individual cutters:")
            for i, (src_geom, op, src_name) in enumerate(bool_sources):
                from compas_cgal.booleans import boolean_difference_mesh_mesh
                T = geometry.to_vertices_and_faces(triangulated=True)
                C = src_geom.to_vertices_and_faces(triangulated=True)
                try:
                    Vr, Fr = boolean_difference_mesh_mesh(T, C)
                    print(f"      {src_name}: V={len(Vr)} F={len(Fr)}")
                except Exception as e2:
                    print(f"      {src_name}: FAILED {e2}")

            # Also try sequential
            print(f"    Testing sequential chain:")
            result_mesh = geometry
            for i, (src_geom, op, src_name) in enumerate(bool_sources):
                T = result_mesh.to_vertices_and_faces(triangulated=True)
                C = src_geom.to_vertices_and_faces(triangulated=True)
                try:
                    Vr, Fr = boolean_difference_mesh_mesh(T, C)
                    if not Vr.size or not Fr.size:
                        print(f"      step {i} ({src_name}): EMPTY")
                        break
                    result_mesh = Mesh.from_vertices_and_faces(Vr.tolist(), Fr.tolist())
                    print(f"      step {i} ({src_name}): V={len(Vr)} F={len(Fr)}")
                except Exception as e2:
                    print(f"      step {i} ({src_name}): FAILED {e2}")
                    break
        else:
            print(f"    RESULT: OK V={len(V)} F={len(F)}")
    except Exception as exc:
        print(f"    RESULT: EXCEPTION {exc}")

print("\n=== Checking wedge boolean results ===")
from compas_tf.plate import PlateElement
for element in floor_model.elements():
    if not isinstance(element, PlateElement):
        continue
    geom = element._modelgeometry
    if geom is None:
        continue
    name = getattr(element, "name", "?")
    nv = geom.number_of_vertices()
    nf = geom.number_of_faces()
    closed = geom.is_closed()
    if nv == 0 or nf == 0:
        print(f"  EMPTY: {name} V={nv} F={nf}")
    elif not closed:
        print(f"  OPEN:  {name} V={nv} F={nf}")

print("\n=== Done ===")
