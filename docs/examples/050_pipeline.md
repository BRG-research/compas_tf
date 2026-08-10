# The full pipeline

The other pages read a finished model. This is where it comes from.

The examples in `examples/` are a chain: each reads the JSON the one before it
wrote, so they only make sense in order. Run the whole thing with

```bash
python tools/run_examples.py            # all of them
python tools/run_examples.py 8 9 10     # only those, by number
```

which regenerates everything in `data/`. Every example ends in `viewer.show()`;
the runner suppresses the window but still builds the scene, so a broken
geometry or an unregistered scene object raises.

## Building up

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

`cantilevers_model.json` at step 8 is the whole building: 237 elements, four
quarters on four columns, everything cut and bolted.

## Fabrication

Examples 12, 13, 14 and 16 read `cantilevers_model.json` and take one part of it
apart - a column, the oculus, a quarter's beds, a quarter's frame, the
connectors - laying the pieces out flat. 13, 14 and 16 write a
`*_fab_model.json`; 12 writes only the Rhino bundle `column_fab_rhino.json`.

## Writing it out

`18_write_model_and_brep` is the hinge. It reads `cantilevers_model.json`,
bakes it - every boolean evaluated once and stored on the element - searches
every element pair for contacts on the Brep faces, and writes the four files the
reading examples open:

```text
cantilevers_baked_model.json      3.9 MB
cantilevers_baked_model.stp      19.5 MB
cantilevers_baked_contacts.stp    4.7 MB
cantilevers_baked_contacts.json   201 KB
```

This is the only step here that runs a boolean, and the only one that needs a
boolean backend. Everything downstream - [Read the model](010_read_model.md),
[Read the Breps](020_read_brep.md), [Extract a bay](030_extract_bay.md) - just
opens files.
