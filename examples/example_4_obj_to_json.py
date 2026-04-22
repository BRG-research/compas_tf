import compas
from compas.datastructures import Mesh
from compas.geometry import Frame
from pathlib import Path

# Set base name once
name = "schoring_vertical_body_end_0"
base_dir = Path("C:/brg/code_python/compas_tf/data/SchoringElement")
obj_path = base_dir / f"{name}.obj"
json_path = base_dir / f"{name}.json"

# Load mesh from OBJ
mesh = Mesh.from_obj(compas.get(str(obj_path)))
frame = Frame.worldXY()
extension_length = mesh.aabb().zsize

# Serialize frame (as two connection frames, for example)
frames = [frame]

# Compose the full JSON structure
json_data = {
    "meshes": [mesh],
    "frames": frames,
    "extension_length": extension_length
}

# Write to JSON file using COMPAS utility
compas.json_dump(json_data, str(json_path))
