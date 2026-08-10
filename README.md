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

bay = model.find_groups_with_names(["column_model_0", "quarter_model_0"], neighbors=True)
bay.to_step("bay_0.stp")
```

The geometry in a written model is *baked* — every boolean already evaluated and
stored on the element — so it loads in 0.60 s with no boolean backend involved.
[`compas_tf_example`](https://github.com/BRG-research/compas_tf_example) is a
standalone project that does nothing but read one.

## Develop it

Prerequisites: [git](https://git-scm.com/downloads),
[uv](https://docs.astral.sh/uv/getting-started/installation/), Python 3.12.

```bash
git clone https://github.com/BRG-research/compas_tf.git
cd compas_tf
uv venv .venv --python 3.12
source .venv/Scripts/activate      # macOS / Linux: source .venv/bin/activate
uv pip install -r requirements.txt -r requirements-dev.txt -r requirements-viewer.txt
uv pip install -e .
```

> Use `uv pip`, not plain `pip` — a `uv venv` has no pip of its own, so a bare
> `pip install` lands in the wrong environment.

Mesh booleans go through **`compas_manifold`**; Breps and STEP through
**`compas_occt`**. Both install with the requirements. `compas_viewer` is
optional — the library never imports it.

```bash
invoke lint
invoke test
invoke docs
python tools/run_examples.py     # the whole example chain, viewer suppressed
```

## Examples

`examples/` is a chain: each reads the JSON the one before it wrote.
`example_model_18_write_model_and_brep.py` is the hinge — it bakes the model,
finds every contact, and writes the four files the last three read:

| Example | Does |
| --- | --- |
| `example_model_19_read_model.py` | reads the model back — elements, tree, contacts |
| `example_model_20_read_brep.py` | reads the STEP — 237 closed solids |
| `example_model_21_extract_bay.py` | pulls one column + one quarter out as its own model |

## References

- [compas_nest](https://github.com/petrasvestartas/compas_nest) — 2D nesting of part outlines.
