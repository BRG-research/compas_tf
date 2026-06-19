# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Column head version based on column centered at the corner of a quarter.
- Dated whole-model OBJ export (`floor_model_<YYYY-MM-DD>.obj`, one named object per element) in `examples/example_2_floor_model_booleans.py`.

### Changed

- `SolidUnionModifier` now prefers `compas_manifold` for boolean union and chain operations, falling back to `compas_cgal` when it is unavailable (matching `SolidDifferenceModifier`).
- Corner column-connection cutter is now drawn yellow instead of orange in the viewer.

### Removed

