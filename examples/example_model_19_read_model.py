import pathlib

import compas
from compas_viewer import Viewer

from compas_tf.model import TFModel

MODEL_FILE = pathlib.Path(__file__).parent.parent / "data" / "cantilevers_baked_model.json"

# Baked before it was written, so nothing is recomputed on load.
model: TFModel = compas.json_load(MODEL_FILE)

elements = list(model.geometry_elements())
contacts = list(model.contacts())
print(f"{len(elements)} elements, {len(contacts)} contacts")

viewer = Viewer()

parts = viewer.scene.add_group("model")
for element in elements:
    viewer.scene.add(element, name=element.name, parent=parts)

group = viewer.scene.add_group("contacts")
for contact in contacts:
    viewer.scene.add(contact.polygon, parent=group, facecolor=(1, 0, 0), linecolor=(1, 0, 0), show_points=False)

viewer.show()
