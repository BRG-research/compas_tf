import sys
import pathlib

import compas
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401
from compas_tf.floor_model import FloorModel
from compas_tf.floor_builder import FloorBuilder

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_model_to_viewer  # noqa: E402

# ------------------------------------------------------------------ #
#  Filepath
# ------------------------------------------------------------------ #
data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Load builder, create FloorModel
# ------------------------------------------------------------------ #

builder = compas.json_load(data_dir / "floorbuilder.json")
floor_model = FloorModel(builder=builder)
session = floor_model.model

# ------------------------------------------------------------------ #
#  Add groups
# ------------------------------------------------------------------ #

supports_group = session.add_group("supports")
columns_group = session.add_group("columns")
column_heads_group = session.add_group("column_heads")
quarters_group = session.add_group("quarters")
oculus_group = session.add_group("oculus")

compas.json_dump(floor_model, data_dir / "floor_model.json")

# ------------------------------------------------------------------ #
#  Show in viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

add_model_to_viewer(session, viewer)

viewer.show()
