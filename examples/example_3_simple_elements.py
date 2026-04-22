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
#  Load FloorModel written by example_2
# ------------------------------------------------------------------ #

floor_model = compas.json_load(data_dir / "floor_model.json")

# ------------------------------------------------------------------ #
#  Add supports and columns
# ------------------------------------------------------------------ #

floor_model.add_support()
floor_model.add_column()

# ------------------------------------------------------------------ #
#  Write to file
# ------------------------------------------------------------------ #

compas.json_dump(floor_model, data_dir / "floor_model_elements.json")

# ------------------------------------------------------------------ #
#  Show in viewer
# ------------------------------------------------------------------ #

session = floor_model.model
config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

add_model_to_viewer(session, viewer)

viewer.show()
