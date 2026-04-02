"""Example: visualize all FloorBuilder public properties."""

from compas_viewer.config import Config
from compas_viewer.viewer import Viewer
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Vector

from compas.colors import Color
from compas_tf.floor_builder import FloorBuilder


def add_plane(viewer, plane, parent=None, size=200):
    """Draw a plane as a rectangle + normal line, matching session_tf style."""
    o = Point(*plane.point)
    n = Vector(*plane.normal)
    # Build local x/y axes from the normal
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


config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

builder = FloorBuilder(
    size=3000,
    height=650,
    rise=453,
    oculus=1000,
    thick=40,
    beam_w=200,
)

# ------------------------------------------------------------------ #
#  Floor plan geometry (2D)
# ------------------------------------------------------------------ #

# Four points whose distance is sqrt(2) * oculus
g = viewer.scene.add_group("oculus_points")
for p in builder.oculus_points:
    viewer.scene.add(p, parent=g)

# The main polygon of the floor
g = viewer.scene.add_group("quarter_polygon")
for line in builder.quarter_polygon.lines:
    viewer.scene.add(line, parent=g)

# The bottom left corner
g = viewer.scene.add_group("corner_point")
viewer.scene.add(builder.corner_point, parent=g)

# Points along quarter boundary
g = viewer.scene.add_group("boundary_points")
for p in builder.boundary_points:
    viewer.scene.add(p, parent=g)

# ------------------------------------------------------------------ #
#  Axes & ribs (3D curves along the vault)
# ------------------------------------------------------------------ #

# Lines of the ribs, with a small offset for the two central axes
g = viewer.scene.add_group("axes")
for line in builder.axes:
    viewer.scene.add(line, parent=g)

# The point where the two boundary axes intersect
g = viewer.scene.add_group("corner_axis_point")
viewer.scene.add(Point(*builder.corner_axis_point), parent=g)

# Two boundary parabolas for first and last axes
g = viewer.scene.add_group("boundary_parabolas")
for polyline in builder.boundary_parabolas:
    viewer.scene.add(polyline, parent=g)

# Planes from lines and z-axis
g = viewer.scene.add_group("target_planes")
for plane in builder.target_planes:
    add_plane(viewer, plane, parent=g)

# Four parabolas at each axis
g = viewer.scene.add_group("rib_parabolas")
for polyline in builder.rib_parabolas:
    viewer.scene.add(polyline, parent=g)

# ------------------------------------------------------------------ #
#  Column head (transition from ribs to column)
# ------------------------------------------------------------------ #

# Top ring and bottom ring of the column head
g = viewer.scene.add_group("column_head_points")
pts, pts_bottom = builder.column_head_points
for i in range(len(pts)):
    viewer.scene.add(pts[i], parent=g)
    viewer.scene.add(pts_bottom[i], parent=g)

# Cut planes for the column head
g = viewer.scene.add_group("cut_planes")
for plane in builder.cut_planes:
    add_plane(viewer, plane, parent=g)

# ------------------------------------------------------------------ #
#  Corner block & end planes
# ------------------------------------------------------------------ #

# Points defining the top block of the column head
g = viewer.scene.add_group("top_corner_block_points")
for p in builder.top_corner_block_points:
    viewer.scene.add(p, parent=g)

# Planes at midpoints of corner block edges
g = viewer.scene.add_group("top_end_planes")
for plane in builder.top_end_planes:
    add_plane(viewer, plane, parent=g)

# End planes for each rib
g = viewer.scene.add_group("end_planes")
for plane in builder.end_planes:
    add_plane(viewer, plane, parent=g)

viewer.show()
