# Installation

## Requirements

**Use Python 3.12; 3.10 and 3.11 work too, 3.9 and 3.13 do not.**

3.9 is out because `shapely >= 2.1` needs 3.10, and 3.13 is out because
`compas_occt` and `compas_manifold` ship wheels for cp39-cp312 only - on 3.13
pip falls back to the source distribution and building the Brep kernel from
source fails. CI runs the tests on 3.10 (Linux, macOS, Windows); 3.12 is what
the examples and the published data files are produced with.

Five runtime dependencies, all pulled in by `pip install compas_tf`:

| Package | What it is for |
| --- | --- |
| `compas >= 2` | Geometry, datastructures, serialization. |
| `compas_model` | Elements, the element tree, the interaction graph, contacts. |
| `shapely` | The 2D polygon overlap behind contact detection. |
| `compas_manifold >= 0.1.0` | Mesh booleans. Only when *building* a model; a baked one never calls it. |
| `compas_occt >= 0.1.18` | The Brep/STEP kernel - `get_brep()`, `to_step()`, and the Brep scene object. |

## Install the package

```bash
pip install compas_tf
python -c "import compas_tf; print(compas_tf.__version__)"
```

That is all a *reader* needs: a written model is baked, so no boolean backend is
involved on load.

## Install this repository

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/Scripts/activate      # macOS / Linux: source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
uv pip install -e .
```

!!! warning "`uv pip`, not plain `pip`"

    A `uv venv` has no `pip` of its own: `python -m pip` fails with
    `No module named pip`, and a bare `pip install` lands in whatever
    environment is first on your `PATH`.

Check it:

```bash
python -m pytest tests/ -q          # 12 passed
python tools/run_examples.py        # 23/23 ok
```

`run_examples.py` runs the example chain with the viewer window suppressed and
regenerates everything in `data/`. It is the integration test: the scenes are
built for real, so broken geometry still raises. Pass numbers to run some of
them - `python tools/run_examples.py 19 20 21`.

With stock `venv` and `pip` the same thing works, minus the `uv` prefix.

## The viewer

Optional and deliberately not a dependency - `compas_tf` never imports it, so
only the drawing needs it. Every example ends in `viewer.show()`.

```bash
pip install compas_viewer
```

!!! warning "Set the deflection before drawing Breps"

    COMPAS defaults `TOL.lineardeflection` to `0.001`, a 1 micron chord
    tolerance on a building: the twisted loft quads tessellate to 2.93M
    triangles in 67 s, against 19.8k in 2.0 s at `1.0`, for the same picture.
    The angular deflection changes neither.

    ```python
    from compas.tolerance import TOL

    TOL.lineardeflection = 1.0
    ```

The camera needs the same treatment. It starts at `[-10, -10, 10]` with a far
plane of 1000, so a 6015 mm building is entirely clipped until you press ++f++.
`compas_tf.viewer.zoom_to` does that from the geometry, before `show()`:

```python
from compas_tf.viewer import zoom_to

zoom_to(viewer, [element.aabb for element in model.geometry_elements()])
```

## The documentation

[mkdocs-material](https://squidfunk.github.io/mkdocs-material/):

```bash
uv pip install -r requirements-docs.txt
invoke docs      # mkdocs build --strict
invoke serve     # live reload on http://127.0.0.1:8000
```

## In a project of your own

```bash
uv init my-project
cd my-project
uv add compas_tf
```

[Set up a project](examples/040_project_setup.md) walks through a complete one.
