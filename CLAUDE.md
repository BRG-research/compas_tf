# Plan

- project directory: C:\brg\compas_tf

## Architecture (current)

- `FloorGuide` (`src/compas_tf/floor_guide.py`) is the single parametric source of
  the floor geometry: ribs, inner beams, t-sections, beds, oculus, and the column
  cutters (all `PlateElement`s), plus `corner_point_column()` for column/support
  placement.
- `FloorBuilder` and the element family that was built on it
  (`quarter_floor.py`/`QuarterFloorElement`, `column_head.py`/`ColumnHeadElement`,
  `oculus.py`/`OculusElement`) have been **removed** — everything comes from `FloorGuide`.
- `FloorModel(guide=...)` (`src/compas_tf/floor_model.py`) assembles the model:
  `add_support` → `add_column` → `add_floor_guide` (×4 quarters) →
  `add_column_connections` → `compute_contacts_inner_beams` →
  `precompute_boolean_modifiers`.
- Mesh booleans: `compas_manifold` for differences (with `compas_cgal` fallback),
  `compas_cgal` for unions. See memory notes `boolean-backend-manifold` and
  `floorguide-single-source`.
- Canonical example: `examples/example_2_floor_model_booleans.py` (writes
  `data/floor_model_booleans.json` and `data/floorguide.json`).

## Interfaces (joints to define — TODO)

Define the faces on each element that can form a joint, then create joints between:

- column head (column capitel) ↔ column
- column head ↔ column head
- column ↔ edge beam (outer rib)
- column head ↔ plate
- quarter slab ↔ quarter slab
- quarter slab ↔ oculus

Note: this joint list predates the FloorGuide refactor and uses the old
ColumnHead / QuarterSlab / Oculus element names. Re-ground it in the current
`FloorGuide` vocabulary when implementing — i.e. `PlateElement` groups
(`outer_ribs`, `inner_ribs`, `inner_beams`, `tsections`, `beds`, `oculus`),
`ColumnElement`, and `FloorColumnConnectionElement`.
