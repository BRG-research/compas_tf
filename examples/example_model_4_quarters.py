import math
import pathlib

import compas
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_model.elements import Group
from compas_model.models import Model

from compas_tf.floor_guide import FloorGuide
from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the FloorGuide written by an earlier example
# ------------------------------------------------------------------ #

guide: FloorGuide = compas.json_load(data_dir / "floorguide.json")

# ------------------------------------------------------------------ #
# Build one quarter_model from the guide's plate groups
# (the oculus is its own model - see example_model_5)
# ------------------------------------------------------------------ #

quarter_model = Model(name="quarter_model")

plate_sections = [
    ("beds", guide.beds),
    ("tsections", guide.tsections),
    ("outer_ribs", guide.outer_ribs),
    ("inner_ribs", guide.inner_ribs),
    ("wedges_inner_beams", guide.wedges_inner_beams),
    ("inner_beams", guide.inner_beams),
]
for group_name, plates in plate_sections:
    group = quarter_model.add_group(group_name)
    # The beds come as three rows (each plate tagged with plate.bed_row); give
    # every row its own subgroup. The other sections are flat.
    if plates and hasattr(plates[0], "bed_row"):
        rows = {}
        for plate in plates:
            rows.setdefault(plate.bed_row, []).append(plate)
        for row_index in sorted(rows):
            rowgroup = quarter_model.add_element(Group(name=f"{group_name}_{row_index}"), parent=group)
            for i, plate in enumerate(rows[row_index]):
                plate.name = f"{group_name}_{row_index}_{i}"
                quarter_model.add_element(plate, parent=rowgroup)
    else:
        for i, plate in enumerate(plates):
            plate.name = f"{group_name}_{i}"
            quarter_model.add_element(plate, parent=group)

quarter_model.transformation = Translation.from_vector([0, 0, guide.bay_height])

# ------------------------------------------------------------------ #
# Create a quarters_model by rotating the quarter four times
# ------------------------------------------------------------------ #

quarter_models = []
for i in range(4):
    copy = quarter_model.duplicate()  # independent copy (new guids) so the 4 can merge
    copy.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0)) * copy.transformation
    # Change names
    copy.name = f"quarter_model_{i}"
    for element in copy.elements():
        element.name = f"{element.name}_{i}"

    quarter_models.append(copy)

quarters_model = Model(name="quarters_model").merge(quarter_models)
print(quarters_model)
# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(quarter_model, data_dir / "quarter_model.json")
compas.json_dump(quarters_model, data_dir / "quarters_model.json")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #

viewer = make_viewer(data_dir)
root_group = viewer.scene.add_group(quarters_model.name)


def add_tree(node, viewer_parent):
    """Mirror the model tree into the viewer (mesh-only), keeping the groups -
    so the three bed rows show up as their own groups in the scene tree."""
    for child in node.children:
        element = child.element
        if isinstance(element, Group):
            add_tree(child, viewer_parent.add_group(element.name))
        else:
            mesh = element.modelgeometry
            if mesh is not None:
                viewer_parent.add(triangulated(mesh), name=element.name, hide_coplanaredges=True, color=(0.85, 0.85, 0.85))


add_tree(quarters_model.tree.root, root_group)
viewer.show()
