# compas_tf

Timber floor development. A parametric model of a timber floor — columns, ribs,
beds, t-sections, oculus and the connectors that hold them together — that you
can build, cut, measure, extract from and hand to a shop as STEP.

**Documentation: <https://brg-research.github.io/compas_tf/>**

## Use it

```bash
pip install compas_tf
```

```python
import compas

model = compas.json_load("cantilevers_baked_model.json")

print(len(list(model.geometry_elements())))   # 237
print(len(list(model.contacts())))            # 733
```

A written model is *baked* — every boolean already evaluated and stored on the
element — so it loads in 0.60 s with no boolean backend involved.
[`compas_tf_example`](https://github.com/BRG-research/compas_tf_example) is a
standalone project that does nothing but read one.

## Develop it

Needs [git](https://git-scm.com/downloads),
[uv](https://docs.astral.sh/uv/getting-started/installation/) and Python 3.10+.

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/Scripts/activate      # macOS / Linux: source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
uv pip install -e .
```

> `uv pip`, not plain `pip` — a `uv venv` has no pip of its own, so a bare
> `pip install` lands in the wrong environment.

```bash
invoke lint
invoke test
python tools/run_examples.py     # all 21 examples, viewer suppressed
```

## Work on another branch

A fresh clone gives you `main` and nothing else — the other branches exist on
GitHub but are not yet on your machine. `git fetch` downloads them; `git switch`
gives you a local branch that tracks one.

```bash
git fetch origin --prune         # download every branch GitHub has, drop stale ones
git branch -r                    # list what is on origin
git switch quantities            # create local `quantities` tracking origin/quantities
```

`git switch <name>` with no other flags is enough when exactly one remote has a
branch of that name — git creates the local branch and sets it to track. Spell
it out when you want a different local name, or when the shorthand fails:

```bash
git switch -c quantities --track origin/quantities
```

From then on it is an ordinary branch: `git pull` to update it, `git push` to
publish, `git switch main` to go back. `git branch -vv` shows every local branch
and which remote branch it tracks.

Two things to know before switching:

- **Commit or stash first.** `git switch` refuses to move if uncommitted changes
  would be overwritten. `git status` tells you.
- **`data/` is regenerated, not shared.** The example outputs are gitignored, so
  switching branches leaves stale JSON behind and the file dates will not match
  the branch. Re-run `python tools/run_examples.py` after switching.

The environment is per-clone, not per-branch: `.venv` and the editable install
survive a `git switch`. Redo the `uv pip install` steps only when a branch
changes `requirements*.txt` or `pyproject.toml`.

## Examples

`examples/` is a chain: each reads the JSON the one before it wrote.
`example_model_18_write_model_and_brep.py` is the hinge — it bakes the model,
finds every contact, and writes the four files the readers open:

| Example | Does |
| --- | --- |
| `example_model_19_read_model.py` | the model back — elements, tree, contacts |
| `example_model_20_read_brep.py` | the STEP — 237 closed solids |
| `example_model_21_extract_bay.py` | one column + one cantilever as its own model |
| `example_model_22_read_brep_adjacency.py` | what touches what, from STEP + sidecar |

## References

- [compas_nest](https://github.com/petrasvestartas/compas_nest) — 2D nesting of part outlines.
