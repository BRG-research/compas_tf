import pathlib

import compas
from compas.geometry import Point
from compas_model.elements import Group
from compas_model.models import Model

from compas_tf.connectors import ConnectorElement
from compas_tf.connectors import OuterRibConnectorElement
from compas_tf.plate import PlateElement
from compas_tf.viewer import TeeScene
from compas_tf.viewer import dump_bundle
from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the floor and the columns written by earlier examples
# ------------------------------------------------------------------ #

floor_model: Model = compas.json_load(data_dir / "floor_model.json")
columns_model: Model = compas.json_load(data_dir / "columns_model.json")

# ------------------------------------------------------------------ #
# Merge floor + columns into one model. merge() nests each input under
# its own top-level group, named after it ("floor_model" / "columns_model").
# ------------------------------------------------------------------ #

cantilever_model = Model(name="cantilever_model").merge([floor_model, columns_model])

# ------------------------------------------------------------------ #
# Contacts between the columns and ONLY the outer ribs - a two-sided
# query: every column element against every outer_ribs element, and nothing
# within either side. Each of the 4 quarters has its own outer_ribs_<i> group.
# Contacts carried in from the loaded models are cleared first, so the result
# holds only the column <-> outer_rib contacts computed here.
# ------------------------------------------------------------------ #

for edge in list(cantilever_model.graph.edges()):
    cantilever_model.graph.edge_attribute(edge, name="contacts", value=[])

cantilever_model.compute_contacts_between_groups(
    ["columns_model"],
    groups_b=[f"outer_ribs_{i}" for i in range(4)],
)
print(f"contacts between groups: {sum(1 for _ in cantilever_model.contacts())}")

# ------------------------------------------------------------------ #
# Connectors: one box per column <-> rib contact, oriented to the contact
# (longest extent across the joint toward the rib, top at the contact's
# topmost point). Each connector is cut into BOTH the column and the rib as a
# feature, so each carries its own pocket for fabrication.
# ------------------------------------------------------------------ #

edge_contacts = []
for edge in cantilever_model.graph.edges():
    contacts = cantilever_model.graph.edge_attribute(edge, name="contacts")
    if contacts:
        a = cantilever_model.graph.node_element(edge[0])
        b = cantilever_model.graph.node_element(edge[1])
        for contact in contacts:
            edge_contacts.append((a, b, contact))

connectors_group = cantilever_model.add_group("connectors")
cylinders_group = cantilever_model.add_group("connector_cylinders")
for i, (a, b, contact) in enumerate(edge_contacts):
    rib = a if isinstance(a, PlateElement) else b
    column = b if rib is a else a

    connector = ConnectorElement.from_contact(contact, toward=Point(*rib.modelgeometry.centroid()), name=f"connector_{i}")
    cantilever_model.add_element(connector, parent=connectors_group)

    # Cut the connector box plus its dowel cylinders into each element: the box
    # and the column-side cylinders into the column, the box and the rib-side
    # cylinders into the rib. Cylinder length = rib thickness, radius 25.
    # overshoot so the box caps poke past the column/rib faces (not flush) - a
    # coplanar cap makes the boolean difference unreliable; see cutter_mesh.
    box = connector.cutter_mesh(overshoot=25.0)
    column_cylinders, rib_cylinders = connector.cylinder_cutters(rib.computed_thickness)

    to_column = column.modeltransformation.inverted()
    to_rib = rib.modeltransformation.inverted()
    column.add_cutters([box.transformed(to_column)] + [c.transformed(to_column) for c in column_cylinders])
    rib.add_cutters([box.transformed(to_rib)] + [c.transformed(to_rib) for c in rib_cylinders])

    # The dowel cylinders also pass through the connector box itself - cut them
    # into it so the box carries the dowel holes too.
    to_connector = connector.modeltransformation.inverted()
    connector.add_cutters([c.transformed(to_connector) for c in (column_cylinders + rib_cylinders)])

    # Add the dowels themselves as model elements (like the wedge components):
    # nominal length (= rib thickness), placed alongside the cuts.
    for cylinder in connector.cylinder_elements(rib.computed_thickness):
        cantilever_model.add_element(cylinder, parent=cylinders_group)

# ------------------------------------------------------------------ #
# Contacts between the quarters' outer ribs ONLY - all-pairs mode: every
# outer_ribs_<i> group against every OTHER one, pairs within a single group
# are never tested (so the two ribs of one quarter do not pair up). The 4
# quarters meet at 4 seams -> exactly 4 face-face contact pairs. Contacts
# from the column <-> rib step above are cleared first, so the result holds
# only the rib <-> rib seam contacts computed here.
# ------------------------------------------------------------------ #

for edge in list(cantilever_model.graph.edges()):
    cantilever_model.graph.edge_attribute(edge, name="contacts", value=[])

cantilever_model.compute_contacts_between_groups(
    [f"outer_ribs_{i}" for i in range(4)],
)

rib_contacts = []
for edge in cantilever_model.graph.edges():
    contacts = cantilever_model.graph.edge_attribute(edge, name="contacts")
    if contacts:
        a = cantilever_model.graph.node_element(edge[0])
        b = cantilever_model.graph.node_element(edge[1])
        for contact in contacts:
            rib_contacts.append((a, b, contact))
print(f"outer-rib seam contacts: {len(rib_contacts)} (expected 4)")

# ------------------------------------------------------------------ #
# One OuterRibConnectorElement per seam. The OBJ templates are modelled in
# the connector's local frame (interface plane at local y = 0, body hanging
# a built-in 138.5 below the placement origin), so from_contact only has to
# orient that frame to the seam: origin at the contact's top-edge midpoint,
# +X = world down, +Y = the horizontal contact normal. The MALE cutter
# (cut0) carves the rib on the local -Y side, the FEMALE (cut1) the +Y side;
# both overshoot the interface by 10 so no cap is coplanar with a seam face.
# ------------------------------------------------------------------ #

rib_connectors_group = cantilever_model.add_group("outer_rib_connectors")
for i, (a, b, contact) in enumerate(rib_contacts):
    rib_connector = OuterRibConnectorElement.from_contact(contact, name=f"outer_rib_connector_{i}")
    cantilever_model.add_element(rib_connector, parent=rib_connectors_group)
    for rib in (a, b):
        cutter = rib_connector.cutter_for(rib.modelgeometry.centroid())
        rib.add_cutters([cutter.transformed(rib.modeltransformation.inverted())], name=f"outer_rib_connector_{i}_cut")

print(f"outer-rib connectors placed: {len(rib_contacts)}")

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(cantilever_model, data_dir / "cantilevers_model.json")

# OBJ export: the simplest way into Rhino (File > Import, no compas needed there).
# element.modelgeometry is the carved, watertight mesh, so the OBJ carries the
# connector pockets and dowel holes as closed geometry - one named object per
# element. OBJ is mesh-only, so it drops the lines/colours/layers the Rhino
# bundle keeps (see the RHINO block below); use whichever fits.
from compas.files import OBJWriter  # noqa: E402

_meshes = []
for element in cantilever_model.elements():
    if isinstance(element, Group):
        continue
    geometry = element.modelgeometry
    if geometry is None:
        continue
    geometry = geometry.copy()
    geometry.name = element.name or type(element).__name__
    _meshes.append(geometry)
OBJWriter(str(data_dir / "cantilevers_model.obj"), _meshes, author="compas_tf").write()
print(f"[obj] wrote data/cantilevers_model.obj ({len(_meshes)} objects)")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #


def add_tree(node, viewer_parent):
    """Mirror the model tree into the viewer, preserving the group hierarchy so
    floor_model / columns_model (and their subgroups) show up as their own
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
scene = TeeScene(viewer.scene)  # draw to the viewer AND record a Rhino bundle
add_tree(cantilever_model.tree.root, scene)

contacts_group = scene.add_group("contacts")
for i, contact in enumerate(cantilever_model.contacts()):
    contacts_group.add(contact.polygon, name=f"contact_{i}", color=(1.0, 0.0, 0.0))

# Plain, already-computed geometry for Rhino (no recompute on load) - see RHINO below.
dump_bundle(scene, data_dir / "cantilevers_rhino.json")

viewer.show()


# ====================================================================== #
#  RHINO  -  copy the code between the triple quotes into the Rhino 8
#  ScriptEditor (Python 3) and Run it to add THIS example's geometry to the
#  active Rhino document (named layers, per-object colour). Needs only the
#  installed compas_tf (see install steps); recomputes nothing.
# ====================================================================== #
RHINO = r'''
from compas_tf.rhino import draw_bundle
draw_bundle(r"C:\brg\compas_tf\data\cantilevers_rhino.json")
'''

# ------------------------------------------------------------------ #
#  STEP  -  solid closed Breps via compas_occt. Every element mesh becomes a
#  solid OCCBrep; simplify() merges the boolean triangles back into flat
#  faces - and unlike a Mesh face, a Brep face carries its hole loops
#  properly, so drilled/slotted faces come out as single faces with holes.
#  All solids are compounded into ONE file: data/cantilevers_model.stp.
# ------------------------------------------------------------------ #
from compas.tolerance import TOL  # noqa: E402
from compas_occt.brep import OCCBrep  # noqa: E402

TOL.lineardeflection = 0.1

breps = []
for element in cantilever_model.elements():
    if isinstance(element, Group):
        continue
    mesh = element.modelgeometry
    if mesh is None:
        continue
    brep = OCCBrep.from_mesh(mesh, solid=True)
    # Tight deflections: the DEFAULT angulardeflection (0.1 rad = 5.7 deg) also
    # merges NEARLY-coplanar faces - it flattened the twisted loft quads of the
    # tsections/ribs and changed their solids (tsections lost 42% volume). With
    # 1e-6 rad only exactly-coplanar boolean triangles merge and every solid
    # keeps its exact mesh volume.
    brep.simplify(merge_edges=True, merge_faces=True, lineardeflection=1e-3, angulardeflection=1e-6)
    brep.name = element.name or type(element).__name__
    if not brep.is_solid:
        print(f"[step] WARNING: '{brep.name}' did not convert to a closed solid")
    mesh_volume = mesh.volume()
    if mesh_volume and abs(brep.volume - mesh_volume) > 1e-6 * abs(mesh_volume):
        # simplify distorted the shape - keep the exact (triangulated) Brep.
        print(f"[step] WARNING: simplify changed '{brep.name}' volume by {brep.volume - mesh_volume:+.1f} mm3, keeping unsimplified Brep")
        brep = OCCBrep.from_mesh(mesh, solid=True)
        brep.name = element.name or type(element).__name__
    breps.append(brep)

compound = OCCBrep.from_breps(breps)
compound.to_step(str(data_dir / "cantilevers_model.stp"), name="cantilever_model", author="compas_tf")
print(f"[step] wrote data/cantilevers_model.stp ({len(breps)} solids)")
