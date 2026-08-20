"""Publish the fabrication files without keeping a second copy of them.

The `examples/example_model_12_fab_*` scripts write their output to
`data/fabrication/`. MkDocs only publishes what lives under `docs/`, so rather
than have the examples write everything twice, this hook hands the files to
the build straight from `data/fabrication/` and mounts them at `_models/` in
the site: the `*_preview.obj` meshes the embedded viewers load, AND the full
`*_fab.stp/.obj/.ifc` sets the part list links as downloads. Serving the
downloads from the site (a few MB, all of them) keeps the links working on
`mkdocs serve` and on every published version - a GitHub raw/main URL only
works once the files are merged to main, and 404s until then.

Registered as `hooks:` in mkdocs.yml.
"""

import pathlib

from mkdocs.structure.files import File

SOURCE = pathlib.Path(__file__).parent.parent / "data" / "fabrication"
DEST = "_models"
PATTERNS = ("*_preview.obj", "*_fab.stp", "*_fab.obj", "*_fab.ifc")


def on_files(files, config):
    """Add every fabrication file to the build as if it lived in docs/."""
    for pattern in PATTERNS:
        for path in sorted(SOURCE.glob(pattern)):
            files.append(File.generated(config, f"{DEST}/{path.name}", abs_src_path=str(path)))
    return files


def on_serve(server, config, builder):
    """Rebuild when an example rewrites a preview, so `mkdocs serve` keeps up."""
    if SOURCE.is_dir():
        server.watch(str(SOURCE), builder)
    return server
