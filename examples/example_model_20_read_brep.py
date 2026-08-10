"""example_model_20_read_brep.py

Open the STEP files - the model as plain solids, the way a shop gets it.

Reads cantilevers_baked_model.stp and cantilevers_baked_contacts.stp
(example_model_18). No elements, no tree, no names: STEP carries none of them,
which is the trade for a file any CAD system opens.
"""

import pathlib

from compas.colors import Color
from compas.tolerance import TOL
from compas_occt.brep import OCCBrep
from compas_viewer import Viewer

from compas_tf.viewer import zoom_to

data_dir = pathlib.Path(__file__).parent.parent / "data"
STEP_FILE = data_dir / "cantilevers_baked_model.stp"
CONTACTS_STEP_FILE = data_dir / "cantilevers_baked_contacts.stp"

# The 0.001 default is 1 micron on a building: 2.93M triangles against 19.8k.
TOL.lineardeflection = 1.0

# Solids only - no elements, no tree, no names. The contacts are loose faces, so
# they need their own file: .solids would drop them.
breps = OCCBrep.from_step(STEP_FILE).solids
contacts = OCCBrep.from_step(CONTACTS_STEP_FILE).faces
print(f"{len(breps)} solids, {sum(len(brep.faces) for brep in breps)} faces, {len(contacts)} contacts")

viewer = Viewer()

parts = viewer.scene.add_group("model")
for brep in breps:
    viewer.scene.add(brep, parent=parts)

group = viewer.scene.add_group("contacts")
for face in contacts:
    viewer.scene.add(face.to_polygon(), parent=group, facecolor=Color(1, 0, 0), linecolor=Color(1, 0, 0), show_points=False)

# The camera's far plane is 1000 mm, so without this the building starts clipped.
zoom_to(viewer, [brep.aabb for brep in breps])

viewer.show()
