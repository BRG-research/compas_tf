# Tutorial

This page is the vocabulary. The [examples](examples/010_read_model.md) are the
same material as runnable scripts; read this once and those will make sense.

## The model

A `TFModel` is a [compas_model](https://github.com/compas-dev/compas_model)
model: a **tree** of elements and a **graph** of interactions between them.

The tree is the building's table of contents. Nothing structural is implied by
it - it is how you find things and how transformations accumulate:

```text
floor_model                                185 parts
  quarters_model                           136
    quarter_model_0 .. quarter_model_3      34 each
      beds_0                                18   3 rows of 6
      tsections_0                            6
      outer_ribs_0                           2
      inner_ribs_0                           2
      inner_beams_0                          3
      wedges_inner_beams_0                   3
  oculus_model                               9
  connectors                                40
columns_model                                8   4 x (column + support)
  column_model_0 .. column_model_3           2 each
connectors                                   8
connector_cylinders                         32
outer_rib_connectors                         4
```

237 elements in all, joined by 733 contacts. A quarter is 34 of them and a bay -
a quarter with the column it stands on and the hardware between them - is 46.

The interior nodes are `Group` elements; the leaves carry geometry.
`model.elements()` yields both, `model.geometry_elements()` only the leaves.

The graph is what touches what. Each edge can hold **contacts** (the shared face
between two elements) and **modifiers** (one element cutting another).

## The elements

Every element type in this package derives from `TFElement`, which adds one
thing to the compas_model element: its geometry survives serialization. The
cast:

| Element | What it is |
| --- | --- |
| `PlateElement` | A plate lofted between two outlines. Ribs, beds, t-sections, inner beams and the oculus are all plates - 145 of the 237 elements in the cantilevers model. |
| `ColumnElement` | A column, with the capitel added and the head cut by features. |
| `SupportElement` | The steel base under a column, read from a bundled OBJ. |
| `ConnectorElement`, `ConnectorWedgeElement`, `ConnectorCylinderElement`, `ConnectorBoxElement`, `DowelCylinderElement` | The fasteners, and the shapes that cut their pockets. |
| `SchoringElement`, `TowerElement` | Shoring for assembly. |

`FloorGuide` sits behind all of them: one parametric object holding the grid,
the column head size, the rib and bed thicknesses, the rise and the oculus size,
from which the plates of a quarter are generated. Change `size_grid_x` and
everything downstream moves.

## Features, and why baking matters

An element's geometry is not stored, it is *computed*: a base shape minus (or
plus) its **features** - the capitel union, the connector pockets, the dowel
holes. Loading a model would therefore mean re-running every boolean in it.

`TFModel.bake` runs them once and stores the result on each element, inside the
element's own `__data__`, so it survives `compas.json_dump`:

```python
model.bake()
compas.json_dump(model, "model.json")
```

A baked model loads with **no boolean and no boolean backend**, in 0.60 s for
the 3.9 MB cantilevers file - against 0.09 s for a raw `json.loads` of the same
bytes, so nearly all of it is deserialization. `model.is_baked` says which kind
of file you have, and `TFModel.unbake` throws the stored geometry away and makes
it parametric again.

Mesh booleans go through `compas_manifold`, with `compas_cgal` as a fallback.

## Contacts

A contact is the shared face between two elements: a polygon, a frame, a size,
and any holes in it. `TFModel.compute_contacts_brep` finds them on the **Brep**
faces rather than the mesh faces, and the difference is not cosmetic. After a
boolean the mesh is triangles, so mesh detection returns one physical interface
as several polygons - the column/outer-rib joint splits into 8 - and it silently
loses area, returning 50344 mm² where the true joint is 62632 mm². On
coplanar-merged Brep faces that joint is one polygon of the full area, found
roughly 65x faster.

```python
from compas_tf import involving, ConnectorCylinderElement, DowelCylinderElement

model.compute_contacts_brep(
    minimum_area=1.0,
    clear=True,
    skip=involving(DowelCylinderElement, ConnectorCylinderElement),
)
```

The `skip=` is worth understanding: a faceted dowel shaft touches its own hole
once per facet, which was 2072 of 2805 contacts and carries no structural
information. Dropping the fasteners leaves 733 real interfaces.

Contacts are stored on the graph edges, so they serialize with the model, and
`TFModel.contact_pairs` hands back the two elements as objects, not as names.

## Groups, and pulling one out

Groups are how the model is navigated *and* how it is subdivided. Three methods
do the surgery:

`find_group_with_name`

:   One group as a standalone model. The group node is dropped and its placement
    folded into the new model's transformation, so the contents keep their place
    in the world.

`find_groups_with_names`

:   Several groups at once, keeping their ancestor chain pruned to what was
    asked for. Use this for anything that spans groups - one column *and* the
    quarter it carries - because the contacts **between** the groups only
    survive if the groups come out together. Extracting each separately and
    merging the results keeps every internal contact and drops exactly the joint
    that connects them.

`merge`

:   The inverse: nest a list of models into one, each under a group named after
    it. This is how the big model is assembled in the first place.

`neighbors=True` on the multi-group version also brings in the elements that
belong with the extracted groups but sit outside them - the connectors, the
outer-rib connectors and the dowels all live in their own top-level groups, so a
bay extracted without them has no fasteners. Two passes: every element that
interacts with one inside, walking one step out only (following the graph from
what it just pulled in would drag the whole model along one edge at a time), and
then, for elements with no interaction at all, every one whose bounding box
lands inside the bay. The second pass exists because the contact search skips
the dowels and connector cylinders, which leaves them with no graph edge for the
first pass to follow.

```python
bay = model.find_groups_with_names(
    ["column_model_0", "quarter_model_0"],
    name="bay_0",
    neighbors=True,
)
```

That is 77 elements and 208 contacts out of 237 and 733; without `neighbors` it
is 36 and 125, the difference being the fasteners - 28 of which are cylinders
found by the box pass. The source model is untouched and the copy is independent
- fresh guids, so it can be placed and merged back alongside the original.

## What comes out

Four files, written by `example_model_18_write_model_and_brep.py`:

| File | Size | What it carries |
| --- | --- | --- |
| `cantilevers_baked_model.json` | 3.9 MB | The model. Elements, features, materials, the tree, the graph with the contacts on it. Read with `compas.json_load`. |
| `cantilevers_baked_model.stp` | 19.5 MB | The same geometry as 237 closed solids, coplanar faces merged. No compas_tf concepts at all. Read with `OCCBrep.from_step`. |
| `cantilevers_baked_contacts.stp` | 4.7 MB | One planar face per contact. |
| `cantilevers_baked_contacts.json` | 201 KB | Which two elements each of those faces joins. |

The contacts need the sidecar because **STEP does not carry per-shape names** -
every face reads back as an unnamed face. What it does preserve is their
**order**, so record *i* describes face *i*.

Writing STEP runs `get_brep()` per element: `OCCBrep.from_mesh` followed by a
merge of coplanar edges and faces, so the boolean triangles collapse back into
the modelled faces and a drilled face is ONE face carrying its hole loops. 13730
mesh faces come out as 4779 Brep faces. The angular deflection is pinned at
1e-6 rad rather than OCC's 0.1, because at 0.1 the merge also fuses *nearly*
coplanar faces and flattens the twisted loft quads - the t-sections lost 42% of
their volume. `mesh_to_brep` checks the volume afterwards and keeps the
unsimplified Brep if it moved.
