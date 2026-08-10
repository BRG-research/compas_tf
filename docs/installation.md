# Installation

## Install it

```bash
pip install compas_tf
```

Needs Python 3.10 or newer. That is everything you need to open a model, walk
it, cut a piece out of it and write STEP.

Did it work?

```bash
python -c "import compas_tf; print(compas_tf.__version__)"
```

## Add the viewer

```bash
pip install compas_viewer
```

Optional. Only the drawing needs it - every example ends in `viewer.show()`.

## Get uv

[uv](https://github.com/astral-sh/uv) builds and manages the environment for
you - no activating, no `pip`. Install it once
([full instructions](https://docs.astral.sh/uv/getting-started/installation/)):

=== "Windows"

    ```powershell
    winget install --id=astral-sh.uv -e
    ```

    Or without winget:

    ```powershell
    powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
    ```

=== "macOS / Linux"

    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

    Or `brew install uv`.

Then `uv --version` should answer, and `uv self update` keeps it current.

## Start a project with uv

```bash
uv init my-project
cd my-project
uv add compas_tf
uv run my_script.py
```

`uv add` writes the dependency into `pyproject.toml` and installs it; `uv run`
runs your script in that environment, creating it on the first call.
[Set up a project](examples/040_project_setup.md) is a complete one, file by
file.

## Work on this repository

Here you want an environment you stay inside, so make one and activate it:

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf

uv venv .venv --python 3.12
source .venv/Scripts/activate      # Linux / macOS: source .venv/bin/activate

uv pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
uv pip install -e .
```

!!! warning "Inside a `uv venv`, type `uv pip`, never `pip`"

    A `uv venv` has no `pip` in it - `which pip` finds nothing, and `python -m
    pip` says `No module named pip`. A bare `pip install` therefore falls
    through to some *other* Python on your `PATH` and installs there, where this
    project will never see it. `uv pip install` always targets the activated
    environment.

`-e` means editable: the package resolves to `src/compas_tf`, so your edits take
effect with no reinstall.

Did it work?

```bash
python -m pytest tests/ -q          # 11 passed
python tools/run_examples.py        # 21/21 ok
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

With the environment above activated:

```bash
uv pip install -r requirements-docs.txt

invoke serve      # live at http://127.0.0.1:8000, reloads as you edit
invoke docs       # one-off build into site/, fails on a broken link
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
