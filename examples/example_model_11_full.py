"""example_model_11_full.py

The full model: merge the cantilever model (floor + columns + connectors, from
example_model_8) with the shoring model (props + tower, from example_model_10)
into one ``full_model``. Each input keeps its own top-level group in the tree.
"""

import pathlib

import compas
from compas_model.elements import Group
from compas_model.models import Model

from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the cantilever model (example_model_8) and the shoring model
# (example_model_10).
# ------------------------------------------------------------------ #

cantilever_model: Model = compas.json_load(data_dir / "cantilever_model.json")
shoring_model: Model = compas.json_load(data_dir / "shoring_model.json")

# ------------------------------------------------------------------ #
# Merge into one model. merge() nests each input under its own top-level group,
# named after it ("cantilever_model" / "shoring_model").
# ------------------------------------------------------------------ #

full_model = Model(name="full_model").merge([cantilever_model, shoring_model])
print(f"full_model: {sum(1 for _ in full_model.elements())} elements")

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(full_model, data_dir / "full_model.json")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #


def add_tree(node, viewer_parent):
    """Mirror the model tree into the viewer, preserving the group hierarchy."""
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer_parent.add_group(element.name))
        else:
            mesh = element.modelgeometry
            if mesh is not None:
                viewer_parent.add(triangulated(mesh), name=element.name, hide_coplanaredges=True, color=(0.85, 0.85, 0.85))


viewer = make_viewer(data_dir)
add_tree(full_model.tree.root, viewer.scene)
viewer.show()
