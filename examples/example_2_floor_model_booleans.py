"""
#! python3
# r: compas, compas_cgal
import pathlib
import sys
# sys.path.insert(0, r"C:\brg\compas_tf\src")
sys.path.insert(0, r"C:\brg\code_python\compas_tf\src")

import compas
import scriptcontext as sc
import rhinoscriptsyntax as rs
from compas_rhino.conversions import mesh_to_rhino
from compas_model.elements.group import Group+

# data_path = pathlib.Path(r"C:\brg\compas_tf\data\floor_model_booleans.json")
data_path = pathlib.Path(r"C:\brg\code_python\compas_tf\data\floor_model_booleans.json")
floor_model = compas.json_load(data_path)

layer = "FloorModel"
rs.AddLayer(layer)
layer_idx = sc.doc.Layers.FindByFullPath(layer, -1)

def add_element(element):
    if isinstance(element, Group):
        for child in element.children:
            add_element(child)
        return
    mesh = element.modelgeometry
    if mesh is None:
        print(f"SKIP (no geometry): {element.name}")
        return
    rh_mesh = mesh_to_rhino(mesh)
    rh_mesh.Vertices.CombineIdentical(True, True)
    rh_mesh.Faces.CullDegenerateFaces()
    rh_mesh.Compact()
    rh_mesh.Normals.ComputeNormals()
    if not rh_mesh.IsValid:
        print(f"SKIP (invalid mesh): {element.name}")
    attr = sc.doc.CreateDefaultAttributes()
    attr.LayerIndex = layer_idx
    sc.doc.Objects.AddMesh(rh_mesh, attr)

for node in floor_model.tree.root.children:
    add_element(node.element)

sc.doc.Views.Redraw()

# "C:/Users/Petras/.rhinocode/py39-rh8/python.exe" -m pip install --no-build-isolation -e C:/brg/compas_tf
"C:/Users/petrasv/.rhinocode/py39-rh8/python.exe" -m pip install --no-build-isolation -e C:/brg/code_python/compas_tf
"""

import math
import pathlib
import sys

import compas
from compas.colors import Color
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_tf  # noqa: F401
from compas_tf.floor_builder import FloorBuilder
from compas_tf.floor_column_connection import FloorColumnConnectionElement
from compas_tf.floor_guide import FloorGuide
from compas_tf.floor_model import FloorModel

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from model import add_model_to_viewer  # noqa: E402

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Parameters
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
    size_wedge=240,
)


# ------------------------------------------------------------------ #
#  Build FloorModel
# ------------------------------------------------------------------ #

floor_model = FloorModel(builder=builder)

floor_model.add_support(column_size=column_size)
floor_model.add_column(column_size=column_size, capitel_width=120, capitel_height=abs(guide.column_head_lowest_height))

floor_level = Translation.from_vector(Vector(0, 0, floor_model.story_height))
floor_model.add_floor_guide(guide, column_index=0, transformation=floor_level, include_oculus=True)
for i in range(1, 4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    floor_model.add_floor_guide(guide, column_index=i, transformation=floor_level * rot, include_oculus=False)

# ------------------------------------------------------------------ #
#  Custom FloorColumnConnection meshes on each column
# ------------------------------------------------------------------ #
# The OBJ is modelled in world coordinates aligned to column_0 (bottom-left
# corner). Each column is positioned by a Rotation(i * 90deg) about the global
# Z-axis, so the same rotation places a copy of the connection on each column.

connections_group = floor_model.add_group("column_connections")
for i in range(4):
    rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
    connection = FloorColumnConnectionElement(transformation=rot, name=f"floor_column_connection_{i}")
    floor_model.add_element(connection, parent=connections_group)

# ------------------------------------------------------------------ #
#  Batch boolean cuts
# ------------------------------------------------------------------ #

# floor_model.precompute_boolean_modifiers()

# ------------------------------------------------------------------ #
#  Contact detection (inner_beams plates only — fast, filtered)
# ------------------------------------------------------------------ #

floor_model.compute_contacts_inner_beams(tolerance=1.0, minimum_area=1.0)
contacts = list(floor_model.contacts())
print(f"[contact] {len(contacts)} contact(s) found")

floor_model.precompute_boolean_modifiers()

compas.json_dump(floor_model, data_dir / "floor_model_booleans.json")
compas.json_dump(builder, data_dir / "floorbuilder.json")

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

add_model_to_viewer(floor_model, viewer)

# screw_heads = Mesh.from_obj(str(data_dir / "CustomElements" / "ScrewHeads.obj"))
# viewer.scene.add(screw_heads, facecolor=(0.6, 0.6, 0.6), show_lines=False)

debug_group = viewer.scene.add_group("debug")
for item in guide.debug:
    viewer.scene.add(item, parent=debug_group, linecolor=(1.0, 0.0, 0.0), linewidth=2)
for item in floor_model.debug:
    viewer.scene.add(item, parent=debug_group, linecolor=(0.0, 0.8, 0.2), linewidth=3)

# dowels_group = viewer.scene.add_group("dowels")
# for dowel in guide.make_dowels():
#     mesh = dowel.compute_mesh()
#     if dowel.transformation:
#         mesh = mesh.transformed(dowel.transformation)
#     viewer.scene.add(mesh, parent=dowels_group, facecolor=(0.2, 0.6, 1.0))

g_contacts = viewer.scene.add_group("contacts")
for contact in contacts:
    viewer.scene.add(contact.polygon, facecolor=Color.red(), linecolor=Color.red(), parent=g_contacts)

viewer.show()
