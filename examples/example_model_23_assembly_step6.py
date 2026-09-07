"""Assembly step 6 - land the first quarter of the floor, with its steel and its dowels.

Fifth of the ``example_model_23_assembly_*`` series; see step 2 for how the
previews reach the docs.

The four columns are up (step 4) and propped (step 5), so the first piece of
floor can go on. A QUARTER is one of the four children of ``quarters_model`` in
``data/cantilevers_baked_model.json`` - 34 plates: 2 outer ribs, 2 inner ribs,
3 inner beams, 3 inner-beam wedge plates, 6 t-sections and 18 bed plates. It
arrives as one assembled unit and is lowered onto ONE column.

WHAT COMES WITH IT
------------------
- the QUARTER, ``quarter_model_0`` - 34 plates;
- the two COLUMN STEEL PLATES for that column. In the model these are
  :class:`compas_tf.connectors.ConnectorElement` (the top-level ``connectors``
  group, 8 of them, 2 per column). Each is a flat 485 x 30 x 250 mm steel plate
  let into a slot that runs right through the column head and on into the end of
  a rib: ``BACK = 220`` mm on the column side - the full width of the shaft -
  and ``FRONT = 265`` mm into the rib;
- the DOWELS that pin those plates. In the model these are
  :class:`compas_tf.connectors.DowelCylinderElement` (the top-level
  ``connector_cylinders`` group, 32 of them, 4 per steel plate), named
  ``cylinder_column_0/1`` and ``cylinder_rib_0/1`` after the side they are
  driven from. They are made by
  :meth:`compas_tf.connectors.ConnectorElement.cylinder_elements` off the same
  ``_dowel_grid`` that drilled the holes, so a dowel and its hole cannot drift.

DO NOT CONFUSE THEM with the OTHER cylinders in the file. The 32
:class:`compas_tf.connectors.ConnectorCylinderElement` under
``floor_model/connectors`` are the screws through the contact wedges, and they
belong to step 9. Ø 50 x 100 pins here; Ø 20 x 160 screws there.

The plates and the dowels are not matched by name. Each steel plate is given the
column and the quarter THE MODEL'S OWN CONTACTS say it touches, and each dowel
is placed in a plate by transforming its centre into that plate's local frame
and testing it against the box - so a dowel in the wrong quarter would come out
as a plate with three dowels, not as a clean four.

WHAT THERE IS NO PLATE ON
-------------------------
There is no head plate on top of a column. The head plates in this model are the
ones under the columns, on the Sherpa Power Bases of step 3, at ``z = 150``. Up
here the column ends in a CAPITEL that flares out of the 220 mm shaft, and the
ribs are seated straight onto its sawn faces - so the check below is not "how
big is the gap over the plate" but "do the rib faces and the capitel faces lie
on the same planes". They do, to 0.0000 mm, and not one of the 11 bearing faces
is horizontal: every one of them is raked about 9 degrees off vertical. The
quarter is not set down on a seat, it is dropped onto a taper.
"""

import math
import pathlib
from collections import defaultdict

import compas
from compas.colors import Color
from compas.geometry import Point
from compas.geometry import Vector
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.connectors import ConnectorElement
from compas_tf.model import TFModel
from compas_tf.support import SupportElement
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step6"

# Which of the four quarters goes on first. The other three are step 7.
QUARTER = 0

# One colour for every object - the black feature edges separate the parts.
STEEL = Color(0.72, 0.74, 0.76)
BLACK = Color(0.05, 0.05, 0.05)

# What is already standing is ghosted; what this step adds is solid.
GHOST = (0.72, 0.74, 0.76, 0.22)
COLUMN_OPACITY = 0.25  # the compas viewer's own way of saying the same thing

# ------------------------------------------------------------------ #
# The model, and the two ways of reaching into it.
#
# There are TWO groups called ``connectors`` in this file - the column steel
# plates at the top level, and the wedges plus their screws under
# ``floor_model``. So groups are walked by PATH from the root, never found by a
# bare name search, which would silently return whichever one comes first.
# ------------------------------------------------------------------ #

model: TFModel = compas.json_load(data_dir / "cantilevers_baked_model.json")


def group_node(*path):
    """The tree node of a group, addressed by its path of names from the root."""
    node = model.tree.root
    for name in path:
        node = next(child for child in node.children if isinstance(child.element, Group) and child.element.name == name)
    return node


def group_parts(node):
    """Every non-group element under a node."""
    return [child.element for child in node.descendants if not isinstance(child.element, Group)]


def contact_map():
    """``{id(element): [(other, contacts), ...]}`` - the model's own answer to what touches what."""
    table = defaultdict(list)
    for edge in model.graph.edges():
        contacts = model.graph.edge_attribute(edge, name="contacts")
        if not contacts:
            continue
        a = model.graph.node_element(edge[0])
        b = model.graph.node_element(edge[1])
        table[id(a)].append((b, contacts))
        table[id(b)].append((a, contacts))
    return table


touching = contact_map()

quarter_node = group_node("floor_model", "quarters_model", f"quarter_model_{QUARTER}")
quarter_parts = group_parts(quarter_node)
quarter_ids = {id(element) for element in quarter_parts}

plates = sorted(group_parts(group_node("connectors")), key=lambda element: element.name)
dowels = group_parts(group_node("connector_cylinders"))

columns = sorted((element for element in model.elements() if isinstance(element, ColumnElement)), key=lambda element: element.name)
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)

print(f"quarter_model_{QUARTER}: {len(quarter_parts)} plates")
for child in quarter_node.children:
    if isinstance(child.element, Group):
        print(f"  {child.element.name:24s} {len(group_parts(child)):3d}")

# ------------------------------------------------------------------ #
# Which column does this quarter go on? The model is asked, not told.
#
# Every contact between one of the quarter's plates and a column is counted. A
# quarter that belonged to another column would show up as contacts spread over
# two of them, or as none at all.
# ------------------------------------------------------------------ #

on_column = defaultdict(lambda: [0, 0.0])
for plate in quarter_parts:
    for other, contacts in touching[id(plate)]:
        if isinstance(other, ColumnElement):
            on_column[other.name][0] += len(contacts)
            on_column[other.name][1] += sum(contact.polygon.area for contact in contacts)

for column in columns:
    count, area = on_column.get(column.name, [0, 0.0])
    print(f"quarter_model_{QUARTER} on {column.name}: {count:2d} contacts, {area / 1e6:.4f} m2")

seat_column = max(on_column, key=lambda name: on_column[name][1])
print(f"-> quarter_model_{QUARTER} lands on {seat_column}, and on nothing else")

# ------------------------------------------------------------------ #
# Does it actually land? Measured, not assumed.
#
# A contact polygon is the shared face. So for each of the 11 bearing faces,
# both solids are asked where their OWN face sits: every face of the mesh whose
# normal is parallel to the contact normal is projected onto that normal, and
# the one nearest the contact plane is taken. The difference is the gap. Two
# faces truly in contact both read 0.000; a quarter hanging off the capitel
# would read the daylight in millimetres.
#
# The rake is printed with it, because none of these faces is flat: the angle is
# measured off VERTICAL, so 0 degrees would be a plumb face and 90 a level seat.
# ------------------------------------------------------------------ #

PARALLEL = math.cos(math.radians(2.0))  # a face counts as parallel within 2 degrees


def face_offset(mesh, normal, plane):
    """Offset of the mesh face nearest ``plane`` along ``normal``, or ``None``."""
    best = None
    for face in mesh.faces():
        facenormal = Vector(*mesh.face_normal(face))
        if facenormal.length < 1e-9 or abs(facenormal.dot(normal)) < PARALLEL:
            continue
        offset = abs(normal.dot(Vector(*mesh.face_centroid(face))) - plane)
        best = offset if best is None else min(best, offset)
    return best


column = next(element for element in columns if element.name == seat_column)
columnmesh = column.modelgeometry

seats = []
for plate in sorted(quarter_parts, key=lambda element: element.name):
    for other, contacts in touching[id(plate)]:
        if other is not column:
            continue
        for contact in contacts:
            normal = Vector(*contact.polygon.normal)
            normal.unitize()
            plane = normal.dot(Vector(*contact.polygon.centroid))
            gap_plate = face_offset(plate.modelgeometry, normal, plane) or 0.0
            gap_column = face_offset(columnmesh, normal, plane) or 0.0
            rake = math.degrees(math.asin(min(1.0, abs(normal.z))))
            heights = [point[2] for point in contact.polygon.points]
            seats.append((plate.name, contact.polygon.area, gap_plate + gap_column, rake, min(heights), max(heights)))
            print(
                f"  {plate.name:24s} on {column.name}: {contact.polygon.area / 1e6:7.4f} m2"
                f" | gap {gap_plate + gap_column:.4f} mm | raked {rake:4.1f} deg off vertical"
                f" | z {min(heights):7.1f} .. {max(heights):7.1f}"
            )

print(
    f"{len(seats)} bearing faces, {sum(seat[1] for seat in seats) / 1e6:.4f} m2 total, worst gap {max(seat[2] for seat in seats):.4f} mm, "
    f"rake {min(seat[3] for seat in seats):.1f} .. {max(seat[3] for seat in seats):.1f} deg off vertical - "
    "no face is level, so there is no seat to land flat on and nothing was nudged to make one"
)

# ------------------------------------------------------------------ #
# The column steel plates: which column, which quarter, how deep.
#
# The owner is read off the model's contacts, not off the name. The depth is
# read off the plate's own local frame, whose origin sits ON the column/rib
# contact plane and whose +X points into the rib - so the two numbers are the
# real embedment, measured from the mesh, and they should come out at
# ConnectorElement.BACK and .FRONT.
# ------------------------------------------------------------------ #


def local_span(element):
    """Extent of an element's mesh along its own local X, in its own frame."""
    inverse = element.modeltransformation.inverted()
    xs = [Point(*element.modelgeometry.vertex_point(vertex)).transformed(inverse).x for vertex in element.modelgeometry.vertices()]
    return min(xs), max(xs)


def owner_of(element, candidates):
    """The candidate group this element has the most contact area with."""
    scores = defaultdict(float)
    for other, contacts in touching[id(element)]:
        for name, ids in candidates.items():
            if id(other) in ids:
                scores[name] += sum(contact.polygon.area for contact in contacts)
    return max(scores, key=scores.get) if scores else None


quarter_ids_by_name = {}
for node in group_node("floor_model", "quarters_model").children:
    quarter_ids_by_name[node.element.name] = {id(element) for element in group_parts(node)}
column_ids_by_name = {element.name: {id(element)} for element in columns}

# Which dowel belongs to which plate: the dowel centre, taken into the plate's
# local frame, has to fall inside the box the plate is made from.
TOL = 1.0


def dowels_in(plate):
    inverse = plate.modeltransformation.inverted()
    inside = []
    for dowel in dowels:
        local = Point(*dowel.modelgeometry.centroid()).transformed(inverse)
        if (
            -ConnectorElement.BACK - TOL <= local.x <= ConnectorElement.FRONT + TOL
            and abs(local.y) <= 0.5 * ConnectorElement.WIDTH + TOL
            and -ConnectorElement.HEIGHT - TOL <= local.z <= TOL
        ):
            inside.append((dowel, local))
    return sorted(inside, key=lambda item: (item[1].x, -item[1].z))


assignment = []
for plate in plates:
    on = owner_of(plate, column_ids_by_name)
    into = owner_of(plate, quarter_ids_by_name)
    back, front = local_span(plate)
    pins = dowels_in(plate)
    assignment.append((plate, on, into, back, front, pins))
    print(f"{plate.name}: on {on}, into {into} | {-back:.1f} mm in the column, {front:.1f} mm in the rib | {len(pins)} dowels")
    for dowel, local in pins:
        side = "column" if local.x < 0 else "rib"
        print(f"    {dowel.name:20s} {side:6s} Ø{2 * dowel.radius:.0f} x {dowel.length:.0f} at local x {local.x:+8.2f}, z {local.z:+8.2f}")

if len({len(item[5]) for item in assignment}) != 1:
    print("!! the dowels do not split evenly over the steel plates - the assignment above is wrong somewhere")

mine = [item for item in assignment if item[2] == quarter_node.element.name]
theirs = [item for item in assignment if item[2] != quarter_node.element.name]
print(
    f"{len(plates)} steel plates and {len(dowels)} dowels in the model: {len(mine)} plates and {sum(len(item[5]) for item in mine)} dowels go on with "
    f"quarter_model_{QUARTER}, the other {len(theirs)} plates and {sum(len(item[5]) for item in theirs)} dowels wait for step 7"
)

# A dowel is 100 long through a 30 mm plate, so what is left is the bearing in
# the timber. Measured off the elements, not quoted from the class.
sample = mine[0][5][0][0]
bearing = 0.5 * (sample.length - ConnectorElement.WIDTH)
print(f"each dowel: Ø{2 * sample.radius:.0f} x {sample.length:.0f} mm across a {ConnectorElement.WIDTH:.0f} mm plate, so {bearing:.1f} mm bears in the timber on each side")

# ------------------------------------------------------------------ #
# The parts, in drawing order.
# ------------------------------------------------------------------ #

quartermeshes = []
for plate in sorted(quarter_parts, key=lambda element: element.name):
    mesh = plate.modelgeometry
    mesh.name = plate.name
    quartermeshes.append(mesh)

platemeshes = []
dowelmeshes = []
for plate, _, _, _, _, pins in mine:
    mesh = plate.modelgeometry
    mesh.name = plate.name
    platemeshes.append(mesh)
    for dowel, _ in pins:
        pin = dowel.modelgeometry
        pin.name = f"{plate.name}_{dowel.name}"
        dowelmeshes.append(pin)

timbers = []
for element in columns:
    timber = element.modelgeometry
    timber.name = element.name
    timbers.append(timber)

bases = []
for element in supports:
    base = element.brep
    base.name = element.name
    bases.append(base)

# ------------------------------------------------------------------ #
# Write the preview the docs page loads (OBJ + MTL, one colour per role).
# ------------------------------------------------------------------ #

written = write_colored_obj(
    [(timber, GHOST) for timber in timbers]
    + [(base, GHOST) for base in bases]
    + [(mesh, STEEL) for mesh in quartermeshes]
    + [(mesh, STEEL) for mesh in platemeshes]
    + [(mesh, STEEL) for mesh in dowelmeshes],
    assembly_dir / f"{STEP}_preview.obj",
)
print("written: " + ", ".join(str(path) for path in written.values()))

# ------------------------------------------------------------------ #
# And the list the docs page shows under the viewer, written as a markdown
# fragment that docs/assembly.md pulls in with a snippet.
#
# ONLY the numbers are generated. The headings and the sentences around them are
# ordinary prose in docs/assembly.md, which pulls each list in by section name
# (`...points.md:totals`), so the wording can change without re-running this.
# ------------------------------------------------------------------ #


def _section(name, rows):
    return [f"<!-- --8<-- [start:{name}] -->", *rows, f"<!-- --8<-- [end:{name}] -->", ""]


lines = [
    "<!-- Generated by examples/example_model_23_assembly_step6.py - do not edit.",
    "     The prose around these lists is in docs/assembly.md; only the",
    "     numbers live here. -->",
    "",
    *_section(
        "totals",
        [
            f"- 1 quarter of 4 &mdash; `quarter_model_{QUARTER}`, {len(quarter_parts)} plates, on `{seat_column}`",
            f"- {len(seats)} bearing faces, {sum(seat[1] for seat in seats) / 1e6:.3f} m&sup2;, gap {max(seat[2] for seat in seats):.4f} mm, "
            f"raked {min(seat[3] for seat in seats):.0f}&ndash;{max(seat[3] for seat in seats):.0f}&deg; off vertical &mdash; no level seat, and no head plate up here",
            f"- {len(mine)} steel plates &mdash; {ConnectorElement.BACK + ConnectorElement.FRONT:.0f} &times; "
            f"{ConnectorElement.WIDTH:.0f} &times; {ConnectorElement.HEIGHT:.0f} mm, "
            f"{-mine[0][3]:.0f} mm through the column head and {mine[0][4]:.0f} mm into the rib",
            f"- {sum(len(item[5]) for item in mine)} dowels &mdash; &Oslash;{2 * sample.radius:.0f} &times; {sample.length:.0f} mm, "
            f"{bearing:.0f} mm bearing in the timber each side",
            f"- {len(theirs)} steel plates and {sum(len(item[5]) for item in theirs)} dowels are left for step 7",
        ],
    ),
    *_section(
        "dowels",
        [
            f"- `{plate.name}` on `{on}` into `{into}` &mdash; " + ", ".join(f"`{dowel.name}` at {local.x:+.1f}, {local.z:+.1f} mm" for dowel, local in pins)
            for plate, on, into, back, front, pins in mine
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
for base in bases:
    viewer.scene.add(base, name=base.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group(f"quarter_{QUARTER}")
for mesh in quartermeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

group = viewer.scene.add_group("column_steel_plates")
for mesh in platemeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

group = viewer.scene.add_group("dowels")
for mesh in dowelmeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

zoom_to(viewer, [mesh.aabb() for mesh in quartermeshes] + [timber.aabb() for timber in timbers])
viewer.renderer.camera.position.set(-8600, -9000, 5600)
viewer.renderer.camera.target.set(-1300, -1300, 3100)




viewer.show()
