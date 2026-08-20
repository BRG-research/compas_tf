import pathlib

import compas
from compas.geometry import Translation
from compas_model.elements import Group
from compas_viewer import Viewer

from compas_tf.floor_guide import FloorGuide
from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the FloorGuide written by an earlier example
# ------------------------------------------------------------------ #

guide: FloorGuide = compas.json_load(data_dir / "floorguide.json")

# ------------------------------------------------------------------ #
# Build the oculus_model from the guide's oculus plates
# (4 boundary beams + bottom wedges + 1 inner plate)
# ------------------------------------------------------------------ #

oculus_model = TFModel(name="oculus_model")

group = oculus_model.add_group("oculus")
for i, plate in enumerate(guide.oculus):
    plate.name = f"oculus_{i}"
    oculus_model.add_element(plate, parent=group)

oculus_model.transformation = Translation.from_vector([0, 0, guide.bay_height])

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(oculus_model, data_dir / "oculus_model.json")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #

viewer = Viewer()
root_group = viewer.scene.add_group(oculus_model.name)


def add_tree(node, viewer_parent):
    """Mirror the model tree into the viewer (mesh-only), keeping the groups -
    so the three bed rows show up as their own groups in the scene tree."""
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer.scene.add_group(element.name, parent=viewer_parent))
        else:
            if element.modelgeometry is not None:
                viewer.scene.add(element, name=element.name, parent=viewer_parent, facecolor=(0.85, 0.85, 0.85))


add_tree(oculus_model.tree.root, root_group)
viewer.show()
