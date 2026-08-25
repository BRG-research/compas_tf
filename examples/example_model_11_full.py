import pathlib

import compas
from compas.colors import Color
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.viewer import human_figure

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the cantilever model (example_model_8) and the shoring model
# (example_model_10).
# ------------------------------------------------------------------ #

cantilever_model: TFModel = compas.json_load(data_dir / "cantilever_model.json")
shoring_model: TFModel = compas.json_load(data_dir / "shoring_model.json")

# ------------------------------------------------------------------ #
# Merge into one model. merge() nests each input under its own top-level group,
# named after it ("cantilever_model" / "shoring_model").
# ------------------------------------------------------------------ #

full_model = TFModel(name="full_model").merge([cantilever_model, shoring_model])
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
            add_tree(child, viewer.scene.add_group(element.name, parent=viewer_parent))
        else:
            if element.modelgeometry is not None:
                viewer.scene.add(element, name=element.name, parent=viewer_parent, facecolor=(0.85, 0.85, 0.85))


viewer = Viewer()
add_tree(full_model.tree.root, None)

# A 1.75 m figure, for reading the scale of the model at a glance. Reference
# geometry only - plain polylines, never added to the model itself.
for _part in human_figure(point=[3600, 0, 0]):
    viewer.scene.add(_part, name="scale_figure", linecolor=Color(0.35, 0.35, 0.35), linewidth=2)

viewer.show()
