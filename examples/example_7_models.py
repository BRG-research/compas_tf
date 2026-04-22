import sys
import pathlib

import compas
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401 — required for SchoringElement + FloorModel deserialization

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_model_to_viewer  # noqa: E402

# ------------------------------------------------------------------ #
#  Filepath
# ------------------------------------------------------------------ #
data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Load schoring models (written by example_4_prop)
# ------------------------------------------------------------------ #
schoring_models = compas.json_load(data_dir / "schoring_models.json")

# ------------------------------------------------------------------ #
#  Load floor model with supports + columns (written by example_3)
# ------------------------------------------------------------------ #
floor_model = compas.json_load(data_dir / "floor_model_elements.json")

# ------------------------------------------------------------------ #
#  Show in viewer
# ------------------------------------------------------------------ #
config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

add_model_to_viewer(floor_model.model, viewer)

for model in schoring_models:
    add_model_to_viewer(model, viewer)

viewer.show()
