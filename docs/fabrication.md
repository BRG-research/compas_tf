---
hide:
  - toc
---

# Parts

<!-- The Image column embeds an interactive 3D preview per part
     (assets/o3dv-init.js builds the viewers lazily, click one to expand it).
     The cells hold <span class="online_3d_viewer">, NOT <div> - block HTML
     breaks the markdown table parser. The Script column names the example
     that writes the part's fabrication files to data/fabrication/. Links use
     reference definitions at the bottom of this file, so a row stays one
     short readable line. Run `python tools/print_part_table.py` to see any
     table aligned in the terminal. -->

<div class="part-list" markdown="block">

### Whole model

| Part | Image | Files | Script | Dimensions (mm) | Qty | Material |
| --- | :---: | --- | --- | --- | ---: | --- |
| Full model | <span class="online_3d_viewer" data-model="_models/model_0_preview.obj" camera="9000,-9000,6000,0,0,1507,0,0,1"></span> | [STEP][model-stp] [OBJ][model-obj] [IFC][model-ifc] | [fab_model.py][model-py] | 6000 x 6000 x 3014 | 1 ||

### Column

| Part | Image | Files | Script | Dimensions (mm) | Qty | Material |
| --- | :---: | --- | --- | --- | ---: | --- |
| Column | <span class="online_3d_viewer" data-model="_models/column_0_preview.obj"></span> | [STEP][column-stp] [OBJ][column-obj] [IFC][column-ifc] | [fab_column.py][column-py] | 220 x 220 x 2850 incl. capitel<br>capitel 340 x 340 x 730 | 4 | Spruce |

### Floor quarter

| Part | Image | Files | Script | Dimensions (mm) | Qty | Material |
| --- | :---: | --- | --- | --- | ---: | --- |
| Outer rib | <span class="online_3d_viewer" data-model="_models/outer_ribs_0_0_preview.obj" camera="2500,-2100,1650,291,133,50,0,0,1"></span> | [STEP][outer-rib-stp] [OBJ][outer-rib-obj] [IFC][outer-rib-ifc] | [fab_outer_rib.py][outer-rib-py] | 2780 x 695 x 100 | 8 | Spruce |
| Inner rib | <span class="online_3d_viewer" data-model="_models/inner_ribs_0_0_preview.obj" camera="2500,-2100,1650,291,133,50,0,0,1"></span> | [STEP][inner-rib-stp] [OBJ][inner-rib-obj] [IFC][inner-rib-ifc] | [fab_inner_rib.py][inner-rib-py] | 3018 x 2026 x 60 | 8 | Spruce |
| Inner beam 1 | <span class="online_3d_viewer" data-model="_models/inner_beams_0_0_preview.obj" camera="1550,-1550,1150,0,6,30,0,0,1"></span> | [STEP][beam1-stp] [OBJ][beam1-obj] [IFC][beam1-ifc] | [fab_inner_beam_1.py][beam1-py] | 197 x 1985 x 60 | 4 | Spruce |
| Inner beam 2 | <span class="online_3d_viewer" data-model="_models/inner_beams_1_0_preview.obj" camera="900,-900,650,0,0,39,0,0,1"></span> | [STEP][beam2-stp] [OBJ][beam2-obj] [IFC][beam2-ifc] | [fab_inner_beam_2.py][beam2-py] | 1105 x 1105 x 80 | 4 | Spruce |
| Inner beam 3 | <span class="online_3d_viewer" data-model="_models/inner_beams_2_0_preview.obj" camera="1550,-1550,1150,6,0,30,0,0,1"></span> | [STEP][beam3-stp] [OBJ][beam3-obj] [IFC][beam3-ifc] | [fab_inner_beam_3.py][beam3-py] | 1985 x 197 x 60 | 4 | Spruce |
| T-section | <span class="online_3d_viewer" data-model="_models/tsections_0_preview.obj" camera="2500,-1900,1900,-4,565,14,0,0,1"></span> | [STEP][tsection-stp] [OBJ][tsection-obj] [IFC][tsection-ifc] | [fab_tsections.py][tsection-py] | 3230 x 151 x 27 (x6) | 4 | Spruce |
| Bed | <span class="online_3d_viewer" data-model="_models/beds_0_preview.obj" camera="4650,-500,2300,1584,2546,14,0,0,1"></span> | [STEP][bed-stp] [OBJ][bed-obj] [IFC][bed-ifc] | [fab_beds.py][bed-py] | strip 1:<br>586 x 467 x 27<br>757 x 441 x 27<br>1047 x 435 x 27<br>1336 x 431 x 27<br>1626 x 428 x 27<br>1875 x 367 x 27<br>strip 2:<br>687 x 314 x 27<br>521 x 505 x 27<br>696 x 516 x 27<br>887 x 512 x 27<br>1078 x 509 x 27<br>1242 x 436 x 27<br>strip 3:<br>726 x 426 x 27<br>757 x 441 x 27<br>1047 x 435 x 27<br>1336 x 431 x 27<br>1626 x 428 x 27<br>1875 x 367 x 27 | 4 | Spruce |

### Oculus

| Part | Image | Files | Script | Dimensions (mm) | Qty | Material |
| --- | :---: | --- | --- | --- | ---: | --- |
| Oculus plate | <span class="online_3d_viewer" data-model="_models/oculus_plate_0_preview.obj" camera="1812,-518,829,647,647,14,0,0,1"></span> | [STEP][oculus-plate-stp] [OBJ][oculus-plate-obj] [IFC][oculus-plate-ifc] | [fab_oculus.py][oculus-py] | 1294 x 1294 x 27 | 1 | Spruce |
| Oculus side plate | <span class="online_3d_viewer" data-model="_models/oculus_side_plates_0_preview.obj" camera="1896,-675,883,677,544,30,0,0,1"></span> | [STEP][oculus-side-plate-stp] [OBJ][oculus-side-plate-obj] [IFC][oculus-side-plate-ifc] | [fab_oculus.py][oculus-py] | 1354 x 197 x 60 (x4) | 1 | Spruce |
| Oculus side t-section | <span class="online_3d_viewer" data-model="_models/oculus_side_tsections_0_preview.obj" camera="1774,-936,812,634,204,14,0,0,1"></span> | [STEP][oculus-side-tsection-stp] [OBJ][oculus-side-tsection-obj] [IFC][oculus-side-tsection-ifc] | [fab_oculus.py][oculus-py] | 1267 x 27 x 27 (x4) | 1 | Spruce |

### Connectors

| Part | Image | Files | Script | Dimensions (mm) | Qty | Material |
| --- | :---: | --- | --- | --- | ---: | --- |
| Column base | <span class="online_3d_viewer" data-model="_models/support_0_preview.obj" camera="300,-300,200,0,0,75,0,0,1"></span> | [STEP][support-stp] [OBJ][support-obj] [IFC][support-ifc] | [fab_feet.py][support-py] | 140 x 140 x 150 | 4 | Steel, Sherpa Power Base 150402_PB_L-140-C (head plate Ø106 x 12, base plate 140 x 140 x 12 with 4 x Ø15 holes) |
| Inner beam wedge | <span class="online_3d_viewer" data-model="_models/wedges_inner_beams_0_preview.obj" camera="1810,-535,1250,310,966,150,0,0,1"></span> | [STEP][wedge-stp] [OBJ][wedge-obj] [IFC][wedge-ifc] | [fab_inner_beam_wedge.py][wedge-py] | 621 x 536 x 240 (x2)<br>577 x 435 x 300 | 4 | Spruce |
| Column-rib connector | <span class="online_3d_viewer" data-model="_models/connector_0_preview.obj" camera="509,-509,397,0,0,15,0,0,1"></span> | [STEP][connector-stp] [OBJ][connector-obj] [IFC][connector-ifc] | [fab_connectors.py][connectors-py] | 485 x 250 x 30 | 8 | Steel |
| Contact wedge | <span class="online_3d_viewer" data-model="_models/connector_wedge_0_preview.obj" camera="1200,-1200,900,0,0,31,0,0,1"></span> | [STEP][contact-wedge-stp] [OBJ][contact-wedge-obj] [IFC][contact-wedge-ifc] | [fab_connectors.py][connectors-py] | 1699 x 211 x 63 (x4)<br>1039 x 211 x 63 (x4) | 8 | Baubuche LVL |
| Outer rib connector | <span class="online_3d_viewer" data-model="_models/outer_rib_connector_0_preview.obj" camera="840,-840,650,0,0,20,0,0,1"></span> | [STEP][outer-conn-stp] [OBJ][outer-conn-obj] [IFC][outer-conn-ifc] | [fab_connectors.py][connectors-py] | 800 x 70 x 40 | 4 | Steel |
| Dowels, column side | <span class="online_3d_viewer" data-model="_models/dowel_0_preview.obj" camera="90,-90,88,0,0,25,0,0,1"></span> | [STEP][dowel-stp] [OBJ][dowel-obj] [IFC][dowel-ifc] | [fab_connectors.py][connectors-py] | 100 x Ø49 | 32 | Hardwood |
| Bolt | <span class="online_3d_viewer" data-model="_models/bolt_0_preview.obj" camera="144,-144,110,0,0,9,0,0,1"></span> | [STEP][bolt-stp] [OBJ][bolt-obj] [IFC][bolt-ifc] | [fab_connectors.py][connectors-py] | 160 x Ø18 | 32 | Steel |

</div>

<!-- Reference links for the part tables. The downloads are the files the
     example_model_12_fab_* scripts write to data/fabrication/, served by the
     site itself at _models/ (hooks/fabrication_assets.py) so they work on
     mkdocs serve and on every published version. The Script links open the
     example on GitHub - those resolve once the branch is merged to main. -->

[model-stp]: _models/model_0_fab.stp
[model-obj]: _models/model_0_fab.obj
[model-ifc]: _models/model_0_fab.ifc
[column-stp]: _models/column_0_fab.stp
[column-obj]: _models/column_0_fab.obj
[column-ifc]: _models/column_0_fab.ifc
[support-stp]: _models/support_0_fab.stp
[support-obj]: _models/support_0_fab.obj
[support-ifc]: _models/support_0_fab.ifc
[outer-rib-stp]: _models/outer_ribs_0_0_fab.stp
[outer-rib-obj]: _models/outer_ribs_0_0_fab.obj
[outer-rib-ifc]: _models/outer_ribs_0_0_fab.ifc
[inner-rib-stp]: _models/inner_ribs_0_0_fab.stp
[inner-rib-obj]: _models/inner_ribs_0_0_fab.obj
[inner-rib-ifc]: _models/inner_ribs_0_0_fab.ifc
[beam1-stp]: _models/inner_beams_0_0_fab.stp
[beam1-obj]: _models/inner_beams_0_0_fab.obj
[beam1-ifc]: _models/inner_beams_0_0_fab.ifc
[beam2-stp]: _models/inner_beams_1_0_fab.stp
[beam2-obj]: _models/inner_beams_1_0_fab.obj
[beam2-ifc]: _models/inner_beams_1_0_fab.ifc
[beam3-stp]: _models/inner_beams_2_0_fab.stp
[beam3-obj]: _models/inner_beams_2_0_fab.obj
[beam3-ifc]: _models/inner_beams_2_0_fab.ifc
[tsection-stp]: _models/tsections_0_fab.stp
[tsection-obj]: _models/tsections_0_fab.obj
[tsection-ifc]: _models/tsections_0_fab.ifc
[bed-stp]: _models/beds_0_fab.stp
[bed-obj]: _models/beds_0_fab.obj
[bed-ifc]: _models/beds_0_fab.ifc
[oculus-plate-stp]: _models/oculus_plate_0_fab.stp
[oculus-plate-obj]: _models/oculus_plate_0_fab.obj
[oculus-plate-ifc]: _models/oculus_plate_0_fab.ifc
[oculus-side-plate-stp]: _models/oculus_side_plates_0_fab.stp
[oculus-side-plate-obj]: _models/oculus_side_plates_0_fab.obj
[oculus-side-plate-ifc]: _models/oculus_side_plates_0_fab.ifc
[oculus-side-tsection-stp]: _models/oculus_side_tsections_0_fab.stp
[oculus-side-tsection-obj]: _models/oculus_side_tsections_0_fab.obj
[oculus-side-tsection-ifc]: _models/oculus_side_tsections_0_fab.ifc
[wedge-stp]: _models/wedges_inner_beams_0_fab.stp
[wedge-obj]: _models/wedges_inner_beams_0_fab.obj
[wedge-ifc]: _models/wedges_inner_beams_0_fab.ifc
[connector-stp]: _models/connector_0_fab.stp
[connector-obj]: _models/connector_0_fab.obj
[connector-ifc]: _models/connector_0_fab.ifc
[contact-wedge-stp]: _models/connector_wedge_0_fab.stp
[contact-wedge-obj]: _models/connector_wedge_0_fab.obj
[contact-wedge-ifc]: _models/connector_wedge_0_fab.ifc
[outer-conn-stp]: _models/outer_rib_connector_0_fab.stp
[outer-conn-obj]: _models/outer_rib_connector_0_fab.obj
[outer-conn-ifc]: _models/outer_rib_connector_0_fab.ifc
[dowel-stp]: _models/dowel_0_fab.stp
[dowel-obj]: _models/dowel_0_fab.obj
[dowel-ifc]: _models/dowel_0_fab.ifc
[bolt-stp]: _models/bolt_0_fab.stp
[bolt-obj]: _models/bolt_0_fab.obj
[bolt-ifc]: _models/bolt_0_fab.ifc

[model-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_model.py
[column-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_column.py
[support-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_feet.py
[outer-rib-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_outer_rib.py
[inner-rib-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_inner_rib.py
[beam1-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_inner_beam_1.py
[beam2-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_inner_beam_2.py
[beam3-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_inner_beam_3.py
[tsection-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_tsections.py
[bed-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_beds.py
[oculus-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_oculus.py
[wedge-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_inner_beam_wedge.py
[connectors-py]: https://github.com/BRG-research/compas_tf/blob/main/examples/example_model_12_fab_connectors.py
