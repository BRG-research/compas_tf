import pathlib

import compas
from compas.geometry import Point
from compas.geometry import Vector
from compas_model.elements import Group
from compas_model.models import Model

from compas_tf.connectors import ConnectorWedgeElement
from compas_tf.floor_guide import FloorGuide
from compas_tf.plate import PlateElement
from compas_tf.solid_difference_modifier import CylinderCutFeature
from compas_tf.solid_difference_modifier import PrismCutFeature
from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the FloorGuide written by an earlier example
# ------------------------------------------------------------------ #

guide: FloorGuide = compas.json_load(data_dir / "floorguide.json")
quarters_model: Model = compas.json_load(data_dir / "quarters_model.json")
oculus_model: Model = compas.json_load(data_dir / "oculus_model.json")

# ------------------------------------------------------------------ #
# Merge the quarters and the oculus into one model.
# ------------------------------------------------------------------ #
floor_model = Model(name="floor_model").merge([quarters_model, oculus_model])

# ------------------------------------------------------------------ #
# Top/bottom contacts between the joint-ring plates (base Model, no FloorModel).
#
# The wedges only sit where the *large* faces of the inner_beams plates and the
# 4 oculus boundary plates meet - the same set example_2 uses. We pair those
# plates directly and ask each pair for its top/bottom-face contacts
# (face_kinds drops the thin side quads), so no side-face contact is ever
# considered.
# ------------------------------------------------------------------ #


def is_joint_ring(element):
    """inner_beams_* plates + the 4 oculus boundary plates (oculus_0..3)."""
    if not isinstance(element, PlateElement):
        return False
    name = element.name or ""
    if name.startswith("inner_beams_"):  # excludes wedges_inner_beams_*
        return True
    if name.startswith("oculus_"):
        try:
            return int(name.rsplit("_", 1)[-1]) < 4
        except ValueError:
            return False
    return False


plates = [el for el in floor_model.elements() if is_joint_ring(el)]

contacts = []  # (plate_a, plate_b, contact)
for i in range(len(plates)):
    for j in range(i + 1, len(plates)):
        a, b = plates[i], plates[j]
        for contact in a.compute_contacts(b, tolerance=1.0, minimum_area=1.0, face_kinds={"top", "bottom"}) or []:
            contacts.append((a, b, contact))
print(f"top/bottom contacts: {len(contacts)}")

# ------------------------------------------------------------------ #
# Connectors: one wedge + its cylinders per contact. Placement, wedge length
# (edge - 3 * plate thickness) and cylinder distribution all live in
# ConnectorWedgeElement - which carries the exact WedgeElement geometry, so the
# result is identical to example_2_floor_model_booleans.py.
# ------------------------------------------------------------------ #

connectors_group = floor_model.add_group("connectors")
for k, (a, b, contact) in enumerate(contacts):
    thickness = max(a.computed_thickness, b.computed_thickness)
    wedge = ConnectorWedgeElement.from_contact(
        contact,
        length_margin=1.5 * thickness,  # target_length = edge - 3 * thickness
        cylinder_radius=10.0,  # dowel Ø 20
        cylinder_spacing=320.0,
        cylinder_sides=8,
        name=f"connector_wedge_{k}",
    )
    floor_model.add_element(wedge, parent=connectors_group)
    cylinders = wedge.create_cylinders()
    for cylinder in cylinders:
        floor_model.add_element(cylinder, parent=connectors_group)

    # The wedge stays as the VISIBLE connector element above; the BOOLEAN cut is
    # no longer the wedge shape. Each neighbour plate is cut by the box of the
    # inclined wedge face that meets it - one box per neighbour - stored as a
    # PrismCutFeature from the box's co-wound (bottom, top) outlines. That gives
    # both the box cutter (the loft) and the drilling outlines (its minimal).
    # inclined_face_box_outlines returns [A-B, A-C] in face order: A-B faces the
    # -normal side, A-C the +normal side, so match each to the plate on its side.
    outlines = wedge.inclined_face_box_outlines(depth=2.0 * thickness / 3.0)  # world, [(b,t) A-B, A-C]
    cnormal = Vector(*contact.polygon.normal)
    ccenter = Point(*contact.polygon.centroid)
    dowels = [(cyl.axis, cyl.radius, cyl.sides) for cyl in cylinders]  # world
    for plate in (a, b):
        side = Vector.from_start_end(ccenter, Point(*plate.modelgeometry.centroid())).dot(cnormal)
        box_bottom, box_top = outlines[1] if side >= 0 else outlines[0]  # +normal -> A-C, -normal -> A-B
        to_local = plate.modeltransformation.inverted()
        plate.add_feature(PrismCutFeature(box_bottom.transformed(to_local), box_top.transformed(to_local), name=f"connector_{k}_box"))
        for j, (axis, radius, sides) in enumerate(dowels):
            plate.add_feature(CylinderCutFeature(axis.transformed(to_local), radius, sides=sides, name=f"connector_{k}_dowel_{j}"))

print(f"wedge connectors placed: {len(contacts)}  (cutters stored as plate features)")

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(floor_model, data_dir / "floor_model.json")

# OBJ export: element.modelgeometry is the carved, CGAL-meshed, watertight mesh
# (the boolean result + CGAL hole triangulation), so the OBJ carries the slots
# and dowel holes as closed geometry. One named object per element.
from compas.files import OBJWriter  # noqa: E402

_meshes = []
for element in floor_model.elements():
    if isinstance(element, Group):
        continue
    geometry = element.modelgeometry
    if geometry is None:
        continue
    geometry = geometry.copy()
    geometry.name = element.name or type(element).__name__
    _meshes.append(geometry)
OBJWriter(str(data_dir / "floor_model.obj"), _meshes, author="compas_tf").write()
print(f"[obj] wrote data/floor_model.obj ({len(_meshes)} objects)")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #


def add_tree(node, viewer_parent):
    """Mirror the model tree into the viewer, preserving the group hierarchy so
    quarters_model / oculus_model (and their subgroups) show up as their own
    groups in the scene tree instead of one flat list."""
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer_parent.add_group(element.name))
        else:
            mesh = element.modelgeometry
            if mesh is not None:
                viewer_parent.add(triangulated(mesh), name=element.name, hide_coplanaredges=True, color=(0.85, 0.85, 0.85))


viewer = make_viewer(data_dir)
add_tree(floor_model.tree.root, viewer.scene)

contacts_group = viewer.scene.add_group("contacts")
for i, (_a, _b, contact) in enumerate(contacts):
    contacts_group.add(contact.polygon, name=f"contact_{i}", color=(1.0, 0.0, 0.0))

viewer.show()
