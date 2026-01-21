import os
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
import math
from compas.geometry import Rotation
from compas.files import OBJ
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
from compas_tf.joint_screw import ScrewElement
from compas_tf.joint_connector import ConnectorElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.joint_dowel import DowelElement
from compas_tf.joint_strip import AlignmentStripElement
from compas_tf.solid_difference_modifier import SolidDifferenceModifier
from compas_tf.plate import PlateElement

# Create a box representing one grid frame unit
frame_size = 220.0
grid_size = 6000.0
height = 3000.0
floor_thickness = 650.0
box = Box(frame_size+grid_size, frame_size+grid_size, height+floor_thickness, Frame([0,0,-(height+floor_thickness)*0.5]))

# Model
model = Model(name="Example Model")

# Store viewer data for hierarchical grouping
viewer_data = {
    "supports": [],
    "columns": [],
    "column_heads": [],  # list of dicts with head, top, and their connectors
    "edge_beams": [],
    "quarters": [],  # list of dicts with elements and their connectors
    "oculus": None,  # dict with elements and their connectors
}

# Supports
for corner_id in box.bottom:
    corner = box.corner(corner_id)
    frame = Frame(corner, [1, 0, 0], [0, 1, 0])
    xform = Transformation.from_frame(frame)
    support = SupportElement(xform)
    model.add_element(support)
    viewer_data["supports"].append(support)

# Columns
for corner_id in box.bottom:
    corner = box.corner(corner_id)
    frame = Frame(corner, [1, 0, 0], [0, 1, 0])
    xform = Transformation.from_frame(frame) * Translation.from_vector([0, 0, SupportElement.HEIGHT])
    column = ColumnElement(frame_size, frame_size, height-SupportElement.HEIGHT, xform)
    model.add_element(column)
    viewer_data["columns"].append(column)

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

for i, xform in enumerate(xforms_columnhead):
    column = viewer_data["columns"][i]
    head_element, top_element, connections, interactions, modifiers = ColumnHeadElement.build(builder, column_element=column)
    head_element.transformation = xform
    top_element.transformation = xform
    model.add_element(head_element)
    model.add_element(top_element)

    for connector in connections:
        connector.transformation = xform * connector.transformation
        model.add_element(connector)

    # Add interactions (connector-element relationships)
    for connector, element in interactions:
        model.add_interaction(connector, element)

    # Add modifiers (boolean operations)
    for connector, element in modifiers:
        model.add_modifier(connector, element, SolidDifferenceModifier())

    # Store for viewer grouping - build element->connectors mapping
    head_connectors = []
    top_connectors = []
    column_connectors = []
    for connector, element in interactions:
        if element is head_element:
            head_connectors.append(connector)
        elif element is top_element:
            top_connectors.append(connector)
        elif element is column:
            column_connectors.append(connector)

    viewer_data["column_heads"].append({
        "head": head_element,
        "head_connectors": head_connectors,
        "top": top_element,
        "top_connectors": top_connectors,
        "column": column,
        "column_connectors": column_connectors,
    })
        


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
    viewer_data["edge_beams"].append(edge_beam)


# 4. Build quarter floor elements and add to model
# Todo: check if you can get minimal info: outlines, central axis, baseplanes, orient to 2d to verify
# Todo: check boolean difference and update issue on github cgal

for i in range(4):
    quarter_result = QuarterFloorElement.build(builder, i*90)

    # Add main elements (axis_elements is a dict keyed by axis index: 0,1,2,3,4,5,6,7)
    for element in quarter_result.axis_elements.values():
        model.add_element(element)
    for element in quarter_result.tsection_elements:
        model.add_element(element)
    for element in quarter_result.surface_elements:
        model.add_element(element)

    # Add connectors
    for screw in quarter_result.screws:
        model.add_element(screw)
    for dowel in quarter_result.dowels:
        model.add_element(dowel)
    for strip in quarter_result.strips:
        model.add_element(strip)

    # Build element->connectors mapping for viewer
    def build_connector_map(elements, interactions):
        """Build mapping from element to its connectors."""
        element_connectors = {e: [] for e in elements}
        for connector, element in interactions:
            if element in element_connectors:
                element_connectors[element].append(connector)
        return element_connectors

    all_elements = (
        list(quarter_result.axis_elements.values()) +
        quarter_result.tsection_elements +
        quarter_result.surface_elements
    )
    connector_map = build_connector_map(all_elements, quarter_result.interactions)

    viewer_data["quarters"].append({
        "axis_elements": [(axis_idx, e, connector_map[e]) for axis_idx, e in quarter_result.axis_elements.items()],
        "tsections": [(e, connector_map[e]) for e in quarter_result.tsection_elements],
        "surfaces": [(e, connector_map[e]) for e in quarter_result.surface_elements],
    })

    # Add interactions (connector-element relationships)
    for connector, element in quarter_result.interactions:
        model.add_interaction(connector, element)


# 5. Build oculus element
oculus_result = OculusElement.build(builder)

# Add main oculus elements
for element in oculus_result.oculus_elements:
    model.add_element(element)

# Add connectors
for screw in oculus_result.screws:
    model.add_element(screw)
for dowel in oculus_result.dowels:
    model.add_element(dowel)
for strip in oculus_result.strips:
    model.add_element(strip)

# Add interactions (connector-element relationships)
for connector, element in oculus_result.interactions:
    model.add_interaction(connector, element)

# Build element->connectors mapping for viewer
oculus_connector_map = {e: [] for e in oculus_result.oculus_elements}
for connector, element in oculus_result.interactions:
    if element in oculus_connector_map:
        oculus_connector_map[element].append(connector)

viewer_data["oculus"] = {
    "elements": [(e, oculus_connector_map[e]) for e in oculus_result.oculus_elements],
}



# View model

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "ghosted"  # "lighted", "wireframe", "shaded", "ghosted"

# Colors
ELEMENT_COLOR = (0.6, 0.6, 0.6)
CONNECTOR_COLOR = (0.8, 0.0, 0.2)
SUPPORT_COLOR = (0.9, 0.9, 0.9)
COLUMN_COLOR = (0.9, 0.9, 0.9)
COLUMN_HEAD_COLOR = (0.4, 0.4, 0.4)

def get_base_frame_from_obb(element) -> Frame:
    """Compute base_frame from element's OBB (for ColumnElement)."""
    mesh = element.modelgeometry
    obb = mesh.obb() if callable(mesh.obb) else mesh.obb
    obb_frame = obb.frame
    bottom_point = obb_frame.point - obb_frame.zaxis * (obb.zsize / 2)
    return Frame(bottom_point, obb_frame.xaxis, obb_frame.yaxis)


def frame_rectangle(frame, scale=100):
    """Create a rectangle polygon and normal line from a frame.

    Parameters
    ----------
    frame : :class:`compas.geometry.Frame`
        The frame to create rectangle on.
    scale : float
        Half-size of the rectangle.

    Returns
    -------
    tuple[:class:`compas.geometry.Polygon`, :class:`compas.geometry.Line`]
        Rectangle polygon and normal line.
    """
    from compas.geometry import Polygon as GeomPolygon
    p0 = frame.point - frame.xaxis * scale - frame.yaxis * scale
    p1 = frame.point + frame.xaxis * scale - frame.yaxis * scale
    p2 = frame.point + frame.xaxis * scale + frame.yaxis * scale
    p3 = frame.point - frame.xaxis * scale + frame.yaxis * scale
    polygon = GeomPolygon([p0, p1, p2, p3])
    normal_line = Line(frame.point, frame.point + frame.zaxis * scale)
    return polygon, normal_line


def add_element_with_connectors(parent_group, element, connectors, element_name, element_color=ELEMENT_COLOR):
    """Add an element and its connectors as a nested group structure."""
    # Create element group
    element_group = viewer.scene.add_group(element_name, parent=parent_group)

    # Add element mesh
    mesh = element.modelgeometry
    element_group.add(mesh, name="mesh", hide_coplanaredges=True, color=element_color)

    # Add top/bottom polylines for PlateElement, EdgeBeamElement
    if isinstance(element, (PlateElement, EdgeBeamElement)):
        if element.top_polyline is not None or element.bottom_polyline is not None:
            polylines_group = viewer.scene.add_group("polylines", parent=element_group)
            if element.top_polyline is not None:
                polylines_group.add(element.top_polyline, name="top_polyline", linewidth=2)
            if element.bottom_polyline is not None:
                polylines_group.add(element.bottom_polyline, name="bottom_polyline", linewidth=2)

    # Add base_frame visualization
    if isinstance(element, ColumnElement):
        base_frame = get_base_frame_from_obb(element)
    else:
        base_frame = element.base_frame

    frame_polygon, frame_normal = frame_rectangle(base_frame, scale=50)
    frames_group = viewer.scene.add_group("base_frame", parent=element_group)
    frames_group.add(frame_polygon, name="frame_rect", facecolor=(0.2, 0.6, 0.9), opacity=0.5)
    frames_group.add(frame_normal, name="frame_normal", linewidth=2, linecolor=(0.9, 0.2, 0.2))

    # Add connectors group if there are connectors
    if connectors:
        connectors_group = viewer.scene.add_group("connectors", parent=element_group)
        for i, connector in enumerate(connectors):
            connector_mesh = connector.modelgeometry
            connector_name = connector.name if connector.name else f"connector_{i}"
            connectors_group.add(connector_mesh, name=connector_name, hide_coplanaredges=True, color=CONNECTOR_COLOR)

    return element_group

# Collect all meshes for OBJ export
all_meshes = []

# 1. Supports group
supports_group = viewer.scene.add_group("supports")
for i, support in enumerate(viewer_data["supports"]):
    add_element_with_connectors(supports_group, support, [], f"support_{i}", SUPPORT_COLOR)
    all_meshes.append(support.modelgeometry)

# 2. Columns group (with connectors from column heads)
columns_group = viewer.scene.add_group("columns")
for i, column in enumerate(viewer_data["columns"]):
    # Get column connectors from the corresponding column head data
    column_connectors = viewer_data["column_heads"][i]["column_connectors"] if i < len(viewer_data["column_heads"]) else []
    add_element_with_connectors(columns_group, column, column_connectors, f"column_{i}", COLUMN_COLOR)
    all_meshes.append(column.modelgeometry)
    for c in column_connectors:
        all_meshes.append(c.modelgeometry)

# 3. Column heads group (with nested connectors)
column_heads_group = viewer.scene.add_group("column_heads")
for i, ch_data in enumerate(viewer_data["column_heads"]):
    corner_group = viewer.scene.add_group(f"corner_{i}", parent=column_heads_group)

    # Head element with connectors
    head_group = add_element_with_connectors(
        corner_group, ch_data["head"], ch_data["head_connectors"],
        "head", COLUMN_HEAD_COLOR
    )
    all_meshes.append(ch_data["head"].modelgeometry)
    for c in ch_data["head_connectors"]:
        all_meshes.append(c.modelgeometry)

    # Top element with connectors
    top_group = add_element_with_connectors(
        corner_group, ch_data["top"], ch_data["top_connectors"],
        "top", COLUMN_HEAD_COLOR
    )
    all_meshes.append(ch_data["top"].modelgeometry)
    for c in ch_data["top_connectors"]:
        all_meshes.append(c.modelgeometry)

# 4. Edge beams group
edge_beams_group = viewer.scene.add_group("edge_beams")
for i, edge_beam in enumerate(viewer_data["edge_beams"]):
    add_element_with_connectors(edge_beams_group, edge_beam, [], f"edge_beam_{i}", ELEMENT_COLOR)
    all_meshes.append(edge_beam.modelgeometry)

# 5. Quarters group (with nested element types and connectors)
quarters_group = viewer.scene.add_group("quarters")
for q_idx, quarter_data in enumerate(viewer_data["quarters"]):
    quarter_group = viewer.scene.add_group(f"quarter_{q_idx}", parent=quarters_group)

    # Axis elements (unified: ribs at 0,1,2,6 and boundaries at 3,4,5,7)
    axis_group = viewer.scene.add_group("axis_elements", parent=quarter_group)
    for axis_idx, element, connectors in quarter_data["axis_elements"]:
        add_element_with_connectors(axis_group, element, connectors, f"axis_{axis_idx}")
        all_meshes.append(element.modelgeometry)
        for c in connectors:
            all_meshes.append(c.modelgeometry)

    # T-sections
    tsections_group = viewer.scene.add_group("tsections", parent=quarter_group)
    for i, (element, connectors) in enumerate(quarter_data["tsections"]):
        add_element_with_connectors(tsections_group, element, connectors, f"tsection_{i}")
        all_meshes.append(element.modelgeometry)
        for c in connectors:
            all_meshes.append(c.modelgeometry)

    # Surfaces
    surfaces_group = viewer.scene.add_group("surfaces", parent=quarter_group)
    for i, (element, connectors) in enumerate(quarter_data["surfaces"]):
        add_element_with_connectors(surfaces_group, element, connectors, f"surface_{i}")
        all_meshes.append(element.modelgeometry)
        for c in connectors:
            all_meshes.append(c.modelgeometry)
    break

# 6. Oculus group (with nested connectors)
oculus_group = viewer.scene.add_group("oculus")
oculus_data = viewer_data["oculus"]
if oculus_data:
    for i, (element, connectors) in enumerate(oculus_data["elements"]):
        element_name = element.name if element.name else f"oculus_element_{i}"
        add_element_with_connectors(oculus_group, element, connectors, element_name)
        all_meshes.append(element.modelgeometry)
        for c in connectors:
            all_meshes.append(c.modelgeometry)

# Export all viewer meshes to a single OBJ file
obj_filepath = os.path.join(os.path.dirname(__file__), "model_export.obj")
obj = OBJ(obj_filepath)
obj.write(all_meshes)
print(f"Exported {len(all_meshes)} mesh(es) to {obj_filepath}")


viewer.show()