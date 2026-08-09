# compas_tf

## Install

Prerequisites: [git](https://git-scm.com/downloads), [uv](https://docs.astral.sh/uv/getting-started/installation/), Python 3.12.

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/Scripts/activate      # macOS / Linux: source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt
uv pip install -e .
```

> Use `uv pip`, not plain `pip` — a `uv venv` has no pip of its own, so a bare
> `pip install` lands in the wrong environment.

`compas_viewer` is installed from the GitHub fork
[`petrasvestartas/compas_viewer`](https://github.com/petrasvestartas/compas_viewer)
(group-visibility cascade + signal-safe live scene reload used by
`examples/example_0_watch_viewer.py`). To work on the viewer itself, clone that
repo and `uv pip install -e path/to/compas_viewer` over the top.

All mesh booleans (difference, union, chain) use **`compas_manifold`**, which
installs automatically with the requirements.

## Run

Each example opens its own viewer. For a faster loop, launch the persistent
watcher **first** — then every example only writes its scene and the watcher
live-reloads it (geometry + sidebar tree), keeping the camera:

```bash
python examples/example_0_watch_viewer.py           # launch once, leave open
python examples/example_2_floor_model_booleans.py   # build floor model, run booleans
python examples/example_3_orient_to_2d.py           # nest parts to 2D (uv pip install compas_nest)
```

## References

- [compas_nest](https://github.com/petrasvestartas/compas_nest) — 2D nesting of part outlines.
