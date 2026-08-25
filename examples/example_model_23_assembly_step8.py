"""Assembly step 8 - close the middle with the oculus.

Seventh of the ``example_model_23_assembly_*`` series; see step 2 for how the
previews reach the docs.

With all four quarters standing (steps 5 and 6) the floor is a square with a
square hole in it. The OCULUS fills that hole. In the model it is
``floor_model/oculus_model/oculus`` - 9
:class:`compas_tf.plate.PlateElement`, 2000 x 2000 mm over all, in three tiers:

- 4 RING plates, ``oculus_0`` .. ``oculus_3``, the full 197 mm depth of the
  floor (``z = 3303 .. 3500``), one per quarter, each mitred to the next;
- 4 BED plates, ``oculus_4`` .. ``oculus_7``, 27 mm thick, on the soffit;
- 1 CENTRE plate, ``oculus_8``, 1830 x 1830 mm, 27 mm thick, over them.

It is put in from BELOW, off the tower that went up in step 5 - which is why the
tower had to be set out with a total station back in step 2 rather than shoved
into the middle of the bay. The check below stands the tower up again, from the
same ``examples/assembly_shoring.py`` layout step 5 builds it from, and measures
its deck against the oculus soffit rather than quoting a number at it.

The wedges that lock the oculus to the four quarters are NOT here. They are
``connector_wedge_1``, ``_4``, ``_6`` and ``_7``, and they go in with the other
four in step 9.

A CONTACT THAT THE MODEL DOES NOT RECORD
----------------------------------------
The interesting number in this step is a missing one. Three of the four quarters
report 4 contacts with the ring; ``quarter_model_2`` reports 1. That reads like
a quarter sitting off its neighbours - so it is measured, not accepted: every
inner beam is compared with every ring plate by closest approach, and the whole
quarter is rotated onto quarter 0 to see whether the two are the same shape in
the same place.

They are, to 0.000000 mm. The ring closes on all four sides; what is missing is
the CONTACT RECORD in the baked file, not the material. The printed lines below
say which pairs meet and which of those the model has an entry for, so the
difference is visible rather than argued about.
"""

import math
import pathlib
from collections import defaultdict

import assembly_shoring
import compas
from compas.colors import Color
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Vector
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.model import TFModel
from compas_tf.support import SupportElement
from compas_tf.viewer import human_figure
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step8"

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

oculus_parts = sorted(group_parts(group_node("floor_model", "oculus_model", "oculus")), key=lambda element: element.name)
quarter_nodes = {node.element.name: node for node in group_node("floor_model", "quarters_model").children if isinstance(node.element, Group)}
quarter_parts = {name: group_parts(node) for name, node in quarter_nodes.items()}
quarter_ids = {name: {id(element) for element in parts} for name, parts in quarter_parts.items()}

plates = group_parts(group_node("connectors"))
dowels = group_parts(group_node("connector_cylinders"))
seamplates = group_parts(group_node("outer_rib_connectors"))
columns = sorted((element for element in model.elements() if isinstance(element, ColumnElement)), key=lambda element: element.name)
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)

boxes = {element.name: element.modelgeometry.aabb() for element in oculus_parts}
print(f"oculus: {len(oculus_parts)} plates")
for element in oculus_parts:
    box = boxes[element.name]
    print(f"  {element.name}: {box.xsize:7.1f} x {box.ysize:7.1f} x {box.zsize:5.1f} mm, z {box.zmin:.1f} .. {box.zmax:.1f}")

soffit = min(box.zmin for box in boxes.values())
crown = max(box.zmax for box in boxes.values())
print(
    f"oculus over all: {max(box.xmax for box in boxes.values()) - min(box.xmin for box in boxes.values()):.0f} x "
    f"{max(box.ymax for box in boxes.values()) - min(box.ymin for box in boxes.values()):.0f} mm, z {soffit:.1f} .. {crown:.1f}"
)

# ------------------------------------------------------------------ #
# The tower it is placed off. Not quoted from step 5 - stood up here from the
# same layout, so the deck height and the oculus soffit are measured against
# each other rather than typed twice.
# ------------------------------------------------------------------ #

tower_box = assembly_shoring.centre_tower().aabb()
print(
    f"tower deck top z={tower_box.zmax:.1f}, oculus soffit z={soffit:.1f} -> {soffit - tower_box.zmax:+.1f} mm between them"
    f" | deck {tower_box.xsize:.0f} x {tower_box.ysize:.0f} mm under a {max(box.xmax for box in boxes.values()) - min(box.xmin for box in boxes.values()):.0f} mm opening"
)

# ------------------------------------------------------------------ #
# Does the oculus meet the four quarters? Two measurements, because the first
# one alone would be misleading.
#
# First the model's own record: how many contact faces and how much area the
# oculus has with each quarter.
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


ring = [element for element in oculus_parts if boxes[element.name].zsize > 100]
beams = {name: sorted((element for element in parts if element.name.startswith("inner_beams_")), key=lambda element: element.name) for name, parts in quarter_parts.items()}


def quadrant(point):
    """Which quarter turn off the +x axis a part sits in - 0, 1, 2 or 3.

    Read off the part's own position in plan, not off its name, so the four-fold
    symmetry below is a geometric statement rather than a naming convention.
    """
    return int(((math.degrees(math.atan2(point[1], point[0])) + 45.0) % 360.0) // 90.0)


def centre(element):
    box = element.modelgeometry.aabb()
    return (box.frame.point.x, box.frame.point.y)


quarter_turn = {name: quadrant([sum(centre(element)[i] for element in parts) / len(parts) for i in range(2)]) for name, parts in quarter_parts.items()}
panel_turn = {element.name: quadrant(centre(element)) for element in ring}
panel_at = {panel_turn[element.name]: element for element in ring}

recorded = defaultdict(lambda: [0, 0.0, 0.0])
pattern = defaultdict(dict)
for panel in ring:
    for other, contacts in touching[id(panel)]:
        for name, ids in quarter_ids.items():
            if id(other) not in ids or other not in beams[name]:
                continue
            row = recorded[name]
            row[0] += len(contacts)
            row[1] += sum(contact.polygon.area for contact in contacts)
            for contact in contacts:
                normal = Vector(*contact.polygon.normal)
                normal.unitize()
                plane = normal.dot(Vector(*contact.polygon.centroid))
                row[2] = max(row[2], (face_offset(panel.modelgeometry, normal, plane) or 0.0) + (face_offset(other.modelgeometry, normal, plane) or 0.0))
            # The pattern of a quarter: (which of its three beams, how many
            # quarter turns from its own quadrant to the panel's).
            pattern[name][(beams[name].index(other), (panel_turn[panel.name] - quarter_turn[name]) % 4)] = contacts

for name in sorted(quarter_parts):
    count, area, gap = recorded.get(name, [0, 0.0, 0.0])
    print(f"{name} against the ring: {count} contact faces recorded, {area / 1e6:.4f} m2, worst gap {gap:.4f} mm")

# ------------------------------------------------------------------ #
# Is a short count a gap, or a gap in the bookkeeping? The floor has four-fold
# symmetry, so every quarter is turned back onto the first one and compared
# vertex for vertex. If a quarter really were sitting off the ring, this is
# where it would show up - in millimetres, not in a contact count.
# ------------------------------------------------------------------ #


def vertices(element):
    mesh = element.modelgeometry
    return [mesh.vertex_point(vertex) for vertex in mesh.vertices()]


def closest(a, b):
    """Closest approach from one vertex cloud to another."""
    return min(min((point - other).length for other in b) for point in a)


reference = sorted(quarter_parts)[0]
deviation = 0.0
for name in sorted(quarter_parts):
    turns = (quarter_turn[reference] - quarter_turn[name]) % 4
    turn = Rotation.from_axis_and_angle(Vector(0, 0, 1), turns * math.pi / 2, Point(0, 0, 0))
    worst = 0.0
    for beam, twin in zip(beams[name], beams[reference]):
        turned = [point.transformed(turn) for point in vertices(beam)]
        target = vertices(twin)
        worst = max(worst, closest(turned, target), closest(target, turned))
    deviation = max(deviation, worst)
    print(f"{name} turned {turns * 90:3d} deg onto {reference}: worst vertex deviation {worst:.6f} mm")

# ------------------------------------------------------------------ #
# So the four quarters meet the ring the same way, and any pair one of them is
# short of is a missing RECORD. Each one is measured all the same: the contact
# another quarter does have is turned onto this quarter, and the two solids that
# should be lying on it are asked where their own faces are - the gap check of
# step 6, applied to a contact the file never wrote down.
# ------------------------------------------------------------------ #

full = set()
for name in pattern:
    full |= set(pattern[name])

missing = []
for name in sorted(quarter_parts):
    for key in sorted(full - set(pattern[name])):
        index, offset = key
        source = next(other for other in pattern if key in pattern[other])
        turns = (quarter_turn[name] - quarter_turn[source]) % 4
        turn = Rotation.from_axis_and_angle(Vector(0, 0, 1), turns * math.pi / 2, Point(0, 0, 0))
        beam = beams[name][index]
        panel = panel_at[(quarter_turn[name] + offset) % 4]
        gap = 0.0
        area = 0.0
        for contact in pattern[source][key]:
            polygon = contact.polygon.transformed(turn)
            normal = Vector(*polygon.normal)
            normal.unitize()
            plane = normal.dot(Vector(*polygon.centroid))
            gap = max(gap, (face_offset(beam.modelgeometry, normal, plane) or 999.0) + (face_offset(panel.modelgeometry, normal, plane) or 999.0))
            area += polygon.area
        missing.append((name, beam.name, panel.name, area, gap))
        print(f"  no contact recorded for {beam.name} | {panel.name}: the face {source} has there lands on both of them, {area / 1e6:.4f} m2, gap {gap:.4f} mm")

print(
    f"{sum(len(pattern[name]) for name in pattern)} of {len(full) * len(quarter_parts)} beam/ring pairs are recorded; the {len(missing)} that are not "
    f"close to {max((item[4] for item in missing), default=0.0):.4f} mm anyway, and the four quarters agree to {deviation:.6f} mm under a quarter turn - "
    "the ring is shut on all four sides, and what the file is short of is the bookkeeping"
)

# ------------------------------------------------------------------ #
# The parts, in drawing order.
# ------------------------------------------------------------------ #


def named(element, name=None):
    mesh = element.modelgeometry
    mesh.name = name or element.name
    return mesh


oculusmeshes = [named(element) for element in oculus_parts]
floormeshes = [named(element) for name in sorted(quarter_parts) for element in sorted(quarter_parts[name], key=lambda item: item.name)]
steelmeshes = [named(element) for element in sorted(plates, key=lambda item: item.name)] + [named(element) for element in sorted(seamplates, key=lambda item: item.name)]
dowelmeshes = [named(element, f"dowel_{index}_{element.name}") for index, element in enumerate(dowels)]
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
    + [(mesh, GHOST) for mesh in floormeshes]
    + [(mesh, GHOST) for mesh in steelmeshes + dowelmeshes]
    + [(mesh, STEEL) for mesh in oculusmeshes],
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


span = max(box.xmax for box in boxes.values()) - min(box.xmin for box in boxes.values())

lines = [
    "<!-- Generated by examples/example_model_23_assembly_step8.py - do not edit.",
    "     The prose around these lists is in docs/assembly.md; only the",
    "     numbers live here. -->",
    "",
    *_section(
        "totals",
        [
            f"- 1 oculus &mdash; {len(oculus_parts)} plates, {span:.0f} &times; {span:.0f} mm, `z = {soffit:.0f} .. {crown:.0f}` mm",
            f"- {len(ring)} ring plates {max(boxes[element.name].zsize for element in ring):.0f} mm deep, "
            f"{len(oculus_parts) - len(ring) - 1} bed plates and 1 centre plate {min(box.zsize for box in boxes.values()):.0f} mm thick",
            f"- placed off the tower deck &mdash; deck top `z = {tower_box.zmax:.0f}` mm, oculus soffit `z = {soffit:.0f}` mm, {soffit - tower_box.zmax:+.0f} mm between them",
            f"- {len(full) * len(quarter_parts)} beam/ring pairs, {sum(len(pattern[name]) for name in pattern)} of them recorded as contacts; "
            f"the {len(missing)} that are not still close to {max((item[4] for item in missing), default=0.0):.4f} mm",
            f"- the four quarters agree with each other to {deviation:.4f} mm under a quarter turn",
        ],
    ),
    *_section(
        "ring",
        [
            f"- `{name}` &mdash; {recorded.get(name, [0, 0.0, 0.0])[0]} recorded "
            f"{'face' if recorded.get(name, [0, 0.0, 0.0])[0] == 1 else 'faces'}, "
            f"{recorded.get(name, [0, 0.0, 0.0])[1] / 1e6:.3f} m&sup2;, gap {recorded.get(name, [0, 0.0, 0.0])[2]:.4f} mm"
            for name in sorted(quarter_parts)
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

group = viewer.scene.add_group("quarters")
for mesh in floormeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("steel")
for mesh in steelmeshes + dowelmeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("oculus")
for mesh in oculusmeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

zoom_to(viewer, [mesh.aabb() for mesh in floormeshes + oculusmeshes])
viewer.renderer.camera.position.set(-6200, -6500, 5400)
viewer.renderer.camera.target.set(0, 0, 3350)



# A 1.75 m figure, for reading the scale of the model at a glance. Reference
# geometry only - plain polylines, never added to the model itself.
for _part in human_figure(point=[3600, 0, 0]):
    viewer.scene.add(_part, name="scale_figure", linecolor=Color(0.35, 0.35, 0.35), linewidth=2)

viewer.show()
