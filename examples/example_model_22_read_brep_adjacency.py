import json
import pathlib
from collections import defaultdict

from compas.colors import Color
from compas.tolerance import TOL
from compas_occt.brep import OCCBrep
from compas_viewer import Viewer

data_dir = pathlib.Path(__file__).parent.parent / "data"
STEP_FILE = data_dir / "cantilevers_baked_model.stp"
CONTACTS_STEP_FILE = data_dir / "cantilevers_baked_contacts.stp"
CONTACTS_JSON_FILE = data_dir / "cantilevers_baked_contacts.json"

# The 0.001 default is a 1 micron chord tolerance on a building: 2.93M triangles.
TOL.lineardeflection = 1.0

solids = OCCBrep.from_step(STEP_FILE).solids
faces = OCCBrep.from_step(CONTACTS_STEP_FILE).faces
records = json.loads(CONTACTS_JSON_FILE.read_text())["contacts"]

# STEP drops per-shape names but keeps their ORDER, so record i describes face i.
# That index is the only thing tying the two files together - if the counts
# disagree they came from different runs and every pairing below is wrong.
if len(records) != len(faces):
    raise SystemExit(f"{len(faces)} faces against {len(records)} records: the STEP and its sidecar are out of sync.")

print(f"{len(solids)} solids, {len(faces)} contact faces, {len(records)} adjacency records")

# The sidecar is a graph over element NAMES. Nothing here can say which of the
# 237 solids is "beds_0_0_0" - for geometry attached to a name, read the JSON
# model instead (example_model_19).
neighbours = defaultdict(set)
joints = defaultdict(list)  # (a, b) -> the face indices they share
for record in records:
    neighbours[record["a"]].add(record["b"])
    neighbours[record["b"]].add(record["a"])
    joints[record["a"], record["b"]].append(record["index"])

area = sum(record["area"] for record in records)
print(f"{len(neighbours)} elements over {len(joints)} pairs, {area / 1e6:.2f} m2 of interface")

# A pair with several faces is one joint the boolean left in pieces, or two
# elements that genuinely touch in more than one place. Group before ranking.
print("\nbiggest joints:")
for (a, b), indices in sorted(joints.items(), key=lambda kv: -sum(records[i]["area"] for i in kv[1]))[:5]:
    print(f"  {sum(records[i]['area'] for i in indices) / 1e6:6.3f} m2  {a} - {b}  ({len(indices)} faces)")

by_type = defaultdict(float)
for record in records:
    by_type[tuple(sorted((record["a_type"], record["b_type"])))] += record["area"]
print("\nby type:")
for (a, b), value in sorted(by_type.items(), key=lambda kv: -kv[1]):
    print(f"  {value / 1e6:6.3f} m2  {a} - {b}")

# One element's joints picked out of the 733. The model is transparent because
# the contacts sit BETWEEN solids.
focus = max(neighbours, key=lambda n: len(neighbours[n]))
selected = {record["index"] for record in records if focus in (record["a"], record["b"])}
print(f"\n{len(selected)} contacts on {focus}, the most connected element")

viewer = Viewer()

parts = viewer.scene.add_group("model")
for solid in solids:
    viewer.scene.add(solid, parent=parts, opacity=0.3)

group = viewer.scene.add_group("contacts")
highlighted = viewer.scene.add_group(f"contacts__{focus}")
for record, face in zip(records, faces):
    hit = record["index"] in selected
    viewer.scene.add(
        face.to_polygon(),
        # The name STEP could not carry, put back from the sidecar.
        name=f"contact_{record['index']}__{record['a']}__{record['b']}",
        parent=highlighted if hit else group,
        facecolor=Color(1, 0, 0) if hit else Color(0.6, 0.6, 0.6),
        linecolor=Color(1, 0, 0) if hit else Color(0.4, 0.4, 0.4),
        show_points=False,
    )

viewer.show()
