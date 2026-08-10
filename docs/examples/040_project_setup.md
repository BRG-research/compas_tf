# Set up a project of your own

The pages before this run inside the compas_tf repository. This is the same code
from a project that only *consumes* the model: installed from PyPI, no clone, no
build step. A complete one is
[compas_tf_example](https://github.com/BRG-research/compas_tf_example).

```bash
uv init my-project
cd my-project
uv add compas_tf
```

With pip instead: `python -m venv .venv`, activate it, `pip install compas_tf`.
Either way it needs Python 3.10 or newer.

`compas_viewer` is not a dependency - add it only to look at the geometry:

```bash
uv add --optional viewer compas_viewer
uv sync --extra viewer
```

Then copy the data files out of the compas_tf repository - or point at them
wherever they are, nothing depends on the layout:

```text
my-project/
  read_model.py
  data/
    cantilevers_baked_model.json      # the model
    cantilevers_baked_model.stp       # the solids
    cantilevers_baked_contacts.stp    # the contact faces
    cantilevers_baked_contacts.json   # which elements each face joins
```

The code is what the three pages before this show - `compas.json_load` for the
model, `OCCBrep.from_step` for the solids, `find_groups_with_names` for a bay.
Nothing changes outside the repository.
