import pathlib

import compas
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.model import TFModel

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
                viewer.scene.add(element, name=element.name, parent=viewer_parent, color=(0.85, 0.85, 0.85))


viewer = Viewer()
add_tree(full_model.tree.root, None)
viewer.show()
