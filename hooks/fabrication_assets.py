"""Publish the fabrication previews without keeping a second copy of them.

`examples/example_model_12_fab_column.py` writes its output to
`data/fabrication/`, next to the STEP and OBJ the part list links. MkDocs only
publishes what lives under `docs/`, so rather than have the example write the
same GLB twice, this hook hands the previews to the build straight from
`data/fabrication/` and mounts them at `_models/` in the site. Only the
`*_preview.obj` files are published - the full STEP/OBJ sets are downloads,
linked from GitHub, and have no business inflating the site.

Registered as `hooks:` in mkdocs.yml.
"""

import pathlib

from mkdocs.structure.files import File

SOURCE = pathlib.Path(__file__).parent.parent / "data" / "fabrication"
DEST = "_models"
PATTERNS = ("*_preview.obj",)


def on_files(files, config):
    """Add every fabrication preview to the build as if it lived in docs/."""
    for pattern in PATTERNS:
        for path in sorted(SOURCE.glob(pattern)):
            files.append(File.generated(config, f"{DEST}/{path.name}", abs_src_path=str(path)))
    return files


def on_serve(server, config, builder):
    """Rebuild when an example rewrites a preview, so `mkdocs serve` keeps up."""
    if SOURCE.is_dir():
        server.watch(str(SOURCE), builder)
    return server
