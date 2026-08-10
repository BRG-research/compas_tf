import pathlib
import time

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

# ------------------------------------------------------------------ #
# Load the full model written by example_model_8 and BAKE it.
#
# Every compas_tf element is parametric: its geometry is a boolean of a base
# shape with its features (capitel unions, connector pockets, dowel holes).
# Loading that model means re-running every boolean. TFModel.bake() runs them
# ONCE and stores the result on each element, applied to its base geometry, so
# it lands inside the element's own __data__ and survives compas.json_dump.
#
# This is the only step here that runs a boolean.
# ------------------------------------------------------------------ #

source: TFModel = compas.json_load(SOURCE_FILE)
model = TFModel.from_model(source, name="cantilevers_baked")

start = time.perf_counter()
model.bake()
elements = list(model.geometry_elements())
print(f"[bake]  {len(elements)} elements in {time.perf_counter() - start:.1f}s, is_baked={model.is_baked}")

# ------------------------------------------------------------------ #
# Contacts between ALL elements, on BREP faces.
#
# The source file carries only the 4 outer-rib seams example_model_8 asked for,
# so they are cleared and every element pair is searched instead.
#
# On Breps, not on the element meshes: modelgeometry is what a boolean left
# behind, so the mesh route returns one physical interface as several contact
# polygons - the column/outer-rib joint splits into 8, from comparing 626 x 246
# faces, ~13 s for that one pair. get_brep() merges those triangles back into
# the modelled faces, so the same joint is 1 contact of the same area in ~0.2 s,
# holes included.
#
# skip= drops the fasteners: a faceted shaft touches its own hole once per
# facet, which is 2072 of 2805 contacts and no structural information.
# The Breps built here are handed to the STEP export below.
# ------------------------------------------------------------------ #

start = time.perf_counter()
detector = model.compute_contacts_brep(
    minimum_area=1.0,
    clear=True,
    skip=involving(DowelCylinderElement, ConnectorCylinderElement),
)
contacts = list(model.contacts())
area = sum(contact.polygon.area for contact in contacts)
holes = sum(len(contact_holes(contact)) for contact in contacts)
pairs = sum(1 for edge in model.graph.edges() if model.graph.edge_attribute(edge, name="contacts"))
print(f"[contacts] {len(contacts)} contacts over {pairs} pairs, {area:.3e} mm2, {holes} holes, {detector.skipped} pairs skipped, in {time.perf_counter() - start:.1f}s")
if detector.errors:
    # shapely failing on a hole loop costs the holes, not the contact.
    print(f"[contacts] {len(detector.errors)} face pairs degraded ({', '.join(sorted({s for _, _, s, _ in detector.errors}))})")

# ------------------------------------------------------------------ #
# 1. compas.json_dump - the compas_tf MODEL.
#
# Elements, features, materials, the element tree and the interaction graph -
# each element carrying its baked geometry, each graph edge the contacts found
# above. example_model_19_read_model.py loads this back with no boolean, no
# boolean backend and no contact search.
# ------------------------------------------------------------------ #

start = time.perf_counter()
compas.json_dump(model, MODEL_FILE)
print(f"[write] {MODEL_FILE.name}: {time.perf_counter() - start:.1f}s, {MODEL_FILE.stat().st_size / 1024 / 1024:.1f} MB")

# ------------------------------------------------------------------ #
# 2. STEP - the same model as solids, for the shop.
#
# to_step() runs get_brep() per element: OCCBrep.from_mesh() then
# simplify(merge_edges, merge_faces), so the boolean triangles collapse back
# into the modelled faces and a drilled face is ONE face with its hole loops.
# cache= hands it the Breps the contact search already built.
#
# The angular deflection is pinned at 1e-6 rad rather than OCC's 0.1: at 0.1 the
# unification also fuses NEARLY coplanar faces and flattens the twisted loft
# quads (tsections lost 42% volume). mesh_to_brep() checks the volume after and
# keeps the unsimplified Brep if it moved.
#
# The contacts go to their own STEP, one planar face each - to_step() splits on
# .solids, which would drop loose faces. example_model_20 reads both.
# ------------------------------------------------------------------ #

start = time.perf_counter()
model.to_step(STEP_FILE, cache=detector.breps)
print(f"[write] {STEP_FILE.name}: {time.perf_counter() - start:.1f}s, {STEP_FILE.stat().st_size / 1024 / 1024:.1f} MB")

start = time.perf_counter()
model.contacts_to_step(CONTACTS_STEP_FILE)
print(f"[write] {CONTACTS_STEP_FILE.name}: {time.perf_counter() - start:.1f}s, {CONTACTS_STEP_FILE.stat().st_size / 1024:.0f} KB")

# ------------------------------------------------------------------ #
# View - the element tree mirrored so the groups stay browsable, contacts in
# their own top-level group. The parts are semi-transparent because every
# contact sits BETWEEN two solids and is invisible on an opaque model.
# ------------------------------------------------------------------ #


def add_tree(node, parent):
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=parent))
            continue
        if element.modelgeometry is not None:
            viewer.scene.add(element, name=element.name, parent=parent, opacity=0.3)


start = time.perf_counter()
viewer = Viewer()
add_tree(model.tree.root, viewer.scene.add_group(f"{model.name}__model"))

contacts_group = viewer.scene.add_group("contacts")
for i, contact in enumerate(contacts):
    viewer.scene.add(
        contact.polygon,
        name=f"contact_{i}",
        parent=contacts_group,
        facecolor=(1.0, 0.0, 0.0),
        linecolor=(0.5, 0.0, 0.0),
        show_points=False,
    )
    # A Polygon scene object has no notion of a hole, so each hole loop is
    # drawn as its own outline on top.
    for j, hole in enumerate(contact_holes(contact)):
        viewer.scene.add(
            hole,
            name=f"contact_{i}_hole_{j}",
            parent=contacts_group,
            show_faces=False,
            linecolor=(0.0, 0.0, 1.0),
            show_points=False,
        )
print(f"[draw]  {len(contacts)} contacts + {len(elements)} parts in {time.perf_counter() - start:.1f}s")

viewer.show()
