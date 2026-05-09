"""example_3_schoring_data.py

Convert a SchoringElement OBJ file to COMPAS JSON format.
Run this once when new OBJ mesh data is available for a schoring body.
The resulting JSON is consumed by SchoringElement at runtime.
"""
from pathlib import Path

import compas
from compas.datastructures import Mesh
from compas.geometry import Frame

name = "schoring_vertical_body_end_0"
base_dir = Path("C:/brg/code_python/compas_tf/data/SchoringElement")
obj_path = base_dir / f"{name}.obj"
json_path = base_dir / f"{name}.json"

mesh = Mesh.from_obj(compas.get(str(obj_path)))
frame = Frame.worldXY()
extension_length = mesh.aabb().zsize

compas.json_dump(
    {
        "meshes": [mesh],
        "frames": [frame],
        "extension_length": extension_length,
    },
    str(json_path),
)
print(f"Written: {json_path}")
