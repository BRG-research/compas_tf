"""Assembly step 7 - the other three quarters, and the steel that ties them together.

Sixth of the ``example_model_23_assembly_*`` series; see step 2 for how the
previews reach the docs.

Step 6 landed ONE quarter on ONE column and pinned it there with two steel
plates and eight dowels. This step repeats that three more times and, because
the quarters now have neighbours, closes the four seams between them.

WHAT GOES ON HERE
-----------------
- the three remaining QUARTERS, ``quarter_model_1``, ``_2`` and ``_3`` - 34
  plates each, each one lowered onto its own column;
- their six COLUMN STEEL PLATES, two per column
  (:class:`compas_tf.connectors.ConnectorElement`, the top-level ``connectors``
  group), and the 24 DOWELS that pin them
  (:class:`compas_tf.connectors.DowelCylinderElement`, the top-level
  ``connector_cylinders`` group). Step 6 fitted 2 and 8 of them; these are the
  rest, and the same contact-and-local-frame test does the sorting, so a plate
  that belonged to the first quarter would show up here rather than being
  quietly drawn twice;
- the four OUTER-RIB CONNECTORS
  (:class:`compas_tf.connectors.OuterRibConnectorElement`, the top-level
  ``outer_rib_connectors`` group). These are NOT column hardware. Each one
  straddles the seam where two quarters' outer ribs meet at the middle of a bay
  edge - 800 mm long, half into each rib - so it can only be fitted once BOTH
  quarters it joins are standing. Two of the four seams reach quarter 0, which
  went up in step 6; the other two are made in this step. Whichever way round,
  none of the four could be closed until now, so all four are here.

The steel is a fixed fabrication shape loaded from
``src/compas_tf/data/OuterRibConnector/*.obj``, not a parametric box, and the
model has already cut the matching male and female pockets into the two ribs.

WHAT THE CHECKS BELOW MEASURE
-----------------------------
Three things, all off the model's own contacts:

1. each quarter against each column - it should touch exactly one, 11 faces,
   the same 0.277 m2 step 6 measured on the first one;
2. each of the four seams between neighbouring quarters - 3 faces, and the gap
   over them;
3. each outer-rib connector against the two quarters it joins - it should read
   the same on both sides, because it is symmetric about the seam.

The gap is measured the way step 6 measures it: both solids are asked where
their own face sits along the contact normal, and the difference is the answer.
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
from compas_tf.viewer import human_figure
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step7"

# The quarter that went on in step 6, and is ghosted here.
STANDING = 0

# One colour for every object - the black feature edges separate the parts.
STEEL = Color(0.72, 0.74, 0.76)
BLACK = Color(0.05, 0.05, 0.05)

# What is already standing is ghosted; what this step adds is solid.
GHOST = (0.72, 0.74, 0.76, 0.22)
COLUMN_OPACITY = 0.25  # the compas viewer's own way of saying the same thing

# ------------------------------------------------------------------ #
# The model. There are TWO groups called ``connectors`` in this file - the
# column steel plates at the top level, and the wedges plus their screws under
# ``floor_model`` - so groups are walked by PATH from the root, never found by a
# bare name search.
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

quarter_nodes = {node.element.name: node for node in group_node("floor_model", "quarters_model").children if isinstance(node.element, Group)}
quarter_parts = {name: group_parts(node) for name, node in quarter_nodes.items()}
quarter_ids = {name: {id(element) for element in parts} for name, parts in quarter_parts.items()}

plates = sorted(group_parts(group_node("connectors")), key=lambda element: element.name)
dowels = group_parts(group_node("connector_cylinders"))
seamplates = sorted(group_parts(group_node("outer_rib_connectors")), key=lambda element: element.name)

columns = sorted((element for element in model.elements() if isinstance(element, ColumnElement)), key=lambda element: element.name)
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)
column_ids = {element.name: {id(element)} for element in columns}

standing = f"quarter_model_{STANDING}"
arriving = [name for name in sorted(quarter_parts) if name != standing]
print(f"already standing: {standing} ({len(quarter_parts[standing])} plates) - ghosted")
print(f"going on now:     {', '.join(f'{name} ({len(quarter_parts[name])} plates)' for name in arriving)}")

# ------------------------------------------------------------------ #
# The gap measurement, as in step 6: a contact polygon is the shared face, so
# both solids are asked where their OWN face sits along the contact normal and
# the difference is the daylight between them.
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


def measure(a, b, contacts):
    """``(count, area, worst gap)`` over the contacts between two elements."""
    worst = 0.0
    area = 0.0
    for contact in contacts:
        normal = Vector(*contact.polygon.normal)
        normal.unitize()
        plane = normal.dot(Vector(*contact.polygon.centroid))
        worst = max(worst, (face_offset(a.modelgeometry, normal, plane) or 0.0) + (face_offset(b.modelgeometry, normal, plane) or 0.0))
        area += contact.polygon.area
    return len(contacts), area, worst


# ------------------------------------------------------------------ #
# 1. Each quarter on its column. Every quarter is checked, including the one
#    from step 6, so the three new ones can be read against a known-good line.
# ------------------------------------------------------------------ #

seats = {}
for name in sorted(quarter_parts):
    tally = defaultdict(lambda: [0, 0.0, 0.0])
    for plate in quarter_parts[name]:
        for other, contacts in touching[id(plate)]:
            if isinstance(other, ColumnElement):
                count, area, gap = measure(plate, other, contacts)
                row = tally[other.name]
                row[0] += count
                row[1] += area
                row[2] = max(row[2], gap)
    column = max(tally, key=lambda key: tally[key][1])
    seats[name] = (column, *tally[column])
    others = [key for key in tally if key != column]
    print(
        f"{name} on {column}: {tally[column][0]:2d} faces, {tally[column][1] / 1e6:.4f} m2, worst gap {tally[column][2]:.4f} mm"
        f" | touches {len(others)} other column(s){'' if not others else ' ' + ', '.join(others)}"
    )

# ------------------------------------------------------------------ #
# 2. The four seams between neighbouring quarters. A quarter that had been set
#    down out of position would open one of these; the number is the gap.
# ------------------------------------------------------------------ #

seams = defaultdict(lambda: [0, 0.0, 0.0])
for name, parts in quarter_parts.items():
    for plate in parts:
        for other, contacts in touching[id(plate)]:
            for othername, ids in quarter_ids.items():
                if othername == name or id(other) not in ids:
                    continue
                count, area, gap = measure(plate, other, contacts)
                row = seams[tuple(sorted((name, othername)))]
                row[0] += count
                row[1] += area
                row[2] = max(row[2], gap)

# Each seam is found from both sides, so halve the counted faces and area.
for key in seams:
    seams[key][0] //= 2
    seams[key][1] /= 2

for (left, right), (count, area, gap) in sorted(seams.items()):
    print(f"seam {left} | {right}: {count} faces, {area / 1e6:.4f} m2, worst gap {gap:.4f} mm")

# ------------------------------------------------------------------ #
# 3. The outer-rib connectors, one per seam. Which two quarters each one joins
#    is read off the contacts, not off the name, and the two sides are printed
#    separately - the connector is symmetric about the seam, so anything other
#    than the same figure twice means it is not sitting central.
# ------------------------------------------------------------------ #

seamsteel = []
for connector in seamplates:
    sides = defaultdict(lambda: [0, 0.0, 0.0])
    for other, contacts in touching[id(connector)]:
        for name, ids in quarter_ids.items():
            if id(other) in ids:
                count, area, gap = measure(connector, other, contacts)
                row = sides[name]
                row[0] += count
                row[1] += area
                row[2] = max(row[2], gap)
    box = connector.modelgeometry.aabb()
    joined = sorted(sides)
    seamsteel.append((connector, joined, sides))
    print(
        f"{connector.name}: joins {' | '.join(joined)} - "
        + ", ".join(f"{name} {sides[name][0]} faces {sides[name][1] / 1e6:.4f} m2 gap {sides[name][2]:.4f} mm" for name in joined)
        + f" | {max(box.xsize, box.ysize):.0f} mm long, top at z={box.zmax:.1f}"
    )
    if len(joined) != 2:
        print(f"!! {connector.name} touches {len(joined)} quarters, not 2 - the seam it sits on is not the one it was built for")

# ------------------------------------------------------------------ #
# The column steel plates and their dowels, sorted exactly as in step 6: the
# owner off the contacts, the dowels off the plate's own local frame.
# ------------------------------------------------------------------ #

TOL = 1.0


def owner_of(element, candidates):
    """The candidate group this element has the most contact area with."""
    scores = defaultdict(float)
    for other, contacts in touching[id(element)]:
        for name, ids in candidates.items():
            if id(other) in ids:
                scores[name] += sum(contact.polygon.area for contact in contacts)
    return max(scores, key=scores.get) if scores else None


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
            inside.append(dowel)
    return inside


assignment = []
for plate in plates:
    assignment.append((plate, owner_of(plate, column_ids), owner_of(plate, quarter_ids), dowels_in(plate)))

mine = [item for item in assignment if item[2] != standing]
theirs = [item for item in assignment if item[2] == standing]
for plate, on, into, pins in assignment:
    when = "step 6 (ghosted)" if into == standing else "this step"
    print(f"{plate.name}: on {on}, into {into}, {len(pins)} dowels - {when}")

if sum(len(item[3]) for item in assignment) != len(dowels):
    print(f"!! {len(dowels) - sum(len(item[3]) for item in assignment)} dowels were not claimed by any steel plate")

print(
    f"{len(mine)} steel plates and {sum(len(item[3]) for item in mine)} dowels go on with the three quarters; "
    f"{len(theirs)} plates and {sum(len(item[3]) for item in theirs)} dowels were already there from step 6"
)
print(f"{len(seamplates)} outer-rib connectors close {len(seams)} seams - {len(seams) * 2} rib ends, half a connector in each")

# ------------------------------------------------------------------ #
# The parts, in drawing order.
# ------------------------------------------------------------------ #


def named(element, name=None):
    mesh = element.modelgeometry
    mesh.name = name or element.name
    return mesh


newmeshes = [named(plate) for name in arriving for plate in sorted(quarter_parts[name], key=lambda element: element.name)]
oldmeshes = [named(plate) for plate in sorted(quarter_parts[standing], key=lambda element: element.name)]

newsteel = []
newdowels = []
for plate, _, _, pins in mine:
    newsteel.append(named(plate))
    newdowels.extend(named(dowel, f"{plate.name}_{dowel.name}") for dowel in pins)

oldsteel = []
olddowels = []
for plate, _, _, pins in theirs:
    oldsteel.append(named(plate))
    olddowels.extend(named(dowel, f"{plate.name}_{dowel.name}") for dowel in pins)

seammeshes = [named(connector) for connector in seamplates]
timbers = [named(element) for element in columns]

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
    + [(mesh, GHOST) for mesh in oldmeshes]
    + [(mesh, GHOST) for mesh in oldsteel + olddowels]
    + [(mesh, STEEL) for mesh in newmeshes]
    + [(mesh, STEEL) for mesh in newsteel + newdowels]
    + [(mesh, STEEL) for mesh in seammeshes],
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


worstseat = max(seats[name][3] for name in arriving)
worstseam = max(row[2] for row in seams.values())

lines = [
    "<!-- Generated by examples/example_model_23_assembly_step7.py - do not edit.",
    "     The prose around these lists is in docs/assembly.md; only the",
    "     numbers live here. -->",
    "",
    *_section(
        "totals",
        [
            f"- 3 quarters &mdash; {sum(len(quarter_parts[name]) for name in arriving)} plates, {len(quarter_parts[arriving[0]])} each, one per column",
            f"- {seats[arriving[0]][1]} bearing faces per quarter, {seats[arriving[0]][2] / 1e6:.3f} m&sup2;, worst gap {worstseat:.4f} mm",
            f"- {len(mine)} steel plates and {sum(len(item[3]) for item in mine)} dowels &mdash; the rest of the 8 and 32; "
            f"{len(theirs)} and {sum(len(item[3]) for item in theirs)} went on in step 6",
            f"- {len(seams)} seams closed, {min(row[0] for row in seams.values())} faces each, worst gap {worstseam:.4f} mm",
            f"- {len(seamplates)} outer-rib connectors &mdash; {max(max(m.aabb().xsize, m.aabb().ysize) for m in seammeshes):.0f} mm long, half into each rib",
        ],
    ),
    *_section(
        "seams",
        [
            f"- `{connector.name}` closes `{joined[0]}` &harr; `{joined[1]}` &mdash; {sides[joined[0]][0]} faces a side, "
            f"{sides[joined[0]][1] / 1e6:.3f} m&sup2;, gap {max(sides[name][2] for name in joined):.4f} mm"
            for connector, joined, sides in seamsteel
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

group = viewer.scene.add_group(f"quarter_{STANDING}_from_step5")
for mesh in oldmeshes + oldsteel + olddowels:
    viewer.scene.add(mesh, name=mesh.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("quarters")
for mesh in newmeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

group = viewer.scene.add_group("column_steel_plates")
for mesh in newsteel + newdowels:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

group = viewer.scene.add_group("outer_rib_connectors")
for mesh in seammeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

zoom_to(viewer, [mesh.aabb() for mesh in newmeshes + oldmeshes] + [timber.aabb() for timber in timbers])
viewer.renderer.camera.position.set(-9800, -10200, 6400)
viewer.renderer.camera.target.set(0, 0, 3000)



# A 1.75 m figure, for reading the scale of the model at a glance. Reference
# geometry only - plain polylines, never added to the model itself.
for _part in human_figure(point=[3600, 0, 0]):
    viewer.scene.add(_part, name="scale_figure", linecolor=Color(0.35, 0.35, 0.35), linewidth=2)

viewer.show()
