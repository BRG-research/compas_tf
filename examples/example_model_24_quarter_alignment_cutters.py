"""Vertical alignment cutters for a laid-flat quarter.

Every plate in the quarter is laid flat on its TOP face (the fabrication
reference - see :meth:`compas_tf.plate.PlateElement.lay_flat_transform`), so the
face that was topmost in the building becomes the one resting on the ground.
That face is then extruded straight UP into a prism, and the prism is
boolean-differenced against the plate.

The point is alignment, not shape. The prism is the volume directly above the
plate's own footprint, so anything the difference returns is material that
overhangs that footprint - exactly what a vertical reference (a jig wall, a
saw's approach, a stacked part above) would collide with. On this quarter that
is 0.60% of the plate volume, and it is only non-zero because the plates taper:
a plate of constant section would return nothing at all.

Why this is cheap where a general boolean is not: the cutter is ONE planar
profile swept along a single vector. It needs no lofting, no cutter mesh, and it
does not care whether the plate is prismatic - the top face lands exactly flat
on z=0 for all 145 plates in the model, which is what makes the extrusion
well-defined in the first place.

Cutters are drawn in RED, the laid-flat plates in grey.
"""

import pathlib

import compas
from compas.colors import Color
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements.group import Group
from compas_occt import _occt
from compas_occt.brep import OCCBrep
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.plate import PlateElement
from compas_tf.viewer import human_figure

data_dir = pathlib.Path(__file__).parent.parent / "data"

GREY = Color(0.85, 0.85, 0.85)  # the laid-flat plate
RED = Color(0.9, 0.2, 0.2)  # the vertical alignment cutter
BLACK = Color(0.0, 0.0, 0.0)  # the top-face outline the cutter is swept from
OVERSHOOT = 10.0  # mm the prism is pushed past the top of the plate, so it cuts cleanly

model: TFModel = TFModel.from_model(compas.json_load(data_dir / "cantilevers_model.json"))
quarter: TFModel = model.find_group_with_name("quarter_model_0")

# Fold every plate's placement into its own transformation and zero the groups,
# so a plate's transformation IS its world placement (same preparation the other
# quarter fabrication examples do).
plates = [element for element in quarter.elements() if isinstance(element, PlateElement)]
placements = {plate: plate.modeltransformation for plate in plates}
for node in quarter.tree.nodes:
    element = getattr(node, "element", None)
    if isinstance(element, Group):
        element.transformation = Transformation()
quarter.transformation = Transformation()
for plate, placement in placements.items():
    plate.transformation = placement


def lay_flat(plate):
    """Lay the plate on its TOP face at its own plan position, body up (+Z)."""
    top = plate.top_frame
    x2d = Vector(top.xaxis[0], top.xaxis[1], 0.0)
    if x2d.length < 1e-9:  # long edge runs vertical - use the top y
        x2d = Vector(top.yaxis[0], top.yaxis[1], 0.0)
    xaxis = x2d.unitized()
    yaxis = Vector(0, 0, -1).cross(xaxis)  # target z down -> body up
    target = Frame(Point(top.point[0], top.point[1], 0.0), xaxis, yaxis)
    return Transformation.from_frame_to_frame(top, target) * plate.transformation


def _loop(polyline, xform):
    """The polyline in laid-flat space, without its duplicated closing point."""
    points = [Point(*point).transformed(xform) for point in polyline.points]
    if points[0].distance_to_point(points[-1]) < 1e-9:
        points = points[:-1]
    return points


def plate_solid(plate, xform):
    """The laid-flat plate as a Brep: two planar caps plus one quad per edge."""
    bottom = _loop(plate.bottom, xform)
    top = _loop(plate.top, xform)
    rise = Vector.from_start_end(Point(*Polygon(bottom).centroid), Point(*Polygon(top).centroid))
    if rise.dot(Polygon(bottom).normal) < 0:  # keep the winding outward
        bottom = list(reversed(bottom))
        top = list(reversed(top))
    polygons = [Polygon(list(reversed(bottom))), Polygon(top)]
    for i in range(len(bottom)):
        j = (i + 1) % len(bottom)
        polygons.append(Polygon([bottom[i], bottom[j], top[j], top[i]]))
    return OCCBrep.from_polygons(polygons, solid=True)


def alignment_cutter(plate, xform, height):
    """The plate's top face, swept straight up - the vertical reference volume."""
    profile = Polygon(_loop(plate.top, xform))
    if profile.normal[2] < 0:  # the face has to look UP to sweep upward
        profile = Polygon(list(reversed(profile.points)))
    shape = _occt.make_face_polygon([list(point) for point in profile.points])
    face = OCCBrep.from_native(shape).faces[0]
    return OCCBrep.from_extrusion(face, Vector(0, 0, height + OVERSHOOT))


viewer = Viewer()
plates_group = viewer.scene.add_group("quarter__laid_flat")
cutters_group = viewer.scene.add_group("alignment_cutters")

total_volume = 0.0
overhang_volume = 0.0

for plate in plates:
    xform = lay_flat(plate)
    body = plate_solid(plate, xform)
    height = max(point[2] for point in body.aabb.points)
    cutter = alignment_cutter(plate, xform, height)

    # Whatever survives the difference sticks out beyond the plate's own
    # footprint - the material a vertical reference would run into.
    overhang = OCCBrep.from_boolean_difference(body, cutter)
    total_volume += body.volume
    overhang_volume += sum(solid.volume for solid in overhang.solids) if overhang.solids else 0.0

    viewer.scene.add(body, name=f"{plate.name}", parent=plates_group, facecolor=GREY)
    viewer.scene.add(cutter, name=f"{plate.name}_cutter", parent=cutters_group, facecolor=RED, opacity=0.35)
    viewer.scene.add(Polygon(_loop(plate.top, xform)), name=f"{plate.name}_top", parent=cutters_group, linecolor=BLACK)

print(f"{len(plates)} plates laid flat, {len(plates)} vertical alignment cutters")
print(f"plate volume        : {total_volume:12.0f} mm3")
print(f"outside footprint   : {overhang_volume:12.0f} mm3  ({overhang_volume / total_volume * 100:.2f}%)")

# A 1.75 m figure, for reading the scale of the model at a glance. Reference
# geometry only - plain polylines, never added to the model itself.
for _part in human_figure(point=[3600, 0, 0]):
    viewer.scene.add(_part, name="scale_figure", linecolor=Color(0.35, 0.35, 0.35), linewidth=2)

viewer.show()
