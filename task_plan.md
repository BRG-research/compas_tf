# Task Plan: Quarter Slab Build in FloorModel

## Goal
Add `add_quarter_floor()`, `add_column_head()`, and `add_oculus()` methods to FloorModel that use the existing builder pattern from QuarterFloorElement.build(), ColumnHeadElement.build(), and OculusElement.build().

## Architecture
- `FloorBuilder` — parametric geometry data
- `QuarterFloorElement.build(builder, angle)` → QuarterResult
- `ColumnHeadElement.build(builder, column_element)` → (head, top, connections, interactions, modifiers)
- `OculusElement.build(builder)` → OculusResult
- `FloorModel` — composition: Model + FloorBuilder. Already has add_support/add_column/add_prop.

## Phases
- [x] Phase 1: Research existing build methods and model tree
- [x] Phase 2: Implement add_quarter_floor() in FloorModel
- [x] Phase 3: Implement add_column_head() in FloorModel
- [x] Phase 4: Implement add_oculus() in FloorModel
- [x] Phase 5: Test full pipeline

## Status
**Complete** — All 458 elements assembled (36 groups, 422 elements)
- [x] Phase 5: Test JSON roundtrip — props serialize/deserialize correctly
- [x] Phase 6: Cleanup

## Errors Encountered
- `TypeError: unsupported operand type(s) for /: 'Transformation' and 'float'`
  - Root cause: `add_prop` called `PropElement(prop_section, prop_section, length, xform)` — the 4th positional arg `xform` landed on `plate_size` after adding `plate_size` and `plate_thickness` params.
  - Fix: Changed to `PropElement(prop_section, prop_section, length, transformation=xform)`.

## Status
**DONE**
