import pathlib

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"
MODEL_FILE = data_dir / "cantilevers_baked_model.json"
BAY_FILE = data_dir / "bay_model.json"

# The model example_model_19 reads, with the hierarchy it prints. The bay is
# lifted out of that hierarchy by name, not rebuilt from geometry.
model: TFModel = compas.json_load(MODEL_FILE)

# One column and the one cantilever it carries - columns_model/column_model_0
# and floor_model/quarters_model/quarter_model_0, whole groups, nothing else.
# Both at once: the contacts BETWEEN them survive only if the two come out
# together.
bay = model.find_groups_with_names(["column_model_0", "quarter_model_0"], name="bay_0")

elements = list(bay.geometry_elements())
print(f"{len(elements)} of {len(list(model.geometry_elements()))} elements, {len(list(bay.contacts()))} contacts")


# Each group keeps its place in the tree, so the bay is not a bag of parts - it
# is still floor_model / quarters_model / quarter_model_0 / beds_0 / ..., only
# pruned to what the bay contains. Printing it is the proof the extraction kept
# the structure.
def print_tree(node, depth=0):
    for child in node.children:
        element = child.element
        if not isinstance(element, Group):
            continue
        parts = sum(1 for n in child.descendants if not isinstance(n.element, Group))
        print(f"{'  ' * depth}{element.name}  ({parts} parts)")
        print_tree(child, depth + 1)


print_tree(bay.tree.root)

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

viewer.show()
