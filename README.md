# compas_tf

Repository for the timber floor development.

<img width="2560" height="1440" alt="Screenshot from 2025-12-08 19-32-04" src="https://github.com/user-attachments/assets/09d2c68b-67c3-489d-9ef1-2f2fcbd17851" />
<img width="2560" height="1440" alt="image" src="https://github.com/user-attachments/assets/bad7b42c-1998-4b0e-ae74-81e7ee667522" />
<img width="2494" height="1568" alt="Screenshot from 2025-12-10 19-05-58" src="https://github.com/user-attachments/assets/496f0dd5-b06e-482c-b3a1-7ab65b1d3051" />
<img width="2494" height="1568" alt="Screenshot from 2025-12-10 19-06-33" src="https://github.com/user-attachments/assets/ab1e5a47-9f85-4785-ad50-eca10c7dbd6e" />


## Quick Setup (Git Bash, Windows)

```bash
cd /c/brg/compas_tf
source .venv/Scripts/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
uv pip install -e .
```

## Quick Setup (macOS / Linux)

```bash
cd /Users/petras/brg/2_code/compas_tf
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
uv pip install -e ".[dev]" compas_model compas_viewer
```

> **Always use `uv pip`, not plain `pip`.** A `uv venv` is created **without**
> pip inside it, so a bare `pip install` falls back to your system/Anaconda pip
> and installs into the wrong environment — `import compas` then fails with
> `ModuleNotFoundError` even though the install "succeeded". `uv pip` installs
> into the activated `.venv` directly.

## Run

```bash
python examples/model.py
```

## Orient Parts to 2D (nesting)

Lay the unique fabrication parts flat onto the XY plane and arrange them in a
grid with [`compas_nest`](https://github.com/petrasvestartas/compas_nest). The
floor has four identical quarters, so only one quarter, the oculus and one
column are oriented:

```bash
uv pip install compas_nest
python examples/example_2_floor_model_booleans.py   # produces data/floor_model_booleans.json
python examples/example_3_orient_to_2d.py
```

## Fresh Install

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/bin/activate          # Windows (Git Bash): source .venv/Scripts/activate
uv pip install -r requirements.txt
uv pip install -r requirements-dev.txt
uv pip install -e ".[dev]" compas_model compas_viewer
```

## Pull All Branches

`git fetch` only downloads remote-tracking refs; it does not create local
branches. Run the following to download everything and create a local branch
for every branch on GitHub:

```bash
git fetch --all
for b in $(git branch -r | grep -v '\->' | grep -v 'HEAD' | sed 's|origin/||'); do
  git branch --track "$b" "origin/$b" 2>/dev/null
done
git branch
```

Switch to a branch and update it:

```bash
git checkout column_head
git pull
```

## References

- [compas_nest](https://github.com/petrasvestartas/compas_nest) — 2D nesting /
  packing of part outlines (`pack`, `opennest_collision`, `nfp`). Used by
  `examples/example_3_orient_to_2d.py`.
