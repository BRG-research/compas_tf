import os
from compas.geometry import Box, Line, Frame, Transformation, Translation
from compas_model.elements.column import ColumnElement
from compas_model.elements.group import Group
from compas_model.models import Model
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

from compas_tf.support import SupportElement
from compas_tf.floor_builder import FloorBuilder
from compas_tf.column_head import ColumnHeadElement
from compas_tf.edge_beam import EdgeBeamElement
from compas_tf.quarter_floor import QuarterFloorElement
from compas_tf.oculus import OculusElement
from compas_tf.solid_difference_modifier import SolidDifferenceModifier
from compas_tf.plate import PlateElement
from compas_tf.joint_screw import ScrewElement
from compas_tf.joint_dowel import DowelElement
from compas_tf.joint_strip import AlignmentStripElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.joint_connector import ConnectorElement

# Connector types for identification
CONNECTOR_TYPES = (ScrewElement, DowelElement, AlignmentStripElement, SherpaXL120Element, ConnectorElement)

# Colors
ELEMENT_COLOR = (0.6, 0.6, 0.6)
CONNECTOR_COLOR = (0.8, 0.0, 0.2)
SUPPORT_COLOR = (0.9, 0.9, 0.9)
COLUMN_COLOR = (0.9, 0.9, 0.9)
COLUMN_HEAD_COLOR = (0.4, 0.4, 0.4)

# Color map by group name
COLOR_MAP = {
    "supports": SUPPORT_COLOR,
    "columns": COLUMN_COLOR,
    "column_heads": COLUMN_HEAD_COLOR,
    "connectors": CONNECTOR_COLOR,
}


def get_base_frame_from_obb(element) -> Frame:
    """Compute base_frame from element's OBB (for ColumnElement)."""
    mesh = element.modelgeometry
    obb = mesh.obb() if callable(mesh.obb) else mesh.obb
    obb_frame = obb.frame
    bottom_point = obb_frame.point - obb_frame.zaxis * (obb.zsize / 2)
    return Frame(bottom_point, obb_frame.xaxis, obb_frame.yaxis)


def frame_rectangle(frame, scale=100):
    """Create a rectangle polygon and normal line from a frame."""
    from compas.geometry import Polygon as GeomPolygon
    p0 = frame.point - frame.xaxis * scale - frame.yaxis * scale
    p1 = frame.point + frame.xaxis * scale - frame.yaxis * scale
    p2 = frame.point + frame.xaxis * scale + frame.yaxis * scale
    p3 = frame.point - frame.xaxis * scale + frame.yaxis * scale
    polygon = GeomPolygon([p0, p1, p2, p3])
    normal_line = Line(frame.point, frame.point + frame.zaxis * scale)
    return polygon, normal_line


def is_connector(element):
    """Check if element is a connector type."""
    return isinstance(element, CONNECTOR_TYPES)


def get_color_for_element(element):
    """Get color based on element's position in hierarchy."""
    # Check if element is a connector type
    if is_connector(element):
        return CONNECTOR_COLOR

    # Check parent chain for color mapping
    current = element.parent
    while current is not None:
        if current.name in COLOR_MAP:
            return COLOR_MAP[current.name]
        current = current.parent

    return ELEMENT_COLOR


def add_element_to_viewer(viewer, viewer_parent, element, color):
    """Add element geometry to viewer group with base frame visualization.

    Returns the created viewer group so children can be nested inside it.
    """
    mesh = element.modelgeometry
    if mesh is None:
        return None

    element_name = element.name or "element"
    element_group = viewer.scene.add_group(element_name, parent=viewer_parent)

    # Add mesh
    element_group.add(mesh, name="mesh", hide_coplanaredges=True, color=color)

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
    elif hasattr(element, 'base_frame'):
        base_frame = element.base_frame
    else:
        return element_group  # No base frame to visualize

    frame_polygon, frame_normal = frame_rectangle(base_frame, scale=50)
    frames_group = viewer.scene.add_group("base_frame", parent=element_group)
    frames_group.add(frame_polygon, name="frame_rect", facecolor=(0.2, 0.6, 0.9), opacity=0.5)
    frames_group.add(frame_normal, name="frame_normal", linewidth=2, linecolor=(0.9, 0.2, 0.2))

    return element_group


def build_element_connectors_map(model):
    """Build mapping from element to all connectors that interact with it.

    Uses the model's interaction graph to find all connectors for each element,
    not just tree children. This handles connectors that connect multiple elements.
    """
    element_connectors = {}

    # Iterate through all interaction edges in the graph
    for edge in model.graph.edges():
        u, v = edge
        a = model.graph.node_element(u)
        b = model.graph.node_element(v)

        # Determine which is the connector
        if is_connector(a) and not is_connector(b):
            connector, element = a, b
        elif is_connector(b) and not is_connector(a):
            connector, element = b, a
        else:
            # Both or neither are connectors - skip
            continue

        if element not in element_connectors:
            element_connectors[element] = []
        if connector not in element_connectors[element]:
            element_connectors[element].append(connector)

    return element_connectors


def add_model_to_viewer(model, viewer):
    """Traverse model tree and create viewer hierarchy."""

    # Build map of element -> all its connectors (from interactions)
    element_connectors = build_element_connectors_map(model)

    def traverse_element(element, viewer_parent):
        """Recursively traverse element children and add to viewer."""
        # element.children returns actual elements (not nodes)
        for child in element.children:
            if isinstance(child, Group):
                # Create viewer group for model groups
                child_group = viewer.scene.add_group(child.name or "group", parent=viewer_parent)
                traverse_element(child, child_group)
            else:
                # Add element geometry and get its viewer group
                color = get_color_for_element(child)
                child_viewer_group = add_element_to_viewer(viewer, viewer_parent, child, color)

                if child_viewer_group is not None:
                    # Add connectors from interactions (not just tree children)
                    if child in element_connectors:
                        connectors_group = viewer.scene.add_group("connectors", parent=child_viewer_group)
                        for connector in element_connectors[child]:
                            conn_color = get_color_for_element(connector)
                            add_element_to_viewer(viewer, connectors_group, connector, conn_color)

                    # Still recurse for any non-connector children (e.g., nested groups)
                    for grandchild in child.children:
                        if isinstance(grandchild, Group):
                            traverse_element(grandchild, child_viewer_group)

    # Traverse from root's direct children (top-level groups)
    # model.tree.root.children returns nodes, so access .element
    for node in model.tree.root.children:
        element = node.element
        if isinstance(element, Group):
            group = viewer.scene.add_group(element.name or "group")
            traverse_element(element, group)
        else:
            color = get_color_for_element(element)
            elem_group = add_element_to_viewer(viewer, viewer.scene, element, color)
            if elem_group is not None and element in element_connectors:
                connectors_group = viewer.scene.add_group("connectors", parent=elem_group)
                for connector in element_connectors[element]:
                    conn_color = get_color_for_element(connector)
                    add_element_to_viewer(viewer, connectors_group, connector, conn_color)


# Create a box representing one grid frame unit
frame_size = 240.0
grid_size = 6000.0
height = 3000.0
floor_thickness = 650.0
box = Box(frame_size+grid_size, frame_size+grid_size, height+floor_thickness, Frame([0,0,-(height+floor_thickness)*0.5]))

# Model with hierarchical groups
model = Model(name="Example Model")

# Create top-level groups (add_group adds to root)
supports_group = model.add_group("supports")
columns_group = model.add_group("columns")
column_heads_group = model.add_group("column_heads")
edge_beams_group = model.add_group("edge_beams")
quarters_group = model.add_group("quarters")
oculus_group = model.add_group("oculus")

# 1. Supports
for i, corner_id in enumerate(box.bottom):
    corner = box.corner(corner_id)
    frame = Frame(corner, [1, 0, 0], [0, 1, 0])
    xform = Transformation.from_frame(frame)
    support = SupportElement(xform)
    support.name = f"support_{i}"
    model.add_element(support, parent=supports_group)

# 2. Columns
columns = []
for i, corner_id in enumerate(box.bottom):
    corner = box.corner(corner_id)
    frame = Frame(corner, [1, 0, 0], [0, 1, 0])
    xform = Transformation.from_frame(frame) * Translation.from_vector([0, 0, SupportElement.HEIGHT])
    column = ColumnElement(frame_size, frame_size, height-SupportElement.HEIGHT, xform)
    column.name = f"column_{i}"
    model.add_element(column, parent=columns_group)
    columns.append(column)

# 3. Create builder for floor elements
builder = FloorBuilder(size=3000, height=650, rise=453, oculus=1000, thick=40, beam_w=frame_size, column_head_scale=460, column_head_inclination=180)
pts, pts_offset = builder.column_head_points

# 4. Build column head elements with nested groups
offset = builder.size + builder.beam_w * 0.5
xforms_columnhead = [
    Transformation.from_frame(Frame([-offset, -offset, 0], [1,0,0], [0,1,0])),
    Transformation.from_frame(Frame([offset, -offset, 0], [0,1,0], [-1,0,0])),
    Transformation.from_frame(Frame([offset, offset, 0], [-1,0,0], [0,-1,0])),
    Transformation.from_frame(Frame([-offset, offset, 0], [0,-1,0], [1,0,0])),
]

for i, xform in enumerate(xforms_columnhead):
    column = columns[i]

    # Create corner group (use Group directly for nested groups)
    corner_group = Group(name=f"corner_{i}")
    model.add_element(corner_group, parent=column_heads_group)

    # Build column head components
    head_element, top_element, connections, interactions, modifiers = ColumnHeadElement.build(builder, column_element=column)
    head_element.transformation = xform
    top_element.transformation = xform
    head_element.name = "head"
    top_element.name = "top"

    model.add_element(head_element, parent=corner_group)
    model.add_element(top_element, parent=corner_group)

    # Create connectors group and add connectors
    connectors_group = Group(name="connectors")
    model.add_element(connectors_group, parent=corner_group)

    for j, connector in enumerate(connections):
        connector.transformation = xform * connector.transformation
        connector.name = f"connector_{j}"
        model.add_element(connector, parent=connectors_group)

    # Add interactions (connector-element relationships)
    for connector, element in interactions:
        model.add_interaction(connector, element)

    # Add modifiers (boolean operations)
    for connector, element in modifiers:
        model.add_modifier(connector, element, SolidDifferenceModifier())


# 5. Build edge beam elements
xforms_beams = [
    Transformation.from_frame(Frame([0, -offset, 0], [1,0,0], [0,1,0])),
    Transformation.from_frame(Frame([offset, 0, 0], [0,1,0], [-1,0,0])),
    Transformation.from_frame(Frame([0, offset, 0], [-1,0,0], [0,-1,0])),
    Transformation.from_frame(Frame([-offset, 0, 0], [0,-1,0], [1,0,0])),
]

for i, xform in enumerate(xforms_beams):
    edge_beam = EdgeBeamElement.build(builder)
    edge_beam.transformation = xform
    edge_beam.name = f"edge_beam_{i}"
    model.add_element(edge_beam, parent=edge_beams_group)


# 6. Build quarter floor elements
for q_idx in range(4):
    quarter_result = QuarterFloorElement.build(builder, q_idx * 90)

    # Create quarter group (use Group directly for nested groups)
    quarter_group = Group(name=f"quarter_{q_idx}")
    model.add_element(quarter_group, parent=quarters_group)

    # Axis elements group
    axis_group = Group(name="axis_elements")
    model.add_element(axis_group, parent=quarter_group)
    for axis_idx, element in quarter_result.axis_elements.items():
        element.name = f"axis_{axis_idx}"
        model.add_element(element, parent=axis_group)

    # T-sections group
    tsections_group = Group(name="tsections")
    model.add_element(tsections_group, parent=quarter_group)
    for i, element in enumerate(quarter_result.tsection_elements):
        element.name = f"tsection_{i}"
        model.add_element(element, parent=tsections_group)

    # Surface elements group
    surfaces_group = Group(name="surfaces")
    model.add_element(surfaces_group, parent=quarter_group)
    for i, element in enumerate(quarter_result.surface_elements):
        element.name = f"surface_{i}"
        model.add_element(element, parent=surfaces_group)

    # Build element -> connectors mapping from interactions
    # A connector may interact with multiple elements, so pick the first as parent
    connector_parent = {}  # connector -> first element it interacts with
    for connector, element in quarter_result.interactions:
        if connector not in connector_parent:
            connector_parent[connector] = element

    # Add connectors as children of their first interacting element
    connector_idx = 0
    for connector, parent_element in connector_parent.items():
        connector.name = f"connector_{connector_idx}"
        model.add_element(connector, parent=parent_element)
        connector_idx += 1

    # Add interactions
    for connector, element in quarter_result.interactions:
        model.add_interaction(connector, element)


# 7. Build oculus element
oculus_result = OculusElement.build(builder)

# Elements group for oculus (use Group directly for nested groups)
elements_group = Group(name="elements")
model.add_element(elements_group, parent=oculus_group)
for i, element in enumerate(oculus_result.oculus_elements):
    element.name = f"oculus_{i}"
    model.add_element(element, parent=elements_group)

# Build element -> connectors mapping from interactions
# A connector may interact with multiple elements, so pick the first as parent
connector_parent = {}
for connector, element in oculus_result.interactions:
    if connector not in connector_parent:
        connector_parent[connector] = element

# Add connectors as children of their first interacting element
connector_idx = 0
for connector, parent_element in connector_parent.items():
    connector.name = f"connector_{connector_idx}"
    model.add_element(connector, parent=parent_element)
    connector_idx += 1

# Add interactions
for connector, element in oculus_result.interactions:
    model.add_interaction(connector, element)


# View model
config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "ghosted"

# Add model to viewer using hierarchy traversal
add_model_to_viewer(model, viewer)

# Export the compas_model Model (preserves full hierarchy)
from compas import json_dumps

model_filepath = os.path.join(os.path.dirname(__file__), "model.json")
with open(model_filepath, "w") as f:
    f.write(json_dumps(model, pretty=True))
print(f"Exported Model to {model_filepath}")

viewer.show()
