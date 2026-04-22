import pathlib

import compas
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Vector
from compas.colors import Color

import compas_tf  # noqa: F401
from compas_tf.floor_builder import FloorBuilder


# ------------------------------------------------------------------ #
#  Filepath
# ------------------------------------------------------------------ #
data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  FloorBuilder
# ------------------------------------------------------------------ #

builder = FloorBuilder(
    size=3000,
    height=650,
    rise=453,
    oculus=1000,
    thick=40,
    beam_w=40,
    column_head_scale=250,
    column_head_inclination=0,
    head_h=500,
    head_b=100,
    head_o=141,
)

compas.json_dump(builder, data_dir / "floorbuilder.json")

# ------------------------------------------------------------------ #
#  Viewer — wireframe
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

def add_plane(viewer, plane, parent=None, size=200):
    o = Point(*plane.point)
    n = Vector(*plane.normal)
    ref = Vector(0, 0, 1) if abs(n.dot(Vector(0, 0, 1))) < 0.9 else Vector(1, 0, 0)
    x = n.cross(ref)
    x.unitize()
    y = n.cross(x)
    y.unitize()
    c0 = Point(*(o - x * size - y * size))
    c1 = Point(*(o + x * size - y * size))
    c2 = Point(*(o + x * size + y * size))
    c3 = Point(*(o - x * size + y * size))
    tip = Point(*(o + n * size))
    blue = Color.blue()
    viewer.scene.add(Polyline([c0, c1, c2, c3, c0]), parent=parent, linecolor=blue)
    viewer.scene.add(Line(o, tip), parent=parent, linecolor=blue)

g = viewer.scene.add_group("oculus_points")
for p in builder.oculus_points:
    viewer.scene.add(p, parent=g)

g = viewer.scene.add_group("quarter_polygon")
for line in builder.quarter_polygon.lines:
    viewer.scene.add(line, parent=g)

g = viewer.scene.add_group("corner_point")
viewer.scene.add(builder.corner_point, parent=g)

g = viewer.scene.add_group("corner_point_column")
viewer.scene.add(builder.corner_point_column(), parent=g)

g = viewer.scene.add_group("boundary_points")
for p in builder.boundary_points:
    viewer.scene.add(p, parent=g)

g = viewer.scene.add_group("axes")
for line in builder.axes:
    viewer.scene.add(line, parent=g)

g = viewer.scene.add_group("corner_axis_point")
viewer.scene.add(Point(*builder.corner_axis_point), parent=g)

g = viewer.scene.add_group("boundary_parabolas")
for polyline in builder.boundary_parabolas:
    viewer.scene.add(polyline, parent=g)

g = viewer.scene.add_group("target_planes")
for plane in builder.target_planes:
    add_plane(viewer, plane, parent=g)

g = viewer.scene.add_group("rib_parabolas")
for polyline in builder.rib_parabolas:
    viewer.scene.add(polyline, parent=g)

g = viewer.scene.add_group("column_head_points")
pts, pts_bottom = builder.column_head_points
for i in range(len(pts)):
    viewer.scene.add(pts[i], parent=g)
    viewer.scene.add(pts_bottom[i], parent=g)

g = viewer.scene.add_group("cut_planes")
for plane in builder.cut_planes:
    add_plane(viewer, plane, parent=g)

g = viewer.scene.add_group("top_corner_block_points")
for p in builder.top_corner_block_points:
    viewer.scene.add(p, parent=g)

g = viewer.scene.add_group("top_end_planes")
for plane in builder.top_end_planes:
    add_plane(viewer, plane, parent=g)

g = viewer.scene.add_group("end_planes")
for plane in builder.end_planes:
    add_plane(viewer, plane, parent=g)

viewer.show()
