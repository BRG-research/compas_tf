"""Assembly step 1 - set out the column bases (Sherpa Power Base 150402_PB_L-140-C).

First of the ``example_model_23_assembly_*`` series. Each step writes one
coloured preview to ``data/assembly/``, which the docs publish at ``_models/``
and ``docs/assembly.md`` embeds as a 3D viewer under a title and a description
- the same pattern as the fabrication part list, without the tables.

This step is the survey. A total station on its tripod is set up on the centre
of the bay, and the points it stakes out are the FOUR BOLT HOLES of each Sherpa
power base plus the FOUR CORNERS of its plate - 4 supports x 8 = 32 points. Both
sets are detected off the connector itself
(:attr:`compas_tf.support.SupportElement.base_hole_points` and
``base_corner_points``), so the marks cannot drift from the part that gets
bolted down.

Everything that is a manufactured part here is a Brep, not a mesh: the
connector with its four real drillings, the anchors, the screws, the marker
balls and the beams. They are tessellated once, on the way into the preview
file, by :func:`compas_tf.writer.write_colored_obj`.

The total station is the exception - it is a downloaded mesh, and it is
modelled in METRES (see data/total_station/README.md) while everything else
here is in millimetres, so it is scaled uniformly by 1000 on the way in:
1.10 x 1.20 x 1.73 m becomes 1097 x 1202 x 1727 mm.
"""

import math
import pathlib

import compas
from compas.colors import Color
from compas.datastructures import Mesh
from compas.geometry import Brep
from compas.geometry import Cylinder
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Scale
from compas.geometry import Sphere
from compas.geometry import Translation
from compas.geometry import Vector
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.support import SupportElement
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step1"

# The station mesh is in metres, the building in millimetres.
M_TO_MM = 1000.0

# Where the instrument is set up: on the centre of the bay, so all the points
# are the same distance away and are staked out from one station without moving
# it - the oculus is open above it, so nothing is in the way.
STATION_POINT = Point(0, 0, 0)
STATION_HEADING = math.radians(45)  # squared to the diagonal of the grid

# Height of the telescope above the ground on the scaled mesh - where the
# beams start.
STATION_EYE = 1500.0

POINT_RADIUS = 8.0  # a marked point, drawn as a small ball
BEAM_RADIUS = 3.0  # a laser beam, drawn as a thin rod

BLUE = Color(0.10, 0.35, 0.85)
PINK = Color(1.00, 0.35, 0.75)
BRASS = Color(0.80, 0.62, 0.20)
BLACK = Color(0.05, 0.05, 0.05)

# The connector is context, not the subject, so it is ghosted - the same way
# step 2 ghosts the columns - and the anchors and screws inside it show through.
GHOST = (0.55, 0.60, 0.66, 0.22)
GHOST_OPACITY = 0.25  # the compas viewer's own way of saying the same thing

# ------------------------------------------------------------------ #
# The four supports, and the eight points to mark under each. Read off the
# built model rather than re-derived, so the survey and the structure cannot
# drift apart.
# ------------------------------------------------------------------ #

model: TFModel = compas.json_load(data_dir / "cantilevers_baked_model.json")
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)

connectors = []
fasteners = []
anchor_points = []
corner_points = []
for support in supports:
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

    holes = support.base_hole_points
    anchor_points.append(holes)
    corner_points.append(support.base_corner_points)
    print(f"{support.name}: " + "  ".join(f"({point.x:8.1f}, {point.y:8.1f})" for point in holes))

print(f"{len(supports)} supports, {sum(len(holes) for holes in anchor_points)} anchor points, {sum(len(corners) for corners in corner_points)} plate corners")
print(f"{len(fasteners)} fasteners: {SupportElement.ANCHOR_COUNT} anchors + {SupportElement.SCREW_COUNT} screws per support")

# ------------------------------------------------------------------ #
# The instrument: metres -> millimetres, then set up on its point.
# ------------------------------------------------------------------ #

station = Mesh.from_obj(data_dir / "total_station" / "total_station_es105.obj")
station.transform(Translation.from_vector(STATION_POINT) * Rotation.from_axis_and_angle(Vector.Zaxis(), STATION_HEADING) * Scale.from_factors([M_TO_MM, M_TO_MM, M_TO_MM]))
station.name = "total_station_es105"
print(f"total station, scaled to mm: {station.aabb()}")

# ------------------------------------------------------------------ #
# A ball on every point, and a beam from the telescope to it.
# ------------------------------------------------------------------ #

eye = Point(STATION_POINT.x, STATION_POINT.y, STATION_EYE)


def mark(point, tag):
    """One marked point and the beam that finds it."""
    ball = Brep.from_sphere(Sphere(POINT_RADIUS, point=point))
    ball.name = f"point_{tag}"
    beam = Brep.from_cylinder(Cylinder.from_line_and_radius(Line(eye, point), BEAM_RADIUS))
    beam.name = f"beam_{tag}"
    return ball, beam


holes = []
hole_beams = []
corners = []
corner_beams = []
for index in range(len(supports)):
    for number, point in enumerate(anchor_points[index]):
        ball, beam = mark(point, f"{index}_{number}")
        holes.append(ball)
        hole_beams.append(beam)
    for number, point in enumerate(corner_points[index]):
        ball, beam = mark(point, f"corner_{index}_{number}")
        corners.append(ball)
        corner_beams.append(beam)

# ------------------------------------------------------------------ #
# Write the preview the docs page loads (OBJ + MTL, one colour per role).
# ------------------------------------------------------------------ #

written = write_colored_obj(
    [(station, BLUE)]
    + [(connector, GHOST) for connector in connectors]
    + [(fastener, BRASS) for fastener in fasteners]
    + [(beam, BLUE) for beam in hole_beams]
    + [(ball, BLUE) for ball in holes]
    + [(beam, PINK) for beam in corner_beams]
    + [(ball, PINK) for ball in corners],
    assembly_dir / f"{STEP}_preview.obj",
)
print("written: " + ", ".join(str(path) for path in written.values()))

# ------------------------------------------------------------------ #
# And the setting-out lists the docs page shows under the viewer, written as a
# markdown fragment that docs/assembly.md pulls in with a snippet. Generated
# rather than typed, so the coordinates on the page are the ones this script
# actually staked out.
# ------------------------------------------------------------------ #


def _row(support, points):
    return f"- `{support.name}` &mdash; " + " &middot; ".join(f"({point.x:.0f}, {point.y:.0f})" for point in points)


lines = [
    "<!-- Generated by examples/example_model_23_assembly_step1.py - do not edit. -->",
    "",
    "**Bolt holes to mark (blue)**",
    "",
    *[_row(support, points) for support, points in zip(supports, anchor_points)],
    "",
    "**Base plate corners to measure (pink)**",
    "",
    *[_row(support, points) for support, points in zip(supports, corner_points)],
    "",
    "All at `z = 0`, in millimetres on the building grid.",
    "",
]
points_file = assembly_dir / f"{STEP}_points.md"
points_file.write_text("\n".join(lines))
print(f"written: {points_file}")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #

viewer = Viewer()

viewer.scene.add(station, name=station.name, facecolor=BLUE, show_lines=False)

group = viewer.scene.add_group("supports")
for connector in connectors:
    viewer.scene.add(connector, name=connector.name, parent=group, opacity=GHOST_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("fasteners")
for fastener in fasteners:
    viewer.scene.add(fastener, name=fastener.name, parent=group, facecolor=BRASS, linecolor=BLACK)

group = viewer.scene.add_group("anchor_points")
for ball, beam in zip(holes, hole_beams):
    viewer.scene.add(ball, name=ball.name, parent=group, facecolor=BLUE, linecolor=BLACK)
    viewer.scene.add(beam, name=beam.name, parent=group, facecolor=BLUE, linecolor=BLACK)

group = viewer.scene.add_group("plate_corners")
for ball, beam in zip(corners, corner_beams):
    viewer.scene.add(ball, name=ball.name, parent=group, facecolor=PINK, linecolor=BLACK)
    viewer.scene.add(beam, name=beam.name, parent=group, facecolor=PINK, linecolor=BLACK)

zoom_to(viewer, [station.aabb()] + [support.aabb for support in supports])
viewer.renderer.camera.position.set(-3394, -3376, 260)
viewer.renderer.camera.target.set(-2890, -2890, 75)

viewer.show()
