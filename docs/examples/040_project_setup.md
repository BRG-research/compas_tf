# Set up a project of your own

Reading a model needs no clone and no build step - `pip install compas_tf` is
the whole setup. A complete example project is
[compas_tf_example](https://github.com/BRG-research/compas_tf_example).

With [uv](https://docs.astral.sh/uv/getting-started/installation/) (install it
with `winget install --id=astral-sh.uv` on Windows, or
`curl -LsSf https://astral.sh/uv/install.sh | sh` on macOS and Linux):

```bash
uv init my-project
cd my-project
uv add compas_tf
uv add compas_viewer   # only to look at the geometry
```

Or with pip: `python -m venv .venv`, activate it, `pip install compas_tf`.
Either way, Python 3.10 or newer.

Then copy the data files out of the compas_tf repository - anywhere you like,
nothing depends on the layout:

```text
my-project/
  read_model.py
  data/
    cantilevers_baked_model.json      # the model
    cantilevers_baked_model.stp       # the solids
    cantilevers_baked_contacts.stp    # the contact faces
    cantilevers_baked_contacts.json   # which elements each face joins
```

The code is what the pages before this show, unchanged outside the repository.
