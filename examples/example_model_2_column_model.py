import pathlib

import compas
from compas.geometry import Frame  # noqa: F401
from compas.geometry import Transformation  # noqa: F401
from compas.geometry import Translation
from compas_viewer import Viewer

from compas_tf.column import ColumnElement
from compas_tf.floor_guide import FloorGuide
from compas_tf.model import TFModel
from compas_tf.support import SupportElement

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
# Deserialize the FloorGuide written by an earlier example
# ------------------------------------------------------------------ #

guide: FloorGuide = compas.json_load(data_dir / "floorguide.json")

# ------------------------------------------------------------------ #
# Create a column_model
# One support, one L-shaped column
# ------------------------------------------------------------------ #

column_model = TFModel(name="column_model")


support = SupportElement(name="support")

column = ColumnElement(
    width=guide.size_column_head,
    depth=guide.size_column_head,
    height=guide.bay_height - SupportElement.HEIGHT,
    transformation=Translation.from_vector([0, 0, SupportElement.HEIGHT]),
    capitel_width=guide.size_column_head_chamfer,
    capitel_height=abs(guide.column_head_lowest_height),  # guide value is negative (a z-level)
    name="column",
)

# ------------------------------------------------------------------ #
# Carve the column head with the guide's cutters, stored as a feature on the
# column (serialized and copied with it, available for fabrication).
# ------------------------------------------------------------------ #
column.add_cutters(guide.column_cutters_for(column.height))

column_model.add_element(support)
column_model.add_element(column)
column_model.add_interaction(support, column)

# ------------------------------------------------------------------ #
#  TFModel can be transformed
# ------------------------------------------------------------------ #
translation = Translation.from_vector(guide.corner_point_column(guide.size_column_head))
column_model.transformation = translation
# column_model.transformation = Transformation.from_frame_to_frame(Frame.worldXY(),Frame.worldYZ())

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump(column_model, data_dir / "column_model.json")

# ------------------------------------------------------------------ #
#  View
# ------------------------------------------------------------------ #

viewer = Viewer()
group = viewer.scene.add_group("column_model")
group.add(support, name="support", color=(0.9, 0.9, 0.9))
group.add(column, name="column", color=(0.9, 0.9, 0.9))
viewer.show()
