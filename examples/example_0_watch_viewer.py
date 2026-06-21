"""example_0_watch_viewer.py - persistent compas_viewer that live-reloads any example.

Run this FIRST, then run the other examples.

Workflow
--------
1. Launch this once from a terminal (it opens the viewer and then waits)::

       c:/brg/compas_tf/.venv/Scripts/python.exe c:/brg/compas_tf/examples/example_0_watch_viewer.py

2. Run any ``example_*.py`` (the IDE "play" button). While this watcher is
   running, each example only records its display geometry to
   ``data/_viewer_scene.json`` (via compas_tf.viewer.make_viewer / show_or_dump)
   instead of opening its own window.

3. This viewer notices the scene file changed and redraws it in place, keeping
   the current camera. Run a different example and the content swaps.

Stop with Ctrl-C or by closing the window.
"""

import atexit
import os
import pathlib

import compas
from compas.colors import Color
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

from compas_tf.viewer import LOCK_FILE
from compas_tf.viewer import SCENE_FILE

data_dir = pathlib.Path(__file__).parent.parent / "data"
scene_path = data_dir / SCENE_FILE
lock_path = data_dir / LOCK_FILE

POLL_MS = 500  # how often (ms) to check the scene file for changes

# Style keys forwarded to viewer.scene.add when redrawing.
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


# ------------------------------------------------------------------ #
#  Lock file: tells the examples a watcher is live, so they write-only.
# ------------------------------------------------------------------ #

lock_path.write_text(str(os.getpid()), encoding="utf-8")


@atexit.register
def _remove_lock():
    try:
        lock_path.unlink()
    except FileNotFoundError:
        pass


# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

# mtime of the scene file last drawn; None forces a draw on the first tick.
_state = {"mtime": None}


def _style(record):
    style = {}
    for key in _STYLE_KEYS:
        if key not in record:
            continue
        value = record[key]
        if key.endswith("color") and isinstance(value, (list, tuple)):
            value = Color(*value[:3])
        style[key] = value
    return style


def _reload():
    """Clear the scene and redraw the recorded items from SCENE_FILE.

    Returns ``True`` on success, ``False`` if the file was missing or could not
    be parsed yet (e.g. caught mid-write) so the next tick retries.
    """
    try:
        data = compas.json_load(scene_path)
    except Exception as exc:
        print(f"[watch] skip (not loadable yet): {exc}")
        return False

    # ViewerScene.add() rebuilds GL buffers + refreshes the sidebar after EVERY
    # object while running, so adding N objects triggers N full rebuilds. Flip
    # ``running`` off during the swap so we add cheaply, then rebuild once.
    was_running = viewer.running
    viewer.running = False
    try:
        viewer.scene.clear()
        # Rebuild the recorded group hierarchy so the sidebar scene-tree keeps
        # its structure. Nodes are in creation order, so a parent always appears
        # before its children; map each recorded id to its live scene object.
        objects = {}
        count = 0
        for record in data.get("nodes", []):
            parent = objects.get(record.get("parent"))
            if record.get("kind") == "group":
                objects[record["id"]] = viewer.scene.add_group(record.get("name") or "group", parent=parent)
                continue
            geometry = record.get("geometry")
            if geometry is None:
                continue
            try:
                obj = viewer.scene.add(geometry, parent=parent, **_style(record))
            except Exception:
                obj = viewer.scene.add(geometry, parent=parent)
            objects[record["id"]] = obj
            count += 1
    finally:
        viewer.running = was_running

    # Single geometry-buffer rebuild for the whole new scene (inits objects).
    viewer.renderer.rebuild_buffers()
    viewer.renderer.update()

    # Refresh the sidebar scene-tree. The compas_viewer fork blocks the tree
    # widget's signals during this rebuild (avoids the stale-node crash) and its
    # 'Show' checkbox cascades visibility to children, so no workaround here.
    try:
        viewer.ui.sidebar.sceneform.update(refresh=True)
    except Exception:
        try:
            viewer.ui.sidebar.update()
        except Exception:
            pass
    print(f"[watch] reloaded {scene_path.name} ({count} objects)")
    return True


def _heartbeat():
    """Refresh the lock mtime so examples know the watcher is still alive."""
    try:
        lock_path.touch()
    except OSError:
        pass


@viewer.on(interval=POLL_MS)
def _tick(frame):
    _heartbeat()
    try:
        mtime = scene_path.stat().st_mtime
    except FileNotFoundError:
        return
    if mtime == _state["mtime"]:
        return
    if _reload():
        _state["mtime"] = mtime


print(f"[watch] watching {scene_path}")
print("[watch] run any example_*.py to update; Ctrl-C or close window to stop.")
viewer.show()
