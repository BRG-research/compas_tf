import pathlib
import sys
import time

import compas
from compas_model.elements import Group

from compas_viewer import Viewer

from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"

MODEL_FILE = data_dir / "cantilevers_baked_model.json"  # written by example_model_18

GREY = (0.85, 0.85, 0.85)

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
# Contacts.
#
# NOT computed on the Breps, even though that is the interesting version:
# compas_model's contact machinery is mesh-only. Both ends of it refuse a Brep -
# ``Element.compute_aabb`` raises NotImplementedError, so the BVH cannot even be
# built, and ``Element.compute_contacts`` ends in a bare ``raise
# NotImplementedError`` unless BOTH modelgeometries are a Mesh. Swapping the
# Breps onto the elements therefore fails before any intersection runs.
#
# So this is the mesh version: a face the boolean left as triangle soup is
# compared triangle by triangle, which is why one physical interface can come
# back as several contact polygons. Doing it properly on the Breps - one merged
# planar face against another, holes included - means writing the face/face
# intersection against compas_occt; it is not a matter of passing Breps in.
#
# It is also the GROUP-restricted query (columns against the outer ribs), the
# same one example_model_8 runs, rather than the all-pairs compute_contacts().
# All-pairs over all 237 elements trips a bug in compas_model itself: shapely
# hands polygon_polygon_overlap a GeometryCollection for some degenerate
# overlap and it goes straight for `.exterior`, so the run dies with
# AttributeError. The restricted query never reaches that pair.
#
# Contacts carried in from the file are cleared first, so what is reported here
# is only what this script computed.
# ------------------------------------------------------------------ #

for edge in list(model.graph.edges()):
    model.graph.edge_attribute(edge, name="contacts", value=[])

start = time.perf_counter()
model.compute_contacts_between_groups(
    ["columns_model"],
    groups_b=[f"outer_ribs_{i}" for i in range(4)],
    tolerance=1e-6,
    minimum_area=1.0,
)
contacts = list(model.contacts())
area = sum(contact.polygon.area for contact in contacts)
print(f"[contacts] {len(contacts)} contacts, {area:.3e} mm2, in {time.perf_counter() - start:.1f}s")

# ------------------------------------------------------------------ #
# View - mirror the model tree into the viewer, so the groups
# (floor_model / columns_model / connectors / ...) stay browsable.
# ------------------------------------------------------------------ #


def add_tree(node, parent):
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=parent))
            continue
        if element.modelgeometry is not None:
            viewer.scene.add(element, name=element.name, parent=parent, color=GREY)


start = time.perf_counter()
viewer = Viewer()
add_tree(model.tree.root, None)
print(f"[draw] {time.perf_counter() - start:.1f}s")

viewer.show()
