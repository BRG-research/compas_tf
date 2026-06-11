"""example_6_assembly.py

Assembly sequence: each floor quarter is offset +1000 mm higher than
the previous one so they appear stacked vertically, with the oculus
added last at the top.

Build order:
  quarter_0 → +0 mm extra    (oculus subgroup deferred)
  quarter_1 → +1000 mm extra
  quarter_2 → +2000 mm extra
  quarter_3 → +3000 mm extra
  oculus    → +4000 mm extra  (from floor_guide 0, guide.oculus plates)
"""

import math
import pathlib
import sys

from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_model.elements.group import Group
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel
from compas_tf.joint_dowel import DowelElement
from compas_tf.wedge import WedgeElement

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_element_to_viewer  # noqa: E402
from model import get_color_for_element  # noqa: E402
from model import get_difference_source_elements  # noqa: E402
from model import get_union_source_elements  # noqa: E402

ASSEMBLY_OFFSET = 300  # mm between each quarter

# ------------------------------------------------------------------ #
#  Parameters (same as example_2)
# ------------------------------------------------------------------ #

column_size = 220

builder = FloorBuilder(
    size=3000,
    height=650,
    rise=453,
    oculus=1000,
    beam_w=40,
    column_head_offset=50,
    inner_thick=60,
    outer_thick=100,
    column_head_scale=250,
    column_head_inclination=0,
    head_h=500,
    head_b=100,
    head_o=141,
)

guide = FloorGuide(
    size_grid_x=3000,
    size_grid_y=3000,
    size_column_head=220,
    size_column_head_chamfer=120,
    size_outer_ribs=100,
    size_inner_ribs=60,
    size_inner_beams=60,
    height=650,
    rise=453,
    size_oculus=1000,
    size_wedge=120,
)

# ------------------------------------------------------------------ #
#  Build FloorModel — oculus lives inside floor_guide 0 (include_oculus=True)
# ------------------------------------------------------------------ #

floor_model = FloorModel(builder=builder)
floor_model.add_support(column_size=column_size)
floor_model.add_column(column_size=column_size)

floor_level = Translation.from_vector(Vector(0, 0, floor_model.story_height))
floor_model.add_floor_guide(guide, column_index=0, transformation=floor_level, include_oculus=True)
for i in range(1, 4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    floor_model.add_floor_guide(guide, column_index=i, transformation=floor_level * rot, include_oculus=False)

floor_model.precompute_boolean_modifiers()

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

hidden_sources = get_union_source_elements(floor_model) | get_difference_source_elements(floor_model)


def add_group_offset(group, viewer_parent, z_offset, skip_subgroup=None):
    """Recursively add a model Group to the viewer with a Z offset on every mesh.

    Parameters
    ----------
    skip_subgroup : str, optional
        Name of a direct child Group to skip (used to defer the oculus).
    """
    extra = Translation.from_vector(Vector(0, 0, z_offset))
    for child in group.children:
        if isinstance(child, Group):
            if skip_subgroup and child.name == skip_subgroup:
                continue
            child_vg = viewer.scene.add_group(child.name or "group", parent=viewer_parent)
            add_group_offset(child, child_vg, z_offset)
        else:
            if child in hidden_sources or isinstance(child, (DowelElement, WedgeElement)):
                continue
            mesh = child.modelgeometry
            if mesh is None:
                continue
            color = get_color_for_element(child)
            name = child.name or "element"
            elem_vg = viewer.scene.add_group(name, parent=viewer_parent)
            elem_vg.add(mesh.transformed(extra), name="mesh", hide_coplanaredges=True, color=color)


# Supports and columns — no extra offset
for node in floor_model.tree.root.children:
    element = node.element
    if isinstance(element, Group) and element.name in ("supports", "columns"):
        vg = viewer.scene.add_group(element.name)
        for child in element.children:
            if child in hidden_sources:
                continue
            add_element_to_viewer(viewer, vg, child, get_color_for_element(child))

# Floor guide quarters — each quarter lifted by q_idx * ASSEMBLY_OFFSET
floor_guide_groups = [node.element for node in floor_model.tree.root.children if isinstance(node.element, Group) and node.element.name == "floor_guide"]

quarters_vg = viewer.scene.add_group("quarters")
for q_idx, fg in enumerate(floor_guide_groups):
    q_vg = viewer.scene.add_group(f"quarter_{q_idx}", parent=quarters_vg)
    skip = "oculus" if q_idx == 0 else None
    add_group_offset(fg, q_vg, q_idx * ASSEMBLY_OFFSET, skip_subgroup=skip)

# Oculus — from floor_guide 0, rendered last at the highest Z
fg0 = floor_guide_groups[0]
for child in fg0.children:
    if isinstance(child, Group) and child.name == "oculus":
        oculus_vg = viewer.scene.add_group("oculus")
        add_group_offset(child, oculus_vg, len(floor_guide_groups) * ASSEMBLY_OFFSET)
        break

viewer.show()
