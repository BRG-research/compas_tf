from compas.geometry import Box
from compas_model.models import Model
from compas_tf.support import SupportElement
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Frame
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer
from compas_model.elements.column import ColumnElement


# Create a box representing one grid frame unit
frame_size = 200.0
grid_size = 6000.0
height = 3000.0
floor_thickness = 650.0
box = Box(frame_size+grid_size, frame_size+grid_size, height+floor_thickness)

# Model
model = Model(name="Example Model")

# Supports
for corner_id in box.bottom:
    corner = box.corner(corner_id)
    frame = Frame(corner, [1, 0, 0], [0, 1, 0])
    xform = Transformation.from_frame(frame)
    support = SupportElement(xform)
    model.add_element(support)

# Columns
for corner_id in box.bottom:
    corner = box.corner(corner_id)
    frame = Frame(corner, [1, 0, 0], [0, 1, 0])
    xform = Transformation.from_frame(frame) * Translation.from_vector([0, 0, SupportElement.HEIGHT])
    support = ColumnElement(frame_size, frame_size, height-SupportElement.HEIGHT, xform)
    model.add_element(support)

# Column Heads

# Beams

# Floor

# View model

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"  # "lighted", "wireframe", "shaded", "ghosted"

groups = {
      SupportElement: viewer.scene.add_group("support_group"),
      ColumnElement: viewer.scene.add_group("column_group"),
    #   BeamElement: viewer.scene.add_group("beam_group"),
    #   ColumnHeadElement: viewer.scene.add_group("column_head_group"),
    #   FloorElement: viewer.scene.add_group("floor_group"),
  }

for element in model.elements():
    groups[type(element)].add(element.modelgeometry, name=element.name)

viewer.show()