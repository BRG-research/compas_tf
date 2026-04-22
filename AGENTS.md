# AGENTS.md

## Purpose

This file provides essential instructions and conventions for AI coding agents working in the compas_tf repository. It summarizes key project architecture, build/test commands, and links to relevant documentation to ensure agents are immediately productive and follow project standards.

---

## Project Overview
- **Domain:** Timber floor development and modeling
- **Main package:** `src/compas_tf/`
- **Documentation:** See [docs/index.rst](docs/index.rst) and [README.md](README.md)

## Key Conventions
- Use the builder pattern for geometry creation (see `column_head.py`, `edge_beam.py`, `quarter_floor.py`)
- New geometry types should be separated into their own modules and use a `build()` method
- Floor composition is managed via `FloorModel` and `FloorBuilder`
- Tests are in the `tests/` directory; examples in `examples/`

## Build & Test
- **Install:**
  - `pip install -r requirements.txt`
  - `pip install -r requirements-dev.txt`
  - `pip install -e .`
- **Run main example:**
  - `python examples/model.py`
- **Run tests:**
  - `invoke test`
- **Development tasks:**
  - `invoke clean`, `invoke check`, `invoke docs`

## Contribution Guidelines
- Follow steps in [CONTRIBUTING.md](CONTRIBUTING.md)
- Add yourself to AUTHORS.md when contributing

## Documentation Links
- [README.md](README.md): Quick setup, install, and run instructions
- [docs/index.rst](docs/index.rst): Sphinx documentation entry point
- [docs/installation.rst](docs/installation.rst): Install instructions
- [docs/tutorial.rst](docs/tutorial.rst): Tutorials
- [docs/examples.rst](docs/examples.rst): Example usage
- [docs/api.rst](docs/api.rst): API reference

## Architecture Notes
- See `CLAUDE.md` and `task_plan.md` for current and planned architecture changes
- Use the builder pattern for new geometry types and keep interfaces modular

---

This file is maintained to help AI coding agents and contributors quickly understand and follow project conventions. Update as the project evolves.
