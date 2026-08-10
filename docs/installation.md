# Installation

## Stable

Stable releases are on PyPI.

```bash
pip install compas_tf
```

That is all a *reader* needs. Loading a model, walking its groups, extracting a
bay and writing STEP all work off this one install - the geometry in a written
model is baked, so no boolean backend is involved. The requirements pull in
`compas`, `compas_model`, `shapely`, `compas_manifold` (mesh booleans) and
`compas_occt` (the Brep/STEP kernel).

Python 3.10 or newer. The package declares `>=3.9`, but the wheels of the Brep
kernel start at 3.10.

## Viewer

The viewer is optional and deliberately not a dependency: `compas_tf` never
imports it, so the library works without it and only the drawing does not.

```bash
pip install compas_viewer
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

## In a project of your own

The usual case: a project that *consumes* a model rather than developing this
package. With [uv](https://docs.astral.sh/uv/):

```bash
uv init my-project
cd my-project
uv add compas_tf
uv run my_script.py
```

[Set up a project](examples/040_project_setup.md) walks through a complete one,
file by file.

## Latest

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
pip install -e .
```

## Development

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/Scripts/activate      # macOS / Linux: source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
uv pip install -e .
```

Use `uv pip`, not plain `pip`: a `uv venv` has no pip of its own, so a bare
`pip install` lands in the wrong environment.

Then:

```bash
invoke lint
invoke test
python tools/run_examples.py
```

`run_examples.py` runs the whole example chain with the viewer window
suppressed, and regenerates everything in `data/`. It is the closest thing to an
integration test this package has - the scenes are built for real, so a broken
geometry or an unregistered scene object still raises.

The documentation is [mkdocs-material](https://squidfunk.github.io/mkdocs-material/):

```bash
pip install -r requirements-docs.txt
mkdocs serve
```
