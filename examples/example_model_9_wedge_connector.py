import pathlib

from compas.geometry import Point
from compas.geometry import Vector
from compas_viewer import Viewer

from compas_tf.connectors import ConnectorWedgeElement

data_dir = pathlib.Path(__file__).parent.parent / "data"

GREY = (0.7, 0.7, 0.7)
BLUE = (0.2, 0.4, 0.9)  # box cutters (one per inclined face)
GREEN = (0.2, 0.7, 0.3)  # dowels

# ------------------------------------------------------------------ #
# 1. A wedge connector on one interface edge.
#    frame: X = edge direction, Y = normal (cut-through / dowel axis),
#    Z = X x Y, centred at the edge midpoint.
# ------------------------------------------------------------------ #

wedge = ConnectorWedgeElement.from_interface(
    start=Point(-300, 0, 0),
    end=Point(300, 0, 0),
    normal=Vector(0, 1, 0),
    length_margin=50.0,  # length = edge - 2 * margin
    cylinder_radius=10.0,  # dowel diameter 20
    cylinder_spacing=240.0,
    cylinder_sides=16,
    name="wedge",
)


# ------------------------------------------------------------------ #
# 2. The cutters: one box per inclined face (now a ConnectorWedgeElement
#    method), plus the dowels - all in model space.
# ------------------------------------------------------------------ #

face_boxes = wedge.inclined_face_boxes(depth=100.0)
dowel_cutters = [cyl.boolean_geometry for cyl in wedge.create_cylinders()]

# ------------------------------------------------------------------ #
# 3. A host slab carved by the inclined boxes + dowels (same MeshCutFeature
#    boolean path a PlateElement runs on its features).
# ------------------------------------------------------------------ #


# ------------------------------------------------------------------ #
#  View - all in model space, no transforms.
# ------------------------------------------------------------------ #

viewer = Viewer()

connector = viewer.scene.add_group("wedge_connector")
viewer.scene.add(wedge.boolean_geometry, name="wedge_solid", parent=connector, facecolor=GREY)
for i, box in enumerate(face_boxes):
    viewer.scene.add(box, name=f"box_cutter_{i}", parent=connector)
for i, dowel in enumerate(dowel_cutters):
    viewer.scene.add(dowel, name=f"dowel_{i}", parent=connector)

viewer.show()
