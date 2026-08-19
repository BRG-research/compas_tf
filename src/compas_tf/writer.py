"""Write element geometry to the files a shop and the docs need.

One place for the export half of a fabrication example, so every element does
it the same way. Three formats, each for a different reader:

- **STEP** is the CAD hand-off. The booleans that carve an element leave
  triangle soup, so the meshes go through :func:`compas_tf.brep.meshes_to_brep`
  first - ``compas_occt``'s coplanar-face merge behind a volume guard - and the
  flat faces the part was modelled with come back as single Brep faces.
- **OBJ** (or PLY/STL/OFF) is the mesh the element already is, no kernel
  involved. Every solid keeps its name, so the file lands as identifiable
  pieces rather than one blob.
- **A preview** is one mesh on its own, for the viewer embedded in the docs.
  Same mesh formats; the viewer reads them directly, which is why nothing here
  needs glTF.

Nothing in here computes geometry. Hand it meshes that are already placed and
carved - see ``examples/example_model_12_fab_column.py``.
"""

import pathlib
from typing import Iterable
from typing import Optional
from typing import Union

from compas.datastructures import Mesh

# Mesh formats compas can write AND the docs viewer can read. Keyed by suffix
# so a caller picks a format by naming the file.
MESH_SUFFIXES = (".obj", ".ply", ".stl", ".off")
STEP_SUFFIXES = (".stp", ".step")

# What the docs viewer loads. Kept as a constant so the writer, the mkdocs hook
# and the <div class="online_3d_viewer"> in fabrication.md agree.
PREVIEW_SUFFIX = ".obj"
PREVIEW_TAG = "preview"


def _named(meshes: Iterable[Mesh], name: str) -> list:
    """Give every mesh a name, so the writers emit identifiable pieces.

    A mesh that already carries a name keeps it; the rest are numbered after
    ``name``. compas' OBJ writer emits one ``o <name>`` group per mesh, and the
    Brep compound is named the same way.
    """
    parts = []
    for index, mesh in enumerate(meshes):
        if mesh is None:
            continue
        if not mesh.name or mesh.name == "Mesh":
            mesh.name = f"{name}_{index}"
        parts.append(mesh)
    return parts


def write_step(
    meshes: Iterable[Mesh],
    filepath: Union[str, pathlib.Path],
    author: str = "compas_tf",
    **kwargs,
) -> pathlib.Path:
    """Write meshes to one STEP file, coplanar faces merged.

    Parameters
    ----------
    meshes : iterable[:class:`compas.datastructures.Mesh`]
        The solids to write. Several become a compound, one solid each.
    filepath : str | :class:`pathlib.Path`
        Destination ``.stp`` / ``.step`` file.
    author : str, optional
        Author recorded in the STEP header.
    **kwargs
        Forwarded to :func:`compas_tf.brep.meshes_to_brep` - e.g.
        ``merge_coplanar=False`` to keep the raw triangles, or a looser
        ``angulardeflection``.

    Returns
    -------
    :class:`pathlib.Path`
        The file written.

    Raises
    ------
    ValueError
        If no mesh survives (nothing to write).
    """
    from compas_tf.brep import meshes_to_brep

    filepath = pathlib.Path(filepath)
    parts = _named(meshes, filepath.stem)
    brep = meshes_to_brep(parts, name=filepath.stem, **kwargs)
    if brep is None:
        raise ValueError(f"write_step: nothing to write to {filepath.name}")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    brep.to_step(filepath, author=author, name=filepath.stem)
    return filepath


def write_mesh(meshes: Iterable[Mesh], filepath: Union[str, pathlib.Path]) -> pathlib.Path:
    """Write meshes to one mesh file, format chosen by the suffix.

    Parameters
    ----------
    meshes : iterable[:class:`compas.datastructures.Mesh`]
        The meshes to write.
    filepath : str | :class:`pathlib.Path`
        Destination file. ``.obj``, ``.ply``, ``.stl`` or ``.off``. Only OBJ
        keeps several meshes as separate named groups; the others are written
        from the first mesh, so join before calling if that matters.

    Returns
    -------
    :class:`pathlib.Path`
        The file written.

    Raises
    ------
    ValueError
        If the suffix is not a supported mesh format, or nothing to write.
    """
    filepath = pathlib.Path(filepath)
    suffix = filepath.suffix.lower()
    if suffix not in MESH_SUFFIXES:
        raise ValueError(f"write_mesh: {suffix or '<none>'} is not one of {', '.join(MESH_SUFFIXES)}")

    parts = _named(meshes, filepath.stem)
    if not parts:
        raise ValueError(f"write_mesh: nothing to write to {filepath.name}")
    filepath.parent.mkdir(parents=True, exist_ok=True)

    if suffix == ".obj":
        from compas.files import OBJ

        # compas' OBJ writer takes a list and emits one `o <name>` per mesh.
        OBJ(filepath).write(parts)
    else:
        mesh = parts[0]
        {".ply": mesh.to_ply, ".stl": mesh.to_stl, ".off": mesh.to_off}[suffix](filepath)
    return filepath


def write_parts(
    meshes: Iterable[Mesh],
    directory: Union[str, pathlib.Path],
    name: str,
    formats: Iterable[str] = ("stp", "obj"),
    preview: Optional[Mesh] = None,
    **kwargs,
) -> dict:
    """Write one element's fabrication set: the solids, plus a docs preview.

    The whole export half of a fabrication example in one call.

    Parameters
    ----------
    meshes : iterable[:class:`compas.datastructures.Mesh`]
        Every solid that belongs to the element - the stock, the carved part,
        the cutters. Written to each requested format.
    directory : str | :class:`pathlib.Path`
        Where the files go. Created if missing.
    name : str
        Stem for the files, e.g. ``"column_0"`` gives ``column_0_fab.stp``.
    formats : iterable[str], optional
        Suffixes, with or without the dot. ``"stp"``/``"step"`` go through the
        Brep merge; the mesh formats are written as-is.
    preview : :class:`compas.datastructures.Mesh`, optional
        One mesh to write on its own as ``<name>_preview.obj``, for the viewer
        in the docs. Usually the finished part: the stock encloses it and the
        cutters pass through it, so all the solids at once would show nothing.
        ``None`` writes no preview.
    **kwargs
        Forwarded to :func:`write_step`.

    Returns
    -------
    dict[str, :class:`pathlib.Path`]
        Every file written, keyed by suffix (``"stp"``, ``"obj"``, ...), with
        the preview under ``"preview"``.

    Examples
    --------
    >>> write_parts([stock, part] + cutters, fab_dir, "column_0", preview=part)  # doctest: +SKIP
    {'stp': ..., 'obj': ..., 'preview': ...}
    """
    directory = pathlib.Path(directory)
    parts = _named(meshes, name)
    written = {}

    for fmt in formats:
        suffix = fmt if fmt.startswith(".") else f".{fmt}"
        suffix = suffix.lower()
        filepath = directory / f"{name}_fab{suffix}"
        if suffix in STEP_SUFFIXES:
            written[suffix.lstrip(".")] = write_step(parts, filepath, **kwargs)
        else:
            written[suffix.lstrip(".")] = write_mesh(parts, filepath)

    if preview is not None:
        preview.name = f"{name}_{PREVIEW_TAG}"
        written[PREVIEW_TAG] = write_mesh([preview], directory / f"{name}_{PREVIEW_TAG}{PREVIEW_SUFFIX}")

    return written
