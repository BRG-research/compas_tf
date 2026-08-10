import pathlib

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.model import TFModel

MODEL_FILE = pathlib.Path(__file__).parent.parent / "data" / "cantilevers_baked_model.json"

# Baked before it was written, so nothing is recomputed on load.
model: TFModel = compas.json_load(MODEL_FILE)

elements = list(model.geometry_elements())
contacts = list(model.contacts())
print(f"{len(elements)} elements, {len(contacts)} contacts")

viewer = Viewer()


# The element tree is the building's table of contents - floor_model /
# quarters_model / quarter_model_0 / beds_0 / ..., columns_model, oculus_model.
# Mirror it into the scene instead of flattening, so it stays browsable.
def add_tree(node, parent=None):
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=parent))
        elif element.modelgeometry is not None:
            viewer.scene.add(element, name=element.name, parent=parent)


add_tree(model.tree.root)

group = viewer.scene.add_group("contacts")
for contact in contacts:
    viewer.scene.add(contact.polygon, parent=group, facecolor=(1, 0, 0), linecolor=(1, 0, 0), show_points=False)

viewer.show()
