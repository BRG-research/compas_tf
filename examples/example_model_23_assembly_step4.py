"""Assembly step 4 - stand the columns on their bases.

Third of the ``example_model_23_assembly_*`` series; see step 2 for how the
previews reach the docs.

Steps 1 and 2 prepared the two halves separately: the base plates staked out
and bolted into the slab, and the head plates screwed into the ends of the four
columns lying flat on trestles. This step is the lift - the columns come
upright and are set down on the four Power Bases, where the coupling nut joins
the half in the slab to the half in the column and takes up the height.

Nothing here is re-derived for the picture. The four supports and the four
columns are drawn WHERE THE MODEL PUTS THEM, each with its own
``placement`` - so if the two do not meet, the model is wrong, not the drawing.
That is what the seating check below prints: the top face of every head plate
against the bottom face of the column that stands on it, and the two centres
against each other.

The columns are ghosted, as in step 3, so the fasteners inside them show: the
three SHERPA screws running up out of the head plate into the end grain, and
the four anchors going the other way, down out of the base plate into the slab.
"""

import pathlib

import compas
from compas.colors import Color
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.model import TFModel
from compas_tf.support import SupportElement
from compas_tf.viewer import human_figure
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step4"

# The column is ghosted so the screws and the connector under it show through;
# the steel stays solid. No hues - the docs viewer draws black edges, and those
# are what separate the parts.
GHOST = (0.72, 0.74, 0.76, 0.22)
COLUMN_OPACITY = 0.25  # the compas viewer's own way of saying the same thing
# One colour for every object - the black feature edges separate the parts.
STEEL = Color(0.72, 0.74, 0.76)
BLACK = Color(0.05, 0.05, 0.05)

# ------------------------------------------------------------------ #
# The four supports and the four columns, in their placed positions.
#
# Sorted by name, which pairs them: ``support_0`` is the base under
# ``column_0``. The pairing is checked below rather than trusted - the seating
# report prints how far apart the two centres are, and a mismatched pair would
# come out metres off, not tenths of a millimetre.
# ------------------------------------------------------------------ #

model: TFModel = compas.json_load(data_dir / "cantilevers_baked_model.json")
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)
columns = sorted((element for element in model.elements() if isinstance(element, ColumnElement)), key=lambda element: element.name)

connectors = []
fasteners = []
timbers = []
for support, column in zip(supports, columns):
    # The exact solid, built from the datasheet - four real drillings, two true
    # hexagonal nuts, a true cylindrical head plate - not the coarse OBJ.
    connector = support.brep
    connector.name = support.name
    connectors.append(connector)

    # The connector is not just the cast body: 4 anchors down into the slab and
    # 3 SHERPA screws up into the column are part of it.
    for index, fastener in enumerate(support.fasteners):
        fastener.name = f"{support.name}_fastener_{index}"
        fasteners.append(fastener)

    # The column as the model carves it - shaft, capitel and the cuts that take
    # the ribs - already in model space, so it needs no transformation here.
    timber = column.modelgeometry
    timber.name = column.name
    timbers.append(timber)

# ------------------------------------------------------------------ #
# Does the column actually sit on the base? Measured, not assumed.
#
# Vertically: the top face of the head plate is the face the column stands on,
# so it should be at SupportElement.HEIGHT - the bottom of the 150-200 mm
# adjustment range - and the column's bottom face should be there too.
#
# Horizontally: the head plate is a Ø 106 disc under a 220 x 220 shaft, so the
# check is that the two centres coincide, not that the outlines match.
#
# What the check turns up is that the model BUTTS the two: the plate's top face
# and the column's end face are both at 150, to the last decimal. The
# HEAD_PLATE_RECESS pocket that step 3 sinks the plate into is not carved out
# of the baked column, so the plate reads as a disc under the end grain here
# rather than inside it. On site the column drops 12 mm lower than this and the
# coupling nut takes the difference up again; for the picture, the screws
# standing in the timber show where the pocket goes.
# ------------------------------------------------------------------ #


def bottom_face_centre(mesh):
    """Centre of the column's lowest face - the end that meets the connector."""
    points = [mesh.vertex_point(vertex) for vertex in mesh.vertices()]
    zmin = min(point.z for point in points)
    lowest = [point for point in points if abs(point.z - zmin) < 1e-6]
    return sum(lowest[1:], lowest[0]) * (1.0 / len(lowest)), zmin


seating = []
for support, column, timber in zip(supports, columns, timbers):
    head = support.head_plate.aabb
    seat = support.head_plate_circle.frame.point  # centre of the plate's top face
    centre, zmin = bottom_face_centre(timber)
    seating.append((support.name, column.name, seat.x, seat.y, zmin))
    print(
        f"{support.name} head plate top z={head.zmax:7.2f} (HEIGHT={SupportElement.HEIGHT})"
        f" | {column.name} bottom z={zmin:7.2f}, gap={zmin - head.zmax:+.3f} mm"
        f" | centres off by ({centre.x - seat.x:+.3f}, {centre.y - seat.y:+.3f}) mm"
    )

print(f"{len(connectors)} supports, {len(timbers)} columns, {len(fasteners)} fasteners")
print(f"supports z {min(support.aabb.zmin for support in supports):.1f} .. {max(support.aabb.zmax for support in supports):.1f} mm")
print(f"columns  z {min(timber.aabb().zmin for timber in timbers):.1f} .. {max(timber.aabb().zmax for timber in timbers):.1f} mm")
print(
    f"fasteners z {min(fastener.aabb.zmin for fastener in fasteners):.1f} .. {max(fastener.aabb.zmax for fastener in fasteners):.1f} mm"
    " - anchors down into the slab, screws up into the end grain"
)
print(
    f"head plate: Ø {SupportElement.HEAD_PLATE_DIAMETER} x {SupportElement.HEAD_PLATE_THICKNESS} mm, top face at z={SupportElement.HEIGHT} - "
    f"the {SupportElement.HEAD_PLATE_RECESS} mm pocket of step 3 is not cut into the baked column, so the two butt here"
)

# ------------------------------------------------------------------ #
# Write the preview the docs page loads (OBJ + MTL, one colour per role).
# ------------------------------------------------------------------ #

written = write_colored_obj(
    [(timber, GHOST) for timber in timbers] + [(connector, STEEL) for connector in connectors] + [(fastener, STEEL) for fastener in fasteners],
    assembly_dir / f"{STEP}_preview.obj",
)
print("written: " + ", ".join(str(path) for path in written.values()))

# ------------------------------------------------------------------ #
# And the list the docs page shows under the viewer: which column stands on
# which base, and where. ONLY the numbers are generated - the headings around
# them are prose in docs/assembly.md, which pulls each list in by section name
# (`...points.md:seating`), so the wording can change without re-running this.
# ------------------------------------------------------------------ #

lines = [
    "<!-- Generated by examples/example_model_23_assembly_step4.py - do not edit.",
    "     The prose around these lists is in docs/assembly.md; only the",
    "     numbers live here. -->",
    "",
    "<!-- --8<-- [start:seating] -->",
    *[f"- `{column}` stands on `{support}` &mdash; ({x:.0f}, {y:.0f}), foot at `z = {z:.0f}` mm" for support, column, x, y, z in seating],
    "<!-- --8<-- [end:seating] -->",
    "",
    "<!-- --8<-- [start:totals] -->",
    f"- {len(timbers)} columns, tops at `z = {max(timber.aabb().zmax for timber in timbers):.0f}` mm",
    f"- {len(fasteners)} fasteners &mdash; {len(supports) * SupportElement.ANCHOR_COUNT} anchors down into the slab, "
    f"{len(supports) * SupportElement.SCREW_COUNT} screws up into the end grain",
    "<!-- --8<-- [end:totals] -->",
    "",
]
points_file = assembly_dir / f"{STEP}_points.md"
points_file.write_text("\n".join(lines))
print(f"written: {points_file}")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #

viewer = Viewer()

group = viewer.scene.add_group("columns")
for timber in timbers:
    viewer.scene.add(timber, name=timber.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("supports")
for connector in connectors:
    viewer.scene.add(connector, name=connector.name, parent=group, facecolor=STEEL, linecolor=BLACK)

group = viewer.scene.add_group("fasteners")
for fastener in fasteners:
    viewer.scene.add(fastener, name=fastener.name, parent=group, facecolor=STEEL, linecolor=BLACK)

# Meshes here for the columns, not the elements: an element's aabb is the box
# of the shaft, and the capitel that flares inwards at the top would fall
# outside the framing.
zoom_to(viewer, [timber.aabb() for timber in timbers] + [support.aabb for support in supports])
viewer.renderer.camera.position.set(-7200, -7600, 3600)
viewer.renderer.camera.target.set(0, 0, 1200)



# A 1.75 m figure, for reading the scale of the model at a glance. Reference
# geometry only - plain polylines, never added to the model itself.
for _part in human_figure(point=[3600, 0, 0]):
    viewer.scene.add(_part, name="scale_figure", linecolor=Color(0.35, 0.35, 0.35), linewidth=2)

viewer.show()
