import pathlib

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.connectors import ConnectorCylinderElement
from compas_tf.connectors import DowelCylinderElement
from compas_tf.contacts import contact_holes
from compas_tf.contacts import involving
from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"
SOURCE_FILE = data_dir / "cantilevers_model.json"  # written by example_model_8
MODEL_FILE = data_dir / "cantilevers_baked_model.json"
STEP_FILE = data_dir / "cantilevers_baked_model.stp"
CONTACTS_STEP_FILE = data_dir / "cantilevers_baked_contacts.stp"
CONTACTS_JSON_FILE = data_dir / "cantilevers_baked_contacts.json"

source: TFModel = compas.json_load(SOURCE_FILE)
model = TFModel.from_model(source, name="cantilevers_baked")

# An element's geometry is a boolean of its base shape with its features. bake()
# runs those once and stores the result on the element, so every reader loads
# with no boolean and no boolean backend. The only booleans in this file.
model.bake()

# Contacts on the Brep faces, not the meshes: after a boolean the mesh is
# triangles, so one interface comes back as several polygons and loses area.
# skip= drops the fasteners - a faceted shaft touches its own hole once per
# facet, 2072 of 2805 contacts and no structural information.
detector = model.compute_contacts_brep(
    minimum_area=1.0,
    clear=True,
    skip=involving(DowelCylinderElement, ConnectorCylinderElement),
)

contacts = list(model.contacts())
elements = list(model.geometry_elements())
print(f"{len(elements)} elements, {len(contacts)} contacts")

# The model: elements, features, the tree, and the graph with the contacts on it.
compas.json_dump(model, MODEL_FILE)

# The solids, for the shop. cache= reuses the Breps the contact search built.
model.to_step(STEP_FILE, cache=detector.breps)

# The contacts as loose planar faces - to_step() splits on .solids and would
# drop them - plus the sidecar naming the two elements each face joins, which
# STEP itself cannot carry.
model.contacts_to_step(CONTACTS_STEP_FILE)
model.contacts_to_json(CONTACTS_JSON_FILE)

for path in (MODEL_FILE, STEP_FILE, CONTACTS_STEP_FILE, CONTACTS_JSON_FILE):
    print(f"  {path.stat().st_size / 1024 / 1024:5.1f} MB  {path.name}")

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
    # A Polygon scene object has no notion of a hole, so each loop is drawn on top.
    for hole in contact_holes(contact):
        viewer.scene.add(hole, parent=group, show_faces=False, linecolor=(0, 0, 1), show_points=False)

viewer.show()
