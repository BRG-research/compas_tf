import pathlib

from compas.tolerance import TOL
from compas_occt.brep import OCCBrep
from compas_viewer import Viewer
from compas.colors import Color

data_dir = pathlib.Path(__file__).parent.parent / "data"
STEP_FILE = data_dir / "cantilevers_baked_model.stp"
CONTACTS_STEP_FILE = data_dir / "cantilevers_baked_contacts.stp"

# The 0.001 default is a 1 micron chord tolerance on a building: 2.93M triangles.
TOL.lineardeflection = 1.0

breps = OCCBrep.from_step(STEP_FILE).solids
contacts = OCCBrep.from_step(CONTACTS_STEP_FILE).faces
print(f"{len(breps)} solids, {sum(len(brep.faces) for brep in breps)} faces, {len(contacts)} contacts")

viewer = Viewer()

parts = viewer.scene.add_group("model")
for brep in breps:
    viewer.scene.add(brep, parent=parts)

group = viewer.scene.add_group("contacts")
for face in contacts:
    viewer.scene.add(
        face.to_polygon(),
        facecolor=Color(1.0, 0.0, 0.0),
        parent=group,
    )

viewer.show()
