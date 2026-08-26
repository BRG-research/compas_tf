import pathlib

import compas
from compas.colors import Color
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.viewer import dump_scene

data_dir = pathlib.Path(__file__).parent.parent / "data"

RED = Color(1.0, 0.0, 0.0)

# The two sides of the search: the quarter's ribs against its wedges.
RIBS = ["outer_ribs", "inner_ribs"]
WEDGES = ["wedges_inner_beams"]
PLATE_GROUPS = RIBS + WEDGES

# ------------------------------------------------------------------ #
# Deserialize ONE quarter written by example_model_4. No columns and no
# other quarters: this example looks only at where a single quarter's ribs
# meet its wedges.
# ------------------------------------------------------------------ #

quarter_model: TFModel = TFModel.from_model(
    compas.json_load(data_dir / "quarter_model.json"),
    name="quarter_contacts_model",
)

# ------------------------------------------------------------------ #
# Contacts between the quarter's ribs and its wedges - nothing else.
#
# A two-sided group search: every element of an outer_ribs/inner_ribs group
# against every element of wedges_inner_beams, and never two elements from
# the same side. That is exactly the column <-> outer_rib query from the
# cantilever example, with both sides now inside the one quarter.
#
# Two-sided is the right shape here because the sides ARE different parts:
# asking for rib-rib or wedge-wedge contacts would be asking a different
# question. (On this quarter it happens to cost nothing - the ribs do not
# touch each other and neither do the wedges, so an all-pairs search over the
# same three groups returns the same 6 contacts. Stating the intent as
# two-sided keeps that an observation rather than an assumption.)
#
# The graph is cleared first: a contact search never removes a contact, it
# only fills in edges that have none, so a loaded model would otherwise report
# stale contacts alongside these.
# ------------------------------------------------------------------ #

quarter_model.clear_contacts()

quarter_model.compute_contacts_between_groups(
    RIBS,
    groups_b=WEDGES,
    tolerance=1.0,
    minimum_area=1.0,
)

quarter_contacts = [(a, b, contact) for _, a, b, contact in quarter_model.contact_pairs()]
print(f"rib <-> wedge contacts: {len(quarter_contacts)}")

# ------------------------------------------------------------------ #
# Report which plate group met which, so the numbers can be sanity-checked
# against the geometry (each wedge sits between an inner rib and a beam).
# ------------------------------------------------------------------ #


def plate_group(element):
    """The plate group an element belongs to."""
    parent = element.treenode.parent if element.treenode is not None else None
    while parent is not None and not parent.is_root:
        if parent.element.name in PLATE_GROUPS:
            return parent.element.name
        parent = parent.parent
    return "?"


counts = {}
for a, b, _ in quarter_contacts:
    key = tuple(sorted((plate_group(a), plate_group(b))))
    counts[key] = counts.get(key, 0) + 1
for (group_a, group_b), count in sorted(counts.items(), key=lambda item: -item[1]):
    marker = "   (same group)" if group_a == group_b else ""
    print(f"   {count:4d}  {group_a} <-> {group_b}{marker}")

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(quarter_model, data_dir / "quarter_contacts_model.json")

# The contacts as their own STEP + adjacency JSON: one planar face per
# contact, plus the record of which two elements each face joins.
quarter_model.contacts_to_step(str(data_dir / "quarter_contacts.stp"))
quarter_model.contacts_to_json(str(data_dir / "quarter_contacts.json"))
print(f"[step] wrote data/quarter_contacts.stp ({len(quarter_contacts)} faces)")

# OBJ export: the simplest way into Rhino (File > Import, no compas needed there).
# element.modelgeometry is the watertight mesh - one named object per element.
from compas.files import OBJWriter  # noqa: E402

_meshes = []
for element in quarter_model.elements():
    if isinstance(element, Group):
        continue
    geometry = element.modelgeometry
    if geometry is None:
        continue
    geometry = geometry.copy()
    geometry.name = element.name or type(element).__name__
    _meshes.append(geometry)
OBJWriter(str(data_dir / "quarter_contacts_model.obj"), _meshes, author="compas_tf").write()
print(f"[obj] wrote data/quarter_contacts_model.obj ({len(_meshes)} objects)")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #


def add_tree(node, viewer_parent=None):
    """Mirror the model tree into the viewer, preserving the group hierarchy so
    the plate groups (and the three bed rows) show up as their own groups in
    the scene tree instead of one flat list."""
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=viewer_parent))
        else:
            if element.modelgeometry is not None:
                viewer.scene.add(element, name=element.name, parent=viewer_parent)


viewer = Viewer()
add_tree(quarter_model.tree.root)

contacts_group = viewer.scene.add_group("contacts")
for i, (a, b, contact) in enumerate(quarter_contacts):
    viewer.scene.add(
        contact.polygon,
        name=f"contact_{i}__{a.name}__{b.name}",
        parent=contacts_group,
        facecolor=RED,
        linecolor=RED,
    )

# Plain, already-computed geometry for Rhino (no recompute on load) - see RHINO below.
dump_scene(viewer.scene, data_dir / "quarter_contacts_rhino.json")

viewer.show()


# ====================================================================== #
#  RHINO  -  copy the code between the triple quotes into the Rhino 8
#  ScriptEditor (Python 3) and Run it to add THIS example's geometry to the
#  active Rhino document (named layers, per-object colour). Needs only the
#  installed compas_tf (see install steps); recomputes nothing.
# ====================================================================== #
RHINO = r"""
from compas_tf.rhino import draw_bundle
draw_bundle(r"C:\brg\code_python\compas_tf\data\quarter_contacts_rhino.json")
"""
