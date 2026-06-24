import pathlib

import compas
from compas.geometry import Point
from compas_model.elements import Group
from compas_model.models import Model

from compas_tf.connectors import ConnectorElement
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
