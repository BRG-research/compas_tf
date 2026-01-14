from compas.geometry import Box
from compas.geometry import Line
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Vector
from compas.geometry import Plane
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import intersection_polyline_plane
from compas_model.elements.column import ColumnElement
from compas_model.models import Model
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

# Column Heads and Edge Beams
from compas_tf.support import SupportElement
from compas_tf.floor_builder import FloorBuilder
from compas_tf.column_head import ColumnHeadElement
from compas_tf.edge_beam import EdgeBeamElement
from compas_tf.quarter_floor import QuarterFloorElement
from compas_tf.oculus import OculusElement
from compas_tf.geometry import PlaneIntersect

# Create a box representing one grid frame unit
frame_size = 220.0
grid_size = 6000.0
height = 3000.0
floor_thickness = 650.0
box = Box(frame_size+grid_size, frame_size+grid_size, height+floor_thickness, Frame([0,0,-(height+floor_thickness)*0.5]))

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

# 1. Create builder (standalone, no FloorSkeleton dependency)
builder = FloorBuilder(size=3000, height=650, rise=453, oculus=1000, thick=40, beam_w=frame_size, column_head_scale=460, column_head_inclination=180)
pts, pts_offset = builder.column_head_points

# 2. Build column head elements
offset = builder.size+builder.beam_w*0.5
xforms_columnhead = [
    Transformation.from_frame(Frame([-offset, -offset, 0],[1,0,0],[0,1,0])),
    Transformation.from_frame(Frame([offset, -offset, 0],[0,1,0],[-1,0,0])),
    Transformation.from_frame(Frame([offset, offset, 0],[-1,0,0],[0,-1,0])),
    Transformation.from_frame(Frame([-offset, offset, 0],[0,-1,0],[1,0,0])),
]

for xform in xforms_columnhead:
    head_element, top_element = ColumnHeadElement.build(builder)
    head_element.transformation = xform
    top_element.transformation = xform
    model.add_element(head_element)
    model.add_element(top_element)


# 3. Build edge beam element (single - rotate yourself for others)

xforms_beams = [
    Transformation.from_frame(Frame([0, -offset, 0],[1,0,0],[0,1,0])),
    Transformation.from_frame(Frame([offset, 0, 0],[0,1,0],[-1,0,0])),
    Transformation.from_frame(Frame([0, offset, 0],[-1,0,0],[0,-1,0])),
    Transformation.from_frame(Frame([-offset, 0, 0],[0,-1,0],[1,0,0])),
]

for xform in xforms_beams:
    edge_beam = EdgeBeamElement.build(builder)
    edge_beam.transformation = xform
    model.add_element(edge_beam)


# 4. Build quarter floor elements and add to model
quarter_result = QuarterFloorElement.build(builder)

for element in quarter_result.rib_elements:
    model.add_element(element)
for element in quarter_result.tsection_elements:
    model.add_element(element)
for element in quarter_result.surface_elements:
    model.add_element(element)
for element in quarter_result.boundary_beam_elements:
    model.add_element(element)


# 5. Build oculus element
oculus_element = OculusElement.build(builder)
model.add_element(oculus_element)


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
    QuarterFloorElement: viewer.scene.add_group("quarter_floor_group"),
    OculusElement: viewer.scene.add_group("oculus_group"),
}

colors = {
    SupportElement: (0.9, 0.9, 0.9),
    ColumnElement: (0.9, 0.9, 0.9),
    ColumnHeadElement: (0.4, 0.4, 0.4),
    EdgeBeamElement: (0.9, 0.9, 0.9),
    QuarterFloorElement: (0.6, 0.6, 0.6),
    OculusElement: (0.9, 0.9, 0.9),
}

for element in model.elements():
    groups[type(element)].add(element.modelgeometry, name=element.name, hide_coplanaredges=True, color=colors[type(element)])


polygon, line = PlaneIntersect.plane_rectangle(builder.cut_planes[0])
# viewer.scene.add(polygon, name="cut_plane")
# viewer.scene.add(line, name="cut_plane")    
parabola = builder.rib_parabolas[0]
parabola = builder.rib_parabolas[0]  # First boundary parabola
cut_plane = builder.cut_planes[3]  # First cut plane
result = intersection_polyline_plane(parabola,cut_plane, 1)
viewer.scene.add(parabola, name="rib_parabola")
viewer.scene.add(Point(*result[0]), name="rib_parabola")

# for plane in builder.end_planes:
#     polygon, line = PlaneIntersect.plane_rectangle(plane)
#     viewer.scene.add(polygon, name="end_plane")
#     viewer.scene.add(line, name="end_plane")

# print(builder.top_end_planes)
# for plane in builder.top_end_planes:
#     polygon, line = PlaneIntersect.plane_rectangle(plane)
#     viewer.scene.add(polygon, name="end_plane")
#     viewer.scene.add(line, name="end_plane")




# polygon, line = PlaneIntersect.plane_rectangle(builder.end_diagonal_plane)
# # polygon, line = PlaneIntersect.plane_rectangle(Plane(builder.end_planes[1].point, builder.cut_planes[1].normal).offset(-30))
# viewer.scene.add(polygon, name="end_diagonal_plane")
# viewer.scene.add(line, name="end_diagonal_plane")

viewer.show()