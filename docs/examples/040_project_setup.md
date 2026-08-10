# Set up a project of your own

The three pages before this run inside the compas_tf repository, where
everything is already installed. This is the same code in a project that only
*consumes* the model - installed from PyPI, no clone, no build step. The
complete version is
[compas_tf_example](https://github.com/BRG-research/compas_tf_example).

Four files, and one of them is data.

```text
my-project/
  pyproject.toml
  read_model.py
  read_brep.py
  extract_bay.py
  data/
    cantilevers_baked_model.json
    cantilevers_baked_model.stp
```

## Start it

With [uv](https://docs.astral.sh/uv/getting-started/installation/):

```bash
uv init my-project
cd my-project
uv add compas_tf
```

Which gets you a `pyproject.toml` like this - the viewer left as an extra,
because reading a model needs nothing but `compas_tf`:

```toml
[project]
name = "my-project"
version = "0.1.0"
requires-python = ">=3.10,<3.13"
dependencies = [
    "compas_tf>=0.1.9",
]

[project.optional-dependencies]
viewer = ["compas_viewer"]

[tool.uv]
package = false
```

`uv run read_model.py` creates the environment and installs on first use.
`uv sync --extra viewer` adds the viewer when you want to look at the geometry
rather than measure it.

With pip instead: `python -m venv .venv`, activate it, `pip install compas_tf`.

## Get the data

The files come out of `example_model_18_write_model_and_brep.py` in the
compas_tf repository. Copy them into `data/` - or point at them wherever they
are, nothing depends on the layout.

## Read it

```python
import pathlib
from collections import Counter

import compas

MODEL_FILE = pathlib.Path(__file__).parent / "data" / "cantilevers_baked_model.json"

model = compas.json_load(MODEL_FILE)

elements = list(model.geometry_elements())
contacts = list(model.contacts())
area = sum(contact.polygon.area for contact in contacts)

print(f"{len(elements)} elements, {len(contacts)} contacts, {area / 1e6:.2f} m2")

for kind, count in Counter(type(element).__name__ for element in elements).most_common():
    print(f"{count:5d}  {kind}")
```

```text
237 elements, 733 contacts, 20.92 m2
  145  PlateElement
   32  ConnectorCylinderElement
   32  DowelCylinderElement
    8  ConnectorWedgeElement
    8  ConnectorElement
    4  SupportElement
    4  ColumnElement
    4  OuterRibConnectorElement
```

The solids, with no compas_tf concepts involved beyond the import:

```python
from compas_occt.brep import OCCBrep

breps = OCCBrep.from_step(STEP_FILE).solids
print(f"{sum(brep.is_solid for brep in breps)}/{len(breps)} closed solids")
```

And a bay out of the middle of it:

```python
bay = model.find_groups_with_names(["column_model_0", "quarter_model_0"], neighbors=True)
compas.json_dump(bay, "data/bay_model.json")
```

## One thing to check

`compas_tf` ships OBJ meshes as package data - `SupportElement` and
`OuterRibConnectorElement` read them at construction time, so deserializing a
model containing one needs them present inside the *installed* package, not just
in the source tree. A project like this one is the only thing that exercises
that path, which is exactly why it exists: it caught the bug when the package
data was missing from the wheel.
