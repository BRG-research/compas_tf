import pathlib

import compas
from compas.colors import Color
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

GREY = Color(0.85, 0.85, 0.85)

# The whole assembled structure, for the row at the top of the part list:
# every carved solid of the cantilevers model in place, in one file set.
model: TFModel = compas.json_load(data_dir / "cantilevers_model.json")

elements = [element for element in model.geometry_elements() if element.modelgeometry is not None]
parts = []
for element in elements:
    solid = element.modelgeometry
    solid.name = element.name
    parts.append(solid)

preview = parts[0].copy()
for mesh in parts[1:]:
    preview.join(mesh)

box = preview.aabb()
print(f"model_0: {len(parts)} solids, {box.xsize:.0f} x {box.ysize:.0f} x {box.zsize:.0f}")

write_parts(parts, fab_dir, "model_0", preview=preview)

viewer = Viewer()
for part in parts:
    viewer.scene.add(part, name=part.name, facecolor=GREY)
zoom_to(viewer, [element.aabb for element in elements])
viewer.show()
