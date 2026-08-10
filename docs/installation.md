# Installation

## Requirements

**Python 3.10, 3.11 or 3.12.** The package metadata says `>=3.9`, but `shapely`
needs 3.10, and `compas_occt` ships wheels for cp39 to cp312 only - **there is
no 3.13 wheel yet**, so 3.13 will try to build the Brep kernel from source and
fail. 3.12 is what this repository is developed and tested on.

Five runtime dependencies, all from PyPI, all installed for you by
`pip install compas_tf`:

| Package | What it is for |
| --- | --- |
| `compas >= 2` | Geometry, datastructures, serialization. `compas.json_load` is the entry point to every model. |
| `compas_model` | Elements, the element tree, the interaction graph, the contact algorithms. |
| `shapely` | The 2D polygon overlap behind contact detection. |
| `compas_manifold >= 0.1.0` | Mesh booleans - the cuts and unions that build an element's geometry. Only needed when *building* a model; a baked one never calls it. |
| `compas_occt >= 0.1.18` | The Brep/STEP kernel. `get_brep()`, `to_step()`, and the Brep scene object the viewer draws. |

Nothing else is required to read a model, walk its groups, extract a bay or
write STEP.

## Install the package

```bash
pip install compas_tf
```

That is all a *reader* needs - the geometry in a written model is baked, so no
boolean backend is involved on load.

Check it:

```bash
python -c "import compas_tf; from compas_tf import TFModel; print(compas_tf.__version__)"
```

## Install this repository from scratch

For working on the package itself, or running the examples.

**1. Get the source.**

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
```

**2. Make an environment.** With [uv](https://docs.astral.sh/uv/getting-started/installation/),
which will fetch Python 3.12 itself if you do not have it:

```bash
uv venv .venv --python 3.12
source .venv/Scripts/activate      # macOS / Linux: source .venv/bin/activate
```

!!! warning "Use `uv pip`, not plain `pip`"

    A `uv venv` contains no `pip` of its own. `python -m pip` inside it fails
    with `No module named pip`, and a bare `pip install` silently lands in
    whatever *other* environment is first on your `PATH`. Every install command
    below is therefore `uv pip`.

**3. Install the dependencies and the package.**

```bash
uv pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
uv pip install -e .
```

`-e` is an editable install: the package resolves to `src/compas_tf`, so your
edits take effect with no reinstall.

**4. Check it.**

```bash
python -c "import compas_tf, sys; print(sys.version.split()[0], compas_tf.__version__)"
python -m pytest tests/ -q
```

```text
3.12.12 0.1.9
11 passed
```

With plain `venv` and `pip` instead of uv, the same thing:

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
pip install -e .
```

## Optional: the viewer

The viewer is deliberately **not** a dependency. `compas_tf` never imports it at
module level, so the library works without it and only the drawing does not.
Every example ends in `viewer.show()`, so you need it to run them as written.

```bash
pip install compas_viewer          # or: uv pip install -r requirements-viewer.txt
```

If you draw **Breps** - anything read back from STEP - set the deflection first:

```python
from compas.tolerance import TOL

TOL.lineardeflection = 1.0
```

!!! warning "Do not leave the deflection at its default"

    COMPAS defaults to `0.001`, a 1 micron chord tolerance on a building. The
    twisted loft quads of the ribs and t-sections then tessellate to 2.93M
    triangles in 67 s; at `1.0` it is 19.8k triangles in 2.0 s for the same
    picture - about the 17.0k of the source mesh, i.e. only the flat faces get
    retriangulated. The angular deflection changes neither.

## Optional: the documentation

The docs are [mkdocs-material](https://squidfunk.github.io/mkdocs-material/).

```bash
uv pip install -r requirements-docs.txt
invoke docs      # mkdocs build --strict
invoke serve     # live reload on http://127.0.0.1:8000
```

## Working on it

```bash
invoke lint
invoke test
python tools/run_examples.py
```

`run_examples.py` runs the whole example chain with the viewer window
suppressed, and regenerates everything in `data/`. It is the closest thing to an
integration test this package has - the scenes are built for real, so a broken
geometry or an unregistered scene object still raises. Pass numbers to run only
some of them: `python tools/run_examples.py 19 20 21`.

## In a project of your own

The usual case: a project that *consumes* a model rather than developing this
package.

```bash
uv init my-project
cd my-project
uv add compas_tf
uv run my_script.py
```

[Set up a project](examples/040_project_setup.md) walks through a complete one,
file by file.
