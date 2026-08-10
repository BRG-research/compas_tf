import pathlib
from collections import Counter

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.connectors import ConnectorElement
from compas_tf.connectors import DowelCylinderElement
from compas_tf.model import TFModel
from compas_tf.viewer import zoom_to

data_dir = pathlib.Path(__file__).parent.parent / "data"
MODEL_FILE = data_dir / "cantilevers_baked_model.json"  # the file example_model_19 reads
BAY_FILE = data_dir / "bay_model.json"

model: TFModel = compas.json_load(MODEL_FILE)

# What mounts this cantilever on its column. The wedges and their bolts are
# inner-beam hardware and the outer-rib connectors join one quarter to the next,
# so neither is here. Put a type back and it comes back with it.
FASTENERS = (
    ConnectorElement,
    DowelCylinderElement,
)

# Both groups in one call: the contacts BETWEEN them survive only if they come
# out together. The fastener groups hold all four bays' hardware and cannot be
# named, so neighbors= takes this bay's own - by contact, and by bounding box for
# the dowels, which have no graph edge because the contact search skipped them.
# Types, not True: True also admits the quarters next door and the oculus.
bay = model.find_groups_with_names(
    ["column_model_0", "quarter_model_0"],
    name="bay_0",
    neighbors=FASTENERS,
)

whole = Counter(type(element).__name__ for element in model.geometry_elements())
part = Counter(type(element).__name__ for element in bay.geometry_elements())

print(f"bay_0: {sum(part.values())} of {sum(whole.values())} elements, {len(list(bay.contacts()))} of {len(list(model.contacts()))} contacts")
for kind, count in part.most_common():
    print(f"  {count:4d} of {whole[kind]:4d}  {kind}")


# The same tree pruned to what the bay contains, not a bag of parts.
def print_tree(node, depth=0):
    for child in node.children:
        element = child.element
        if not isinstance(element, Group):
            continue
        parts = sum(1 for n in child.descendants if not isinstance(n.element, Group))
        print(f"{'  ' * depth}{element.name}  ({parts} parts)")
        print_tree(child, depth + 1)


print_tree(bay.tree.root)

# Fresh guids, source untouched: a model in its own right.
compas.json_dump(bay, BAY_FILE)

viewer = Viewer()


def add_tree(node, parent=None):
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=parent))
        elif element.modelgeometry is not None:
            viewer.scene.add(element, name=element.name, parent=parent)


add_tree(bay.tree.root)

# The camera's far plane is 1000 mm, so without this the bay starts clipped.
zoom_to(viewer, [element.aabb for element in bay.geometry_elements()])

viewer.show()
