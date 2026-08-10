# Extract one column and one cantilever

The model read on the first page is a nest of named groups, and any of them can
be lifted out as a model of its own. One column plus the cantilever it carries
is the unit that gets assembled on site.

![One bay lifted out of the building: a column carrying one quarter](../_images/example_model_21_extract_bay.png)
/// caption
The 46 elements that make a bay, and nothing else - the quarter fans out from
the column it stands on, cut off along the seams where the next quarters would
begin. Four groups in the scene tree: `columns_model` and `floor_model` are the
two that were asked for by name, `connectors` and `connector_cylinders` are the
hardware `neighbors=` found.
///

```python
--8<-- "examples/example_model_21_extract_bay.py"
```

```text
bay_0: 46 of 237 elements, 143 of 733 contacts
    34 of  145  PlateElement
     8 of   32  DowelCylinderElement
     2 of    8  ConnectorElement
     1 of    4  SupportElement
     1 of    4  ColumnElement
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
connectors  (2 parts)
connector_cylinders  (8 parts)
```

The 34 plates are exactly `quarter_model_0`'s 34: no fragment of a neighbouring
quarter, no oculus. The fastener rows are the other thing to read - the bay
takes its own share of hardware, not all of it.

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
connectors and the dowels each live in their own top-level group. `neighbors=`
brings them in:

```text
neighbors=False        36 elements, 125 contacts
neighbors=FASTENERS    46 elements, 143 contacts
neighbors=True         77 elements, 208 contacts
```

**Pass the types, not `True`.** `True` admits anything that touches the
selection, and across the seam that is `outer_ribs_1_1`, `outer_ribs_0_3`,
`inner_beams_2_1`, `inner_beams_0_3` and two oculus plates - elements that touch
this bay but are no part of it. They arrive as 2-part fragments of
`quarter_model_1`, `quarter_model_3` and `oculus_model`: right for "what touches
this bay", wrong for "what this bay is made of". A tuple of element types (or a
predicate) admits only the hardware, and the bay comes out as exactly its two
groups plus 10 fasteners.

The list is also where you say what *kind* of hardware the bay means. Only the
column connectors and their dowels are named here, which is what mounts this
cantilever on its column. The wedges and their bolts (`ConnectorWedgeElement`,
`ConnectorCylinderElement`) are inner-beam hardware and `OuterRibConnectorElement`
joins this quarter's ribs to the next quarter's, so all three stay out - 18
elements' worth: 3 wedges, their 13 bolts, 2 rib connectors. Put a type back in
the tuple and it comes back with it.

The 10 that stay arrive by two different routes, and the difference matters.

**By the graph** - every element that interacts with one inside, walking **one
step out only**, since following the graph again from what it just pulled in
would drag the whole model along one edge at a time. That is the 2
`connector_*`.

**By their boxes** - the 8 `DowelCylinderElement`, 4 to a connector.
These have no graph edge at all, so no walk can reach them: the contact search
that built the graph was told to skip them
(`skip=involving(DowelCylinderElement, ConnectorCylinderElement)`) because a
faceted shaft touches its own hole once per facet, which was 74% of the contacts
and no structural information. Geometry is the only signal left for them, so an
element with no interactions is included when its bounding box lands inside the
bay. That test is applied to those elements *only* - on elements the graph does
describe it would be far too loose, one diagonal rib's box swallowing half the
floor.

The two passes compound, which is the other reason to filter. Under `True` the
oculus plates arrive by contact, and `connector_wedge_7`'s three cylinders then
arrive because their boxes overlap `oculus_3` - a wedge outside the bay
contributing cylinders to it, one admission having widened what the box pass
tests against. Naming the types stops the cascade at the first step.

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
