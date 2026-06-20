# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Column head version based on column centered at the corner of a quarter.
- Dated whole-model OBJ export (`floor_model_<YYYY-MM-DD>.obj`, one named object per element) in `examples/example_2_floor_model_booleans.py`.
- `FloorModel.add_column_connections()` — places a `FloorColumnConnectionElement` on each column and carves the connector pocket out of the column and that quarter's two outer ribs via boolean difference.
- `FloorGuide.corner_point_column()` — column/support grid placement, moved off the removed `FloorBuilder`.
- `compas_manifold` as a runtime dependency (declared in `requirements.txt`).

### Changed

- **`FloorGuide` is now the single parametric source of the floor.** `FloorModel` is constructed from a guide (`FloorModel(guide=...)`, was `builder=...`) and serializes it under the `"guide"` key.
- `SolidDifferenceModifier` and `SolidUnionModifier` now prefer `compas_manifold` for boolean difference/union/chain operations, falling back to `compas_cgal` when it is unavailable.
- `PolylineLoft.to_mesh`/`multiple_to_mesh` repair capped-loft face winding so lofted plates (e.g. t-sections) come out watertight.
- `PlateElement.compute_contacts` supports both `polygon_polygon_overlap` signatures across `compas_model` versions.
- Corner column-connection cutter is now drawn yellow instead of orange in the viewer.

### Removed

- **`FloorBuilder`** (`floor_builder.py`) and the legacy element family built on it: `QuarterFloorElement` (`quarter_floor.py`), `ColumnHeadElement` (`column_head.py`), `OculusElement` (`oculus.py`).
- `FloorModel.add_oculus()` (used the removed `OculusElement`; oculus geometry now comes from `guide.oculus`) and `build_model()` from `examples/model.py`.

