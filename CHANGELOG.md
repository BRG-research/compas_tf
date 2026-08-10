# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

### Changed

### Removed

## [0.1.12] 2026-08-10

### Added

### Changed

* Changed `docs/installation.md` to say how to get uv, per platform - `winget install --id=astral-sh.uv` or the `astral.sh/uv/install.ps1` script on Windows, `astral.sh/uv/install.sh` or Homebrew elsewhere - with links to the repository and the official instructions. The page told you to run `uv init` without ever saying where `uv` comes from. Needs `pymdownx.tabbed`, which `mkdocs.yml` did not have.
* Changed the example pages to the minimum that is not already in the script beside them - 445 lines to 287. What is left per page is the screenshot, the script, its output, and only the facts the code does not show: the deflection numbers, why the contacts need a second STEP, why `neighbors=` takes types. `040_project_setup` gets the uv install link back and drops the `--optional viewer` / `uv sync --extra` pair for a plain `uv add compas_viewer`, both verified by running them into a scratch project.
* Changed the `release` workflow's build matrix to Python 3.10-3.12. It still ran 3.9, which `requires-python = ">=3.10"` now rejects, and the `publish` job needs the build - so the tag went up and nothing was published.

### Removed

* Removed `examples/example_model_15_fab_formwork.py`, `example_model_17_quantities.py` and their entries in `tools/run_examples.py`. Both were 0-byte files that the runner counted as passing and the pipeline page described as if they did something. The chain is 21 examples.
* Removed `tests/test_placeholder.py` - `assert True`, the stub that kept pytest from failing on an empty suite before there were real tests. 11 remain.

## [0.1.11] 2026-08-10

### Added

* Added `compas_tf.viewer.zoom_to`, which frames the camera on the geometry before `viewer.show()`. On a model in millimetres the viewer opens at `[-10, -10, 10]` with a far plane of 1000 (scaled by `camera.scale`, which starts at 1), so a 6015 mm building is entirely clipped until you press ++f++. compas_viewer's own `zoom_selected` cannot be called for you - it reads the scene objects' bounding boxes, which do not exist until the renderer has run - so this does the same arithmetic from `element.aabb` / `brep.aabb` instead, keeping the camera's existing view direction. Using `target - position` as `zoom_selected` does is degenerate before the first render: the default position sits almost on the origin, so on a model centred 1.5 m up the camera ends up underneath the building.

### Changed

* Changed `find_groups_with_names(neighbors=...)` to accept a tuple of element types, or a predicate, as well as a bool. `True` admits anything that touches the selection, which is rarely what an assembly means: across the seam a bay touches `outer_ribs_1_1`, `outer_ribs_0_3`, `inner_beams_2_1`, `inner_beams_0_3` and two oculus plates, so the extraction came out with 2-part fragments of `quarter_model_1`, `quarter_model_3` and `oculus_model` hanging off it. The filter applies to both passes, which matters more than it looks: under `True` the oculus arrives by contact and then `connector_wedge_7`'s cylinders arrive because their boxes overlap `oculus_3` - one wrong admission widening what the box pass tests against.
* Changed `example_model_21_extract_bay.py` to name only the hardware that mounts the cantilever on its column (`ConnectorElement`, `DowelCylinderElement`). The wedges and their bolts are inner-beam hardware and `OuterRibConnectorElement` joins one quarter to the next, so the bay is 46 elements and 143 contacts rather than 64 and 168. `docs/examples/030_extract_bay` gets the viewer screenshot of it.
* Changed `example_model_18` to `_22` to drop the timing scaffolding and the comment blocks the documentation now carries.
* Changed the docs to say how big anything is - 237 elements and 733 contacts in the building, 185 in the floor, 34 in a quarter, 46 in a bay - in the tutorial tree and the screenshot captions.
* Changed `requires-python` to `>=3.10`. It said `>=3.9`, which `shapely >= 2.1` rules out, and was briefly capped at `<3.13` on the assumption that `compas_occt` and `compas_manifold` stop at 3.12 - they ship a `cp312-abi3` wheel, built against the stable ABI, so it installs on every CPython from 3.12 on. Verified up to 3.14; the cap was what broke the docs workflow, which now pins 3.12 to match the local environment rather than out of necessity.

### Removed

## [0.1.10] 2026-08-10

### Added

* Added `examples/example_model_22_read_brep_adjacency.py` and `docs/examples/025_read_brep_adjacency`, which read the STEP model, the contact STEP and its JSON sidecar together. `020_read_brep` could draw the contacts but not say which two elements any of them joins, because STEP drops per-shape names; the sidecar describes face *i* in record *i*, so the pair is what turns 733 anonymous faces into 585 named joints, an area per pair and a type table.

### Changed

* Changed `docs/index.md` to a two-sentence description of what the package does, the project presentation, and direct download links for the current STEP model, its contacts and their sidecar. The code sample it opened with belonged in the examples, and there was no link to either the presentation or the model.
* Changed `requirements-dev.txt` to depend on `pytest` directly. It arrived transitively with `sphinx_compas2_theme`, so dropping that for mkdocs left the `build` workflow failing with `pytest: command not found` - lint green, tests never run.
* Changed `find_groups_with_names(neighbors=True)` to find the elements that have no interactions at all. It was a graph walk only, and the contact search skips the fasteners (`skip=involving(DowelCylinderElement, ConnectorCylinderElement)`, 74% of the contacts for no structural information), which leaves 64 of the 237 elements with no edge for a walk to follow: a bay came out with its connectors but without the 32 dowels and 32 cylinders that bolt them on. Geometry is the only signal left for those, so an unlinked element is now included when its bounding box lands inside the bay - applied to the unlinked only, because on elements the graph does describe a box test is far too loose, one diagonal rib's box swallowing half the floor. Bay 0 goes from 49 elements to 77 (+16 cylinders, +12 dowels).
* Changed `example_model_21_extract_bay.py` back to `neighbors=True`, which is now worth passing.

### Removed

* Removed `data/bay_model.stp` and the outputs of examples that no longer exist (`floor_model_booleans.json`, `schoring_models.json`, `orient_2d.json`, `unwrap_beds.json`/`.png`, `example_2_floor_model.obj`, `example_model_7_contacts_columns.obj`), plus the two `PLACEHOLDER` files that kept the now-populated `docs/_images` and `docs/examples` in git.

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

