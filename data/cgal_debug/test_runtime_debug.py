"""Reproduce the exact code path in precompute_boolean_modifiers for the failing element."""
import pathlib
import sys
import math
import numpy as np

from compas.geometry import Point, Rotation, Translation, Vector
from compas.datastructures import Mesh

sys.path.insert(0, str(pathlib.Path(r"C:\brg\code_python\compas_tf\examples")))
import compas_tf
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel
from compas_tf.solid_difference_modifier import SolidDifferenceModifier, _triangulate_mesh
from compas_model.elements.group import Group
from compas_tf.joint_dowel import DowelElement
from compas_tf.wedge import WedgeElement
from compas_cgal.booleans import boolean_chain_with_face_source, boolean_difference_mesh_mesh

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

# Run contacts but WITHOUT the second precompute — just add wedges
from compas_tf.plate import PlateElement
floor_model.compute_contacts_inner_beams(tolerance=1.0, minimum_area=1.0, wedge_spacing=0)

# Manually add wedges like _add_wedges_along_contacts does
from compas.geometry import Frame, Polygon as GeomPolygon, Transformation
from compas_tf.floor_model import merge_collinear_points

edge_contacts = []
for edge in floor_model.graph.edges():
    contacts = floor_model.graph.edge_attribute(edge, name="contacts")
    if contacts:
        u, v = edge
        el_a = floor_model.graph.node_element(u)
        el_b = floor_model.graph.node_element(v)
        for contact in contacts:
            edge_contacts.append((el_a, el_b, contact))

wedges_group = floor_model.add_group("contact_wedges_debug")
wedge_idx = 0
wedge_spacing = 700
first_fail_found = False

for el_a, el_b, contact in edge_contacts:
    polygon = getattr(contact, "polygon", None)
    if polygon is None:
        continue
    pts = list(polygon.points)
    pts = merge_collinear_points(pts, angle_tol=1e-3, closed=True)
    n_pts = len(pts)
    if n_pts < 3:
        continue
    contact_normal = GeomPolygon(pts).normal
    centroid_z = sum(p[2] for p in pts) / n_pts
    scored = []
    for i in range(n_pts):
        a, b = pts[i], pts[(i + 1) % n_pts]
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
        wedge.name = f"debug_wedge_{wedge_idx}"

        # Get the boolean geometry the same way precompute_boolean_modifiers would
        src_geom = getattr(wedge, "boolean_geometry", None) or wedge.modelgeometry

        # Get target geometry the same way
        for target_el in [el_a, el_b]:
            target_name = getattr(target_el, "name", "?")
            xform = target_el.modeltransformation
            target_geom = target_el.elementgeometry.transformed(xform)

            if not isinstance(target_geom, Mesh) or not target_geom.is_closed():
                continue
            if not isinstance(src_geom, Mesh) or not src_geom.is_closed():
                continue

            # Test the boolean directly (EPICK)
            T = target_geom.to_vertices_and_faces(triangulated=True)
            C = src_geom.to_vertices_and_faces(triangulated=True)
            V, F = boolean_difference_mesh_mesh(T, C)
            is_empty = V.shape[0] == 0

            if is_empty and not first_fail_found:
                first_fail_found = True
                print(f"\n=== FIRST FAILURE ===")
                print(f"Target: {target_name}")
                print(f"Cutter: debug_wedge_{wedge_idx}")
                print(f"Target V={len(T[0])} F={len(T[1])}")
                print(f"Cutter V={len(C[0])} F={len(C[1])}")

                # Dump triangulated data
                print(f"\nTarget vertices:")
                for i, v in enumerate(T[0]):
                    print(f"  {i}: {v}")
                print(f"\nTarget faces:")
                for i, f in enumerate(T[1]):
                    print(f"  {i}: {f}")

                # Now try loading from the same mesh as OBJ roundtrip
                target_geom.to_obj("debug_rt_target.obj")
                src_geom.to_obj("debug_rt_cutter.obj")
                t2 = Mesh.from_obj("debug_rt_target.obj")
                c2 = Mesh.from_obj("debug_rt_cutter.obj")
                T2 = t2.to_vertices_and_faces(triangulated=True)
                C2 = c2.to_vertices_and_faces(triangulated=True)
                V2, F2 = boolean_difference_mesh_mesh(T2, C2)
                print(f"\nOBJ roundtrip result: V={V2.shape[0]} F={F2.shape[0]}")

                print(f"\nRoundtrip target vertices:")
                for i, v in enumerate(T2[0]):
                    print(f"  {i}: {v}")
                print(f"\nRoundtrip target faces:")
                for i, f in enumerate(T2[1]):
                    print(f"  {i}: {f}")

                # Check if the triangulated data differs
                tv = np.array(T[0])
                tv2 = np.array(T2[0])
                if tv.shape == tv2.shape:
                    vdiff = np.abs(tv - tv2).max()
                    print(f"\nVertex max diff: {vdiff}")
                else:
                    print(f"\nVertex shapes differ: {tv.shape} vs {tv2.shape}")

                tf = np.array(T[1])
                tf2 = np.array(T2[1])
                if tf.shape == tf2.shape:
                    print(f"Face arrays equal: {np.array_equal(tf, tf2)}")
                    if not np.array_equal(tf, tf2):
                        for i in range(len(tf)):
                            if not np.array_equal(tf[i], tf2[i]):
                                print(f"  face {i}: {tf[i]} vs {tf2[i]}")
                else:
                    print(f"Face shapes differ: {tf.shape} vs {tf2.shape}")

        wedge_idx += 1
