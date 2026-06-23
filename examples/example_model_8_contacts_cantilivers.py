import pathlib

import compas
from compas.geometry import Point
from compas_model.elements import Group
from compas_model.models import Model

from compas_tf.connectors import ConnectorElement
from compas_tf.plate import PlateElement
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
    box = connector.cutter_mesh()
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
add_tree(cantilever_model.tree.root, viewer.scene)

contacts_group = viewer.scene.add_group("contacts")
for i, contact in enumerate(cantilever_model.contacts()):
    contacts_group.add(contact.polygon, name=f"contact_{i}", color=(1.0, 0.0, 0.0))

viewer.show()
