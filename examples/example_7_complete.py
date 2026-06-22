"""example_5_complete.py
#! python3
# r: compas, compas_cgal, compas_model, shapely
import pathlib
import sys
sys.path.insert(0, r"C:\brg\code_python\compas_tf\src")

import compas_tf  # surface real import error before json_load swallows it
import compas
import scriptcontext as sc
import rhinoscriptsyntax as rs
from compas_rhino.conversions import mesh_to_rhino
from compas_model.elements.group import Group

data_dir = pathlib.Path(r"C:\brg\code_python\compas_tf\data")

floor_model = compas.json_load(data_dir / "floor_model_booleans.json")
schoring_models = compas.json_load(data_dir / "schoring_models.json")


def get_or_create_layer(name, parent=None):
    full = f"{parent}::{name}" if parent else name
    idx = sc.doc.Layers.FindByFullPath(full, -1)
    if idx < 0:
        layer = sc.doc.Layers.FindByFullPath(parent, -1) if parent else -1
        new_layer = Rhino.DocObjects.Layer()
        new_layer.Name = name
        if layer >= 0:
            new_layer.ParentLayerId = sc.doc.Layers[layer].Id
        idx = sc.doc.Layers.Add(new_layer)
    return idx


def add_elements(element, layer_idx):
    if isinstance(element, Group):
        for child in element.children:
            add_elements(child, layer_idx)
        return
    mesh = element.modelgeometry
    if mesh is None:
        return
    rh_mesh = mesh_to_rhino(mesh)
    attr = sc.doc.CreateDefaultAttributes()
    attr.LayerIndex = layer_idx
    sc.doc.Objects.AddMesh(rh_mesh, attr)


import Rhino

rs.AddLayer("FloorModel")
floor_layer = sc.doc.Layers.FindByFullPath("FloorModel", -1)
for node in floor_model.tree.root.children:
    add_elements(node.element, floor_layer)

rs.AddLayer("Schoring")
schoring_layer = sc.doc.Layers.FindByFullPath("Schoring", -1)
for model in schoring_models:
    for node in model.tree.root.children:
        add_elements(node.element, schoring_layer)

sc.doc.Views.Redraw()
print("Done.")

"""

import pathlib

import compas
from compas_model.elements import Group

import compas_tf  # noqa: F401 — required for deserialization of TF types
from compas_tf.viewer import make_viewer

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Load models
# ------------------------------------------------------------------ #

floor_model = compas.json_load(data_dir / "floor_model_booleans.json")
schoring_models = compas.json_load(data_dir / "schoring_models.json")

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

viewer = make_viewer(data_dir)
g_floor = viewer.scene.add_group("floor_model")
for element in floor_model.elements():
    if isinstance(element, Group):
        continue
    mesh = element.modelgeometry
    if mesh is not None:
        g_floor.add(mesh, name=element.name, hide_coplanaredges=True, color=(0.6, 0.6, 0.6))
for model in schoring_models:
    g = viewer.scene.add_group(model.name or "model")
    for element in model.elements():
        if isinstance(element, Group):
            continue
        mesh = element.modelgeometry
        if mesh is not None:
            g.add(mesh, name=element.name, hide_coplanaredges=True, color=(0.6, 0.6, 0.6))
viewer.show()
