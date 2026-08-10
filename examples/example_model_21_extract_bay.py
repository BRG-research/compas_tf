import pathlib

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"
MODEL_FILE = data_dir / "cantilevers_baked_model.json"
BAY_FILE = data_dir / "bay_model.json"
BAY_STEP_FILE = data_dir / "bay_model.stp"

model: TFModel = compas.json_load(MODEL_FILE)

# Both groups at once: the contacts between them survive only if they come out
# together. neighbors= adds the fasteners, which live in their own groups.
bay = model.find_groups_with_names(["column_model_0", "quarter_model_0"], name="bay_0", neighbors=True)

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
bay.to_step(BAY_STEP_FILE)

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
