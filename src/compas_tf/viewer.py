import os
import pathlib
import time

import compas
from compas.geometry import Line

# ------------------------------------------------------------------ #
#  watch_viewer.py handoff: write-only mode + scene recorder
# ------------------------------------------------------------------ #
# When watch_viewer.py is running it drops a lock file and watches SCENE_FILE.
# In that case make_viewer() returns a SceneRecorder stand-in so an example's
# existing ``viewer.scene.add(...)`` calls are captured instead of drawn, and
# viewer.show() writes them to SCENE_FILE for the persistent viewer to reload.

LOCK_FILE = ".watch_viewer.lock"
SCENE_FILE = "_viewer_scene.json"

# Default data directory (repo ``data/``). viewer.py lives at
# src/compas_tf/viewer.py, so three parents up is the repo root.
DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "data"

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


class _TeeNode:
    """A group handle that forwards ``add``/``add_group`` to BOTH a live scene
    group and a :class:`SceneRecorder` group, so geometry drawn into the viewer
    is captured into the recorder bundle at the same time.
    """

    def __init__(self, live, rec_node):
        self._live = live
        self._rec = rec_node

    def add(self, item, **style):
        self._live.add(item, **style)
        return self._rec.add(item, **style)

    def add_group(self, name=None, **kwargs):
        return _TeeNode(self._live.add_group(name), self._rec.add_group(name))


class TeeScene:
    """Drop-in for ``viewer.scene`` that draws into the live scene AND records a
    flat node bundle alongside it.

    Wrap the viewer's scene once (``scene = TeeScene(viewer.scene)``) and use it
    exactly like ``viewer.scene`` - every ``add``/``add_group`` is mirrored into
    an internal :class:`SceneRecorder`. Call :func:`dump_bundle` at the end to
    write the recorded geometry to a JSON "Rhino bundle" (plain COMPAS Mesh /
    Polyline / Polygon / Line + layer + colour), which the
    :mod:`compas_tf.rhino` loader replays into Rhino with no recompute.
    """

    def __init__(self, live_scene):
        self._live = live_scene
        self._rec = SceneRecorder()

    @property
    def nodes(self):
        return self._rec.nodes

    def add(self, item, **style):
        self._live.add(item, **style)
        return self._rec.add(item, **style)

    def add_group(self, name=None, **kwargs):
        return _TeeNode(self._live.add_group(name), self._rec.add_group(name))


def dump_bundle(scene, path):
    """Write a :class:`TeeScene` (or :class:`SceneRecorder`) to a Rhino bundle.

    The bundle is ``{"nodes": [...]}`` - the recorded group/geometry node list -
    serialized with :func:`compas.json_dump`, so the embedded COMPAS geometry
    round-trips. Load it in Rhino with :func:`compas_tf.rhino.draw_bundle`.
    """
    nodes = scene.nodes if hasattr(scene, "nodes") else list(scene)
    compas.json_dump({"nodes": nodes}, str(path))
    print(f"[bundle] wrote {pathlib.Path(path).name} ({sum(1 for n in nodes if n.get('kind') == 'geometry')} objects)")
    return path


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

    def __init__(self, data_dir):
        self.scene = SceneRecorder()
        self.renderer = _Stub()
        self._data_dir = data_dir

    def show(self):
        path = pathlib.Path(self._data_dir) / SCENE_FILE
        tmp = path.with_name(path.name + ".tmp")
        compas.json_dump({"nodes": self.scene.nodes}, tmp)
        for _ in range(40):
            try:
                os.replace(tmp, path)
                break
            except PermissionError:
                time.sleep(0.05)
        else:
            os.replace(tmp, path)
        n_geo = sum(1 for node in self.scene.nodes if node.get("kind") == "geometry")
        print(f"[viewer] watch_viewer running -> wrote {path.name} ({n_geo} objects), skipping local viewer.")


def watcher_running(data_dir) -> bool:
    """True if watch_viewer.py is live, i.e. its lock file exists and was
    heartbeated within ``LOCK_FRESH_SECONDS``. A stale lock from a crashed
    watcher is ignored (and cleaned up) so examples open their own viewer.
    """
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


# Default mesh wireframe (edge) colour. compas_viewer draws a mesh's edges in its
# "contrast" colour - the face ``color`` DARKENED BY 50% - so the examples' grey
# (0.85) meshes get a medium-grey wireframe (~0.42). Override that with a single,
# darker grey so the edges read clearly. Set to ``None`` to keep the default.
EDGECOLOR = (0.08, 0.08, 0.08)


def _apply_edgecolor():
    """Force every mesh's edge colour to :data:`EDGECOLOR` (face colours and line
    objects are left untouched).

    compas core ``MeshObject`` resolves its edge colour as
    ``edgecolor = edgecolor or self.contrastcolor``, so overriding
    ``contrastcolor`` on that one class is the single, targeted hook that
    recolours every mesh wireframe - no need to pass a colour per ``scene.add``.
    Idempotent; a no-op when ``EDGECOLOR`` is ``None``.
    """
    if EDGECOLOR is None:
        return
    from compas.colors import Color
    from compas.scene.meshobject import MeshObject

    color = Color(*EDGECOLOR)
    MeshObject.contrastcolor = property(lambda self: color, lambda self, _value: None)


def make_viewer(data_dir):
    """Return a live ``Viewer`` (lighted, mm units), or a recording stand-in
    when watch_viewer.py is running, so the example becomes write-only.
    """
    _apply_edgecolor()
    if watcher_running(data_dir):
        return _RecorderViewer(data_dir)
    from compas_viewer.config import Config
    from compas_viewer.viewer import Viewer

    config = Config()
    config.unit = "mm"
    viewer = Viewer(config)
    viewer.renderer.rendermode = "lighted"
    return viewer


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


def triangulated(mesh):
    """Return a copy of ``mesh`` with every face ear-clipped into triangles.

    compas_viewer triangulates an n-gon face with a *centroid fan*
    (``meshobject.py``), which is only correct for convex faces. A concave face
    — e.g. the L-shaped column sides produced by the capitel/cutter booleans —
    fans into overlapping triangles and renders wrong. Ear-clipping each face up
    front hands the viewer correct triangles. The added diagonals are coplanar
    with their original face, so ``hide_coplanaredges`` hides them and the
    visible wireframe is unchanged.
    """
    from compas.datastructures import Mesh
    from compas.geometry import Polygon
    from compas.geometry import earclip_polygon

    out = Mesh()
    vmap = {v: out.add_vertex(x=p[0], y=p[1], z=p[2]) for v, p in ((v, mesh.vertex_coordinates(v)) for v in mesh.vertices())}
    for face in mesh.faces():
        fv = mesh.face_vertices(face)
        if len(fv) <= 3:
            out.add_face([vmap[v] for v in fv])
            continue
        try:
            tris = earclip_polygon(Polygon([mesh.vertex_coordinates(v) for v in fv]))
        except Exception:
            tris = None
        if not tris:  # earclip raised or returned None/empty for a degenerate face
            out.add_face([vmap[v] for v in fv])  # fall back to the original face
            continue
        for tri in tris:
            out.add_face([vmap[fv[i]] for i in tri])
    return out
