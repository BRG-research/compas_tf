import pathlib

import compas
from compas.colors import Color
from compas.geometry import Translation
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.plate import PlateElement
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

GREY = Color(0.85, 0.85, 0.85)
RED = Color(0.9, 0.2, 0.2)
MARGIN = 100.0  # gap between the packed wedges

model: TFModel = TFModel.from_model(compas.json_load(data_dir / "cantilevers_model.json"))

# The three wedges that seat the inner beams of one quarter, one per beam.
wedges: list[PlateElement] = [model.find_element_with_name(f"wedges_inner_beams_{i}_0") for i in range(3)]

# Lay each wedge flat on its top face and pack them in a row along Y.
cursor = 0.0
parts = []
previews = []
for wedge in wedges:
    flat = wedge.lay_flat_transform()
    cut = wedge.modelgeometry.transformed(flat)

    aabb = cut.aabb()
    shift = Translation.from_vector([-aabb.xmin, cursor - aabb.ymin, -aabb.zmin])
    cursor += (aabb.ymax - aabb.ymin) + MARGIN

    cut.transform(shift)
    print(wedge.name, cut.aabb().xsize, cut.aabb().ysize, cut.aabb().zsize)

    uncut = wedge.compute_elementgeometry(include_features=False).transformed(wedge.modeltransformation).transformed(flat).transformed(shift)
    cutters = [mesh.transformed(flat).transformed(shift) for feature in wedge.get_features() for mesh in getattr(feature, "meshes", None) or []]

    uncut.name = f"{wedge.name}_uncut"
    cut.name = wedge.name
    for index, solid in enumerate(cutters):
        solid.name = f"{wedge.name}_cutter_{index}"
    parts += [uncut, cut] + cutters
    previews.append(cut)

preview = previews[0].copy()
for mesh in previews[1:]:
    preview.join(mesh)

write_parts(parts, fab_dir, "wedges_inner_beams_0", preview=preview)

viewer = Viewer()
for wedge in wedges:
    group = viewer.scene.add_group(wedge.name)
    for part in parts:
        if part.name == wedge.name or part.name.startswith(f"{wedge.name}_"):
            color = RED if "_cutter_" in part.name else GREY if part.name.endswith("_uncut") else None
            viewer.scene.add(part, name=part.name, parent=group, facecolor=color)

viewer.show()
