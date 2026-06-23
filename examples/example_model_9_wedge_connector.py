"""Wedge connector and its boolean cuts - a self-contained demo.

A ConnectorWedgeElement is built on a single interface edge, then used purely as
a GEOMETRY SOURCE for cut features. Instead of the triangular wedge itself, the
cutters are BOXES oriented to the wedge's two INCLINED faces (the slants A-B and
A-C of the triangular profile) - each box's large face lies on an incline and
extends outward into the plate that face meets. Each box (plus the dowels) is
differenced out of a host slab, the same MeshCutFeature path a PlateElement uses.

Everything is drawn in model space - no viewer-side transforms - so the cutters
sit exactly where they cut.
"""

import pathlib

from compas.geometry import Point
from compas.geometry import Vector

from compas_tf.connectors import ConnectorWedgeElement
from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

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

viewer = make_viewer(data_dir)

connector = viewer.scene.add_group("wedge_connector")
connector.add(triangulated(wedge.boolean_geometry), name="wedge_solid", color=GREY, hide_coplanaredges=True)
for i, box in enumerate(face_boxes):
    connector.add(triangulated(box), name=f"box_cutter_{i}", hide_coplanaredges=True)
for i, dowel in enumerate(dowel_cutters):
    connector.add(triangulated(dowel), name=f"dowel_{i}", hide_coplanaredges=True)

viewer.show()
