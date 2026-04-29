import sys
import pathlib

import compas
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401 — required for FloorModel deserialization

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_model_to_viewer  # noqa: E402
from compas_tf.floor_model import FloorModel

# ------------------------------------------------------------------ #
#  Filepath
# ------------------------------------------------------------------ #
data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Models
# ------------------------------------------------------------------ #
models = []

# ------------------------------------------------------------------ #
#  Load floor model with supports + columns (written by example_3)
# ------------------------------------------------------------------ #
floor_model : FloorModel = compas.json_load(data_dir / "floor_model_elements.json")
models.append(floor_model)

# ------------------------------------------------------------------ #
#  Load schoring models (written by example_4_prop)
# ------------------------------------------------------------------ #
# schoring_models : list = compas.json_load(data_dir / "schoring_models.json")
# models.extend(schoring_models)

# ------------------------------------------------------------------ #
#  Create floor model
# ------------------------------------------------------------------ #

floor_model.add_floor_block()
floor_model.add_column_cutter()
floor_model.add_sherpa_joints()
floor_model.add_ribs()
floor_model.add_boundaries()
floor_model.add_wedges()

# ------------------------------------------------------------------ #
#  Write to file
# ------------------------------------------------------------------ #

compas.json_dump(floor_model, data_dir / "floor_model_elements_floor.json")

# ------------------------------------------------------------------ #
#  Show in viewer
# ------------------------------------------------------------------ #
config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

for model in models:
    add_model_to_viewer(model, viewer)
viewer.show()
