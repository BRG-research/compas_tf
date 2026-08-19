import pathlib

import compas
from compas.colors import Color
from compas.geometry import Frame
from compas.geometry import Transformation
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.model import TFModel
from compas_tf.viewer import dump_scene
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

GREY = Color(0.85, 0.85, 0.85)
RED = Color(0.9, 0.2, 0.2)

# ------------------------------------------------------------------ #
# Deserialize the cantilevers model written by example_model_8
# Then pick a column by element name.
# ------------------------------------------------------------------ #

model: TFModel = compas.json_load(data_dir / "cantilevers_model.json")
column: ColumnElement = model.find_element_with_name("column_0")
xform = Transformation.from_frame_to_frame(Frame.worldXY().translated((-column.width * 0.5, -column.depth * 0.5, 0)), Frame.worldYZ())

# ------------------------------------------------------------------ #
# Uncut stock: apply ONLY the additive capitel, skip the cuts.
# ------------------------------------------------------------------ #

uncut = column.compute_elementgeometry(types=["ColumnAddFeature"]).transformed(xform)
cut = column.elementgeometry.transformed(xform)

# ------------------------------------------------------------------ #
# The cut solids that carve it, recovered by type for fabrication.
# ------------------------------------------------------------------ #

cuts = []
for feature in column.get_features(["ColumnCutFeature"]):
    for mesh in feature.meshes:
        cuts.append(mesh.transformed(xform))

# ------------------------------------------------------------------ #
# Export
#
#   STEP     the meshes go through compas_occt's coplanar-face merge.
#   OBJ      the mesh the part already is.
#   PREVIEW  the carved part on its own
# ------------------------------------------------------------------ #

uncut.name = f"{column.name}_uncut"
cut.name = f"{column.name}_cut"
for index, solid in enumerate(cuts):
    solid.name = f"{column.name}_cutter_{index}"

written = write_parts([uncut, cut] + cuts, fab_dir, column.name, preview=cut)

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

viewer = Viewer()

stock = viewer.scene.add_group(f"{column.name}__stock_and_cuts")
viewer.scene.add(uncut, name=f"{column.name}_uncut", parent=stock, facecolor=GREY)
viewer.scene.add(cut, name=f"{column.name}_cut", parent=stock)
cutters = viewer.scene.add_group("cut_solids", parent=stock)
for index, solid in enumerate(cuts):
    viewer.scene.add(solid, name=f"cut_{index}", parent=cutters, facecolor=RED)

viewer.show()