"""Load a compas_tf "Rhino bundle" into Rhino via the COMPAS scene.

A *bundle* is the flat node list the fab examples record while they draw
(:class:`compas_tf.viewer.TeeScene` + :func:`compas_tf.viewer.dump_bundle`)::

    {"nodes": [
        {"id": 0, "parent": None, "kind": "group", "name": "oculus_flat"},
        {"id": 1, "parent": 0, "kind": "geometry", "name": "...",
         "geometry": <COMPAS Mesh/Polyline/Polygon/Line>, "color": [r, g, b]},
        ...
    ]}

The geometry is plain COMPAS geometry **already computed on the desktop** (the
boolean carves are baked in), so replaying it needs only ``compas`` and Rhino's
own ``compas_rhino`` backend - NOT ``compas_manifold``, ``compas_model`` or the
``compas_tf`` element classes. Each group becomes a (nested) Rhino layer and
each geometry is added to the COMPAS :class:`~compas.scene.Scene` under its
parent group's layer, with its recorded colour and name; ``scene.draw()`` then
emits the objects into the active Rhino document.

Run in the Rhino 8 ScriptEditor (Python 3) after ``compas_tf`` is installed::

    from compas_tf.rhino import draw_bundle
    draw_bundle(r"C:\\brg\\compas_tf\\data\\oculus_fab_model_rhino.json")
"""


def _layer_paths(nodes):
    """Map each node id to its ``"a::b::c"`` layer path (chain of group names)."""
    by_id = {node["id"]: node for node in nodes}

    def path_of(node_id):
        names = []
        current = by_id.get(node_id)
        while current is not None:
            if current.get("kind") == "group":
                names.append(current.get("name") or "group")
            current = by_id.get(current.get("parent"))
        names.reverse()
        return "::".join(names)

    return {node["id"]: path_of(node["id"]) for node in nodes}


def draw_bundle(path, scene=None, redraw=True):
    """Replay a Rhino bundle into the active Rhino document.

    Parameters
    ----------
    path : str
        Path to a ``*_rhino.json`` bundle written by a fab example.
    scene : :class:`compas.scene.Scene`, optional
        Scene to add to. A fresh one is created (and drawn) by default.
    redraw : bool, optional
        Redraw the active Rhino view when done (Rhino only).

    Returns
    -------
    :class:`compas.scene.Scene`
        The scene the bundle was drawn with.
    """
    import compas
    from compas.colors import Color
    from compas.scene import Scene

    data = compas.json_load(path)
    nodes = data["nodes"] if isinstance(data, dict) else data
    layers = _layer_paths(nodes)

    scene = scene or Scene()
    count = 0
    for node in nodes:
        if node.get("kind") != "geometry":
            continue
        geometry = node.get("geometry")
        if geometry is None:
            continue
        rgb = node.get("color") or node.get("facecolor") or node.get("linecolor") or node.get("pointcolor")
        kwargs = {"layer": layers.get(node["parent"]) or None}
        if node.get("name"):
            kwargs["name"] = node["name"]
        if rgb:
            kwargs["color"] = Color(*rgb)
        if node.get("opacity") is not None:
            kwargs["opacity"] = node["opacity"]
        scene.add(geometry, **kwargs)
        count += 1

    scene.draw()
    print("[compas_tf.rhino] drew {} objects from {}".format(count, path))

    if redraw:
        try:
            import scriptcontext as sc  # Rhino only

            sc.doc.Views.Redraw()
        except Exception:
            pass

    return scene
