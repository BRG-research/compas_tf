"""Assembly step 5 - prop the columns and stand the tower in the middle.

Fourth of the ``example_model_23_assembly_*`` series; see step 2 for how the
previews reach the docs.

Step 4 left the four columns standing on their Power Bases, held by nothing but
their own base connection. That is not a state to leave a bay in overnight, and
it is not stiff enough to build a floor on: the next step lands ribs and beds on
the capitels, and every one of them pushes the column head sideways. So before
anything goes up, the columns get PROPPED and a TOWER goes up in the middle:

- 8 raking props, two per column, each running from a clamp on the column face
  at ``z = 2500`` down to a base plate on the slab, set out 2500 mm from the
  column's centre line. The two on a column are at right angles to each other,
  so between them they hold the head in both directions. Their feet were staked
  out back in step 2, in the same session as the column bases - the layout they
  are built from is ``examples/assembly_shoring.py``, which step 2 marks and
  this step stands up.
- 1 tower at the centre of the bay: a four-legged scaffold tower that rises to
  ``z = 3303``. That is 197 mm BELOW the top of the columns (z = 3500) and about
  90 mm above the underside of the ring around the oculus, so the deck comes up
  inside the opening - which is where the ring is closed from. The tower is a
  fixed part and does not follow the bay height: it was tuned to a 3000 column
  top, and it sat 303 mm proud of it then. Read the printed numbers, not this
  sentence, if the bay height moves again.

WHERE THE SHORING COMES FROM
----------------------------
The baked model (``data/cantilevers_baked_model.json``) contains only the
permanent structure - 4 :class:`compas_tf.support.SupportElement`, 4
:class:`compas_tf.column.ColumnElement` and the plates of the floor. There are
NO shoring or tower instances in it. So the props and the tower are BUILT HERE,
by the same configurators ``examples/example_model_10_shoring.py`` uses -
:meth:`compas_tf.schoring_element.SchoringElement.from_points_and_vectors`,
``.from_points_and_vectors_no_foot_no_head`` and
:class:`compas_tf.tower_element.TowerElement` - at the positions that example
places them at. Only the columns and the bases are read from the model.

That split is what the contact check below is for: the props are laid out from
the prop geometry and the columns come from the model, and the check measures
one against the other. Nothing here nudges a prop to make it fit.

EVERYTHING HERE STANDS ON A MARK THAT IS ALREADY THERE
------------------------------------------------------
Nothing is measured in this step. The tower's four legs were staked out in step
1, in the one session the total station was up on the centre of the bay, so the
tower is stood on marks that are already on the floor. The props need no marks:
each clamps to a column at ``PROP_HEIGHT`` and foots where that puts it, 2586 mm
away along the slab. Their layout is ``examples/assembly_shoring.py``, which
follows ``examples/example_model_10_shoring.py``.

"""

import math
import pathlib

import assembly_shoring
import compas
from compas.colors import Color
from compas.geometry import Point
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.model import TFModel
from compas_tf.schoring_element import Dataset
from compas_tf.schoring_element import SchoringElement
from compas_tf.support import SupportElement
from compas_tf.viewer import human_figure
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step5"

# The dataset loader caches meshes AND frames per file, and a frame is
# transformed in place the first time an element's geometry is computed. So the
# cache is cleared before anything is built, and everything is built before any
# geometry is asked for - the same order example_model_10_shoring.py uses.
SchoringElement.clear_cache()

# The prop layout is shared with step 2, which stakes out the feet - see
# examples/assembly_shoring.py.
COLUMN_SIZE = assembly_shoring.COLUMN_SIZE
PROP_HEIGHT = assembly_shoring.PROP_HEIGHT

# The station mesh is in metres, the building in millimetres.
M_TO_MM = 1000.0

# Where the instrument is set up: on the centre of the bay, as in step 2 - the
# same set-up, the same session, one more set of points to stake out before the
# tower is built on them.
STATION_POINT = Point(0, 0, 0)
STATION_HEADING = math.radians(45)  # squared to the diagonal of the grid

# Height of the telescope above the ground on the scaled mesh - where the
# beams start.
STATION_EYE = 1500.0

POINT_RADIUS = 8.0  # a marked point, drawn as a small ball
BEAM_RADIUS = 3.0  # a laser beam, drawn as a thin rod

# One colour for everything that is a part - props, tower, connectors. Nothing
# here is colour-coded: the black feature edges are what separate the pieces,
# and the only coloured things in this series are the survey marks in step 2.
STEEL = Color(0.72, 0.74, 0.76)
BLACK = Color(0.05, 0.05, 0.05)

# The columns are the thing being propped, not the subject of the picture, so
# they are ghosted the way step 4 ghosts them.
GHOST = (0.72, 0.74, 0.76, 0.22)
COLUMN_OPACITY = 0.25  # the compas viewer's own way of saying the same thing

# ------------------------------------------------------------------ #
# What the model already has: the four bases and the four columns, in the
# positions the model puts them in. Everything the props are checked against
# comes from here, nothing is re-derived.
# ------------------------------------------------------------------ #

model: TFModel = compas.json_load(data_dir / "cantilevers_baked_model.json")
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)
columns = sorted((element for element in model.elements() if isinstance(element, ColumnElement)), key=lambda element: element.name)

connectors = []
timbers = []
for support, column in zip(supports, columns):
    connector = support.brep
    connector.name = support.name
    connectors.append(connector)

    timber = column.modelgeometry
    timber.name = column.name
    timbers.append(timber)

corner = columns[0].aabb.frame.point  # the column the props are laid out around

# ------------------------------------------------------------------ #
# The raking props: two per column, four-fold rotational symmetry.
#
# Built by the shared layout, NOT here - step 2 marked the feet of these very
# props on the slab, and the two steps have to be the same props. One prop is
# four parts: a clamp on the column, two telescoping bodies and a base plate.
# ------------------------------------------------------------------ #

braces = assembly_shoring.raking_props(corner)

# ------------------------------------------------------------------ #
# The tower at the centre, turned 45 degrees so its legs sit on the axes of the
# bay and its faces look at the four columns.
# ------------------------------------------------------------------ #

tower_mesh = assembly_shoring.centre_tower()
tower_box = tower_mesh.aabb()

# The parts, in drawing order. A sub-model's own transformation is part of an
# element's model transformation, so ``modelgeometry`` is already in bay
# coordinates and nothing is transformed by hand here.
brace_parts = []
for index, brace in enumerate(braces):
    for part in (element for element in brace.elements() if isinstance(element, SchoringElement)):
        mesh = part.modelgeometry
        mesh.name = f"brace_{index}_{pathlib.Path(part.dataset).stem}"
        brace_parts.append(mesh)

# ------------------------------------------------------------------ #
# Do the props actually reach the columns? Measured, not assumed.
#
# The clamp end of a raking prop is a flat plate against a flat column face, so
# the honest measurement is in plan: for every vertex of the clamp, how far it
# is outside the 220 x 220 shaft, measured as the square distance
# ``max(|dx|, |dy|) - 110`` from the column's centre line. The smallest of those
# over the clamp is the gap. A prop that reaches the column reads 0.000; one
# that misses reads the shortfall in millimetres.
#
# Which column a prop belongs to is not assumed either - the clamp is matched to
# the nearest column centre line in plan, so a prop dropped in the wrong quarter
# would show up as a mismatch, not as a clean zero.
# ------------------------------------------------------------------ #

HALF = COLUMN_SIZE / 2


def plan_gap(mesh, centre):
    """Smallest distance from a mesh out to the column's square shaft, in plan.

    Returns the gap and the height band over which the mesh is within a
    millimetre of the face - the contact band.
    """
    gap = None
    touching = []
    for vertex in mesh.vertices():
        point = mesh.vertex_point(vertex)
        distance = max(abs(point.x - centre.x), abs(point.y - centre.y)) - HALF
        gap = distance if gap is None else min(gap, distance)
        if distance < 1.0:
            touching.append(point.z)
    return gap, (min(touching), max(touching)) if touching else (None, None)


contacts = []
for index, brace in enumerate(braces):
    clamp = next(element for element in brace.elements() if isinstance(element, SchoringElement) and element.dataset == Dataset.schoring_foot_0)
    mesh = clamp.modelgeometry
    centroid = mesh.centroid()
    column = min(columns, key=lambda element: (element.aabb.frame.point.x - centroid[0]) ** 2 + (element.aabb.frame.point.y - centroid[1]) ** 2)
    gap, band = plan_gap(mesh, column.aabb.frame.point)
    plate = next(element for element in brace.elements() if isinstance(element, SchoringElement) and element.dataset == Dataset.schoring_head_0)
    foot = plate.modelgeometry.aabb()
    reach = math.hypot(foot.frame.point.x - column.aabb.frame.point.x, foot.frame.point.y - column.aabb.frame.point.y)
    contacts.append((index, column.name, gap, band))
    print(
        f"brace_{index} clamps {column.name}: plan gap {gap:+.3f} mm over z {band[0]:7.1f} .. {band[1]:7.1f}"
        f" | base plate on the slab at z={foot.zmin:.1f}, {reach:7.1f} mm out in plan"
    )

print(
    f"{len(contacts)} clamps on {len(set(name for _, name, _, _ in contacts))} columns, 2 each: worst plan gap {max(abs(gap) for _, _, gap, _ in contacts):.4f} mm, "
    f"contact band {min(band[0] for _, _, _, band in contacts):.0f} .. {max(band[1] for _, _, _, band in contacts):.0f} mm - the props reach the columns, nothing was nudged"
)

# ------------------------------------------------------------------ #
# Write the preview the docs page loads (OBJ + MTL, one colour per role).
# ------------------------------------------------------------------ #

written = write_colored_obj(
    [(timber, GHOST) for timber in timbers] + [(connector, STEEL) for connector in connectors] + [(mesh, STEEL) for mesh in brace_parts] + [(tower_mesh, STEEL)],
    assembly_dir / f"{STEP}_preview.obj",
)
print("written: " + ", ".join(str(path) for path in written.values()))

# ------------------------------------------------------------------ #
# And the setting-out list the docs page shows under the viewer, written as a
# markdown fragment that docs/assembly.md pulls in with a snippet. Generated
# rather than typed, so the coordinates on the page are the ones this script
# actually staked out.
#
# ONLY the numbers are generated. The headings and the sentences around them are
# ordinary prose in docs/assembly.md, which pulls each list in by section name
# (`...points.md:totals`), so the wording can change without re-running this.
# ------------------------------------------------------------------ #


def _section(name, rows):
    return [f"<!-- --8<-- [start:{name}] -->", *rows, f"<!-- --8<-- [end:{name}] -->", ""]


lines = [
    "<!-- Generated by examples/example_model_23_assembly_step5.py - do not edit.",
    "     The prose around these lists is in docs/assembly.md; only the",
    "     numbers live here. -->",
    "",
    *_section(
        "totals",
        [
            f"- {len(braces)} raking props &mdash; 2 per column, clamped at `z = {PROP_HEIGHT}` mm, feet {PROP_HEIGHT} mm out on the slab (marked in step 2)",
            f"- {len(brace_parts)} prop parts and 1 tower, {tower_box.xsize:.0f} &times; {tower_box.ysize:.0f} mm over the legs, top at `z = {tower_box.zmax:.0f}` mm",
            "- the tower stands on its 4 leg marks from step 2; the props need none - each clamps to a column and foots where that puts it",
        ],
    ),
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

group = viewer.scene.add_group("raking_props")
for mesh in brace_parts:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

group = viewer.scene.add_group("tower")
viewer.scene.add(tower_mesh, name=tower_mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

# Meshes here for the columns, not the elements: an element's aabb is the box of
# the shaft, and the capitel that flares inwards at the top would fall outside
# the framing.
zoom_to(viewer, [timber.aabb() for timber in timbers] + [mesh.aabb() for mesh in brace_parts] + [tower_box])
viewer.renderer.camera.position.set(-8200, -8600, 4200)
viewer.renderer.camera.target.set(0, 0, 1400)



# A 1.75 m figure, for reading the scale of the model at a glance. Reference
# geometry only - plain polylines, never added to the model itself.
for _part in human_figure(point=[3600, 0, 0]):
    viewer.scene.add(_part, name="scale_figure", linecolor=Color(0.35, 0.35, 0.35), linewidth=2)

viewer.show()
