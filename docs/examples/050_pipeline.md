# The full pipeline

The other pages read a finished model. This is where it comes from: a chain of
examples, each reading the JSON the one before it wrote.

```bash
python tools/run_examples.py            # all of them
python tools/run_examples.py 8 9 10     # only those, by number
```

The runner suppresses the viewer window but still builds the scene, so broken
geometry still raises, and it rewrites everything in `data/`.

| Example | Reads | Writes |
| --- | --- | --- |
| `1_floorguide` | the parameters | `floorguide.json` |
| `2_column_model` | `floorguide` | `column_model.json` |
| `3_columns_model` | `floorguide`, `column_model` | `columns_model.json` |
| `4_quarters` | `floorguide` | `quarter_model`, `quarters_model` |
| `5_oculus` | `floorguide` | `oculus_model.json` |
| `6_contacts_floor` | `quarters_model`, `oculus_model` | `floor_model.json` |
| `7_contacts_cantilever` | `quarter_model`, `column_model` | `cantilever_model.json` |
| `8_contacts_cantilevers` | `floor_model`, `columns_model` | `cantilevers_model.json` |
| `9_wedge_connector` | - | the wedge connector on its own |
| `10_shoring` | `floorguide` | `shoring_model.json` |
| `11_full` | `cantilever_model`, `shoring_model` | `full_model.json` |
| `12`, `13`, `14`, `16` | `cantilevers_model` | the parts laid out flat for fabrication |

Step 8 is the whole building: 237 elements, four quarters on four columns,
everything cut and bolted.

`18_write_model_and_brep` is the hinge. It bakes that model - every boolean
evaluated once and stored - searches every element pair for contacts on the Brep
faces, and writes the four files the reading pages open:

```text
cantilevers_baked_model.json      3.9 MB
cantilevers_baked_model.stp      19.5 MB
cantilevers_baked_contacts.stp    4.7 MB
cantilevers_baked_contacts.json   201 KB
```

It is the only step that runs a boolean, and the only one that needs a boolean
backend. Everything downstream just opens files.
