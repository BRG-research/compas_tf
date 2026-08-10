import pathlib
import time

import compas
from compas_model.elements import Group

from compas_viewer import Viewer

from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"

SOURCE_FILE = data_dir / "cantilevers_model.json"  # written by example_model_8
MODEL_FILE = data_dir / "cantilevers_baked_model.json"
STEP_FILE = data_dir / "cantilevers_baked_model.stp"

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
# 1. compas.json_dump - the compas_tf MODEL.
#
# Elements, features, materials, the element tree and the interaction graph,
# each element carrying its baked geometry. example_model_19_read_model.py
# loads this back with no boolean and no boolean backend.
# ------------------------------------------------------------------ #

start = time.perf_counter()
compas.json_dump(model, MODEL_FILE)
print(f"[write] {MODEL_FILE.name}: {time.perf_counter() - start:.1f}s, {MODEL_FILE.stat().st_size / 1024 / 1024:.1f} MB")

# ------------------------------------------------------------------ #
# 2. STEP - the same model as solids, for the shop.
#
# to_step() runs get_brep() per element - OCCBrep.from_mesh() followed by
# brep.simplify(merge_edges=True, merge_faces=True), so the boolean triangles
# collapse back into the flat faces the part was modelled with and a drilled
# face comes back as ONE face carrying its hole loops (a Mesh face cannot hold
# a hole at all) - then writes them as one compound.
#
# The deflections are pinned tight (1e-6 rad) rather than left at the OCC
# default of 0.1 rad, because at 0.1 rad the unification also fuses NEARLY
# coplanar faces and flattens the twisted loft quads of the ribs and
# t-sections - see the same note in example_model_8. mesh_to_brep() checks the
# volume afterwards and keeps the unsimplified Brep if it moved.
#
# example_model_20_read_brep.py reads this file back.
# ------------------------------------------------------------------ #

start = time.perf_counter()
model.to_step(STEP_FILE)
print(f"[write] {STEP_FILE.name}: {time.perf_counter() - start:.1f}s, {STEP_FILE.stat().st_size / 1024 / 1024:.1f} MB")

# ------------------------------------------------------------------ #
# View what was just written.
#
# The model meshes are drawn from the baked geometry that went into
# MODEL_FILE, with the element tree mirrored so the groups stay browsable.
# The STEP solids are NOT drawn here - most faces of this building are twisted
# loft quads (lofted between parabolas), which OCC meshes on a fixed grid, so
# the whole set tessellates to ~2.9M triangles and takes ~95 s regardless of
# the linear or angular deflection. example_model_20_read_brep.py does that.
# ------------------------------------------------------------------ #


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
add_tree(model.tree.root, viewer.scene.add_group(f"{model.name}__model"))
print(f"[draw]  {time.perf_counter() - start:.1f}s")

viewer.show()
