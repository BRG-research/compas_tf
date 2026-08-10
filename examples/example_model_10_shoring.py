import math
import pathlib

import compas
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.floor_guide import FloorGuide
from compas_tf.model import TFModel
from compas_tf.schoring_element import Dataset
from compas_tf.schoring_element import SchoringElement
from compas_tf.tower_element import TowerElement

SchoringElement.clear_cache()

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Prop positions from FloorGuide
# ------------------------------------------------------------------ #

column_size = 220
prop_height = 2500  # height of the inclined props
story_height = 3200  # height of the custom vertical props (below the floor)
guide: FloorGuide = compas.json_load(data_dir / "floorguide.json")
column_plan = guide.corner_point_column(column_size)

# ------------------------------------------------------------------ #
#  Schoring sub-models (4-fold rotational symmetry)
# ------------------------------------------------------------------ #

submodels = []

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

model_scaffolding1 = model_scaffolding0.duplicate()
model_scaffolding1.transformation = Translation.from_vector(Vector(column_plan.x, column_plan.y, 0)) * Rotation.from_axis_and_angle(Vector(0, 0, 1), math.pi / 2, Point(0, 0, 0))

# .duplicate() gives independent copies (new guids) so the sub-models can merge.
for i in range(4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    m0 = model_scaffolding0.duplicate()
    m0.transformation = rot * m0.transformation
    submodels.append(m0)
    m1 = model_scaffolding1.duplicate()
    m1.transformation = rot * m1.transformation
    submodels.append(m1)

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
    m = model_custom.duplicate()
    m.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    submodels.append(m)

# Tower at origin
model_tower = TFModel("tower")
tower = TowerElement()
tower.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), math.pi / 4, Point(0, 0, 0))
model_tower.add_element(tower)
submodels.append(model_tower)

# ------------------------------------------------------------------ #
#  Merge into one shoring_model (unique group names so the tree is clean)
# ------------------------------------------------------------------ #

prop_index = 0
for sm in submodels:
    if sm.name != "tower":
        sm.name = f"prop_{prop_index}"
        prop_index += 1

shoring_model = TFModel(name="shoring_model").merge(submodels)

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(shoring_model, data_dir / "shoring_model.json")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #


def add_tree(node, viewer_parent):
    """Mirror the model tree into the viewer, preserving the group hierarchy."""
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=viewer_parent))
        else:
            if element.modelgeometry is not None:
                viewer.scene.add(element, name=element.name, parent=viewer_parent, color=(0.85, 0.85, 0.85))


viewer = Viewer()
add_tree(shoring_model.tree.root, None)
viewer.show()
