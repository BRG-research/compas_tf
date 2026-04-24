import math
import pathlib
import compas
from compas_viewer import Viewer
from compas_tf.schoring_element import SchoringElement
from compas_tf.schoring_element import Dataset

# Clear caches to avoid stale data issues
SchoringElement.clear_cache()
from compas_tf.tower_element import TowerElement
from compas_model.models import Model
from compas.geometry import Translation
from compas.geometry import Rotation
from compas.geometry import Vector
from compas.geometry import Point
from compas_viewer.config import Config

from model import add_model_to_viewer  # noqa: E402

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Models
# ------------------------------------------------------------------ #
schoring_models = []

# ------------------------------------------------------------------ #
#  Floor parameters — drive prop positioning from FloorBuilder
# ------------------------------------------------------------------ #

column_size = 200
prop_height = 2500
story_height = 3000
builder = compas.json_load(data_dir / "floorbuilder.json")
column_plan = builder.corner_point_column(column_size)  # e.g. (-2940, -2940, 0)
offset_from_corner = column_size / 2  # small clearance from column face

# ------------------------------------------------------------------ #
#  Create shoring model
# ------------------------------------------------------------------ #

model_scaffolding0 = SchoringElement.from_points_and_vectors(
    p0=Point(offset_from_corner, 0, prop_height),
    v0=Vector(0, 0, 1),
    p1=Point(prop_height, 0, 0),
    v1=Vector(1, 0, 0),
    dataset_foot=Dataset.schoring_foot_0,
    dataset_head=Dataset.schoring_head_0,
    dataset_body0=Dataset.schoring_body_start_0,
    dataset_body1=Dataset.schoring_body_end_0
)

model_scaffolding0.transformation *= Translation.from_vector(Vector(column_plan.x, column_plan.y, 0))
model_scaffolding1 = model_scaffolding0.copy()
model_scaffolding1.transformation = Translation.from_vector(Vector(column_plan.x, column_plan.y, 0)) * Rotation.from_axis_and_angle(Vector(0, 0, 1), math.pi / 2, Point(0, 0, 0))


model_scaffolding = Model()
for i in range(4):
    model_rotated0 = model_scaffolding0.copy()
    model_rotated0.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0)) * model_rotated0.transformation
    schoring_models.append(model_rotated0)
    model_rotated1 = model_scaffolding1.copy()
    model_rotated1.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0)) * model_rotated1.transformation
    schoring_models.append(model_rotated1)

# ------------------------------------------------------------------ #
#  Tower element at origin, rotated 45° around Z (XY plane)
# ------------------------------------------------------------------ #

model_tower = Model("tower")
tower = TowerElement()
tower.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), math.pi / 4, Point(0, 0, 0))
model_tower.add_element(tower)
schoring_models.append(model_tower)

# ------------------------------------------------------------------ #
#  Prop with custom head shape
# ------------------------------------------------------------------ #

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
    model_rotated = model_custom.copy()
    model_rotated.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    schoring_models.append(model_rotated)

# ------------------------------------------------------------------ #
#  Write models to file
# ------------------------------------------------------------------ #

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