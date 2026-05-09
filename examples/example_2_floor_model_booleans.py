"""example_2_floor_model_booleans.py

Build a FloorModel, run boolean cuts via precompute_boolean_modifiers(),
then run face-to-face contact detection and display contact polygons in red.
"""
import pathlib
import sys

import compas
from compas.colors import Color
from compas.geometry import Translation
from compas.geometry import Vector
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_model_to_viewer  # noqa: E402

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Parameters
# ------------------------------------------------------------------ #

column_size = 220

builder = FloorBuilder(
    size=3000,
    height=650,
    rise=453,
    oculus=1000,
    beam_w=40,
    column_head_offset=50,
    inner_thick=60,
    outer_thick=100,
    column_head_scale=250,
    column_head_inclination=0,
    head_h=500,
    head_b=100,
    head_o=141,
)

guide = FloorGuide(
    size_grid_x=3000,
    size_grid_y=3000,
    size_column_head=220,
    size_column_head_chamfer=120,
    size_outer_ribs=100,
    size_inner_ribs=60,
    size_inner_beams=60,
    height=650,
    rise=453,
    size_oculus=1000,
    size_wedge=120,
)


# ------------------------------------------------------------------ #
#  Build FloorModel
# ------------------------------------------------------------------ #

floor_model = FloorModel(builder=builder)

floor_model.add_support(column_size=column_size)
floor_model.add_column(column_size=column_size)

floor_level = Translation.from_vector(Vector(0, 0, floor_model.story_height))
floor_model.add_floor_guide(guide, column_index=0, transformation=floor_level)

# ------------------------------------------------------------------ #
#  Batch boolean cuts
# ------------------------------------------------------------------ #

floor_model.precompute_boolean_modifiers()

compas.json_dump(floor_model, data_dir / "floor_model_booleans.json")

# ------------------------------------------------------------------ #
#  Contact detection
# ------------------------------------------------------------------ #

floor_model.compute_contacts(tolerance=1.0, minimum_area=1.0)
contacts = list(floor_model.contacts())
print(f"[contact] {len(contacts)} contact(s) found")

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

add_model_to_viewer(floor_model, viewer)

g_contacts = viewer.scene.add_group("contacts")
for contact in contacts:
    viewer.scene.add(contact.polygon, facecolor=Color.red(), linecolor=Color.red(), parent=g_contacts)

viewer.show()
