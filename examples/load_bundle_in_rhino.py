"""Open THIS file in the Rhino 8 ScriptEditor (Python 3) and Run it to load a
fab "Rhino bundle" into the active Rhino document.

A bundle is a ``data/*_rhino.json`` file written by a fab example (examples 12,
13, 14...). It holds plain COMPAS geometry already computed on the desktop, so
this loader needs ONLY ``compas`` + Rhino's own ``compas_rhino`` backend - no
``compas_manifold``, ``compas_model`` or ``compas_tf`` (the geometry is baked in,
nothing is recomputed here).

Each example's group tree is rebuilt as nested Rhino layers, and every object
keeps the colour and name it had in the desktop viewer. Set ``BUNDLE`` below to
the example you want, then Run.
"""

import compas
from compas.colors import Color
from compas.scene import Scene

# ------------------------------------------------------------------ #
# Pick which fab example's bundle to load (edit this one line).
# ------------------------------------------------------------------ #
BUNDLE = r"C:\brg\compas_tf\data\oculus_fab_rhino.json"
# BUNDLE = r"C:\brg\compas_tf\data\column_fab_rhino.json"
# BUNDLE = r"C:\brg\compas_tf\data\quarter_bed_fab_rhino.json"
# BUNDLE = r"C:\brg\compas_tf\data\quarter_frame_fab_rhino.json"


def layer_path(by_id, node_id):
    """The ``"a::b::c"`` Rhino layer path for a node id (chain of group names)."""
    names = []
    node = by_id.get(node_id)
    while node is not None:
        if node.get("kind") == "group":
            names.append(node.get("name") or "group")
        node = by_id.get(node.get("parent"))
    names.reverse()
    return "::".join(names) or None


def draw_bundle(path):
    """Replay a bundle into the active Rhino document via the COMPAS scene."""
    data = compas.json_load(path)
    nodes = data["nodes"] if isinstance(data, dict) else data
    by_id = {node["id"]: node for node in nodes}

    scene = Scene()
    count = 0
    for node in nodes:
        if node.get("kind") != "geometry":
            continue
        geometry = node.get("geometry")
        if geometry is None:
            continue
        rgb = node.get("color") or node.get("facecolor") or node.get("linecolor") or node.get("pointcolor")
        kwargs = {"layer": layer_path(by_id, node.get("parent"))}
        if node.get("name"):
            kwargs["name"] = node["name"]
        if rgb:
            kwargs["color"] = Color(*rgb)
        if node.get("opacity") is not None:
            kwargs["opacity"] = node["opacity"]
        scene.add(geometry, **kwargs)
        count += 1

    scene.draw()
    print("Loaded {} objects from {}".format(count, path))

    try:
        import scriptcontext as sc  # Rhino only

        sc.doc.Views.Redraw()
    except Exception:
        pass


if __name__ == "__main__":
    draw_bundle(BUNDLE)
