import pathlib
import sys
import time

import compas
from compas_model.elements import Group

from compas_tf.model import TFModel
from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

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
# View - mirror the model tree into the viewer, so the groups
# (floor_model / columns_model / connectors / ...) stay browsable.
# ------------------------------------------------------------------ #


def add_tree(node, parent):
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, parent.add_group(element.name))
            continue
        mesh = element.modelgeometry
        if mesh is not None:
            parent.add(triangulated(mesh), name=element.name, hide_coplanaredges=True, color=GREY)


start = time.perf_counter()
viewer = make_viewer(data_dir)
add_tree(model.tree.root, viewer.scene)
print(f"[draw] {time.perf_counter() - start:.1f}s")

viewer.show()
