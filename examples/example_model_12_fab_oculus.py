import math
import pathlib

import compas
from compas.colors import Color
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Transformation
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
MARGIN = 100.0  # gap between the packed plates of one set

model: TFModel = TFModel.from_model(compas.json_load(data_dir / "cantilevers_model.json"))

# The oculus is 9 PlateElements in the "oculus" group, written as one
# fabrication set PER CATEGORY: the 4 side plates (0..3), the 4 side
# t-sections (4..7) and the oculus plate itself (8). The side plates rest on
# their BOTTOM face (flip=True) - laid on the top face their angled edge cuts
# face the machine bed.
SETS = {
    "oculus_side_plates_0": ([0, 1, 2, 3], True),
    "oculus_side_tsections_0": ([4, 5, 6, 7], False),
    "oculus_plate_0": ([8], False),
}


def lay_flat_bottom(plate):
    """Transformation that lays the plate flat on worldXY resting on its
    BOTTOM face, body up - the opposite resting face of
    :meth:`PlateElement.lay_flat_transform`."""
    base = plate.base_frame
    x2d = Vector(base.xaxis[0], base.xaxis[1], 0.0)
    if x2d.length < 1e-9:
        x2d = Vector(base.yaxis[0], base.yaxis[1], 0.0)
    xaxis = x2d.unitized()
    yaxis = Vector(0, 0, 1).cross(xaxis)  # zaxis = xaxis x yaxis = +Z (up)
    return Transformation.from_frame_to_frame(base, Frame(Point(0, 0, 0), xaxis, yaxis))


def align_longest_edge(mesh):
    """Rotation about Z that turns the flat mesh's longest OBB axis onto X,
    so the packed pieces all run the same way (same align as the t-sections
    example)."""
    obb = mesh.obb()
    axis = obb.frame.xaxis if obb.xsize >= obb.ysize else obb.frame.yaxis
    direction = Vector(axis[0], axis[1], 0.0).unitized()
    angle = -math.atan2(direction.y, direction.x)
    # The axis has no sign, so this can ask for a ~180-degree spin that flips
    # the piece end over end - fold that into the equivalent small rotation.
    angle = (angle + math.pi / 2) % math.pi - math.pi / 2
    return Rotation.from_axis_and_angle(Vector.Zaxis(), angle, point=obb.frame.point)


viewer = Viewer()

for set_name, (indices, flip) in SETS.items():
    plates: list[PlateElement] = [model.find_element_with_name(f"oculus_{i}") for i in indices]

    # Lay each plate flat, turn its longest edge onto X, and pack the set in a
    # row along Y starting at the origin.
    cursor = 0.0
    parts = []
    previews = []
    for plate in plates:
        flat = plate.lay_flat_transform() if not flip else lay_flat_bottom(plate)
        cut = plate.modelgeometry.transformed(flat)
        align = align_longest_edge(cut)
        cut.transform(align)

        aabb = cut.aabb()
        shift = Translation.from_vector([-aabb.xmin, cursor - aabb.ymin, -aabb.zmin])
        cursor += (aabb.ymax - aabb.ymin) + MARGIN

        cut.transform(shift)
        print(plate.name, cut.aabb().xsize, cut.aabb().ysize, cut.aabb().zsize)

        uncut = plate.compute_elementgeometry(include_features=False).transformed(plate.modeltransformation).transformed(flat).transformed(align).transformed(shift)
        cutters = [mesh.transformed(flat).transformed(align).transformed(shift) for feature in plate.get_features() for mesh in getattr(feature, "meshes", None) or []]

        uncut.name = f"{plate.name}_uncut"
        cut.name = plate.name
        for index, solid in enumerate(cutters):
            solid.name = f"{plate.name}_cutter_{index}"
        parts += [uncut, cut] + cutters
        previews.append(cut)

    preview = previews[0].copy()
    for mesh in previews[1:]:
        preview.join(mesh)

    write_parts(parts, fab_dir, set_name, preview=preview)

    group = viewer.scene.add_group(set_name)
    for plate in plates:
        for part in parts:
            if part.name == plate.name or part.name.startswith(f"{plate.name}_"):
                color = RED if "_cutter_" in part.name else GREY if part.name.endswith("_uncut") else None
                viewer.scene.add(part, name=part.name, parent=group, facecolor=color)

viewer.show()
