# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

* Added `compas_tf.contacts` - contact detection on Brep faces instead of mesh faces: `brep_brep_contacts`, `prepare_faces`, the `BrepContacts` element-pair detector (with a per-element Brep and face cache), the `involving` / `between` skip predicates, and the `contact_holes` accessor. The face pairs are prefiltered on opposite normals and boundary AABBs rather than by `Brep.overlap`, which would tessellate every Brep first - identical results, 3.8x faster, and no dependence on `TOL.lineardeflection`.
* Added `TFModel.compute_contacts_brep`, the one-call Brep version of the contact search, all-pairs or restricted to named groups.
* Added `TFModel.clear_contacts`, `TFModel.contact_breps` and `TFModel.contacts_to_step`.
* Added a `contactmethod` hook to `TFModel.compute_contacts` and `BaseModel.compute_contacts_between_groups`, so the spatial search can be driven by something other than `element.compute_contacts`.
* Added a `cache` argument to `TFModel.element_breps` and `TFModel.to_step`, to reuse Breps already built by a contact search.

### Changed

* Changed `example_model_18_write_model_and_brep.py` to compute contacts between all elements on the Brep faces, skipping the fasteners, and to write them to both the model JSON and their own STEP file.
* Changed `example_model_19_read_model.py` and `example_model_20_read_brep.py` to read the contacts instead of recomputing them.
* Changed `example_model_20_read_brep.py` to set `TOL.lineardeflection = 1.0`: at the 0.001 default the Breps tessellate to 2.93M triangles in 67 s, at 1.0 to 19.8k in 2.0 s, for the same picture. The old comment claiming the count was independent of the deflection was wrong.

### Removed

## [0.1.6] 2026-08-10

### Added

### Changed

### Removed

## [0.1.5] 2026-08-10

### Added

### Changed

### Removed

## [0.1.4] 2026-08-09

### Added

### Changed

### Removed

## [0.1.3] 2026-08-09

### Added

### Changed

### Removed

## [0.1.2] 2026-08-09

### Added

### Changed

### Removed

## [0.1.1] 2026-08-09

### Added

- Column head version based on column centered at the corner of a quarter.
- Dated whole-model OBJ export (`floor_model_<YYYY-MM-DD>.obj`, one named object per element) in `examples/example_2_floor_model_booleans.py`.
- `FloorModel.add_column_connections()` — places a `FloorColumnConnectionElement` on each column and carves the connector pocket out of the column and that quarter's two outer ribs via boolean difference.
- `FloorGuide.corner_point_column()` — column/support grid placement, moved off the removed `FloorBuilder`.
- `compas_manifold` as a runtime dependency (declared in `requirements.txt`).

### Changed

- **`FloorGuide` is now the single parametric source of the floor.** `FloorModel` is constructed from a guide (`FloorModel(guide=...)`, was `builder=...`) and serializes it under the `"guide"` key.
- **All mesh booleans now use `compas_manifold` exclusively** (difference, union, chain) — the `compas_cgal` fallback and dependency were removed. `compas_cgal` no longer in `requirements.txt`.
- `compute_contacts_inner_beams` no longer calls `precompute_boolean_modifiers` internally (the caller does it once), removing a duplicate boolean pass.
- Top docstring of `example_2` is a raw string (fixes the `\c` SyntaxWarning).
- `PolylineLoft.to_mesh`/`multiple_to_mesh` repair capped-loft face winding so lofted plates (e.g. t-sections) come out watertight.
- `PlateElement.compute_contacts` supports both `polygon_polygon_overlap` signatures across `compas_model` versions.
- Corner column-connection cutter is now drawn yellow instead of orange in the viewer.

### Removed

- **`FloorBuilder`** (`floor_builder.py`) and the legacy element family built on it: `QuarterFloorElement` (`quarter_floor.py`), `ColumnHeadElement` (`column_head.py`), `OculusElement` (`oculus.py`).
- `FloorModel.add_oculus()` (used the removed `OculusElement`; oculus geometry now comes from `guide.oculus`) and `build_model()` from `examples/model.py`.

