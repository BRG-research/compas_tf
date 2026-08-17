import pathlib

import compas
from compas.geometry import Frame
from compas_viewer import Viewer

from compas_tf.floor_guide import FloorGuide
from compas_tf.viewer import frame_rectangle

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Create a FloorGuide used by the other models, and save it.
# ------------------------------------------------------------------ #

guide = FloorGuide(
    size_grid_x=3000,
    size_grid_y=3000,
    size_column_head=220,
    size_column_head_chamfer=120,
    size_outer_ribs=100,
    size_inner_ribs=60,
    size_inner_beams=60,
    size_wedge=240,
    height=650,
    rise=453,
    size_oculus=1000,
)

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(guide, data_dir / "floorguide.json")

# ------------------------------------------------------------------ #
#  View the construction geometry
# ------------------------------------------------------------------ #
viewer = Viewer()

# Plan polygons (2D): the quarter boundary, the column-head polygon, and the oculus points.
plan = viewer.scene.add_group("plan")
viewer.scene.add(guide.quarter_polygon, name="quarter_polygon", parent=plan, linewidth=3)
viewer.scene.add(guide.quarter_column_polygon, name="quarter_column_polygon", parent=plan, linewidth=3)
for i, point in enumerate(guide.oculus_points):
    viewer.scene.add(point, name=f"oculus_point_{i}", parent=plan, pointsize=10)

# Construction quads (2D): one rectangle per rib / beam / wedge / t-section.
quads = viewer.scene.add_group("construction_quads")
for key, polygons in guide.construction_quads.items():
    group = viewer.scene.add_group(key, parent=quads)
    for i, polygon in enumerate(polygons):
        viewer.scene.add(polygon, name=f"{key}_{i}", parent=group, linewidth=2)

# Boundary parabolas plus its two# t-section offsets.
parabolas = viewer.scene.add_group("parabolas")
for i, offsets in enumerate(guide.boundary_parabolas):
    group = viewer.scene.add_group(f"parabola_{i}", parent=parabolas)
    for j, polyline in enumerate(offsets):
        viewer.scene.add(polyline, name=f"offset_{j}", parent=group, linewidth=2)

# Construction planes: shown as a small rectangle + normal line per plane.
planes = viewer.scene.add_group("planes")
for key, plane_pairs in guide.construction_planes.items():
    group = viewer.scene.add_group(key, parent=planes)
    for i, pair in enumerate(plane_pairs):
        for j, plane in enumerate(pair):
            rectangle, normal = frame_rectangle(Frame.from_plane(plane), scale=150)
            viewer.scene.add(rectangle, name=f"{key}_{i}_{j}", parent=group, facecolor=(0.2, 0.6, 0.9), opacity=0.3)
            viewer.scene.add(normal, name=f"{key}_{i}_{j}_normal", parent=group, linewidth=2, linecolor=(0.9, 0.2, 0.2))

viewer.show()
