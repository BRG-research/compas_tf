import math
import pathlib

import compas
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Vector

from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.floor_guide import FloorGuide

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the FloorGuide and column_model written by an earlier example
# ------------------------------------------------------------------ #

guide: FloorGuide = compas.json_load(data_dir / "floorguide.json")
column_model: TFModel = compas.json_load(data_dir / "column_model.json")

# ------------------------------------------------------------------ #
# Create a columns_model by placing four columns at the grid corners
# ------------------------------------------------------------------ #

column_models = []
for i in range(4):
    copy = column_model.duplicate()
    copy.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0)) * copy.transformation

    # Change names
    copy.name = f"column_model_{i}"
    for element in copy.elements():
        element.name = f"{element.name}_{i}"

    column_models.append(copy)

columns_model = TFModel(name="columns_model").merge(column_models)

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(columns_model, data_dir / "columns_model.json")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #

viewer = Viewer()
for cm in column_models:
    g = viewer.scene.add_group(cm.name)
    for element in cm.elements():
        if element.modelgeometry is not None:
            g.add(element, name=element.name, color=(0.9, 0.9, 0.9))
viewer.show()
