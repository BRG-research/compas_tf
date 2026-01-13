from compas.geometry import Box
from compas.geometry import Line
from compas.geometry import Frame
from compas.geometry import Transformation
from compas.geometry import Translation
from compas_model.elements.column import ColumnElement
from compas_model.models import Model
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

from compas_tf.support import SupportElement

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

# Column Heads and Edge Beams
from compas_tf.floor_builder import FloorBuilder
from compas_tf.column_head import ColumnHeadElement
from compas_tf.edge_beam import EdgeBeamElement
from compas_tf.geometry import PlaneIntersect

# 1. Create builder (standalone, no FloorSkeleton dependency)
builder = FloorBuilder()
pts, pts_offset = builder.corner_points
# 2. Build column head elements
head_element, top_element = ColumnHeadElement.build(builder)
model.add_element(head_element)
model.add_element(top_element)

# 3. Build edge beam element (single - rotate yourself for others)
edge_beam = EdgeBeamElement.build(builder)
model.add_element(edge_beam)

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
    ColumnHeadElement: viewer.scene.add_group("column_head_group"),
    EdgeBeamElement: viewer.scene.add_group("edge_beam_group"),
}

for element in model.elements():
    groups[type(element)].add(element.modelgeometry, name=element.name, hide_coplanaredges=True)

for i in range(len(pts)):
    line = Line(pts[i], pts_offset[i])
    viewer.scene.add(line, color=(0, 0, 255), size=5)

for axis in builder.axes:
    viewer.scene.add(axis, color=(0, 255, 0), size=5)
    


for plane in builder.target_planes:
    viewer.scene.add(PlaneIntersect.plane_rectangle(plane)[0], color=(255, 0, 0), opacity=0.3)


viewer.show()