import pathlib
from collections import Counter

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"
MODEL_FILE = data_dir / "cantilevers_baked_model.json"  # the file example_model_19 reads
BAY_FILE = data_dir / "bay_model.json"

model: TFModel = compas.json_load(MODEL_FILE)

# A bay is one column and the one quarter it carries, plus the hardware that
# bolts the two together.
#
# Only the two structural groups are named, and both in one call - the contacts
# BETWEEN a column and its quarter survive only if the two come out together.
#
# The fasteners are deliberately NOT named: `connectors`, `connector_cylinders`
# and `outer_rib_connectors` are top-level groups holding the hardware of all
# four bays, so asking for them by name would drag in the other three.
# neighbors=True takes only the ones belonging here - first everything with a
# contact to something already inside, then, for the dowels and cylinders the
# contact search skipped and which therefore have no edge to follow, everything
# whose bounding box lands in the bay.
bay = model.find_groups_with_names(
    ["column_model_0", "quarter_model_0"],
    name="bay_0",
    neighbors=True,
)

# What came out, against what the whole building holds. The fastener rows are
# the ones to read: the bay takes its own share, not all of them.
whole = Counter(type(element).__name__ for element in model.geometry_elements())
part = Counter(type(element).__name__ for element in bay.geometry_elements())

print(f"bay_0: {sum(part.values())} of {sum(whole.values())} elements, {len(list(bay.contacts()))} of {len(list(model.contacts()))} contacts")
for kind, count in part.most_common():
    print(f"  {count:4d} of {whole[kind]:4d}  {kind}")


# Every group keeps its place, so the bay is not a bag of parts - it is the same
# tree pruned to what the bay contains, the fastener groups included.
def print_tree(node, depth=0):
    for child in node.children:
        element = child.element
        if not isinstance(element, Group):
            continue
        parts = sum(1 for n in child.descendants if not isinstance(n.element, Group))
        print(f"{'  ' * depth}{element.name}  ({parts} parts)")
        print_tree(child, depth + 1)


print_tree(bay.tree.root)

# The source is untouched and the copy is independent - fresh guids - so the bay
# is a model in its own right and writes like any other.
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
