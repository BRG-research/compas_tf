import pathlib

import compas
from compas.colors import Color
from compas.geometry import Frame
from compas.geometry import Transformation
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.model import TFModel
from compas_tf.viewer import dump_scene

data_dir = pathlib.Path(__file__).parent.parent / "data"

GREY = Color(0.85, 0.85, 0.85)
RED = Color(0.9, 0.2, 0.2)

# ------------------------------------------------------------------ #
# Deserialize the cantilevers model written by example_model_8, pick a column.
# ------------------------------------------------------------------ #

model: TFModel = compas.json_load(data_dir / "cantilevers_model.json")
column: ColumnElement = model.find_element_with_name("column_0")
xform = Transformation.from_frame_to_frame(Frame.worldXY().translated((-column.width * 0.5, -column.depth * 0.5, 0)), Frame.worldYZ())

# column.transformation = xform

# ------------------------------------------------------------------ #
# Uncut stock: apply ONLY the additive capitel, skip the cuts.
# ------------------------------------------------------------------ #

uncut = column.compute_elementgeometry(types=["ColumnAddFeature"]).transformed(xform)

# ------------------------------------------------------------------ #
# The cut solids that carve it, recovered by type for fabrication.
# ------------------------------------------------------------------ #

cuts = []
for feature in column.get_features(["ColumnCutFeature"]):
    for mesh in feature.meshes:
        cuts.append(mesh.transformed(xform))

print(f"column {column.name}: {len(cuts)} cut solids")

# ------------------------------------------------------------------ #
#  View - the uncut stock (grey) with the cut solids (red) that carve it.
# ------------------------------------------------------------------ #

viewer = Viewer()

stock = viewer.scene.add_group(f"{column.name}__stock_and_cuts")
viewer.scene.add(uncut, name=f"{column.name}_uncut", parent=stock, facecolor=GREY)

cutters = viewer.scene.add_group("cut_solids", parent=stock)
for index, solid in enumerate(cuts):
    viewer.scene.add(solid, name=f"cut_{index}", parent=cutters, facecolor=RED)

# Write the Rhino bundle (plain, already-computed geometry) from the finished
# scene, so it can be loaded into Rhino with no recompute - see RHINO block below.
dump_scene(viewer.scene, data_dir / "column_fab_rhino.json")

viewer.show()


# ====================================================================== #
#  RHINO  -  copy the code between the triple quotes into the Rhino 8
#  ScriptEditor (Python 3) and Run it to add THIS example's geometry to the
#  active Rhino document (named layers, per-object colour). Needs only the
#  installed compas_tf (see install steps); recomputes nothing.
# ====================================================================== #
RHINO = r"""
from compas_tf.rhino import draw_bundle
draw_bundle(r"C:\brg\compas_tf\data\column_fab_rhino.json")
"""
