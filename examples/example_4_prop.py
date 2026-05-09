"""example_4_prop.py

Build and visualize 4-fold rotational schoring (prop/shoring) models
around the floor column positions, plus a central tower element.

Reads floorbuilder.json written by example_2_floor_model_booleans.py so that
the prop positions are driven by the same parametric geometry.
"""
import math
import pathlib
import sys

import compas
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

from compas_tf.schoring_element import Dataset
from compas_tf.schoring_element import SchoringElement
from compas_tf.tower_element import TowerElement
from compas_model.models import Model

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_model_to_viewer  # noqa: E402

SchoringElement.clear_cache()

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Prop positions from FloorBuilder
# ------------------------------------------------------------------ #

column_size = 200
prop_height = 2500
story_height = 3000
builder = compas.json_load(data_dir / "floorbuilder.json")
column_plan = builder.corner_point_column(column_size)

# ------------------------------------------------------------------ #
#  Schoring models (4-fold rotational symmetry)
# ------------------------------------------------------------------ #

schoring_models = []

model_scaffolding0 = SchoringElement.from_points_and_vectors(
    p0=Point(column_size / 2, 0, prop_height),
    v0=Vector(0, 0, 1),
    p1=Point(prop_height, 0, 0),
    v1=Vector(1, 0, 0),
    dataset_foot=Dataset.schoring_foot_0,
    dataset_head=Dataset.schoring_head_0,
    dataset_body0=Dataset.schoring_body_start_0,
    dataset_body1=Dataset.schoring_body_end_0,
)
model_scaffolding0.transformation *= Translation.from_vector(Vector(column_plan.x, column_plan.y, 0))

model_scaffolding1 = model_scaffolding0.copy()
model_scaffolding1.transformation = (
    Translation.from_vector(Vector(column_plan.x, column_plan.y, 0))
    * Rotation.from_axis_and_angle(Vector(0, 0, 1), math.pi / 2, Point(0, 0, 0))
)

for i in range(4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    m0 = model_scaffolding0.copy()
    m0.transformation = rot * m0.transformation
    schoring_models.append(m0)
    m1 = model_scaffolding1.copy()
    m1.transformation = rot * m1.transformation
    schoring_models.append(m1)

# Custom vertical prop (no foot/head) on each side
model_custom = SchoringElement.from_points_and_vectors_no_foot_no_head(
    p0=Point(0, column_plan.y, 0),
    v0=Vector(1, 0, 0),
    p1=Point(0, column_plan.y, story_height),
    v1=Vector(0, 1, 0),
    dataset_body0=Dataset.schoring_vertical_body_start_5,
    dataset_body1=Dataset.schoring_vertical_body_end_5,
    dataset_hat=Dataset.schoring_head_custom,
)
for i in range(4):
    m = model_custom.copy()
    m.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    schoring_models.append(m)

# Tower at origin
model_tower = Model("tower")
tower = TowerElement()
tower.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), math.pi / 4, Point(0, 0, 0))
model_tower.add_element(tower)
schoring_models.append(model_tower)

compas.json_dump(schoring_models, data_dir / "schoring_models.json")

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

for model in schoring_models:
    add_model_to_viewer(model, viewer)

viewer.show()
