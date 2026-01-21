#! python3
# venv: tf
# r: compas, compas_model

"""
Read model.json and add geometry to Rhino canvas using compas_model's hierarchy.

The Model's tree structure naturally provides the layer organization.
Connectors are found via the interaction graph, not tree children.
"""

from pathlib import Path
from compas import json_load
from compas.geometry import Frame, Transformation
from compas.scene import Scene
from compas_rhino.layers import create_layers_from_paths
from compas_model.elements.group import Group

# Import compas_tf to register custom element types for JSON deserialization
import compas_tf
from compas_tf.joint_screw import ScrewElement
from compas_tf.joint_dowel import DowelElement
from compas_tf.joint_strip import AlignmentStripElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.joint_connector import ConnectorElement

# Connector types for identification
CONNECTOR_TYPES = (ScrewElement, DowelElement, AlignmentStripElement, SherpaXL120Element, ConnectorElement)


def is_connector(element):
    """Check if element is a connector type."""
    return isinstance(element, CONNECTOR_TYPES)


def get_element_connectors(model, element):
    """Get all connectors that interact with the given element from the interaction graph."""
    connectors = []
    for edge in model.graph.edges():
        u, v = edge
        a = model.graph.node_element(u)
        b = model.graph.node_element(v)

        if is_connector(a) and b is element:
            if a not in connectors:
                connectors.append(a)
        elif is_connector(b) and a is element:
            if b not in connectors:
                connectors.append(b)

    return connectors

MODEL_FILEPATH = Path(r"C:\brg\code_python\compas_tf\examples\model.json")


def get_layer_path(element, model):
    """Build layer path from element's position in model tree.

    Traverses up the tree to build a path like:
    "quarters::quarter_0::axis_elements::axis_0"
    """
    path_parts = []
    current = element

    while current is not None:
        if current.name:
            path_parts.append(current.name)
        current = current.parent

    # Reverse to get root-to-leaf order, skip "root"
    path_parts = list(reversed(path_parts))
    if path_parts and path_parts[0] == "root":
        path_parts = path_parts[1:]

    return "::".join(path_parts) if path_parts else "default"


def load_model_to_rhino(model_filepath):
    """Load model and add to Rhino with layer structure from model hierarchy."""

    # Load the model
    model = json_load(model_filepath)
    print(f"Loaded model: {model.name}")

    # Collect all layer paths (skip Group elements which have no geometry)
    layer_paths = set()
    for element in model.elements():
        if isinstance(element, Group):
            continue
        layer_path = get_layer_path(element, model)
        layer_paths.add(layer_path)

    # Create layers
    create_layers_from_paths(sorted(layer_paths))
    print(f"Created {len(layer_paths)} layers")

    # Create scene and add geometry
    scene = Scene()
    scene.clear()

    count = 0
    for element in model.elements():
        if isinstance(element, Group):
            continue
        geom = element.modelgeometry
        if geom is None:
            continue

        layer_path = get_layer_path(element, model)
        name = element.name or f"element_{count}"

        scene.add(geom, layer=layer_path, name=name)
        count += 1

    scene.draw()
    print(f"Added {count} objects to Rhino")

    return model


def collect_all_children(element):
    """Recursively collect all descendant elements (excluding Groups)."""
    children = []
    for child in element.children:
        if isinstance(child, Group):
            # Recurse into groups
            children.extend(collect_all_children(child))
        else:
            children.append(child)
            # Also get children of this element
            children.extend(collect_all_children(child))
    return children


def orient_element_to_xy(model, element_name):
    """Orient an element and all its connectors from base_frame to world XY.

    Collects:
    - Main element mesh
    - top_polyline and bottom_polyline if available
    - All connectors from interactions (not tree children)

    Parameters
    ----------
    model : Model
        The loaded compas_model Model.
    element_name : str
        Name of the element to orient.

    Returns
    -------
    dict
        Dictionary with categorized geometry:
        {
            "mesh": (name, transformed_mesh),
            "top_polyline": transformed_polyline or None,
            "bottom_polyline": transformed_polyline or None,
            "connectors": [(name, transformed_mesh), ...]
        }
    """
    # Find element by name
    element = model.find_element_with_name(element_name)
    if element is None:
        print(f"Element '{element_name}' not found")
        return None

    # Get base_frame
    if not hasattr(element, 'base_frame'):
        print(f"Element '{element_name}' has no base_frame")
        return None

    base_frame = element.base_frame

    # Compute transformation to world XY
    xform = Transformation.from_frame_to_frame(base_frame, Frame.worldXY())

    result = {
        "mesh": None,
        "top_polyline": None,
        "bottom_polyline": None,
        "connectors": []
    }

    # Transform main element mesh
    geom = element.modelgeometry
    if geom:
        result["mesh"] = (element.name, geom.transformed(xform))

    # Transform polylines if available
    if hasattr(element, 'top_polyline') and element.top_polyline is not None:
        result["top_polyline"] = element.top_polyline.transformed(xform)

    if hasattr(element, 'bottom_polyline') and element.bottom_polyline is not None:
        result["bottom_polyline"] = element.bottom_polyline.transformed(xform)

    # Get connectors from interaction graph (not tree children)
    connectors = get_element_connectors(model, element)
    for connector in connectors:
        try:
            conn_geom = connector.modelgeometry
            if conn_geom:
                result["connectors"].append((connector.name, conn_geom.transformed(xform)))
        except NotImplementedError:
            continue

    print(f"Oriented '{element_name}' with {len(connectors)} connectors to world XY")
    return result


def orient_and_draw_to_rhino(model, element_name):
    """Orient element to XY and draw to Rhino with organized layers.

    Creates layers:
    - oriented::{element_name}::mesh
    - oriented::{element_name}::polylines
    - oriented::{element_name}::connectors
    """
    result = orient_element_to_xy(model, element_name)
    if not result:
        return

    base_layer = f"oriented::{element_name}"
    layers = [
        f"{base_layer}::mesh",
        f"{base_layer}::polylines",
        f"{base_layer}::connectors",
    ]
    create_layers_from_paths(layers)

    scene = Scene()

    # Add main mesh
    if result["mesh"]:
        name, mesh = result["mesh"]
        scene.add(mesh, layer=f"{base_layer}::mesh", name=name)

    # Add polylines
    if result["top_polyline"]:
        scene.add(result["top_polyline"], layer=f"{base_layer}::polylines", name="top_polyline")
    if result["bottom_polyline"]:
        scene.add(result["bottom_polyline"], layer=f"{base_layer}::polylines", name="bottom_polyline")

    # Add connectors
    for name, geom in result["connectors"]:
        scene.add(geom, layer=f"{base_layer}::connectors", name=name)

    scene.draw()
    print(f"Drew oriented '{element_name}' to Rhino")
    print(f"  - Mesh: {1 if result['mesh'] else 0}")
    print(f"  - Polylines: {int(result['top_polyline'] is not None) + int(result['bottom_polyline'] is not None)}")
    print(f"  - Connectors: {len(result['connectors'])}")


def list_elements(model):
    """Print all element names in the model for reference."""
    print("\nAvailable elements:")
    print("-" * 50)
    for element in model.elements():
        if isinstance(element, Group):
            continue
        layer_path = get_layer_path(element, model)
        print(f"  {element.name:20s} -> {layer_path}")
    print("-" * 50)


if __name__ == "__main__":
    if MODEL_FILEPATH.exists():
        # Load full model with hierarchy
        model = load_model_to_rhino(MODEL_FILEPATH)

        # =====================================================
        # EXAMPLE: Orient a specific element to world XY
        # =====================================================
        # Uncomment and modify the element name to orient:
        
        list_elements(model)  # Print all available element names
        
        orient_and_draw_to_rhino(model, "axis_0")      # A rib element
        # orient_and_draw_to_rhino(model, "surface_0")   # A surface element
        # orient_and_draw_to_rhino(model, "head")        # Column head
        # orient_and_draw_to_rhino(model, "edge_beam_0") # Edge beam
        
        # =====================================================

    else:
        print(f"File not found: {MODEL_FILEPATH}")
        print("Run model.py first to generate the model file.")
