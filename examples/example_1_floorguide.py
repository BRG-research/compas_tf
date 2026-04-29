import pathlib

import compas
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer
from compas.geometry import Point
from compas.geometry import Vector
from compas.geometry import Line
from compas.geometry import Polyline
from compas.colors import Color

from compas_tf.floor_guide import FloorGuide


# ------------------------------------------------------------------ #
#  Filepath
# ------------------------------------------------------------------ #
data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  FloorGuide
# ------------------------------------------------------------------ #

guide = FloorGuide(
    size_grid_x=3000,
    size_grid_y=3000,
    size_column_head=250,
    size_column_head_chamfer=120,
    size_outer_ribs=100,
    size_inner_ribs=60,
    size_inner_beams=60,
    height=650,
    rise=453,
    size_oculus=1000,
)

compas.json_dump(guide, data_dir / "floorguide.json")

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
for p in guide.oculus_points:
    viewer.scene.add(p, parent=g)

g = viewer.scene.add_group("quarter_polygon")
viewer.scene.add(guide.quarter_polygon, parent=g)

g = viewer.scene.add_group("quarter_column_polygon")
viewer.scene.add( guide.quarter_column_polygon, parent=g)
print(guide.quarter_column_polygon.points)

g = viewer.scene.add_group("construction_planes")
guide.construction_planes
for key, planes_lists in guide.construction_planes.items():
    for planes in planes_lists:
        for plane in planes:
            add_plane(viewer, plane, parent=g)

g = viewer.scene.add_group("construction_quads")
for key, polygons in guide.construction_quads.items():
    for polygon in polygons:
        viewer.scene.add(polygon, parent=g)
        viewer.scene.add(polygon.points[0], anchor=polygon.points[0], parent=g)
        viewer.scene.add(polygon.lines[0].point_at(0.25), anchor=polygon.points[0], parent=g)
        viewer.scene.add(polygon.lines[0].point_at(0.125), anchor=polygon.points[0], parent=g)

g = viewer.scene.add_group("boundary_parabolas")
for parabolas in guide.boundary_parabolas:
    for parabola in parabolas:
        viewer.scene.add(parabola, parent=g, linecolor=Color.red())

g = viewer.scene.add_group("debug")
for o in guide.debug:
    viewer.scene.add(o, parent=g)

viewer.show()
