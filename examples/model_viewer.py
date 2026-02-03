"""Live viewer that loads model.json and watches it for changes.

Usage:
    1. Run this script:  python examples/model_viewer.py
    2. To update the geometry, re-run:  python examples/model.py
       The viewer will detect the updated model.json and refresh automatically.
    3. If you edit model.py code (e.g. viewer functions), the viewer will
       also detect that and reimport before refreshing.
"""

import importlib
import os
import sys
import traceback

from compas import json_load
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

# Import compas_tf to register custom element types for JSON deserialization
import compas_tf  # noqa: F401

# Import viewer utilities from model.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import model as model_module

MODEL_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.json")
MODEL_PY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "model.py")


def load_model():
    """Load model from model.json."""
    return json_load(MODEL_JSON)


def get_mtime(filepath):
    """Get modification time of a file, or 0 if missing."""
    try:
        return os.path.getmtime(filepath)
    except OSError:
        return 0


def replace_scene(viewer, model):
    """Clear the scene and rebuild from model, with a single buffer rebuild at the end.

    Temporarily sets viewer.running = False so that individual scene.add()
    calls don't each trigger a full rebuild_buffers() (which makes it O(n^2)).
    """
    # Remove all existing objects without per-remove GL rebuilds
    for obj in list(viewer.scene.objects):
        viewer.scene.remove(obj, rebuild_buffers=False)

    # Suppress per-add rebuild_buffers by pretending viewer isn't running
    viewer.running = False
    try:
        model_module.add_model_to_viewer(model, viewer)
    finally:
        viewer.running = True

    # Single rebuild at the end
    viewer.renderer.rebuild_buffers()
    viewer.renderer.update()
    viewer.ui.sidebar.update()


# --- Main ---

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

# Initial load (before show, so viewer.running is still False — no per-add rebuilds)
model = load_model()
model_module.add_model_to_viewer(model, viewer)
last_json_mtime = get_mtime(MODEL_JSON)
last_py_mtime = get_mtime(MODEL_PY)


@viewer.on(interval=1000)
def check_reload(frame):
    global last_json_mtime, last_py_mtime

    json_mtime = get_mtime(MODEL_JSON)
    py_mtime = get_mtime(MODEL_PY)

    if json_mtime == last_json_mtime and py_mtime == last_py_mtime:
        return

    # Reimport model.py if it changed
    if py_mtime != last_py_mtime:
        print("[model_viewer] model.py changed, reimporting...")
        try:
            importlib.reload(model_module)
        except Exception:
            traceback.print_exc()
            print("[model_viewer] Reimport failed, using previous version.")
        last_py_mtime = py_mtime

    last_json_mtime = json_mtime

    print("[model_viewer] Reloading scene...")
    try:
        model = load_model()
        replace_scene(viewer, model)
        print("[model_viewer] Reload successful.")
    except Exception:
        traceback.print_exc()
        print("[model_viewer] Reload failed, viewer stays open.")


viewer.show()
