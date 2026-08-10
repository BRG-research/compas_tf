import pathlib
import sys
import time

from compas.tolerance import TOL
from compas_occt.brep import OCCBrep
from compas_viewer import Viewer


data_dir = pathlib.Path(__file__).parent.parent / "data"

STEP_FILE = data_dir / "cantilevers_baked_model.stp"  # written by example_model_18
CONTACTS_STEP_FILE = data_dir / "cantilevers_baked_contacts.stp"

RED = (1.0, 0.0, 0.0)

# The deflection the viewer tessellates with. TOL's default of 0.001 mm is a
# 1 micron chord tolerance on a building: the twisted loft quads of the ribs
# and t-sections then come to 2.93M triangles and 67 s. At 1.0 mm it is 19.8k
# triangles and 2.0 s - about the 17.0k of the source mesh, i.e. only the flat
# faces get retriangulated. The angular deflection changes neither.
TOL.lineardeflection = 1.0

# ------------------------------------------------------------------ #
# OCCBrep.from_step - solids straight off a STEP file.
#
# No element, no model, no boolean, no compas_tf at all beyond the viewer
# helper: this is the same file the shop gets. Each solid comes back with its
# coplanar faces already merged, so a drilled face is ONE face with its hole
# loops rather than a fan of mesh triangles.
#
# The model is one compound, so .solids splits it into the individual parts.
# The contacts are a second file - they are loose planar faces, which .solids
# would drop - and they are read, not recomputed: example_model_18 found them.
# ------------------------------------------------------------------ #

if not STEP_FILE.exists():
    sys.exit(f"{STEP_FILE.name} not found - run example_model_18_write_model_and_brep.py first.")

start = time.perf_counter()
compound = OCCBrep.from_step(STEP_FILE)
breps = compound.solids or [compound]
print(f"[load] {STEP_FILE.name}: {time.perf_counter() - start:.1f}s, {len(breps)} solids")

solids = sum(brep.is_solid for brep in breps)
faces = sum(len(brep.faces) for brep in breps)
volume = sum(brep.volume for brep in breps)
print(f"{STEP_FILE.stem}: {solids}/{len(breps)} closed solids, {faces} faces, {volume:.3e} mm3")

contacts = []
if CONTACTS_STEP_FILE.exists():
    start = time.perf_counter()
    contact_compound = OCCBrep.from_step(CONTACTS_STEP_FILE)
    contacts = contact_compound.faces
    area = sum(face.area for face in contacts)
    print(f"[load] {CONTACTS_STEP_FILE.name}: {time.perf_counter() - start:.1f}s, {len(contacts)} contact faces, {area:.3e} mm2")

# ------------------------------------------------------------------ #
# View - a Brep goes into the scene like any other geometry. compas_viewer
# registers a Brep scene object only for compas_occ, but compas_occt ships its
# own register_scene_objects plugin that compas collects alongside it.
#
# The solids keep the viewer's default appearance (black edges); the contacts
# are red, in their own group so the model can be switched off to see them.
# ------------------------------------------------------------------ #

start = time.perf_counter()
viewer = Viewer()
group = viewer.scene.add_group(STEP_FILE.stem)
for index, brep in enumerate(breps):
    group.add(brep, name=brep.name or f"brep_{index}")

if contacts:
    # viewer.scene.add(parent=...), NOT contacts_group.add(...): Group.add routes
    # through SceneObject.add, which drops facecolor/linecolor and leaves the
    # contacts the default grey.
    contacts_group = viewer.scene.add_group("contacts")
    for index, face in enumerate(contacts):
        viewer.scene.add(
            face.to_polygon(),
            name=f"contact_{index}",
            parent=contacts_group,
            facecolor=RED,
            linecolor=RED,
            show_points=False,
        )
print(f"[draw] {len(contacts)} contacts + {len(breps)} solids in {time.perf_counter() - start:.1f}s")

viewer.show()
