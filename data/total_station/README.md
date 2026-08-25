# Total station 3D model

`total_station_es105` — Topcon-style ES-105 total station mounted on a survey tripod.

| file | notes |
|---|---|
| `total_station_es105.obj` | Z-up, metres, origin at the instrument's vertical axis on the ground plane. Load with `Mesh.from_obj(...)`. |
| `total_station_es105.glb` | original download (glTF binary, Y-up, textured) |
| `total_station_es105_preview.jpg` | thumbnail |

- Overall size: 1.59 × 1.55 m tripod footprint, 1.73 m to the top of the instrument.
- Triangles: 25 739 (welds to 19 164 faces when read as a COMPAS `Mesh`).

## Source / attribution

- "TOTAL STATION ES 105" by *dicki A.*, Trimble 3D Warehouse (2023-02-06)
- https://3dwarehouse.sketchup.com/model/5f67aafc-05d2-4c37-b238-7d4f63390c5f
- Covered by the Trimble 3D Warehouse General Model License: free to use in your own
  projects and renderings; do not resell or redistribute the model on its own.

The `.obj` was produced from the `.glb` by a stdlib glTF reader (node transforms baked,
Y-up rotated to Z-up); no geometry was otherwise modified apart from the origin shift.
