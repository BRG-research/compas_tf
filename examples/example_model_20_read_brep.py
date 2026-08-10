import pathlib
import sys
import time

from compas_occt.brep import OCCBrep
from compas_viewer import Viewer


data_dir = pathlib.Path(__file__).parent.parent / "data"

STEP_FILE = data_dir / "cantilevers_baked_model.stp"  # written by example_model_18

GREY = (0.85, 0.85, 0.85)

# ------------------------------------------------------------------ #
# OCCBrep.from_step - solids straight off a STEP file.
#
# No element, no model, no boolean, no compas_tf at all beyond the viewer
# helper: this is the same file the shop gets. Each solid comes back with its
# coplanar faces already merged (they were merged when it was written), so a
# drilled face is ONE face with its hole loops rather than a fan of mesh
# triangles.
#
# example_model_18 writes the whole model as a single compound, so the file
# reads back as one Brep; .solids splits it into the individual parts.
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

# ------------------------------------------------------------------ #
# View - a Brep goes into the scene like any other geometry. compas_viewer
# registers a Brep scene object only for compas_occ, but compas_occt ships its
# own register_scene_objects plugin (compas_occt/scene.py) that compas collects
# alongside it, so nothing extra is needed here.
#
# It is not cheap though: most faces of this building are twisted loft quads
# (lofted between parabolas), which OCC meshes on a fixed grid regardless of
# the linear OR angular deflection - ~2.9M triangles for the whole set. The
# same model as meshes (example_model_19_read_model.py) is ~13.7k faces.
# ------------------------------------------------------------------ #

start = time.perf_counter()
viewer = Viewer()
group = viewer.scene.add_group(STEP_FILE.stem)
for index, brep in enumerate(breps):
    group.add(brep, name=brep.name or f"brep_{index}", color=GREY)
print(f"[draw] {time.perf_counter() - start:.1f}s")

viewer.show()
