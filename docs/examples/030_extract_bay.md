# Extract one column and one cantilever

The model read on the first page is a nest of named groups, and any of them can
be lifted out as a model of its own. One column plus the cantilever it carries
is the unit that gets assembled on site.

```python
--8<-- "examples/example_model_21_extract_bay.py"
```

```text
77 of 237 elements, 208 contacts
columns_model  (2 parts)
  column_model_0  (2 parts)
floor_model  (59 parts)
  quarters_model  (38 parts)
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
    quarter_model_1  (2 parts)
    quarter_model_3  (2 parts)
  connectors  (19 parts)
  oculus_model  (2 parts)
connectors  (2 parts)
outer_rib_connectors  (2 parts)
connector_cylinders  (12 parts)
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

The two named groups hold the column, its support and the cantilever - 36
elements and no fasteners at all, because the connectors, the outer-rib
connectors and the dowels each live in their own top-level group. `neighbors=True`
brings them in:

```text
neighbors=False    36 elements, 125 contacts
neighbors=True     77 elements, 208 contacts
```

The 41 it adds arrive by two different routes, and the difference matters.

**By the graph** - every element that interacts with one inside, walking **one
step out only**, since following the graph again from what it just pulled in
would drag the whole model along one edge at a time. That is 2 `connector_*`, 3
`connector_wedge_*`, 2 `outer_rib_connector_*`, and 6 plates of
`quarter_model_1` / `quarter_model_3` and the oculus that reach across the seam.
Those last are whole groups in the tree and 2-part fragments in the bay: right
for "what touches this bay", not for "what this bay is made of".

**By their boxes** - 16 `ConnectorCylinderElement` and 12 `DowelCylinderElement`.
These have no graph edge at all, so no walk can reach them: the contact search
that built the graph was told to skip them
(`skip=involving(DowelCylinderElement, ConnectorCylinderElement)`) because a
faceted shaft touches its own hole once per facet, which was 74% of the contacts
and no structural information. Geometry is the only signal left for them, so an
element with no interactions is included when its bounding box lands inside the
bay. That test is applied to those elements *only* - on elements the graph does
describe it would be far too loose, one diagonal rib's box swallowing half the
floor.

One consequence to know: a cylinder is included when it sits in the bay's
timber, not when its parent connector does. `connector_wedge_7` is outside the
bay but its pockets are cut into `inner_beams_0`, so its cylinders come along.
For the pocket that is correct; for a parts list, filter by the parent.

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
