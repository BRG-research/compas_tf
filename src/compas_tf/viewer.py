"""Rhino-bundle export, and small drawing helpers.

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
- ``TeeScene``/``SceneRecorder`` mirrored every ``add``/``add_group`` into a
  parallel node list, so the examples had to draw through a wrapper instead of
  ``viewer.scene``. :func:`dump_scene` walks the finished scene instead - the
  bundle is then whatever the viewer actually shows, and there is one drawing
  API. It also removed a trap: a group handle's ``add`` is core compas'
  ``Group.add``, which never sees ``compas_viewer``'s ``facecolor`` ->
  ``surfacecolor`` translation, so ``facecolor=`` passed to a group was silently
  dropped.

What is left is the Rhino bundle: :func:`dump_scene` flattens the viewer scene
to a node list, so a fabrication example can draw into the viewer and write a
Rhino-loadable JSON from the same scene.
"""

import pathlib

import compas
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Pointcloud
from compas.geometry import Polyline


def _coerce_color(value):
    """Convert a Color/tuple to a plain ``[r, g, b]`` list for JSON; else None."""
    if value is None:
        return None
    try:
        return [float(value[0]), float(value[1]), float(value[2])]
    except (TypeError, IndexError, KeyError):
        return None


def _drawn_color(obj):
    """The one colour Rhino should give this object.

    A scene object carries a colour per buffer - point, line, surface - but a
    Rhino object has a single display colour, so pick the one that is actually
    seen: an explicit ``color=`` if the example set one, then the colour of the
    buffer that carries the geometry.
    """
    if obj.color is not None:
        return obj.color
    if isinstance(obj.item, (Point, Pointcloud)):
        return getattr(obj, "pointcolor", None)
    # Curves have no surface, and a solid drawn as a wireframe is its edges.
    if isinstance(obj.item, (Line, Polyline)) or not getattr(obj, "show_faces", True):
        return getattr(obj, "linecolor", None)
    return getattr(obj, "surfacecolor", None)


def scene_nodes(scene):
    """Flatten a viewer scene to the Rhino bundle's node list.

    Walks the scene tree in the order the objects were added, so each group
    becomes a node its children point back at through ``parent``.

    Parameters
    ----------
    scene : :class:`compas_viewer.scene.ViewerScene`
        The scene to read, i.e. ``viewer.scene``.

    Returns
    -------
    list[dict]
        ``{"id", "parent", "kind"}`` per node, plus ``name`` / ``geometry`` /
        ``color`` / ``opacity`` on the geometry ones.
    """
    from compas.scene import Group as SceneGroup

    nodes = []

    def walk(objects, parent_id):
        for obj in objects:
            node_id = len(nodes)
            if isinstance(obj, SceneGroup):
                nodes.append({"id": node_id, "parent": parent_id, "kind": "group", "name": obj.name or "group"})
                walk(obj.children, node_id)
                continue
            node = {"id": node_id, "parent": parent_id, "kind": "geometry", "geometry": obj.item}
            if obj.name:
                node["name"] = obj.name
            color = _coerce_color(_drawn_color(obj))
            if color is not None:
                node["color"] = color
            if obj.opacity is not None and obj.opacity != 1.0:
                node["opacity"] = obj.opacity
            nodes.append(node)
            walk(obj.children, node_id)

    walk(scene.root.children, None)
    return nodes


def dump_scene(scene, path):
    """Write the viewer scene to a Rhino bundle.

    The bundle is ``{"nodes": [...]}`` - :func:`scene_nodes` of the finished
    scene - serialized with :func:`compas.json_dump`, so the embedded COMPAS
    geometry round-trips. Load it in Rhino with
    :func:`compas_tf.rhino.draw_bundle`.

    Call it after everything is drawn and before ``viewer.show()``: the scene is
    the record, so anything added later is not in the file.

    Parameters
    ----------
    scene : :class:`compas_viewer.scene.ViewerScene`
        The scene to write, i.e. ``viewer.scene``.
    path : str or :class:`pathlib.Path`
        Where to write the bundle.

    Returns
    -------
    str or :class:`pathlib.Path`
        The path written.
    """
    nodes = scene_nodes(scene)
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


def zoom_to(viewer, boxes, tightness=10.0):
    """Aim the camera at the geometry, before ``viewer.show()``.

    What the ``F`` key does - compas_viewer's ``zoom_selected`` - but computed
    from geometry rather than from the scene objects, whose bounding boxes do
    not exist until the renderer has run, so ``F`` cannot be pressed for you.

    Needed on a model in millimetres. The camera starts at ``position``
    ``[-10, -10, 10]`` with a ``far`` plane of ``1000``, and ``far`` is scaled by
    ``camera.scale``, which starts at 1 - so on a 6015 mm building the whole
    thing sits behind the far plane until something sets the scale.

    Parameters
    ----------
    viewer : :class:`compas_viewer.Viewer`
    boxes : sequence[:class:`compas.geometry.Box`]
        The bounding boxes to frame - ``element.aabb`` for model elements,
        ``brep.aabb`` for Breps. Empty leaves the camera alone.
    tightness : float, optional
        Divisor for the camera scale, as in ``zoom_selected``. Larger fills
        more of the window.
    """
    corners = [point for box in boxes if box is not None for point in box.points]
    if not corners:
        return

    low = [min(point[i] for point in corners) for i in range(3)]
    high = [max(point[i] for point in corners) for i in range(3)]
    diagonal = max(sum((high[i] - low[i]) ** 2 for i in range(3)) ** 0.5, 1.0)
    center = [(low[i] + high[i]) / 2 for i in range(3)]

    camera = viewer.renderer.camera
    # scale drives near/far as well as pan speed, so it is what stops the model
    # being clipped away.
    camera.scale = diagonal / tightness

    # Keep the direction the camera is already looking from and only move it -
    # the view vector is position MINUS target, not target minus position. Using
    # the latter is degenerate here: the default position sits almost on the
    # origin, so on a model whose centre is 1.5 m up it points nearly straight
    # down and the camera ends up underneath the building.
    view = [camera.position[i] - camera.target[i] for i in range(3)]
    length = sum(value**2 for value in view) ** 0.5 or 1.0
    camera.target = center
    camera.position = [center[i] + view[i] / length * diagonal for i in range(3)]
