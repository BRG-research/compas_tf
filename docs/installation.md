# Installation

## Use it

```bash
pip install compas_tf
```

Needs Python 3.10 or newer. That is everything you need to open a model, walk
it, cut a piece out of it and write STEP.

Did it work?

```bash
python -c "import compas_tf; print(compas_tf.__version__)"
```

## See it

```bash
pip install compas_viewer
```

Optional. Only the drawing needs it - every example ends in `viewer.show()`.

## Work on it

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/Scripts/activate      # Linux / macOS: source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
uv pip install -e .
```

!!! warning "Type `uv pip`, not `pip`"

    A `uv venv` has no `pip` inside it. Plain `pip install` puts the packages in
    some other Python, and then nothing works.

Did it work?

```bash
python -m pytest tests/ -q          # 12 passed
python tools/run_examples.py        # 23/23 ok
```

`run_examples.py` runs every example with the window suppressed and rewrites
everything in `data/`. Add numbers to run only some: `python tools/run_examples.py 19 20 21`.

## Two things that will trip you up

**Drawing Breps is slow unless you say this first.**

```python
from compas.tolerance import TOL

TOL.lineardeflection = 1.0
```

The default is `0.001` - a 1 micron tolerance on a 6 metre building. That is
2.93M triangles and 67 s, against 19.8k and 2.0 s at `1.0`, for the same
picture.

**The camera starts somewhere useless.** The model is in millimetres, the camera
is not, so you see nothing until you press ++f++. Do it in code instead:

```python
from compas_tf.viewer import zoom_to

zoom_to(viewer, [element.aabb for element in model.geometry_elements()])
```

## Build the docs

```bash
uv pip install -r requirements-docs.txt
invoke serve      # live at http://127.0.0.1:8000
```

??? info "What gets installed, and why"

    | Package | What it is for |
    | --- | --- |
    | `compas >= 2` | Geometry, datastructures, serialization. |
    | `compas_model` | Elements, the element tree, the interaction graph, contacts. |
    | `shapely` | The 2D polygon overlap behind contact detection. |
    | `compas_manifold >= 0.1.0` | Mesh booleans. Only when *building* a model; a baked one never calls it. |
    | `compas_occt >= 0.1.18` | The Brep/STEP kernel - `get_brep()`, `to_step()`, and the Brep scene object. |

    Python 3.9 is out because `shapely >= 2.1` needs 3.10. There is no upper
    bound: `compas_occt` and `compas_manifold` stop at a cp312 wheel, but it is
    a `cp312-abi3` wheel - built against the stable ABI - so it installs on 3.12
    and every CPython after it. Verified up to 3.14. CI tests on 3.10 across
    Linux, macOS and Windows; the examples and the published data files are
    produced on 3.12.
