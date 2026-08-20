import pathlib

import compas
from compas.colors import Color
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.plate import PlateElement
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

GREY = Color(0.85, 0.85, 0.85)
RED = Color(0.9, 0.2, 0.2)

model: TFModel = TFModel.from_model(compas.json_load(data_dir / "cantilevers_model.json"))
rib: PlateElement = model.find_element_with_name("inner_ribs_0_0")

# Lay the plate flat on its top face at the origin, body up.
xform = rib.lay_flat_transform()

# Stock: the lofted plate without cuts, placed via modeltransformation.
uncut = rib.compute_elementgeometry(include_features=False).transformed(rib.modeltransformation).transformed(xform)
cut = rib.modelgeometry.transformed(xform)
print(cut.aabb().xsize, cut.aabb().ysize, cut.aabb().zsize)

cuts = []
for feature in rib.get_features():
    for mesh in getattr(feature, "meshes", None) or []:
        cuts.append(mesh.transformed(xform))

uncut.name = f"{rib.name}_uncut"
cut.name = f"{rib.name}_cut"
for index, solid in enumerate(cuts):
    solid.name = f"{rib.name}_cutter_{index}"

write_parts([uncut, cut] + cuts, fab_dir, rib.name, preview=cut)

viewer = Viewer()

stock = viewer.scene.add_group(f"{rib.name}__stock_and_cuts")
viewer.scene.add(uncut, name=f"{rib.name}_uncut", parent=stock, facecolor=GREY)
viewer.scene.add(cut, name=f"{rib.name}_cut", parent=stock)
cutters = viewer.scene.add_group("cut_solids", parent=stock)
for index, solid in enumerate(cuts):
    viewer.scene.add(solid, name=f"cut_{index}", parent=cutters, facecolor=RED)

viewer.show()
