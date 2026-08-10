"""Rhino-bundle recording, and small drawing helpers.

There is deliberately no viewer wrapper here any more. Examples use
``compas_viewer`` directly::

    from compas_viewer import Viewer

    viewer = Viewer()
    viewer.scene.add(element, name=element.name)
    viewer.show()

and a compas_tf element draws itself, because :mod:`compas_tf.scene` registers a
scene object for it through the standard compas plugin mechanism.

What used to be here and why it is gone
---------------------------------------
- ``make_viewer()`` returned either a real ``Viewer`` or a recorder stand-in, so
  a persistent ``watch_viewer.py`` could live-reload the scene from JSON. That
  workflow, its example and the compas_viewer fork it needed are all dropped in
  favour of the stock viewer API.
- ``triangulated()`` copied every mesh, ear-clipping it, because
  ``MeshObject`` fans an n-gon from its centroid and gets concave faces wrong.
  :class:`compas_tf.scene.TFElementObject` ear-clips straight into the shader
  buffer instead, so there is no copy - and it is exact, where the centroid fan
  overstated the most carved plate's surface by 1.3%.
- ``_apply_edgecolor()`` monkeypatched core ``MeshObject.contrastcolor`` to fix
  washed-out wireframes. The scene object emits its own edge colour now.

What is left is the Rhino bundle: a recorder that captures ``add``/``add_group``
calls to a flat node list, so a fabrication example can draw into the viewer and
write a Rhino-loadable JSON at the same time.
"""

import pathlib

import compas
from compas.geometry import Line

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


def _patch_group_nesting():
    """Give compas_viewer's ``Group`` an ``add_group`` method.

    A live ``Group`` cannot create sub-groups itself - only the scene can, via
    ``scene.add_group(name, parent=group)``. :class:`_TeeNode` mirrors a live
    group handle and a recorder group handle behind one object, and the recorder
    side does support ``add_group``, so without this the two sides diverge and a
    nested group blows up on the live one. Idempotent.

    Only :class:`TeeScene` needs this. Code using the viewer directly should
    call ``scene.add_group(name, parent=group)``, which is the native API.
    """
    from compas_viewer.scene import Group

    if hasattr(Group, "add_group"):
        return

    def add_group(self, name=None, **kwargs):
        return self.scene.add_group(name, parent=self, **kwargs)

    Group.add_group = add_group


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
    carries its parent id) instead of drawing.
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
        _patch_group_nesting()
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
