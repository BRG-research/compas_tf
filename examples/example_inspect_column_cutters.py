"""Inspect the column-head cutter plates in the viewer WITHOUT any boolean.

Shows only the 4 columns (gray) and the column-head cutter plates
(``guide.column_cutters``) drawn in bright orange with edges, so the plates are
easy to see against the columns. No boolean is run — the plates are drawn
directly from their ``elementgeometry``.
"""

import math
import pathlib
import sys

from compas.colors import Color
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401
from compas_tf.column import ColumnElement
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel

sys.path.insert(0, str(pathlib.Path(__file__).parent))

# ------------------------------------------------------------------ #
#  Parameters (same as example_2)
# ------------------------------------------------------------------ #

column_size = 220

guide = FloorGuide(
    size_grid_x=3000, size_grid_y=3000, size_column_head=220,
    size_column_head_chamfer=120, size_outer_ribs=100, size_inner_ribs=60,
    size_inner_beams=60, height=650, rise=453, size_oculus=1000, size_wedge=240,
)

# ------------------------------------------------------------------ #
#  Build only the columns (no floor plates, no boolean)
# ------------------------------------------------------------------ #

floor_model = FloorModel(guide=guide)
floor_model.add_column(column_size=column_size)
floor_level = Translation.from_vector(Vector(0, 0, floor_model.story_height))

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

# Columns (gray, raw — uncut)
columns_group = viewer.scene.add_group("columns")
for col in floor_model.find_all_elements_of_type(ColumnElement):
    mesh = col.elementgeometry.transformed(col.modeltransformation)
    columns_group.add(mesh, name=col.name, facecolor=Color(0.8, 0.8, 0.8), opacity=0.5)

# Cutter plates (bright orange + edges) — one fan per quarter
ORANGE = Color(1.0, 0.45, 0.0)
cutters_group = viewer.scene.add_group("column_cutter_plates")
for q in range(4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), q * math.pi / 2, Point(0, 0, 0))
    xform = floor_level * rot
    qgroup = viewer.scene.add_group(f"quarter_{q}", parent=cutters_group)
    for i, plate in enumerate(guide.column_cutters):
        mesh = plate.elementgeometry.transformed(xform)
        qgroup.add(
            mesh,
            name=f"cutter_{i}",
            facecolor=ORANGE,
            linecolor=Color(0.4, 0.15, 0.0),
            show_lines=True,
            linewidth=2,
        )

viewer.show()
