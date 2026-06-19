# compas_tf

Timber floor development.

<img width="2560" height="1440" alt="floor model" src="https://github.com/user-attachments/assets/09d2c68b-67c3-489d-9ef1-2f2fcbd17851" />

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

Boolean backends install automatically: **`compas_manifold`** (differences) and
**`compas_cgal`** (unions + fallback).

## Run

```bash
python examples/example_2_floor_model_booleans.py   # build floor model, run booleans, open viewer
python examples/example_3_orient_to_2d.py           # nest parts to 2D (uv pip install compas_nest)
```

## References

- [compas_nest](https://github.com/petrasvestartas/compas_nest) — 2D nesting of part outlines.
