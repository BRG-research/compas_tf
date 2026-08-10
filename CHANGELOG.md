# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

### Changed

* Changed `find_groups_with_names(neighbors=True)` to find the elements that have no interactions at all. It was a graph walk only, and the contact search skips the fasteners (`skip=involving(DowelCylinderElement, ConnectorCylinderElement)`, 74% of the contacts for no structural information), which leaves 64 of the 237 elements with no edge for a walk to follow: a bay came out with its connectors but without the 32 dowels and 32 cylinders that bolt them on. Geometry is the only signal left for those, so an unlinked element is now included when its bounding box lands inside the bay - applied to the unlinked only, because on elements the graph does describe a box test is far too loose, one diagonal rib's box swallowing half the floor. Bay 0 goes from 49 elements to 77 (+16 cylinders, +12 dowels).
* Changed `example_model_21_extract_bay.py` back to `neighbors=True`, which is now worth passing.

### Removed

## [0.1.9] 2026-08-10

### Added

* Added `BaseModel.find_groups_with_names` - several named groups extracted at once as one standalone model, for lifting an assembly (one column plus the quarter it carries) out of the building. The plural matters: contacts BETWEEN the groups only survive if the groups come out together, so `find_group_with_name` twice plus `merge` keeps every internal contact and drops exactly the joint that connects them. Each group keeps its ancestor chain, pruned to what was asked for, so the extracted parts stay where they are in the world. `neighbors=True` also brings in the elements that interact with the extracted ones - the fasteners live in their own top-level groups, so a bay extracted by name alone has none - one step out only, or the whole model follows one edge at a time. On the cantilevers model: 49 elements and 208 contacts against 36 and 125 without.
* Added `examples/example_model_21_extract_bay.py`, and the documentation the reading side never had: `docs/examples/010_read_model`, `020_read_brep`, `030_extract_bay`, `040_project_setup` (a consumer project from scratch) and `050_pipeline`, plus a written `tutorial` and a populated API reference.

### Changed

* Changed `examples/example_model_19_read_model.py` and `example_model_20_read_brep.py` to the minimum API that does the job. What the comment blocks explained - baking, Brep contacts against mesh contacts, the STEP name/order sidecar, the deflection - is now prose in the docs, where it is read once rather than scrolled past in every example.
* Changed `README.md`, which still described a `compas_viewer` fork and an `example_0_watch_viewer.py` that no longer exist.

### Removed

## [0.1.8] 2026-08-10

### Added

### Changed

* Changed `PlateElement` to build its loft on first use instead of in `__init__`. `compute_elementgeometry` is the only reader and it is `@baked`, so a baked plate returned its stored mesh and the loft was thrown away unused - yet all 145 plates paid for it on every load. `compas.json_load` of the cantilevers model drops from 3.3 s to 0.60 s (the raw `json.loads` of the same 3.9 MB file is 0.09 s).

### Removed

## [0.1.7] 2026-08-10

### Added

* Added `compas_tf.contacts` - contact detection on Brep faces instead of mesh faces: `brep_brep_contacts`, `prepare_faces`, the `BrepContacts` element-pair detector (with a per-element Brep and face cache), the `involving` / `between` skip predicates, and the `contact_holes` accessor. The face pairs are prefiltered on opposite normals and boundary AABBs rather than by `Brep.overlap`, which would tessellate every Brep first - identical results, 3.8x faster, and no dependence on `TOL.lineardeflection`.
* Added `TFModel.compute_contacts_brep`, the one-call Brep version of the contact search, all-pairs or restricted to named groups.
* Added `TFModel.clear_contacts`, `TFModel.contact_pairs`, `TFModel.contact_breps`, `TFModel.contact_adjacency`, `TFModel.contacts_to_step` and `TFModel.contacts_to_json`. STEP drops per-shape names, so the contact faces carry no adjacency; it goes in a JSON sidecar keyed by index, which STEP does preserve.
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

