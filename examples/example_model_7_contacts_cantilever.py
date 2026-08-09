import pathlib

import compas
from compas_model.elements import Group

from compas_tf.model import TFModel
from compas_tf.floor_guide import FloorGuide
from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the FloorGuide written by an earlier example
# ------------------------------------------------------------------ #

guide: FloorGuide = compas.json_load(data_dir / "floorguide.json")
quarter_model: TFModel = compas.json_load(data_dir / "quarter_model.json")
column_model: TFModel = compas.json_load(data_dir / "column_model.json")

# ------------------------------------------------------------------ #
# Interactions between quarters and oculus models
# ------------------------------------------------------------------ #
cantilever_model = TFModel(name="floor_model").merge([quarter_model, column_model])

# ------------------------------------------------------------------ #
# Compute contacts between individual groups
# ------------------------------------------------------------------ #

cantilever_model.compute_contacts_between_groups(
    [
        "quarter_model",
        "column_model",
    ]
)
print(f"contacts between groups: {sum(1 for _ in cantilever_model.contacts())}")

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(cantilever_model, data_dir / "cantilever_model.json")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #


def add_tree(node, viewer_parent):
    """Mirror the model tree into the viewer, preserving the group hierarchy so
    quarters_model / oculus_model (and their subgroups) show up as their own
    groups in the scene tree instead of one flat list."""
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer_parent.add_group(element.name))
        else:
            mesh = element.modelgeometry
            if mesh is not None:
                viewer_parent.add(triangulated(mesh), name=element.name, hide_coplanaredges=True, color=(0.85, 0.85, 0.85))


viewer = make_viewer(data_dir)
add_tree(cantilever_model.tree.root, viewer.scene)

contacts_group = viewer.scene.add_group("contacts")
for i, contact in enumerate(cantilever_model.contacts()):
    contacts_group.add(contact.polygon, name=f"contact_{i}", color=(1.0, 0.0, 0.0))

viewer.show()
