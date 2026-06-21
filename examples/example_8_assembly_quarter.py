"""example_7_assembly_quarter.py

Assembly sequence for one floor quarter: each plate group is offset
+300 mm higher than the previous so the layers appear stacked.

Assembly order:
  beds          → +0
  tsections     → +300
  outer_ribs    → +600
  inner_ribs    → +900
  wedge_block   → +1200
  wedges_column → +1500
  inner_beams   → +1800
  sherpas       → +2100
  oculus        → +2400  (highest / last)
"""

import pathlib

from compas.colors import Color
from compas.geometry import Translation
from compas.geometry import Vector

from compas_tf.floor_guide import FloorGuide
from compas_tf.joint_dowel import DowelElement
from compas_tf.plate import PlateElement
from compas_tf.viewer import make_viewer
from compas_tf.viewer import show_or_dump

data_dir = pathlib.Path(__file__).parent.parent / "data"

ASSEMBLY_OFFSET = 400  # mm vertical between each layer (> plate height 650)

guide = FloorGuide(
    size_grid_x=3000,
    size_grid_y=3000,
    size_column_head=250,
    size_column_head_chamfer=120,
    size_outer_ribs=100,
    size_inner_ribs=60,
    size_inner_beams=60,
    height=650,
    rise=453,
    size_oculus=1000,
)

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

viewer = make_viewer(data_dir)


def add_plates_offset(group_name, plates, facecolor, step):
    offset = Translation.from_vector(Vector(0, 0, step * ASSEMBLY_OFFSET))
    g = viewer.scene.add_group(group_name)
    for i, plate in enumerate(plates):
        if isinstance(plate, DowelElement):
            continue
        if not isinstance(plate, PlateElement):
            continue
        mesh = plate.elementgeometry.transformed(offset)
        pg = viewer.scene.add_group(f"{group_name}_{i}", parent=g)
        pg.add(mesh, facecolor=facecolor, show_lines=False)
        if plate.top_polyline:
            pg.add(plate.top_polyline.transformed(offset), linecolor=Color.black())
        if plate.bottom_polyline:
            pg.add(plate.bottom_polyline.transformed(offset), linecolor=Color.black())


sections = [
    ("wedge_block", guide.wedge_block, Color.yellow()),
    ("tsections", guide.tsections, Color.orange()),
    ("outer_ribs", guide.outer_ribs, Color.yellow()),
    ("inner_ribs", guide.inner_ribs, Color.yellow()),
    ("wedges_inner_beams", guide.wedges_inner_beams, Color.cyan()),
    ("inner_beams", guide.inner_beams, Color.yellow()),
    ("beds", guide.beds, Color.lime()),
]

for step, (name, plates, color) in enumerate(sections):
    add_plates_offset(name, plates, color, step)

# Oculus — last / highest
add_plates_offset("oculus", guide.oculus, Color.blue(), len(sections) + 1)

show_or_dump(viewer, data_dir)
