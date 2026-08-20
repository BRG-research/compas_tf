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
from compas.geometry import angle_vectors_signed
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.plate import PlateElement
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

GREY = Color(0.85, 0.85, 0.85)
RED = Color(0.9, 0.2, 0.2)
MARGIN = 50.0  # gap between the packed bed strips

model: TFModel = compas.json_load(data_dir / "cantilevers_model.json")

# A quarter has three beds ("beds_0_0", "beds_1_0", "beds_2_0"), each a chain
# of six plates that curve up off the floor. Plates are named
# beds_<strip>_<chain>_<quarter>; token 2 is the unroll order.
strips: list[list[PlateElement]] = [[model.find_element_with_name(f"beds_{strip}_{chain}_0") for chain in range(6)] for strip in range(3)]


def _plate_edges(plate):
    # Hinge about the TOP face edges: the strips are unrolled lying on their
    # top face, so folding about the bottom edges rotates each plate INTO its
    # neighbour's body and the flattened plates overlap.
    pts = list(plate.face_polylines["top"].points[:-1])
    n = len(pts)
    return [(pts[i], pts[(i + 1) % n]) for i in range(n)]


def shared_edge(p, q, tol=5.0):
    """The edge (two world points) shared by plates ``p`` and ``q``, or None."""
    for a0, a1 in _plate_edges(p):
        for b0, b1 in _plate_edges(q):
            if (a0.distance_to_point(b0) < tol and a1.distance_to_point(b1) < tol) or (a0.distance_to_point(b1) < tol and a1.distance_to_point(b0) < tol):
                return a0, a1
    return None


def hinge_unfold(plates):
    """One world->flat transform per plate: hinge each plate about the edge it
    shares with the previous one, so the chain lands co-planar on the ground
    (same unroll as example_model_14_fab_quarter_bed, but the plates already
    come in chain order)."""
    placed = [Transformation()]
    for prev, plate in zip(plates, plates[1:]):
        edge = shared_edge(prev, plate)
        if edge is None:
            raise ValueError(f"{prev.name} and {plate.name} share no edge")
        axis = Vector.from_start_end(*edge).unitized()
        theta = angle_vectors_signed(plate.base_frame.zaxis, prev.base_frame.zaxis, axis)
        placed.append(placed[-1] * Rotation.from_axis_and_angle(axis, theta, point=edge[0]))

    # Drop the flattened strip onto z=0 pointing the way the bed runs in plan,
    # turned over so it rests on the opposite face (base plane down). The first
    # plate never moved, so the strip is anchored on its base point.
    first = plates[0].base_frame.point
    last = plates[-1].base_frame.point
    flat_last = last.transformed(placed[-1])

    source_x = Vector.from_start_end(first, flat_last).unitized()
    source_z = plates[0].base_frame.zaxis
    source = Frame(first, source_x, source_z.cross(source_x))

    axis = Vector(last.x - first.x, last.y - first.y, 0.0)
    if axis.length < 1e-9:  # bed runs straight up in plan - fall back to flat axis
        axis = Vector(source_x.x, source_x.y, 0.0)
    target_x = axis.unitized()
    target = Frame(Point(first.x, first.y, 0.0), target_x, Vector(0, 0, -1).cross(target_x))

    flatten = Transformation.from_frame_to_frame(source, target)
    return [flatten * transform for transform in placed]


def align_longest_edge(mesh):
    """Rotation about Z that turns the flat mesh's longest OBB axis onto X,
    so the packed strips all run the same way (same align as the t-sections
    example)."""
    obb = mesh.obb()
    axis = obb.frame.xaxis if obb.xsize >= obb.ysize else obb.frame.yaxis
    direction = Vector(axis[0], axis[1], 0.0).unitized()
    angle = -math.atan2(direction.y, direction.x)
    # The axis has no sign, so this can ask for a ~180-degree spin that flips
    # the strip end over end - fold that into the equivalent small rotation.
    angle = (angle + math.pi / 2) % math.pi - math.pi / 2
    return Rotation.from_axis_and_angle(Vector.Zaxis(), angle, point=obb.frame.point)


# Unroll each strip, rotate its long axis onto X, and pack the three strips
# in a row along Y.
cursor = 0.0
groups = []  # the parts of each strip, in viewer group order
previews = []
for plates in strips:
    unrolled = hinge_unfold(plates)

    flat_cuts = [plate.modelgeometry.transformed(transform) for plate, transform in zip(plates, unrolled)]
    strip_mesh = flat_cuts[0].copy()
    for mesh in flat_cuts[1:]:
        strip_mesh.join(mesh)

    align = align_longest_edge(strip_mesh)
    strip_mesh.transform(align)
    aabb = strip_mesh.aabb()
    drop = Translation.from_vector([-aabb.xmin, cursor - aabb.ymin, -aabb.zmin]) * align
    cursor += (aabb.ymax - aabb.ymin) + MARGIN

    strip_parts = []
    for plate, transform, flat_cut in zip(plates, unrolled, flat_cuts):
        place = drop * transform
        uncut = plate.compute_elementgeometry(include_features=False).transformed(place * plate.modeltransformation)
        cut = flat_cut.transformed(drop)
        cutters = [mesh.transformed(place) for feature in plate.get_features() for mesh in getattr(feature, "meshes", None) or []]

        plate_obb = cut.obb()
        dims = sorted([plate_obb.xsize, plate_obb.ysize, plate_obb.zsize], reverse=True)
        print(plate.name, *dims)

        uncut.name = f"{plate.name}_uncut"
        cut.name = plate.name
        for index, solid in enumerate(cutters):
            solid.name = f"{plate.name}_cutter_{index}"
        strip_parts += [uncut, cut] + cutters
        previews.append(cut)
    groups.append(strip_parts)

parts = [part for strip_parts in groups for part in strip_parts]

preview = previews[0].copy()
for mesh in previews[1:]:
    preview.join(mesh)

write_parts(parts, fab_dir, "beds_0", preview=preview)

viewer = Viewer()
for strip_index, strip_parts in enumerate(groups):
    group = viewer.scene.add_group(f"beds_{strip_index}_0")
    for part in strip_parts:
        color = RED if "_cutter_" in part.name else GREY if part.name.endswith("_uncut") else None
        viewer.scene.add(part, name=part.name, parent=group, facecolor=color)

viewer.show()
