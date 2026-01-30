#! python3
# venv: tf
# r: compas, compas_model, compas_cgal

"""
Read model.json and add geometry to Rhino canvas using compas_model's hierarchy.

The Model's tree structure naturally provides the layer organization.
Connectors are found via the interaction graph, not tree children.
"""

from pathlib import Path
from compas import json_load
from compas.colors import Color
from compas.datastructures import Mesh
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
from compas_tf.solid_difference_modifier import SolidDifferenceModifier

# Connector types for identification
CONNECTOR_TYPES = (ScrewElement, DowelElement, AlignmentStripElement, SherpaXL120Element)

# Colors for different connector types (RGB tuples 0-255)
CONNECTOR_COLORS = {
    ScrewElement: (255, 0, 0),          # Red - screws
    DowelElement: (0, 0, 255),          # Blue - dowels
    AlignmentStripElement: (0, 255, 0), # Green - strips
    SherpaXL120Element: (255, 165, 0),  # Orange - sherpa connectors
}


def get_connector_color(element):
    """Get color for a connector element based on its type."""
    for connector_type, color in CONNECTOR_COLORS.items():
        if isinstance(element, connector_type):
            return color
    return (128, 128, 128)  # Gray default


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


def get_element_geometry_with_cuts(element, connectors):
    """Get element geometry with boolean cuts from connectors applied.

    Parameters
    ----------
    element : Element
        The element to get geometry for.
    connectors : list
        List of connectors that interact with this element.

    Returns
    -------
    Mesh or geometry
        The element geometry with cuts applied, or original if no cuts needed.
    """
    geom = element.modelgeometry
    if geom is None:
        return None

    # Apply boolean difference for each connector (modifier skips non-mesh)
    modifier = SolidDifferenceModifier()
    for connector in connectors:
        geom = modifier.apply(connector, geom)

    return geom

MODEL_FILEPATH = Path(r"C:\brg\code_python\compas_tf\examples\model.json")


def convert_meshes_to_breps(guids, merge_coplanar=True, tolerance=None):
    """Convert mesh GUIDs to NURBS breps with merged coplanar faces.

    Equivalent to running MeshToNURB + MergeAllCoplanarFaces in Rhino.

    Parameters
    ----------
    guids : list
        List of Rhino object GUIDs (meshes will be converted, others kept as-is).
    merge_coplanar : bool
        If True, merge coplanar faces after conversion.
    tolerance : float, optional
        Tolerance for merging coplanar faces. Defaults to document tolerance.

    Returns
    -------
    list
        New GUIDs (breps replacing meshes, original GUIDs for non-meshes).
    """
    import Rhino
    import Rhino.Geometry as rg
    import scriptcontext as sc

    if tolerance is None:
        tolerance = sc.doc.ModelAbsoluteTolerance

    new_guids = []

    for guid in guids:
        obj = sc.doc.Objects.FindId(guid)
        if obj is None:
            continue

        # Check if it's a mesh
        if obj.ObjectType == Rhino.DocObjects.ObjectType.Mesh:
            mesh = obj.Geometry
            # Convert mesh to brep (each mesh face becomes a NURBS surface)
            brep = rg.Brep.CreateFromMesh(mesh, trimmedTriangles=True)

            if brep and brep.IsValid:
                # Merge coplanar faces
                if merge_coplanar:
                    brep.MergeCoplanarFaces(tolerance)

                # Copy attributes (layer, color, name, etc.)
                attributes = obj.Attributes.Duplicate()

                # Delete old mesh and add new brep
                sc.doc.Objects.Delete(guid, quiet=True)
                new_guid = sc.doc.Objects.AddBrep(brep, attributes)

                if new_guid:
                    new_guids.append(new_guid)
            else:
                # Keep original if conversion failed
                new_guids.append(guid)
        else:
            # Not a mesh, keep as-is
            new_guids.append(guid)

    return new_guids


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


def load_model_to_rhino(model_filepath, create_groups=True, convert_to_brep=True):
    """Load model and add to Rhino with layer structure from model hierarchy.

    Uses element-centric approach: each element gets its own copies of connector
    geometry, ensuring groups are independent with no shared GUIDs.

    Parameters
    ----------
    model_filepath : Path
        Path to the model.json file.
    create_groups : bool
        If True, create Rhino groups for each element with its connectors.
    convert_to_brep : bool
        If True, convert meshes to NURBS breps and merge coplanar faces.
    """
    import rhinoscriptsyntax as rs
    import Rhino.Geometry as rg
    import scriptcontext as sc

    # Load the model
    model = json_load(model_filepath)
    print(f"Loaded model: {model.name}")

    # Build element -> connectors mapping from interaction graph
    # Store ALL non-connector elements, even those without connectors
    element_connectors = {}
    for element in model.elements():
        if isinstance(element, Group) or is_connector(element):
            continue
        connectors = get_element_connectors(model, element)
        element_connectors[element] = connectors  # Store even if empty

    # Collect layer paths for non-connector elements only
    layer_paths = set()
    for element in element_connectors.keys():
        layer_path = get_layer_path(element, model)
        layer_paths.add(layer_path)
        # Also add connector layer path as sublayer
        layer_paths.add(f"{layer_path}::connectors")

    # Create layers
    create_layers_from_paths(sorted(layer_paths))
    print(f"Created {len(layer_paths)} layers")

    scene = Scene()
    element_count = 0
    connector_count = 0

    # Track scene objects per element for grouping later
    element_scene_objects = {}  # element -> (group_name, [scene_objects])

    # Add all elements and their connectors to scene (single batch)
    for element, connectors in element_connectors.items():
        # Get geometry with boolean cuts from cutting connectors applied
        geom = get_element_geometry_with_cuts(element, connectors)
        if geom is None:
            continue

        layer_path = get_layer_path(element, model)
        name = element.name or f"element_{element_count}"

        scene_objects = []  # Track objects for this element's group

        # Add element geometry
        elem_obj = scene.add(geom, layer=layer_path, name=name)
        scene_objects.append(elem_obj)
        element_count += 1

        # Add connectors for THIS element (as separate copies)
        connector_layer = f"{layer_path}::connectors"
        for i, connector in enumerate(connectors):
            conn_geom = connector.modelgeometry
            if conn_geom is None:
                continue

            rgb = get_connector_color(connector)
            color = Color.from_rgb255(*rgb)
            conn_name = f"{name}_{connector.name or f'conn_{i}'}"

            conn_obj = scene.add(conn_geom, layer=connector_layer, name=conn_name, color=color)
            scene_objects.append(conn_obj)
            connector_count += 1

        # Use layer_path for unique group name (elements in different quarters have same name)
        group_name = layer_path.replace("::", "_") + "_group"
        element_scene_objects[element] = (group_name, scene_objects)

    # Single draw call for all geometry
    scene.draw()
    print(f"Added {element_count} elements, {connector_count} connector instances")

    # Convert meshes to breps and create groups (GUIDs are now available)
    group_count = 0
    brep_count = 0

    for element, (group_name, scene_objects) in element_scene_objects.items():
        guids = []
        for obj in scene_objects:
            if hasattr(obj, 'guids') and obj.guids:
                guids.extend(obj.guids)

        if not guids:
            continue

        # Convert meshes to breps with merged coplanar faces
        if convert_to_brep:
            original_count = len(guids)
            guids = convert_meshes_to_breps(guids, merge_coplanar=True)
            brep_count += original_count  # Count converted objects

        # Create groups with the (possibly converted) GUIDs
        if create_groups and guids:
            rs.AddGroup(group_name)
            rs.AddObjectsToGroup(guids, group_name)
            group_count += 1

    if convert_to_brep:
        print(f"Converted {brep_count} meshes to NURBS breps with merged coplanar faces")
    print(f"Created {group_count} groups")

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
            "connectors": [(name, transformed_geom, connector_element), ...]
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

    # Get connectors from interaction graph (needed for boolean cuts)
    connectors = get_element_connectors(model, element)

    result = {
        "mesh": None,
        "top_polyline": None,
        "bottom_polyline": None,
        "connectors": []
    }

    # Transform main element mesh (with boolean cuts applied)
    geom = get_element_geometry_with_cuts(element, connectors)
    if geom:
        result["mesh"] = (element.name, geom.transformed(xform))

    # Transform polylines if available
    if hasattr(element, 'top_polyline') and element.top_polyline is not None:
        result["top_polyline"] = element.top_polyline.transformed(xform)

    if hasattr(element, 'bottom_polyline') and element.bottom_polyline is not None:
        result["bottom_polyline"] = element.bottom_polyline.transformed(xform)

    # Add connectors
    for connector in connectors:
        try:
            conn_geom = connector.modelgeometry
            if conn_geom:
                result["connectors"].append((connector.name, conn_geom.transformed(xform), connector))
        except NotImplementedError:
            continue

    print(f"Oriented '{element_name}' with {len(connectors)} connectors to world XY")
    return result


def orient_and_draw_to_rhino(model, element_name, create_group=True, convert_to_brep=True):
    """Orient element to XY and draw to Rhino with organized layers.

    Creates layers:
    - oriented::{element_name}::mesh
    - oriented::{element_name}::polylines
    - oriented::{element_name}::connectors

    Parameters
    ----------
    model : Model
        The loaded compas_model Model.
    element_name : str
        Name of the element to orient.
    create_group : bool
        If True, create a Rhino group containing the element and its connectors.
    convert_to_brep : bool
        If True, convert meshes to NURBS breps and merge coplanar faces.
    """
    import rhinoscriptsyntax as rs

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
    scene_objects = []  # Track all scene objects for grouping

    # Add main mesh
    if result["mesh"]:
        name, mesh = result["mesh"]
        obj = scene.add(mesh, layer=f"{base_layer}::mesh", name=name)
        scene_objects.append(obj)

    # Add polylines
    if result["top_polyline"]:
        obj = scene.add(result["top_polyline"], layer=f"{base_layer}::polylines", name="top_polyline")
        scene_objects.append(obj)
    if result["bottom_polyline"]:
        obj = scene.add(result["bottom_polyline"], layer=f"{base_layer}::polylines", name="bottom_polyline")
        scene_objects.append(obj)

    # Add connectors with type-specific colors
    for name, geom, connector in result["connectors"]:
        rgb = get_connector_color(connector)
        color = Color.from_rgb255(*rgb)
        obj = scene.add(geom, layer=f"{base_layer}::connectors", name=name, color=color)
        scene_objects.append(obj)

    scene.draw()

    # Collect GUIDs from scene objects
    guids = []
    for obj in scene_objects:
        if hasattr(obj, 'guids') and obj.guids:
            guids.extend(obj.guids)

    # Convert meshes to breps with merged coplanar faces
    if convert_to_brep and guids:
        guids = convert_meshes_to_breps(guids, merge_coplanar=True)
        print(f"Converted meshes to NURBS breps with merged coplanar faces")

    # Create Rhino group with all objects
    if create_group and guids:
        group_name = f"oriented_{element_name}_group"
        rs.AddGroup(group_name)
        rs.AddObjectsToGroup(guids, group_name)
        print(f"Created group '{group_name}' with {len(guids)} objects")

    print(f"Drew oriented '{element_name}' to Rhino")
    print(f"  - Mesh: {1 if result['mesh'] else 0}")
    print(f"  - Polylines: {int(result['top_polyline'] is not None) + int(result['bottom_polyline'] is not None)}")
    print(f"  - Connectors: {len(result['connectors'])}")


def draw_single_element_to_rhino(model, element_name, create_group=True, convert_to_brep=True):
    """Draw a single element with its connectors in 3D position (not oriented).

    Creates layers:
    - single::{element_name}::mesh
    - single::{element_name}::polylines
    - single::{element_name}::connectors

    Parameters
    ----------
    model : Model
        The loaded compas_model Model.
    element_name : str
        Name of the element to draw.
    create_group : bool
        If True, create a Rhino group containing the element and its connectors.
    convert_to_brep : bool
        If True, convert meshes to NURBS breps and merge coplanar faces.
    """
    import rhinoscriptsyntax as rs

    # Find element by name
    element = model.find_element_with_name(element_name)
    if element is None:
        print(f"Element '{element_name}' not found")
        return

    base_layer = f"single::{element_name}"
    layers = [
        f"{base_layer}::mesh",
        f"{base_layer}::polylines",
        f"{base_layer}::connectors",
    ]
    create_layers_from_paths(layers)

    # Get connectors (needed for boolean cuts)
    connectors = get_element_connectors(model, element)

    scene = Scene()
    scene_objects = []

    # Add main mesh (with boolean cuts applied)
    geom = get_element_geometry_with_cuts(element, connectors)
    if geom:
        obj = scene.add(geom, layer=f"{base_layer}::mesh", name=element_name)
        scene_objects.append(obj)

    # Add polylines if available
    if hasattr(element, 'top_polyline') and element.top_polyline is not None:
        obj = scene.add(element.top_polyline, layer=f"{base_layer}::polylines", name="top_polyline")
        scene_objects.append(obj)
    if hasattr(element, 'bottom_polyline') and element.bottom_polyline is not None:
        obj = scene.add(element.bottom_polyline, layer=f"{base_layer}::polylines", name="bottom_polyline")
        scene_objects.append(obj)

    # Add connectors with type-specific colors
    for i, connector in enumerate(connectors):
        conn_geom = connector.modelgeometry
        if conn_geom is None:
            continue
        rgb = get_connector_color(connector)
        color = Color.from_rgb255(*rgb)
        conn_name = connector.name or f"conn_{i}"
        obj = scene.add(conn_geom, layer=f"{base_layer}::connectors", name=conn_name, color=color)
        scene_objects.append(obj)

    scene.draw()

    # Collect GUIDs from scene objects
    guids = []
    for obj in scene_objects:
        if hasattr(obj, 'guids') and obj.guids:
            guids.extend(obj.guids)

    # Convert meshes to breps with merged coplanar faces
    if convert_to_brep and guids:
        guids = convert_meshes_to_breps(guids, merge_coplanar=True)
        print(f"Converted meshes to NURBS breps with merged coplanar faces")

    # Create Rhino group with all objects
    if create_group and guids:
        group_name = f"single_{element_name}_group"
        rs.AddGroup(group_name)
        rs.AddObjectsToGroup(guids, group_name)
        print(f"Created group '{group_name}' with {len(guids)} objects")

    print(f"Drew '{element_name}' in 3D position")
    print(f"  - Mesh: {1 if geom else 0}")
    polyline_count = int(hasattr(element, 'top_polyline') and element.top_polyline is not None)
    polyline_count += int(hasattr(element, 'bottom_polyline') and element.bottom_polyline is not None)
    print(f"  - Polylines: {polyline_count}")
    print(f"  - Connectors: {len(connectors)}")


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
    # =========================================================================
    # CONFIGURATION
    # =========================================================================
    # MODE options:
    #   "full"     - Load all elements to Rhino with grouping (option a)
    #   "oriented" - Load single element oriented to XY frame (option b)
    #   "single"   - Load single element in 3D position (option c)

    MODE = "full"
    ELEMENT_NAME = "axis_0"  # Used for "oriented" and "single" modes
    # =========================================================================

    if not MODEL_FILEPATH.exists():
        print(f"File not found: {MODEL_FILEPATH}")
        print("Run model.py first to generate the model file.")

    elif MODE == "full":
        # Option a) Add everything to Rhino
        model = load_model_to_rhino(MODEL_FILEPATH)
        list_elements(model)

    elif MODE == "oriented":
        # Option b) Single element oriented to XY frame
        model = json_load(MODEL_FILEPATH)
        print(f"Loaded model: {model.name}")
        list_elements(model)
        orient_and_draw_to_rhino(model, ELEMENT_NAME)

    elif MODE == "single":
        # Option c) Single element in 3D position
        model = json_load(MODEL_FILEPATH)
        print(f"Loaded model: {model.name}")
        list_elements(model)
        draw_single_element_to_rhino(model, ELEMENT_NAME)

    else:
        print(f"Unknown MODE: {MODE}")
        print("Valid modes: 'full', 'oriented', 'single'")
