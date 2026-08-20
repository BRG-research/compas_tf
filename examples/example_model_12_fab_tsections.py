import math
import pathlib

import compas
from compas.colors import Color
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.plate import PlateElement
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

GREY = Color(0.85, 0.85, 0.85)
RED = Color(0.9, 0.2, 0.2)
MARGIN = 50.0  # gap between the packed t-sections

model: TFModel = TFModel.from_model(compas.json_load(data_dir / "cantilevers_model.json"))
tsections: list[PlateElement] = [model.find_element_with_name(f"tsections_{i}_0") for i in range(6)]

# Fabrication order follows the ribs: outer_rib0, inner_rib0, inner_rib1,
# outer_rib1. Outer ribs carry one t-section, inner ribs two.
ribs: list[PlateElement] = [
    model.find_element_with_name(name)
    for name in ["outer_ribs_0_0", "inner_ribs_0_0", "inner_ribs_1_0", "outer_ribs_1_0"]
]


def rib_of(tsection) -> PlateElement:
    """The rib a t-section runs along: parallel in plan, then nearest axis."""
    frame = tsection.base_frame
    parallel = [rib for rib in ribs if abs(frame.xaxis.dot(rib.base_frame.xaxis)) > 0.9]
    return min(parallel or ribs, key=lambda rib: _axis_distance(frame, rib.base_frame))


def _axis_distance(a, b) -> float:
    """Plan distance from a's origin to the line of b's long axis."""
    dx, dy = a.point.x - b.point.x, a.point.y - b.point.y
    return abs(dx * b.xaxis.y - dy * b.xaxis.x)


ordered = sorted(tsections, key=lambda t: ribs.index(rib_of(t)))

# Lay each flat on its top face, rotate its long axis onto X
# (lay_flat_transform keeps the plan orientation, and these strips run
# diagonally), and pack them in a row along Y.
cursor = 0.0
parts = []
previews = []
for t in ordered:
    flat = t.lay_flat_transform()
    cut = t.modelgeometry.transformed(flat)
    obb = cut.obb()
    axis = obb.frame.xaxis if obb.xsize >= obb.ysize else obb.frame.yaxis
    direction = Vector(axis[0], axis[1], 0.0).unitized()
    angle = -math.atan2(direction.y, direction.x)
    # The axis has no sign, so this can ask for a ~180-degree spin that flips
    # the strip end over end - fold that into the equivalent small rotation.
    angle = (angle + math.pi / 2) % math.pi - math.pi / 2
    align = Rotation.from_axis_and_angle(Vector.Zaxis(), angle, point=obb.frame.point)

    cut.transform(align)
    print(t.name, cut.aabb().xsize, cut.aabb().ysize, cut.aabb().zsize)
    uncut = t.compute_elementgeometry(include_features=False).transformed(t.modeltransformation).transformed(flat).transformed(align)
    cutters = [mesh.transformed(flat).transformed(align) for feature in t.get_features() for mesh in getattr(feature, "meshes", None) or []]

    shift = Translation.from_vector([0, cursor - cut.aabb().ymin, 0])
    cursor += (cut.aabb().ymax - cut.aabb().ymin) + MARGIN

    uncut.transform(shift)
    cut.transform(shift)
    for solid in cutters:
        solid.transform(shift)

    uncut.name = f"{t.name}_uncut"
    cut.name = t.name
    for index, solid in enumerate(cutters):
        solid.name = f"{t.name}_cutter_{index}"
    parts += [uncut, cut] + cutters
    previews.append(cut)

preview = previews[0].copy()
for mesh in previews[1:]:
    preview.join(mesh)

write_parts(parts, fab_dir, "tsections_0", preview=preview)

viewer = Viewer()
for t in ordered:
    group = viewer.scene.add_group(t.name)
    for part in parts:
        if part.name == t.name or part.name.startswith(f"{t.name}_"):
            color = RED if "_cutter_" in part.name else GREY if part.name.endswith("_uncut") else None
            viewer.scene.add(part, name=part.name, parent=group, facecolor=color)

viewer.show()
