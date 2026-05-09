"""example_5_complete.py

Combined view: floor model (with boolean cuts) + schoring props.

Loads:
  - floor_model_booleans.json  written by example_2_floor_model_booleans.py
  - schoring_models.json       written by example_4_prop.py
"""
import pathlib
import sys

import compas
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401 — required for deserialization of TF types

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_model_to_viewer  # noqa: E402

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Load models
# ------------------------------------------------------------------ #

floor_model = compas.json_load(data_dir / "floor_model_booleans.json")
schoring_models = compas.json_load(data_dir / "schoring_models.json")

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

add_model_to_viewer(floor_model, viewer)
for model in schoring_models:
    add_model_to_viewer(model, viewer)

viewer.show()
