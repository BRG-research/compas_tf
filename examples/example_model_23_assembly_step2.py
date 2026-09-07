"""Assembly step 2 - screw the head plates onto the columns.

Second of the ``example_model_23_assembly_*`` series; see step 1 for how the
previews reach the docs.

A Power Base comes apart at its coupling nut. The half with the base plate
stays anchored in the slab from step 1; the Ø 106 x 12 head plate goes onto the
column first, flat on trestles, where three SHERPA 8 x 180 screws can be driven
into the end grain comfortably. This step is that operation: the four columns
lying on their side, each with its head plate screwed on.

The plate is sunk into the column by its own thickness, because that is how it
is fixed - into a machined pocket - so what overlaps the timber here is the
pocket. The column is drawn ghosted so the plate and the screws inside it show.

The columns are laid down by the transformation that takes each one from where
it stands in the model to where it lies here, and the SAME transformation is
applied to its plate and screws - so the fit between column and connector is
the model's, not something re-derived for the picture.
"""

import pathlib

import compas
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.model import TFModel
from compas_tf.support import SupportElement
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step2"

SPACING = 700.0  # mm between the columns as they lie side by side

# The column is ghosted so the screws and the recessed plate show through it;
# the steel stays solid. No hues - the docs viewer draws black edges, and those
# are what separate the parts.
GHOST = (0.72, 0.74, 0.76, 0.22)
SOLID = (0.72, 0.74, 0.76, 1.0)
COLUMN_OPACITY = 0.25  # the compas viewer's own way of saying the same thing
BLACK = (0.05, 0.05, 0.05)


# ------------------------------------------------------------------ #
# Pair each column with its support, and lay it down.
#
# The source frame is the top face of the head plate, with the support's OWN
# axes rather than the world's: each quarter is rotated 90 degrees about z in
# the model, and taking the world axes here would carry that roll into the
# picture and lay the four columns four different ways up.
# ------------------------------------------------------------------ #

model: TFModel = compas.json_load(data_dir / "cantilevers_baked_model.json")
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)
columns = sorted((element for element in model.elements() if isinstance(element, ColumnElement)), key=lambda element: element.name)

column_meshes = []
head_meshes = []
screw_meshes = []
for index, (support, column) in enumerate(zip(supports, columns)):
    placed = Frame.worldXY().transformed(support.placement)
    source = Frame(Point(0, 0, SupportElement.HEIGHT).transformed(support.placement), placed.xaxis, placed.yaxis)
    # Local +z (up into the column) becomes +x, so the column lies along x with
    # its connector end at the origin.
    target = Frame(Point(0, index * SPACING, 0), Vector(0, 1, 0), Vector(0, 0, 1))
    lay_down = Transformation.from_frame_to_frame(source, target)

    timber = column.modelgeometry.transformed(lay_down)
    timber.name = column.name
    column_meshes.append(timber)

    # Sink the head plate into the column end, the depth the datasheet asks
    # for. What overlaps the timber here is the pocket that gets machined out
    # of it, so the two are modelled overlapping rather than butted: the
    # boolean that cuts the pocket needs the solid to be inside the column.
    # The screws are driven through the plate, so they move down with it.
    recess = Translation.from_vector(placed.zaxis * SupportElement.HEAD_PLATE_RECESS)

    plate = support.head_plate.transformed(lay_down * recess)
    plate.name = f"{support.name}_head_plate"
    head_meshes.append(plate)

    for screw, brep in enumerate(support.column_screws):
        solid = brep.transformed(lay_down * recess)
        solid.name = f"{support.name}_screw_{screw}"
        screw_meshes.append(solid)

# Set them on the ground rather than through it: they lie on the capitel, which
# is wider than the shaft, so the resting height comes from the geometry. Only
# the columns are asked for it - the connector is inside them.
solids = column_meshes + head_meshes + screw_meshes
lift = Translation.from_vector([0, 0, -min(timber.aabb().zmin for timber in column_meshes)])
for solid in solids:
    solid.transform(lift)

print(f"{len(column_meshes)} columns, {len(head_meshes)} head plates, {len(screw_meshes)} screws")
print(f"first column, laid down: {column_meshes[0].aabb()}")
print(f"head plate: exact Brep, {len(head_meshes[0].faces)} faces")
print(f"screws: {SupportElement.SCREW_COUNT} x {SupportElement.SCREW_DIAMETER} x {SupportElement.SCREW_LENGTH} mm per column")

# ------------------------------------------------------------------ #
# Write the preview the docs page loads, and the spec list under it.
# ------------------------------------------------------------------ #

written = write_colored_obj(
    [(timber, GHOST) for timber in column_meshes] + [(plate, SOLID) for plate in head_meshes] + [(solid, SOLID) for solid in screw_meshes],
    assembly_dir / f"{STEP}_preview.obj",
)
print("written: " + ", ".join(str(path) for path in written.values()))

lines = [
    "<!-- Generated by examples/example_model_23_assembly_step2.py - do not edit. -->",
    "",
    "**Per column**",
    "",
    f"- 1 x head plate &mdash; &Oslash; {SupportElement.HEAD_PLATE_DIAMETER} mm, "
    f"{SupportElement.HEAD_PLATE_THICKNESS} mm thick, let {SupportElement.HEAD_PLATE_RECESS} mm into a pocket in the column end",
    f"- {SupportElement.SCREW_COUNT} x SHERPA screw {SupportElement.SCREW_DIAMETER} x {SupportElement.SCREW_LENGTH} mm, "
    f"driven at {SupportElement.SCREW_ANGLE}&deg; to each other into the end grain",
    "",
    f"**{len(columns)} columns** &mdash; {len(head_meshes)} head plates, {len(screw_meshes)} screws in total.",
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
for timber in column_meshes:
    viewer.scene.add(timber, name=timber.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("head_plates")
for plate in head_meshes:
    viewer.scene.add(plate, name=plate.name, parent=group, linecolor=BLACK)

group = viewer.scene.add_group("screws")
for solid in screw_meshes:
    viewer.scene.add(solid, name=solid.name, parent=group, linecolor=BLACK)

# Meshes here, not the Breps: a Brep's aabb is a property, a Mesh's is a
# method, and the columns bound the scene anyway.
zoom_to(viewer, [timber.aabb() for timber in column_meshes])
viewer.renderer.camera.position.set(-1800, -600, 1100)
viewer.renderer.camera.target.set(400, 1050, 170)



viewer.show()
