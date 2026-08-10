import pathlib

import compas
from compas.colors import Color
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


# Mirror the element tree instead of flattening it, so floor_model /
# quarters_model / quarter_model_0 / ... stays browsable in the scene.
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
    viewer.scene.add(contact.polygon, parent=group, facecolor=Color(1, 0, 0), linecolor=Color(1, 0, 0), show_points=False)

viewer.show()
