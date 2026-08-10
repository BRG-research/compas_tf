# Extract one column and one cantilever

The model read on the first page is a nest of named groups, and any of them can
be lifted out as a model of its own. One column plus the cantilever it carries
is the unit that gets assembled on site.

```python
--8<-- "examples/example_model_21_extract_bay.py"
```

```text
36 of 237 elements, 125 contacts
columns_model  (2 parts)
  column_model_0  (2 parts)
floor_model  (34 parts)
  quarters_model  (34 parts)
    quarter_model_0  (34 parts)
      beds_0  (18 parts)
        beds_0_0  (6 parts)
        beds_1_0  (6 parts)
        beds_2_0  (6 parts)
      tsections_0  (6 parts)
      outer_ribs_0  (2 parts)
      inner_ribs_0  (2 parts)
      wedges_inner_beams_0  (3 parts)
      inner_beams_0  (3 parts)
```

The result is a model like any other: it writes to JSON, exports to STEP, and
draws. The source is untouched, and the copy is independent - fresh guids - so
it can be placed and merged back alongside the original.

Note what the tree shows: the bay is not a bag of parts. Every group keeps its
place, so it is still `floor_model/quarters_model/quarter_model_0/beds_0/...`,
pruned to what the bay contains. Mirror that tree into the viewer rather than
flattening it, or the structure is lost in the picture even though it is in the
model.

## Both groups at once

`find_groups_with_names` takes a list, and that is the point. The contacts
*between* the column and the cantilever it carries survive only if the two come
out together. Extracting each with `find_group_with_name` and merging the
results keeps every contact internal to each group and drops exactly the joint
that connects them.

Each group keeps its ancestor chain, pruned to what was asked for, so
`quarter_model_0` comes back at `floor_model/quarters_model/quarter_model_0` and
the transformations along the way still apply - the bay stays where it is in the
building.

The pairing is the model's, not a guess: `column_0` has contacts with
`quarter_model_0` plates and with nothing else in the floor. Ask the graph which
quarter a column touches rather than assuming the indices line up.

## `neighbors`

The fasteners live in their own top-level groups, not inside the bay, so the 36
elements above are the column, its support and the cantilever - and no
connectors. `neighbors=True` adds every element that interacts with one inside,
walking **one step out only** - following the graph again from what it just
pulled in would drag the whole model along one edge at a time:

```text
neighbors=False    36 elements, 125 contacts
neighbors=True     49 elements, 208 contacts
```

It is a *graph* walk, and that is the thing to know before using it here. The
contact search that built this graph was told to skip the fasteners' dowels
(`skip=involving(DowelCylinderElement, ConnectorCylinderElement)`), so no edge
in the model touches a cylinder. `neighbors=True` therefore brings in
`connector_wedge_0`, `connector_0` and the outer-rib connectors *without* the 21
cylinders that belong to them, and it brings in the 4 plates of
`quarter_model_1` / `quarter_model_3` that reach across the seam - whole groups
in the tree, 2-part fragments in the bay. Both are right for "what interacts
with this bay" and wrong for "what this bay is made of", which is why the
example asks for the hierarchy units and nothing else.

## The groups you can name

```text
floor_model                    185 parts
  quarters_model               136
    quarter_model_0 .. _3       34 each
      beds_0, tsections_0, outer_ribs_0, inner_ribs_0,
      wedges_inner_beams_0, inner_beams_0
  oculus_model                   9
  connectors                    40
columns_model                    8
  column_model_0 .. _3           2 each
connectors                       8
connector_cylinders             32
outer_rib_connectors             4
```

Printed from the tree with:

```python
from compas_model.elements import Group

for element in model.elements():
    if isinstance(element, Group):
        print(element.name)
```

A name that matches no group raises `ModelElementNotFound` rather than quietly
returning the ones that did match.
