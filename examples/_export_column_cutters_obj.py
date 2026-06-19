"""Export every column (WITH merged capitel boolean-union features) and every
column-cutter source to OBJ, for debugging the column boolean in another app.

Output folder: examples/obj_export/  (columns + cutters only)
  column_<i>.obj        - column i target solid, capitel union included, model space
  cut_column_<i>_<...>.obj - each difference-cutter source registered on column i
"""
import math
import pathlib

from compas.datastructures import Mesh
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector

from compas_tf.column import ColumnElement
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel
from compas_tf.solid_difference_modifier import SolidDifferenceModifier

out_dir = pathlib.Path(__file__).parent / "obj_export"
out_dir.mkdir(exist_ok=True)

column_size = 220
builder = FloorBuilder(size=3000, height=650, rise=453, oculus=1000, beam_w=40,
                       column_head_offset=50, inner_thick=60, outer_thick=100,
                       column_head_scale=250, column_head_inclination=0,
                       head_h=500, head_b=100, head_o=141)
guide = FloorGuide(size_grid_x=3000, size_grid_y=3000, size_column_head=220,
                   size_column_head_chamfer=120, size_outer_ribs=100,
                   size_inner_ribs=60, size_inner_beams=60, height=650,
                   rise=453, size_oculus=1000, size_wedge=240)

fm = FloorModel(builder=builder)
fm.add_support(column_size=column_size)
fm.add_column(column_size=column_size)
floor_level = Translation.from_vector(Vector(0, 0, fm.story_height))
fm.add_floor_guide(guide, column_index=0, transformation=floor_level, include_oculus=True)
for i in range(1, 4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    fm.add_floor_guide(guide, column_index=i, transformation=floor_level * rot, include_oculus=False)

columns_by_index = {int(c.name.split("_")[-1]): c for c in fm.find_all_elements_of_type(ColumnElement)}

# Sanity: a plain column box is 8/6; with the capitel union it is more.
probe = columns_by_index[0]
print(f"box-only:        V/F={probe.box.to_mesh(True).number_of_vertices()}/{probe.box.to_mesh(True).number_of_faces()}")
print(f"with features:   V/F={probe.compute_elementgeometry(include_features=True).number_of_vertices()}/{probe.compute_elementgeometry(include_features=True).number_of_faces()}")

for idx, col in sorted(columns_by_index.items()):
    # TARGET solid exactly as fed to CGAL: capitel union included, in model space.
    target = col.compute_elementgeometry(include_features=True).transformed(col.modeltransformation)
    target.to_obj(str(out_dir / f"column_{idx}.obj"))
    print(f"column_{idx}: V/F={target.number_of_vertices()}/{target.number_of_faces()} closed={target.is_closed()}")

    k = 0
    for nbr in fm.graph.neighbors_in(col.graphnode):
        mods = fm.graph.edge_attribute((nbr, col.graphnode), name="modifiers") or []
        src = fm.graph.node_element(nbr)
        if not any(isinstance(m, SolidDifferenceModifier) for m in mods):
            continue
        sg = src.modelgeometry
        if not isinstance(sg, Mesh):
            continue
        name = getattr(src, "name", "src") or "src"
        # Prefix with k so same-named cutters (e.g. the 3 "PlateElement" sherpas)
        # don't overwrite each other.
        sg.to_obj(str(out_dir / f"cut_col{idx}_{k}_{name}.obj"))
        k += 1

print(f"\nwrote OBJs to {out_dir}")
