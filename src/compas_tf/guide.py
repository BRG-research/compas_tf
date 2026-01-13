"""Visualize FloorSkeleton computation steps in sequence."""

from compas.data import json_load
from compas.datastructures import Mesh
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas_viewer import Viewer
from compas_viewer.config import Config

from compas_tf.geometry import PlaneIntersect


def add_geometry_to_group(group, geometry, name_prefix=""):
    """Add geometry to viewer group based on type."""
    if isinstance(geometry, Mesh):
        group.add(geometry, hide_coplanaredges=True)
    elif isinstance(geometry, (Plane,)):
        rect, normal = PlaneIntersect.plane_rectangle(geometry, scale=200)
        group.add(rect)
        group.add(normal)
    elif isinstance(geometry, (Point, Line, Polyline, Polygon)):
        group.add(geometry)
    elif isinstance(geometry, list):
        for i, item in enumerate(geometry):
            add_geometry_to_group(group, item, f"{name_prefix}_{i}")
    elif isinstance(geometry, dict):
        for key, value in geometry.items():
            add_geometry_to_group(group, value, f"{name_prefix}_{key}")


# Load serialized steps
steps = json_load("floor_steps.json")

# Setup viewer
config = Config()
config.unit = "mm"
viewer = Viewer(config)

# Add each step as group (step names already have numeric prefixes)
for step_name, geometry in steps.items():
    group = viewer.scene.add_group(step_name)
    add_geometry_to_group(group, geometry, step_name)
    print(f"{step_name}")

print(f"\nTotal steps: {len(steps)}")

viewer.show()
