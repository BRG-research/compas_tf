import pathlib
import sys
import time

import compas
from compas_model.elements import Group

from compas_viewer import Viewer

from compas_tf.contacts import contact_holes
from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"

MODEL_FILE = data_dir / "cantilevers_baked_model.json"  # written by example_model_18

# ------------------------------------------------------------------ #
# compas.json_load - the compas_tf model, straight off disk.
#
# The geometry was baked before it was written, so nothing is recomputed:
# no boolean runs and no boolean backend is needed. The elements come back
# whole - features, parameters and the element tree all intact beside the
# baked shape - which is what separates this from the geometry-only files.
# ------------------------------------------------------------------ #

if not MODEL_FILE.exists():
    sys.exit(f"{MODEL_FILE.name} not found - run example_model_18_write_model_and_brep.py first.")

start = time.perf_counter()
model: TFModel = compas.json_load(MODEL_FILE)
elements = list(model.geometry_elements())
print(f"[load] {MODEL_FILE.name}: {time.perf_counter() - start:.1f}s, {len(elements)} elements, is_baked={model.is_baked}")

# ------------------------------------------------------------------ #
# Contacts - read, not recomputed. example_model_18 searched every element pair
# on the Brep faces, and a Contact serializes whole (polygon, frame, size,
# holes). To redo the search: model.compute_contacts_brep(minimum_area=1.0,
# clear=True). See compas_tf/contacts.py for why that beats the mesh route.
# ------------------------------------------------------------------ #

contacts = list(model.contacts())
area = sum(contact.polygon.area for contact in contacts)
holes = sum(len(contact_holes(contact)) for contact in contacts)
pairs = sum(1 for edge in model.graph.edges() if model.graph.edge_attribute(edge, name="contacts"))
print(f"[contacts] {len(contacts)} contacts over {pairs} pairs, {area:.3e} mm2, {holes} holes (read from file)")

# ------------------------------------------------------------------ #
# View - mirror the model tree into the viewer, so the groups
# (floor_model / columns_model / connectors / ...) stay browsable. The parts
# keep the viewer's default appearance (black edges); the contacts are red, in
# their own group so the model can be switched off to see them.
# ------------------------------------------------------------------ #

RED = (1.0, 0.0, 0.0)


def add_tree(node, parent):
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=parent))
            continue
        if element.modelgeometry is not None:
            viewer.scene.add(element, name=element.name, parent=parent)


start = time.perf_counter()
viewer = Viewer()
add_tree(model.tree.root, None)

contacts_group = viewer.scene.add_group("contacts")
for index, contact in enumerate(contacts):
    viewer.scene.add(
        contact.polygon,
        name=f"contact_{index}",
        parent=contacts_group,
        facecolor=RED,
        linecolor=RED,
        show_points=False,
    )
    # A Polygon scene object has no notion of a hole, so each hole loop is
    # drawn as its own outline on top.
    for j, hole in enumerate(contact_holes(contact)):
        viewer.scene.add(
            hole,
            name=f"contact_{index}_hole_{j}",
            parent=contacts_group,
            show_faces=False,
            linecolor=RED,
            show_points=False,
        )
print(f"[draw] {len(contacts)} contacts + {len(elements)} parts in {time.perf_counter() - start:.1f}s")

viewer.show()
