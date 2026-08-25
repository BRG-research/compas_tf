"""Assembly step 9 - drive the wedges and put their screws in.

Eighth and last of the ``example_model_23_assembly_*`` series; see step 2 for
how the previews reach the docs.

The floor is complete but not yet locked. Every joint made in steps 5, 6 and 7
was a face against a face: the quarters sit on their capitels, the seams are
closed by the outer-rib connectors, the oculus is set into the ring. What pulls
those joints TIGHT are the WEDGES, and this step drives all eight of them and
screws them home.

WHAT A WEDGE IS, IN THE MODEL
-----------------------------
The 8 :class:`compas_tf.connectors.ConnectorWedgeElement` under
``floor_model/connectors``. Each is a triangular prism on the fixed
``PROFILE`` - 208.5 mm from apex to back, 63.5 mm across the back - lofted along
an interface line, so its LENGTH is the length of the joint it locks, not a
catalogue size. They come in two lengths here, and which is which is read off
the model's contacts, not off the name:

- 4 long ones on the SEAMS between neighbouring quarters;
- 4 short ones around the OCULUS, one to each of its four ring plates.

The apex points down: the wedge is dropped into a V-pocket cut into the two
parts it joins, and driving it down forces them apart along the joint - which is
what closes it.

AND THE SCREWS
--------------
They are real elements, not a note on a drawing: the 32
:class:`compas_tf.connectors.ConnectorCylinderElement` in the same group,
Ø 20 x 160 mm, made by
:meth:`compas_tf.connectors.ConnectorWedgeElement.create_cylinders` along each
wedge's ``DOWEL`` axis - 5 to a long wedge, 3 to a short one. They run ACROSS
the wedge, 100 mm below its back face, so each one passes through the narrow
part of the prism and on into the timber either side of it.

They are also the one part of this model that is deliberately NOT square to what
carries it. ``create_cylinders(horizontal=True)`` flattens every screw axis onto
the horizontal plane through its own centre, so that on the inclined faces
around the oculus the screws still go in level. The check below measures the
rise over each screw to prove it, rather than trusting the flag.

A wedge is matched to its screws by taking each screw's centre into the wedge's
own local frame - so a screw belonging to the next wedge along would come out as
a wedge with four screws, not as a clean five.

DO NOT CONFUSE the two kinds of cylinder in this file: these Ø 20 x 160 screws
belong to the wedges, and the Ø 50 x 100
:class:`compas_tf.connectors.DowelCylinderElement` of step 6 pin the column
steel plates. Nor are these wedges the ``wedges_inner_beams_*`` PLATES inside
each quarter - those are timber, part of the quarter, and went up in steps 5
and 6.
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
from compas_tf.connectors import ConnectorCylinderElement
from compas_tf.connectors import ConnectorWedgeElement
from compas_tf.model import TFModel
from compas_tf.support import SupportElement
from compas_tf.viewer import human_figure
from compas_tf.viewer import zoom_to
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"

STEP = "assembly_step9"

# One colour for every object - the black feature edges separate the parts.
STEEL = Color(0.72, 0.74, 0.76)
BLACK = Color(0.05, 0.05, 0.05)

# The whole floor is standing by now, so all of it is ghosted; only the wedges
# and their screws are solid.
GHOST = (0.72, 0.74, 0.76, 0.22)
COLUMN_OPACITY = 0.25  # the compas viewer's own way of saying the same thing

# ------------------------------------------------------------------ #
# The model. There are TWO groups called ``connectors`` in this file - the
# column steel plates at the top level, and the wedges plus their screws under
# ``floor_model``, which are the subject of this step. So groups are walked by
# PATH from the root, never found by a bare name search, which here would return
# precisely the wrong one.
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

hardware = group_parts(group_node("floor_model", "connectors"))
wedges = sorted((element for element in hardware if isinstance(element, ConnectorWedgeElement)), key=lambda element: element.name)
screws = [element for element in hardware if isinstance(element, ConnectorCylinderElement)]

quarter_nodes = {node.element.name: node for node in group_node("floor_model", "quarters_model").children if isinstance(node.element, Group)}
quarter_parts = {name: group_parts(node) for name, node in quarter_nodes.items()}
oculus_parts = group_parts(group_node("floor_model", "oculus_model", "oculus"))

owners = {name: {id(element) for element in parts} for name, parts in quarter_parts.items()}
owners["oculus"] = {id(element) for element in oculus_parts}

plates = group_parts(group_node("connectors"))
dowels = group_parts(group_node("connector_cylinders"))
seamplates = group_parts(group_node("outer_rib_connectors"))
columns = sorted((element for element in model.elements() if isinstance(element, ColumnElement)), key=lambda element: element.name)
supports = sorted((element for element in model.elements() if isinstance(element, SupportElement)), key=lambda element: element.name)

floortop = max(element.modelgeometry.aabb().zmax for parts in quarter_parts.values() for element in parts)
print(f"{len(wedges)} wedges and {len(screws)} screws; the floor they lock tops out at z={floortop:.1f}")

# ------------------------------------------------------------------ #
# Which screw belongs to which wedge. By geometry, not by name: each screw's
# centre is taken into the wedge's own local frame and tested against the slab
# the prism lives in - local X over the wedge length, local Y and Z inside the
# profile. The screws around the oculus have had their axes flattened to
# horizontal and carry no transformation of their own, so their world centre is
# the only thing the two have in common - which is exactly what this uses.
# ------------------------------------------------------------------ #

TOL = 1.0
PROFILE_BACK = max(point.z for point in ConnectorWedgeElement.PROFILE)
PROFILE_APEX = min(point.z for point in ConnectorWedgeElement.PROFILE)
PROFILE_HALF = max(abs(point.y) for point in ConnectorWedgeElement.PROFILE)


def screws_in(wedge):
    inverse = wedge.modeltransformation.inverted()
    inside = []
    for screw in screws:
        local = Point(*screw.axis.midpoint).transformed(inverse)
        if abs(local.x) <= 0.5 * wedge.length + TOL and abs(local.y) <= PROFILE_HALF + TOL and PROFILE_APEX - TOL <= local.z <= PROFILE_BACK + TOL:
            inside.append((screw, local))
    return sorted(inside, key=lambda item: item[1].x)


# The prism narrows toward the apex, so the width the screws pass through is not
# the 63.5 mm of the back face. It is interpolated on the profile at the height
# the screws actually sit at, which is read back off the model.
def profile_width(height):
    return 2.0 * PROFILE_HALF * (height - PROFILE_APEX) / (PROFILE_BACK - PROFILE_APEX)


# ------------------------------------------------------------------ #
# What each wedge locks, and how well it sits in its pocket. Both sides of a
# wedge are printed: it is a symmetrical prism in a symmetrical pocket, so
# anything other than the same figures twice means it is not central.
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


report = []
for wedge in wedges:
    sides = defaultdict(lambda: [0, 0.0, 0.0])
    for other, contacts in touching[id(wedge)]:
        for name, ids in owners.items():
            if id(other) not in ids:
                continue
            row = sides[name]
            row[0] += len(contacts)
            row[1] += sum(contact.polygon.area for contact in contacts)
            for contact in contacts:
                normal = Vector(*contact.polygon.normal)
                normal.unitize()
                plane = normal.dot(Vector(*contact.polygon.centroid))
                row[2] = max(row[2], (face_offset(wedge.modelgeometry, normal, plane) or 0.0) + (face_offset(other.modelgeometry, normal, plane) or 0.0))

    joined = sorted(sides)
    pins = screws_in(wedge)
    box = wedge.modelgeometry.aabb()
    height = sum(local.z for _, local in pins) / len(pins)
    width = profile_width(height)
    rise = max(abs(screw.axis.end[2] - screw.axis.start[2]) for screw, _ in pins)
    report.append((wedge, joined, sides, pins, box, height, width, rise))

    print(
        f"{wedge.name}: {wedge.length:7.1f} mm long, locks {' | '.join(joined)} - "
        + ", ".join(f"{name} {sides[name][0]} faces {sides[name][1] / 1e6:.4f} m2 gap {sides[name][2]:.4f} mm" for name in joined)
    )
    print(
        f"    z {box.zmin:7.1f} .. {box.zmax:7.1f}, so {box.zmax - floortop:+.1f} mm on the floor top"
        f" | {len(pins)} screws Ø{2 * pins[0][0].radius:.0f} x {pins[0][0].axis.length:.0f} mm at {abs(height):.0f} mm below the back face,"
        f" through {width:.1f} mm of wedge, {0.5 * (pins[0][0].axis.length - width):.1f} mm into the timber each side"
        f" | rise over the screw {rise:.4f} mm"
    )
    if len(joined) != 2:
        print(f"!! {wedge.name} touches {len(joined)} parts, not 2 - it is not sitting in the joint it was built for")

claimed = sum(len(item[3]) for item in report)
if claimed != len(screws):
    print(f"!! {len(screws) - claimed} screws were not claimed by any wedge - the matching above is wrong somewhere")

lengths = sorted({round(wedge.length, 1) for wedge in wedges})
byjoint = defaultdict(list)
for wedge, joined, _, pins, _, _, _, _ in report:
    byjoint["oculus" if "oculus" in joined else "seam"].append((wedge, pins))

for kind in sorted(byjoint):
    group = byjoint[kind]
    print(
        f"{len(group)} {kind} wedges: {min(wedge.length for wedge, _ in group):.1f} mm long, "
        f"{sum(len(pins) for _, pins in group)} screws, {min(len(pins) for _, pins in group)} each, "
        f"spaced {min(wedge.length for wedge, _ in group) / min(len(pins) for _, pins in group):.1f} mm"
    )

print(
    f"{len(wedges)} wedges in {len(lengths)} lengths ({', '.join(f'{value:.1f}' for value in lengths)} mm) and {claimed} screws, "
    f"all of them level to {max(item[7] for item in report):.4f} mm, standing {min(item[4].zmax for item in report) - floortop:+.1f} .. "
    f"{max(item[4].zmax for item in report) - floortop:+.1f} mm proud of the floor - measured, not levelled by hand"
)

# ------------------------------------------------------------------ #
# The parts, in drawing order.
# ------------------------------------------------------------------ #


def named(element, name=None):
    mesh = element.modelgeometry
    mesh.name = name or element.name
    return mesh


wedgemeshes = [named(wedge) for wedge in wedges]
screwmeshes = [named(screw) for wedge, _, _, pins, _, _, _, _ in report for screw, _ in pins]

floormeshes = [named(element) for name in sorted(quarter_parts) for element in sorted(quarter_parts[name], key=lambda item: item.name)]
floormeshes += [named(element) for element in sorted(oculus_parts, key=lambda item: item.name)]
steelmeshes = [named(element) for element in sorted(plates, key=lambda item: item.name)] + [named(element) for element in sorted(seamplates, key=lambda item: item.name)]
steelmeshes += [named(element, f"dowel_{index}_{element.name}") for index, element in enumerate(dowels)]
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
    + [(mesh, GHOST) for mesh in steelmeshes]
    + [(mesh, STEEL) for mesh in wedgemeshes]
    + [(mesh, STEEL) for mesh in screwmeshes],
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


sample = report[0]

lines = [
    "<!-- Generated by examples/example_model_23_assembly_step9.py - do not edit.",
    "     The prose around these lists is in docs/assembly.md; only the",
    "     numbers live here. -->",
    "",
    *_section(
        "totals",
        [
            f"- {len(wedges)} wedges &mdash; {len(byjoint['seam'])} on the seams between quarters, {len(byjoint['oculus'])} around the oculus",
            f"- {', '.join(f'{value:.0f}' for value in lengths)} mm long, {PROFILE_BACK - PROFILE_APEX:.1f} mm from apex to back face, {2 * PROFILE_HALF:.1f} mm across the back",
            f"- {claimed} screws &mdash; &Oslash;{2 * sample[3][0][0].radius:.0f} &times; {sample[3][0][0].axis.length:.0f} mm, "
            f"{min(len(item[3]) for item in report)} to a short wedge and {max(len(item[3]) for item in report)} to a long one",
            f"- every screw level to {max(item[7] for item in report):.4f} mm, through {min(item[6] for item in report):.1f} mm of wedge, "
            f"{0.5 * (sample[3][0][0].axis.length - sample[6]):.0f} mm into the timber each side",
            f"- worst gap in a pocket {max(row[2] for _, joined, sides, _, _, _, _, _ in report for row in sides.values()):.4f} mm; "
            f"the wedges stand {min(item[4].zmax for item in report) - floortop:+.0f} to {max(item[4].zmax for item in report) - floortop:+.0f} mm proud of the floor top",
        ],
    ),
    *_section(
        "wedges",
        [
            f"- `{wedge.name}` &mdash; {wedge.length:.0f} mm, locks `{joined[0]}` &harr; `{joined[1]}`, {len(pins)} screws, "
            f"{sides[joined[0]][0]} faces a side, gap {max(sides[name][2] for name in joined):.4f} mm"
            for wedge, joined, sides, pins, box, height, width, rise in report
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

group = viewer.scene.add_group("floor")
for mesh in floormeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("steel")
for mesh in steelmeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, opacity=COLUMN_OPACITY, linecolor=BLACK)

group = viewer.scene.add_group("wedges")
for mesh in wedgemeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

group = viewer.scene.add_group("screws")
for mesh in screwmeshes:
    viewer.scene.add(mesh, name=mesh.name, parent=group, facecolor=STEEL, linecolor=BLACK)

zoom_to(viewer, [mesh.aabb() for mesh in floormeshes])
viewer.renderer.camera.position.set(-8200, -8600, 5800)
viewer.renderer.camera.target.set(0, 0, 3400)



# A 1.75 m figure, for reading the scale of the model at a glance. Reference
# geometry only - plain polylines, never added to the model itself.
for _part in human_figure(point=[3600, 0, 0]):
    viewer.scene.add(_part, name="scale_figure", linecolor=Color(0.35, 0.35, 0.35), linewidth=2)

viewer.show()
