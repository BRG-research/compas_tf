
import os
import pathlib
import time

import compas
from compas.geometry import Frame
from compas.geometry import Line
from compas_model.elements.group import Group

from compas_tf.column import ColumnElement
from compas_tf.floor_column_connection import FloorColumnConnectionElement
from compas_tf.joint_dowel import DowelElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.plate import PlateElement
from compas_tf.solid_difference_modifier import SolidDifferenceModifier
from compas_tf.solid_union_modifier import SolidUnionModifier
from compas_tf.wedge import WedgeElement

# Connector types for identification
CONNECTOR_TYPES = (DowelElement, SherpaXL120Element)

# Colors
ELEMENT_COLOR = (0.6, 0.6, 0.6)
CONNECTOR_COLOR = (0.8, 0.0, 0.2)
SUPPORT_COLOR = (0.9, 0.9, 0.9)
COLUMN_COLOR = (0.9, 0.9, 0.9)
COLUMN_HEAD_COLOR = (0.4, 0.4, 0.4)
CONNECTION_COLOR = (1.0, 1.0, 0.0)  # corner column-connection cutter (kept visible)

# Color map by group name
COLOR_MAP = {
    "supports": SUPPORT_COLOR,
    "columns": COLUMN_COLOR,
    "column_heads": COLUMN_HEAD_COLOR,
    "connectors": CONNECTOR_COLOR,
    "column_connections": CONNECTION_COLOR,
}

# Cutter (SolidDifferenceModifier source) types that should still be drawn in
# the viewer instead of hidden, so the cutting geometry can be inspected.
VISIBLE_CUTTER_TYPES = (DowelElement, WedgeElement, FloorColumnConnectionElement)

# ------------------------------------------------------------------ #
#  watch_viewer.py handoff: write-only mode + scene recorder
# ------------------------------------------------------------------ #
# When watch_viewer.py is running it drops a lock file and watches SCENE_FILE.
# In that case make_viewer() returns a SceneRecorder stand-in so an example's
# existing ``viewer.scene.add(...)`` calls are captured instead of drawn, and
# show_or_dump() writes them to SCENE_FILE for the persistent viewer to reload.

LOCK_FILE = ".watch_viewer.lock"
SCENE_FILE = "_viewer_scene.json"

# A watcher is considered live only if its lock file was touched within this
# many seconds (the watcher heartbeats it every tick). This way a crashed
# watcher's stale lock is ignored and examples open their own viewer again.
LOCK_FRESH_SECONDS = 5.0

# Style kwargs preserved through the record -> JSON -> redraw round-trip.
_STYLE_KEYS = (
    "color",
    "facecolor",
    "linecolor",
    "pointcolor",
    "linewidth",
    "pointsize",
    "opacity",
    "show_lines",
    "show_points",
    "hide_coplanaredges",
)


def _coerce_color(value):
    """Convert a Color/tuple to a plain ``[r, g, b]`` list for JSON; else None."""
    if value is None:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except (TypeError, IndexError, KeyError):
        return None


class _RecorderNode:
    """A group handle returned by the recorder. Supports ``add``/``add_group``
    so geometry and nested groups are recorded under the right parent, keeping
    the scene-tree hierarchy intact through the JSON round-trip.
    """

    def __init__(self, recorder, node_id):
        self._rec = recorder
        self._id = node_id

    def add(self, item, parent=None, **style):
        return self._rec._record(item, self._id, style)

    def add_group(self, name=None, parent=None, **kwargs):
        return self._rec._record_group(name, self._id)


class SceneRecorder:
    """Quacks like ``viewer.scene`` (and a scene group): ``add``/``add_group``
    record drawable geometry and group structure to a flat node list (each node
    carries its parent id) instead of drawing. The watcher rebuilds the same
    group hierarchy from these nodes so the sidebar scene-tree is preserved.
    """

    def __init__(self):
        self.nodes = []
        self._next_id = 0

    def _new_id(self):
        node_id = self._next_id
        self._next_id += 1
        return node_id

    @staticmethod
    def _parent_id(parent):
        return parent._id if isinstance(parent, _RecorderNode) else None

    def add_group(self, name=None, parent=None, **kwargs):
        return self._record_group(name, self._parent_id(parent))

    def _record_group(self, name, parent_id):
        node_id = self._new_id()
        self.nodes.append({"id": node_id, "parent": parent_id, "kind": "group", "name": name or "group"})
        return _RecorderNode(self, node_id)

    def add(self, item, parent=None, **style):
        return self._record(item, self._parent_id(parent), style)

    def _record(self, item, parent_id, style):
        from compas.data import Data

        if isinstance(item, Data):
            record = {"id": self._new_id(), "parent": parent_id, "kind": "geometry", "geometry": item}
            if style.get("name"):
                record["name"] = style["name"]
            for key in _STYLE_KEYS:
                if style.get(key) is None:
                    continue
                record[key] = _coerce_color(style[key]) if key.endswith("color") else style[key]
            self.nodes.append(record)
        # Geometry adds are never used as a parent, but return a node anyway so
        # any chained .add()/.add_group() still works.
        return _RecorderNode(self, None)


class _Stub:
    """Absorbs any attribute access/call (e.g. ``viewer.renderer.x = ...``)."""

    def __getattr__(self, name):
        return _Stub()

    def __setattr__(self, name, value):
        pass

    def __call__(self, *args, **kwargs):
        return _Stub()


class _RecorderViewer:
    """Drop-in for ``Viewer`` whose ``.scene`` records instead of drawing."""

    def __init__(self):
        self.scene = SceneRecorder()
        self.renderer = _Stub()


def watcher_running(data_dir) -> bool:
    """True if watch_viewer.py is live, i.e. its lock file exists and was
    heartbeated within ``LOCK_FRESH_SECONDS``. A stale lock from a crashed
    watcher is ignored (and cleaned up) so examples open their own viewer.
    """
    import time

    lock = pathlib.Path(data_dir) / LOCK_FILE
    try:
        age = time.time() - lock.stat().st_mtime
    except FileNotFoundError:
        return False
    if age <= LOCK_FRESH_SECONDS:
        return True
    # Stale lock -> remove it so we don't keep going write-only forever.
    try:
        lock.unlink()
    except OSError:
        pass
    return False


def make_viewer(data_dir):
    """Return a live ``Viewer`` (lighted, mm units), or a recording stand-in
    when watch_viewer.py is running, so the example becomes write-only.
    """
    if watcher_running(data_dir):
        return _RecorderViewer()
    from compas_viewer.config import Config
    from compas_viewer.viewer import Viewer

    config = Config()
    config.unit = "mm"
    viewer = Viewer(config)
    viewer.renderer.rendermode = "lighted"
    return viewer


def show_or_dump(viewer, data_dir):
    """Show the live viewer, or - when recording - dump the captured scene to
    SCENE_FILE for watch_viewer.py to reload.
    """
    if isinstance(viewer, _RecorderViewer):
        path = pathlib.Path(data_dir) / SCENE_FILE
        # Atomic write: dump to a temp file then os.replace() onto the final
        # name. The watcher polls this file, so a plain in-place write lets it
        # read a half-written (invalid) JSON; os.replace swaps it atomically so
        # the watcher only ever sees a complete file.
        tmp = path.with_name(path.name + ".tmp")
        compas.json_dump({"nodes": viewer.scene.nodes}, tmp)
        # On Windows os.replace raises PermissionError if the watcher has the
        # destination open for reading at that instant; its read is brief, so
        # retry a few times to ride it out.
        for _ in range(40):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                time.sleep(0.05)
        else:
            os.replace(tmp, path)  # final attempt; let it raise if truly stuck
        n_geo = sum(1 for node in viewer.scene.nodes if node.get("kind") == "geometry")
        print(f"[viewer] watch_viewer running -> wrote {path.name} ({n_geo} objects), skipping local viewer.")
        return
    viewer.show()


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
    element_group = viewer.scene.add_group(element_name) if viewer_parent is None else viewer.scene.add_group(element_name, parent=viewer_parent)

    element_group.add(mesh, name="mesh", hide_coplanaredges=True, color=color)

    # Add top/bottom polylines for PlateElement
    if isinstance(element, PlateElement):
        if element.top_polyline is not None or element.bottom_polyline is not None:
            polylines_group = viewer.scene.add_group("polylines", parent=element_group)
            if element.top_polyline is not None:
                polylines_group.add(element.top_polyline, name="top_polyline", linewidth=2)
            if element.bottom_polyline is not None:
                polylines_group.add(element.bottom_polyline, name="bottom_polyline", linewidth=2)

    # Add base_frame visualization
    if isinstance(element, ColumnElement):
        base_frame = get_base_frame_from_obb(element)
    elif hasattr(element, "base_frame"):
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


def get_union_source_elements(model):
    """Get elements whose geometry has been absorbed into another via SolidUnionModifier.

    These elements should not be drawn separately (their geometry is merged into the target).
    """
    sources = set()
    for edge in model.graph.edges():
        modifiers = model.graph.edge_attribute(edge, name="modifiers")
        if not modifiers:
            continue
        for modifier in modifiers:
            if isinstance(modifier, SolidUnionModifier):
                u, _v = edge
                source = model.graph.node_element(u)
                sources.add(source)
    return sources


def get_difference_source_elements(model):
    """Get elements acting as cutters via SolidDifferenceModifier.

    Cutters carve other elements but are not meant to be drawn themselves.
    """
    sources = set()
    for edge in model.graph.edges():
        modifiers = model.graph.edge_attribute(edge, name="modifiers")
        if not modifiers:
            continue
        for modifier in modifiers:
            if isinstance(modifier, SolidDifferenceModifier):
                u, _v = edge
                el = model.graph.node_element(u)
                sources.add(el)
    return sources


def add_model_to_viewer(model, viewer):
    """Traverse model tree and create viewer hierarchy."""

    # Build map of element -> all its connectors (from interactions)
    element_connectors = build_element_connectors_map(model)

    # Find elements absorbed by boolean union (works after JSON round-trip)
    union_sources = get_union_source_elements(model)
    # Find cutters (sources of SolidDifferenceModifier) to hide from the viewer
    difference_sources = get_difference_source_elements(model)
    hidden_sources = union_sources | difference_sources

    def traverse_element(element, viewer_parent):
        """Recursively traverse element children and add to viewer."""
        # element.children returns actual elements (not nodes)
        for child in element.children:
            if isinstance(child, Group):
                # Create viewer group for model groups
                child_group = viewer.scene.add_group(child.name or "group", parent=viewer_parent)
                traverse_element(child, child_group)
            else:
                # Skip elements absorbed by boolean union or used as difference cutters
                # but keep the inspectable cutter types visible even though they cut.
                if child in hidden_sources and not isinstance(child, VISIBLE_CUTTER_TYPES):
                    continue
                # Add element geometry and get its viewer group
                color = get_color_for_element(child)
                child_viewer_group = add_element_to_viewer(viewer, viewer_parent, child, color)

                if child_viewer_group is not None:
                    # Add connectors from interactions (not just tree children)
                    # Connectors can appear under multiple elements they connect
                    if child in element_connectors:
                        connectors_group = viewer.scene.add_group("connectors", parent=child_viewer_group)
                        for connector in element_connectors[child]:
                            # Skip modifier-only connectors (e.g., dowel cutters)
                            if isinstance(connector, DowelElement):
                                continue
                            conn_color = get_color_for_element(connector)
                            add_element_to_viewer(viewer, connectors_group, connector, conn_color)

                    # Recurse into all tree children (groups and plain elements alike)
                    # This covers e.g. DowelElement children of WedgeElement for debug display.
                    for grandchild in child.children:
                        if isinstance(grandchild, Group):
                            traverse_element(grandchild, child_viewer_group)
                        else:
                            if grandchild in hidden_sources and not isinstance(grandchild, VISIBLE_CUTTER_TYPES):
                                continue
                            gc_color = (0.2, 0.5, 1.0) if isinstance(grandchild, DowelElement) else get_color_for_element(grandchild)
                            add_element_to_viewer(viewer, child_viewer_group, grandchild, gc_color)

    # Traverse from root's direct children (top-level groups)
    # model.tree.root.children returns nodes, so access .element
    for node in model.tree.root.children:
        element = node.element
        if isinstance(element, Group):
            group = viewer.scene.add_group(element.name or "group")
            traverse_element(element, group)
        else:
            if element in hidden_sources and not isinstance(element, VISIBLE_CUTTER_TYPES):
                continue
            color = get_color_for_element(element)
            elem_group = add_element_to_viewer(viewer, None, element, color)
            if elem_group is not None and element in element_connectors:
                connectors_group = viewer.scene.add_group("connectors", parent=elem_group)
                for connector in element_connectors[element]:
                    conn_color = get_color_for_element(connector)
                    add_element_to_viewer(viewer, connectors_group, connector, conn_color)
