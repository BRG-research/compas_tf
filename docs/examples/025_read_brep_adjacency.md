# Read the Breps with their adjacency

The page before draws the STEP files. This one asks them what is connected to
what, which needs the third file: the JSON sidecar.

![One element's joints highlighted in red across the ghosted building](../_images/example_model_22_read_brep_adjacency.png)
/// caption
The 17 contacts on `inner_ribs_0_0` in red, the rest ghosted behind them. The
sidecar is what turns "face 412" into "this rib meets that bed".
///

```python
--8<-- "examples/example_model_22_read_brep_adjacency.py"
```

```text
237 solids, 733 contact faces, 733 adjacency records
169 elements over 585 pairs, 20.92 m2 of interface

biggest joints:
   0.344 m2  inner_beams_0_1 - connector_wedge_3  (3 faces)
   0.344 m2  inner_beams_2_2 - connector_wedge_3  (3 faces)
   0.344 m2  inner_beams_0_0 - connector_wedge_0  (3 faces)
   0.344 m2  inner_beams_2_1 - connector_wedge_0  (3 faces)
   0.344 m2  inner_beams_0_2 - connector_wedge_5  (3 faces)

by type:
  12.818 m2  PlateElement - PlateElement
   4.459 m2  ConnectorWedgeElement - PlateElement
   1.106 m2  ColumnElement - PlateElement
   1.101 m2  ConnectorElement - PlateElement
   0.895 m2  ColumnElement - ConnectorElement
   0.541 m2  OuterRibConnectorElement - PlateElement

17 contacts on inner_ribs_0_0, the most connected element
```

A record per face, in the same order the faces were written:

```python
{"index": 0, "a": "beds_0_0_0", "b": "wedges_inner_beams_0_0",
 "a_type": "PlateElement", "b_type": "PlateElement",
 "a_guid": "c46c8acc-...", "b_guid": "3098146e-...",
 "area": 39851.67}
```

Three things worth knowing:

**Index is the only join.** Equal counts is the one check that the two files
came from the same run - pair a STEP with the wrong sidecar and every name lands
on the wrong face, silently.

**The names are element names.** The solids stay anonymous; nothing here says
which of the 237 is `beds_0_0_0`. For that, read the JSON model.

**A pair is not a face.** 585 pairs carry 733 faces, so group by `(a, b)` before
ranking or one joint split in three sorts below a single big one.
