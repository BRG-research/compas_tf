import pathlib
from collections import Counter

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.connectors import ConnectorElement
from compas_tf.connectors import DowelCylinderElement
from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"
MODEL_FILE = data_dir / "cantilevers_baked_model.json"  # the file example_model_19 reads
BAY_FILE = data_dir / "bay_model.json"

model: TFModel = compas.json_load(MODEL_FILE)

# The hardware that mounts this cantilever on its column. The wedges and their
# bolts are inner-beam hardware and OuterRibConnectorElement joins one quarter
# to the next, so neither belongs to the bay - put a type back and it returns.
FASTENERS = (
    ConnectorElement,
    DowelCylinderElement,
)

# Both groups in one call: the contacts BETWEEN a column and its quarter survive
# only if the two come out together.
#
# The fasteners cannot be named - `connectors`, `connector_cylinders` and
# `outer_rib_connectors` hold the hardware of all four bays - so neighbors=
# picks out the ones belonging here, by contact for the connectors and by
# bounding box for the dowels, which the contact search skipped and which
# therefore have no graph edge to follow. Types rather than True is what keeps
# the bay a bay: True also admits the ribs and beams of the quarters next door
# and two oculus plates, which touch this bay but are no part of it.
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


# Every group keeps its place, so the bay is the same tree pruned to what it
# contains, not a bag of parts.
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

viewer.show()
