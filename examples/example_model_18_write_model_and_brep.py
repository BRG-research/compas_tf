import pathlib

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.contacts import contact_holes
from compas_tf.model import TFModel
from compas_tf.viewer import zoom_to

data_dir = pathlib.Path(__file__).parent.parent / "data"
SOURCE_FILE = data_dir / "cantilevers_model.json"  # written by example_model_8
MODEL_FILE = data_dir / "cantilevers_baked_model.json"
STEP_FILE = data_dir / "cantilevers_baked_model.stp"
CONTACTS_STEP_FILE = data_dir / "cantilevers_baked_contacts.stp"
CONTACTS_JSON_FILE = data_dir / "cantilevers_baked_contacts.json"

source: TFModel = compas.json_load(SOURCE_FILE)
model = TFModel.from_model(source, name="cantilevers_baked")

# Every element's booleans, evaluated once and stored: readers load with none.
model.bake()

# Plate-to-plate contacts through wood_nano. It reads the top/bottom outline
# pair of each plate, so it never sees the fasteners the old Brep search had to
# filter out with skip= - and it is the whole reason this is fast.
model.compute_contacts_wood(minimum_area=1.0, clear=True)

# ...and the columns, which wood cannot see: it speaks only in plate outline
# pairs, and a column has none. The group search fills in what wood skipped -
# every column against the outer ribs it carries. Without this the model ships
# with zero column contacts, and example_model_23_assembly_step6 (which asks
# which column a quarter lands on) has nothing to measure.
#
# Contacts are additive - a search only fills edges that have none - so this
# adds to the wood result rather than replacing it. No clear= here.
for _side_a, _side_b in (
    (["columns_model"], [f"outer_ribs_{i}" for i in range(4)]),
    (["connectors"], ["floor_model"]),
    (["connectors"], ["columns_model"]),
    (["connector_cylinders"], ["floor_model"]),
    (["connector_cylinders"], ["connectors"]),
    (["outer_rib_connectors"], ["floor_model"]),
):
    model.compute_contacts_between_groups(_side_a, groups_b=_side_b, tolerance=1.0, minimum_area=1.0)

contacts = list(model.contacts())
elements = list(model.geometry_elements())
print(f"{len(elements)} elements, {len(contacts)} contacts")

from compas_tf.wood import skipped_elements  # noqa: E402

skipped = skipped_elements(model)
if skipped:
    print(f"not searched (wood reads plates only): {sum(skipped.values())} elements {skipped}")

# Elements, features, the tree, the graph with the contacts on it.
compas.json_dump(model, MODEL_FILE)

# The solids, for the shop. The Brep search used to hand over its cache here;
# wood works on outlines and builds no Breps, so they are made fresh.
model.to_step(STEP_FILE)

# Their own file - .solids would drop loose faces - plus the sidecar naming the
# two elements each face joins, which STEP cannot carry.
model.contacts_to_step(CONTACTS_STEP_FILE)
model.contacts_to_json(CONTACTS_JSON_FILE)

viewer = Viewer()


def add_tree(node, parent=None):
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=parent))
        elif element.modelgeometry is not None:
            viewer.scene.add(element, name=element.name, parent=parent, opacity=0.3)


# Transparent, because every contact sits BETWEEN two solids.
add_tree(model.tree.root)

group = viewer.scene.add_group("contacts")
for contact in contacts:
    viewer.scene.add(contact.polygon, parent=group, facecolor=(1, 0, 0), linecolor=(1, 0, 0), show_points=False)
    # A Polygon has no holes, so each loop is drawn on top.
    for hole in contact_holes(contact):
        viewer.scene.add(hole, parent=group, show_faces=False, linecolor=(0, 0, 1), show_points=False)

# The camera's far plane is 1000 mm, so without this the building starts clipped.
zoom_to(viewer, [element.aabb for element in elements])



viewer.show()
