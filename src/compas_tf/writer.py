"""Write element geometry to the files a shop and the docs need.

One place for the export half of a fabrication example, so every element does
it the same way. Four formats, each for a different reader:

- **STEP** is the CAD hand-off. The booleans that carve an element leave
  triangle soup, so the meshes go through :func:`compas_tf.brep.meshes_to_brep`
  first - ``compas_occt``'s coplanar-face merge behind a volume guard - and the
  flat faces the part was modelled with come back as single Brep faces.
- **OBJ** (or PLY/STL/OFF) is the mesh the element already is, no kernel
  involved. Every solid keeps its name, so the file lands as identifiable
  pieces rather than one blob.
- **IFC** is the BIM hand-off, written with ``compas_ifc``: one
  ``IfcBuildingElementProxy`` per solid inside a minimal
  project/site/building/storey template, millimetres, IFC4.
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
IFC_SUFFIXES = (".ifc",)

# What the docs viewer loads. Kept as a constant so the writer, the mkdocs hook
# and the <div class="online_3d_viewer"> in fabrication.md agree.
PREVIEW_SUFFIX = ".obj"
PREVIEW_TAG = "preview"


def triangulated(mesh: Mesh) -> Mesh:
    """A copy of ``mesh`` with every ngon face ear-clipped to triangles.

    The coplanar-face merge leaves concave polygon faces; web viewers
    fan-triangulate ngons and smear triangles across the concavities, so a
    mesh meant for the docs viewer goes through this first. Reuses the
    ear-clipping the plate caps already use.
    """
    from compas.geometry import Polygon

    from compas_tf.plate import PlateElement

    result = mesh.copy()
    for face in list(result.faces()):
        vertices = result.face_vertices(face)
        if len(vertices) <= 3:
            continue
        polygon = Polygon([result.vertex_coordinates(vertex) for vertex in vertices])
        result.delete_face(face)
        for tri in PlateElement._earclip_polygon(polygon):
            result.add_face([vertices[index] for index in tri])
    return result


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


def write_ifc(
    meshes: Iterable[Mesh],
    filepath: Union[str, pathlib.Path],
    schema: str = "IFC4",
) -> pathlib.Path:
    """Write meshes to one IFC file via ``compas_ifc``.

    Every mesh becomes one ``IfcBuildingElementProxy`` (named after the mesh)
    on the single storey of a minimal template project, in millimetres.

    Parameters
    ----------
    meshes : iterable[:class:`compas.datastructures.Mesh`]
        The solids to write.
    filepath : str | :class:`pathlib.Path`
        Destination ``.ifc`` file.
    schema : str, optional
        IFC schema version.

    Returns
    -------
    :class:`pathlib.Path`
        The file written.

    Raises
    ------
    ValueError
        If no mesh survives (nothing to write).
    """
    from compas_ifc.bim import BuildingInformationModel

    filepath = pathlib.Path(filepath)
    parts = _named(meshes, filepath.stem)
    if not parts:
        raise ValueError(f"write_ifc: nothing to write to {filepath.name}")
    filepath.parent.mkdir(parents=True, exist_ok=True)

    bim = BuildingInformationModel.template(schema=schema, unit="mm", name=filepath.stem)
    storey = bim.storeys[0]
    for mesh in parts:
        bim.create_element(geometry=mesh, name=mesh.name, parent=storey)
    bim.save(str(filepath))
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
    formats: Iterable[str] = ("stp", "obj", "ifc"),
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
        Brep merge, ``"ifc"`` goes through :func:`write_ifc`; the mesh formats
        are written as-is.
    preview : :class:`compas.datastructures.Mesh`, optional
        One mesh to write on its own as ``<name>_preview.obj``, for the viewer
        in the docs. Usually the finished part: the stock encloses it and the
        cutters pass through it, so all the solids at once would show nothing.
        Triangulated on the way out - web viewers fan-triangulate the merged
        concave faces and draw garbage. ``None`` writes no preview.
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
        elif suffix in IFC_SUFFIXES:
            written[suffix.lstrip(".")] = write_ifc(parts, filepath)
        else:
            written[suffix.lstrip(".")] = write_mesh(parts, filepath)

    if preview is not None:
        preview = triangulated(preview)
        preview.name = f"{name}_{PREVIEW_TAG}"
        written[PREVIEW_TAG] = write_mesh([preview], directory / f"{name}_{PREVIEW_TAG}{PREVIEW_SUFFIX}")

    return written


def _rgba(color) -> tuple:
    """Coerce a :class:`compas.colors.Color`, a tuple or ``None`` to 0-1 rgba.

    Alpha rides along because an assembly step sometimes wants a part present
    but see-through - a support shown as a ghost around the points that are the
    subject of the picture. ``Color`` carries its own alpha; a plain tuple may
    give one as a fourth value, and is opaque without it.
    """
    if color is None:
        return (0.66, 0.68, 0.70, 1.0)
    if hasattr(color, "rgba"):
        return tuple(color.rgba)
    values = tuple(color)
    r, g, b = values[:3]
    alpha = values[3] if len(values) > 3 else 1.0
    if max(r, g, b) > 1.0:  # 0-255 tuple
        return (r / 255.0, g / 255.0, b / 255.0, alpha)
    return (r, g, b, alpha)


# Tessellation for a preview. It is the ANGULAR deflection that drives the
# segment count on a curved face - the linear one barely moves it - and compas'
# default of 0.1 rad puts ~63 segments on every hole, which is how an 8 mm
# marker ball ends up with 2022 triangles. 0.5 rad is ~13 segments round a
# circle: low-poly on purpose, and the right trade for a page that loads
# several dozen parts at once. Pass `deflection` to a writer to override it.
PREVIEW_DEFLECTION = 0.5


def _as_mesh(geometry, deflection: float = PREVIEW_DEFLECTION) -> Mesh:
    """A mesh for the writers, from a Mesh or from a Brep.

    Parts are modelled as Breps - exact cylinders, exact holes - and only
    become triangles on the way into a file a viewer can read, so the
    tessellation lives here rather than in every example.
    """
    if isinstance(geometry, Mesh):
        return geometry
    if hasattr(geometry, "to_tesselation"):
        mesh, _ = geometry.to_tesselation(linear_deflection=deflection, angular_deflection=deflection)
        mesh.name = geometry.name
        return mesh
    raise TypeError(f"cannot write {type(geometry).__name__}: not a Mesh and not a Brep")


def write_colored_obj(parts: Iterable, filepath: Union[str, pathlib.Path], deflection: float = PREVIEW_DEFLECTION) -> dict:
    """Write named, coloured meshes as one OBJ next to its MTL.

    :func:`write_mesh` goes through compas' OBJ writer, which has no notion of
    materials - every solid comes out the one grey the viewer defaults to. An
    assembly step is the opposite case: the whole point of the picture is that
    the instrument, the marked points and the sight lines read as different
    things. So this writes the OBJ by hand, one ``usemtl`` per part, plus the
    ``.mtl`` that gives each colour a diffuse value.

    Both files have to reach the docs viewer: Online 3D Viewer only fetches
    what it is handed, so the embed names them both,
    ``data-model="_models/x.obj,_models/x.mtl"``.

    Parameters
    ----------
    parts : iterable
        Either meshes or Breps, or ``(geometry, color)`` pairs. A Brep is
        tessellated on the way out. The colour may be a
        :class:`compas.colors.Color`, an ``(r, g, b)`` or ``(r, g, b, a)``
        tuple in 0-1 or 0-255, or ``None`` for the default grey. An alpha below
        1 is written as the material's ``d``, so the part comes out
        see-through. Each mesh keeps its ``name`` as the OBJ object name.
    filepath : str | :class:`pathlib.Path`
        Where the ``.obj`` goes. The ``.mtl`` lands beside it under the same
        stem.
    deflection : float, optional
        Tessellation tolerance for the Breps, in mm and radians. See
        :data:`PREVIEW_DEFLECTION`.

    Returns
    -------
    dict[str, :class:`pathlib.Path`]
        The two files written, keyed ``"obj"`` and ``"mtl"``.
    """
    filepath = pathlib.Path(filepath).with_suffix(".obj")
    filepath.parent.mkdir(parents=True, exist_ok=True)
    mtlpath = filepath.with_suffix(".mtl")

    items = []
    for index, part in enumerate(parts):
        geometry, color = part if isinstance(part, (tuple, list)) else (part, None)
        if geometry is None:
            continue
        mesh = _as_mesh(geometry, deflection)
        name = mesh.name if mesh.name and mesh.name != "Mesh" else f"part_{index}"
        items.append((name, mesh, _rgba(color)))

    if not items:
        raise ValueError(f"write_colored_obj: nothing to write to {filepath.name}")

    # One material per distinct colour, so a step with 8 red markers carries
    # one "red" and not eight.
    materials = {}
    for _, _, rgba in items:
        materials.setdefault(rgba, "mat_{:02x}{:02x}{:02x}{:02x}".format(*(int(round(c * 255)) for c in rgba)))

    with open(mtlpath, "w") as f:
        f.write("# compas_tf assembly step materials\n")
        for rgba, material in materials.items():
            f.write(f"\nnewmtl {material}\n")
            f.write("Kd {:.4f} {:.4f} {:.4f}\n".format(*rgba[:3]))
            f.write("Ka 0.0000 0.0000 0.0000\n")
            f.write("Ks 0.0500 0.0500 0.0500\n")
            f.write("Ns 20.0000\n")
            f.write(f"d {rgba[3]:.4f}\n")
            f.write("illum 2\n")

    with open(filepath, "w") as f:
        f.write("# compas_tf assembly step\n")
        f.write(f"mtllib {mtlpath.name}\n")
        offset = 1
        for name, mesh, rgba in items:
            index_of = {}
            f.write(f"\no {name}\n")
            f.write(f"usemtl {materials[rgba]}\n")
            for vertex in mesh.vertices():
                x, y, z = mesh.vertex_coordinates(vertex)
                f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
                index_of[vertex] = offset
                offset += 1
            for face in mesh.faces():
                vertices = mesh.face_vertices(face)
                f.write("f {}\n".format(" ".join(str(index_of[vertex]) for vertex in vertices)))

    return {"obj": filepath, "mtl": mtlpath}
