"""Interface detection through the ``wood_nano`` timber-joinery kernel.

``compas_tf`` used to detect contacts by intersecting element geometry pair by
pair - mesh faces, or merged Brep faces. Both answered *where* two elements
touch and nothing more, and both have been removed:
:meth:`compas_tf.model.TFModel.compute_contacts_wood` is now the detector.

``wood_nano`` answers a different question. It takes the whole plate assembly at
once, as the top/bottom outline pair every plate is modelled from, and returns
the interfaces together with a **joint type** for each - the classification a
joinery solver needs before it can cut anything. That type is what neither of
the geometric searches produces.

The trade is coverage. wood speaks only in polyline pairs, so it sees
:class:`compas_tf.plate.PlateElement` and nothing else: the columns, dowels,
cylinders and connectors of a full floor model have no outline-pair form and are
simply absent from the search. Keep the geometric searches for those, and use
this for plate-to-plate joint typing.

Measured on one quarter (34 plates, ``data/quarter_model.json``): wood reports
117 interfaces, the same 117 that
:meth:`compas_tf.base_model.BaseModel.compute_contacts_within_groups` finds and
that a brute-force sweep over every plate pair confirms - with an identical
breakdown per group pair, and in 0.03s against 0.8s.

Two wood_nano APIs
------------------

``wood_nano`` changed its Python surface between the version this was first
written against and the current one, so both are supported and picked at
runtime:

- **modern** (1.x): ``wood_nano.joinery_solver.joinery_solver_elements(bottom,
  top, search_type)`` returning ``(elements, joints)``, where each joint is a
  ``JointResult`` carrying ``element_ids``, ``joint_type`` and ``area``.
- **legacy** (0.3.x): ``wood_nano.joints(point2, search_type, int2, point2,
  int1)``, filling out-parameters, with the outlines interleaved into one flat
  list.

:func:`wood_api` reports which one is in use.

The joint type values are wood's own, and they are NOT comparable between the
two APIs - the legacy search and the modern face-to-face pipeline classify
differently. On the quarter, legacy returned 12 (15 joints, bed row to bed row,
meeting edge to edge in plane), 20 (96, the bulk, a plate face meeting another
plate's edge) and 40 (6, rib to tsection). Treat the integers as opaque keys
tied to the API that produced them.

``wood_nano`` is an optional dependency; nothing here is imported at module
load, so ``compas_tf`` works without it.
"""

import contextlib
import os
import pathlib
import sys
from typing import Optional

from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import centroid_points
from compas.geometry import dot_vectors
from compas_model.elements import Element
from compas_model.elements import Group

from compas_tf.plate import PlateElement

WOOD_INSTALL_HINT = (
    "compas_tf.wood needs the `wood_nano` package.\n"
    "The PyPI wheel (wood-nano 1.0.19) does NOT work on Python 3.10+: its\n"
    "binaries link against python39.dll even though the wheel is tagged abi3,\n"
    "so importing it fails with a DLL load error. Build it from source against\n"
    "the interpreter you are running instead - nanobind emits genuinely\n"
    "stable-ABI binaries when built on Python 3.12+:\n"
    "    uv pip install /path/to/wood_nano"
)


def _import_wood():
    """Import ``wood_nano``, with an error that says what to do about it."""
    try:
        import wood_nano
    except ImportError as error:  # pragma: no cover - depends on the environment
        raise ImportError(f"{WOOD_INSTALL_HINT}\n\noriginal error: {error}") from error
    return wood_nano


def wood_api() -> str:
    """Which wood_nano Python API is installed - ``"modern"`` or ``"legacy"``.

    The 0.3.x raw entry point is ``wood_nano.joints``; 1.x replaced it with
    ``wood_nano.joinery_solver.joinery_solver_elements``. Detection is by
    attribute, not by version string, so a build that carries both still works.
    """
    wood_nano = _import_wood()
    if hasattr(wood_nano, "joints"):
        return "legacy"
    return "modern"


@contextlib.contextmanager
def _muted_output(mute: bool = True):
    """Silence the kernel's ``[GCZ]`` progress chatter.

    wood writes its pipeline trace from C++, so reassigning ``sys.stdout`` is
    not enough - the file descriptors themselves have to be pointed elsewhere.
    Both are redirected: the trace goes to stderr, not stdout, so muting fd 1
    alone leaves it fully visible.
    """
    if not mute:
        yield
        return
    sys.stdout.flush()
    sys.stderr.flush()
    saved = {fd: os.dup(fd) for fd in (1, 2)}
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        for fd in (1, 2):
            os.dup2(devnull, fd)
        yield
    finally:
        for fd, original in saved.items():
            os.dup2(original, fd)
            os.close(original)
        os.close(devnull)


def plate_outlines(plates: list[PlateElement]) -> tuple[list[list[Point]], list[list[Point]]]:
    """The bottom and top outline of every plate, in model space, closed.

    Parameters
    ----------
    plates
        The plates to convert, in the order their indices should take.

    Returns
    -------
    tuple[list[list[:class:`compas.geometry.Point`]], list[list[:class:`compas.geometry.Point`]]]
        ``(bottoms, tops)``, one closed point loop each per plate.

    """
    bottoms, tops = [], []
    for plate in plates:
        transformation = plate.modeltransformation
        for outline, target in ((plate.bottom, bottoms), (plate.top, tops)):
            points = [Point(*point).transformed(transformation) for point in outline]
            if points and points[0] != points[-1]:
                points.append(points[0])
            target.append(points)
    return bottoms, tops


def plate_outline_pairs(plates: list[PlateElement]) -> list[list[Point]]:
    """The outlines interleaved the way the legacy API reads them.

    The legacy ``joints`` takes one flat list read two at a time: the top of
    element 0, the bottom of element 0, the top of element 1, and so on. So the
    plate at index ``i`` owns polylines ``2 * i`` and ``2 * i + 1``, which is
    what maps wood's element indices back onto the elements here.
    """
    bottoms, tops = plate_outlines(plates)
    loops = []
    for top, bottom in zip(tops, bottoms):
        loops.append(top)
        loops.append(bottom)
    return loops


def _polygon(points: list) -> Optional[Polygon]:
    """A closed loop of wood points as a :class:`compas.geometry.Polygon`."""
    coordinates = [Point(point[0], point[1], point[2]) for point in points]
    # wood closes its loops; a Polygon must not repeat the first point.
    if len(coordinates) > 1 and coordinates[0] == coordinates[-1]:
        coordinates.pop()
    if len(coordinates) < 3:
        return None
    return Polygon(coordinates)


def _joints_modern(wood_nano, plates, search_type, quiet):
    from wood_nano.joinery_solver import joinery_solver_elements

    bottoms, tops = plate_outlines(plates)
    bottom_input = [[list(point) for point in loop] for loop in bottoms]
    top_input = [[list(point) for point in loop] for loop in tops]

    with _muted_output(quiet):
        _elements, joints = joinery_solver_elements(bottom_input, top_input, search_type=int(search_type))

    results = []
    for joint in joints:
        polygon = _polygon(list(joint.area))
        if polygon is None:
            continue
        index_a, index_b = joint.element_ids
        results.append((int(index_a), int(index_b), polygon, int(joint.joint_type)))
    return results


def _joints_legacy(wood_nano, plates, search_type, quiet):
    polylines = wood_nano.point2()
    for loop in plate_outline_pairs(plates):
        polyline = wood_nano.point1()
        for point in loop:
            polyline.append(wood_nano.point(point[0], point[1], point[2]))
        polylines.append(polyline)

    element_pairs = wood_nano.int2()
    joint_areas = wood_nano.point2()
    joint_types = wood_nano.int1()

    with _muted_output(quiet):
        wood_nano.joints(polylines, int(search_type), element_pairs, joint_areas, joint_types)

    results = []
    for pair, area, joint_type in zip(element_pairs, joint_areas, list(joint_types)):
        polygon = _polygon(list(area))
        if polygon is None:
            continue
        results.append((int(pair[0]), int(pair[1]), polygon, int(joint_type)))
    return results


def wood_joints(
    plates: list[PlateElement],
    search_type: int = 0,
    quiet: bool = True,
    face_kinds: Optional[set] = None,
    connections: Optional[set] = None,
    kind_pairs: Optional[set] = None,
    tolerance: float = 1.0,
) -> list[tuple[int, int, Polygon, int, Optional[str], Optional[str]]]:
    """Detect the interfaces between plates with ``wood_nano``.

    Works with either wood_nano Python API - see the module docstring and
    :func:`wood_api`. ``search_type=0`` is face-to-face in both.

    Parameters
    ----------
    plates
        The plates to search. Their order fixes the indices in the result.
    search_type
        wood's search type, passed through unchanged. 0 = face-to-face,
        and on the modern API 1 = cross-joint, 2 = both.
    quiet
        Silence the kernel's ``[GCZ]`` progress trace, which it writes straight
        to file descriptor 1. Pass ``False`` to see it while debugging.
    face_kinds
        Keep only interfaces whose area lies on one of these faces, a subset of
        ``{"top", "bottom", "side"}``. As in
        :meth:`compas_tf.plate.PlateElement.compute_contacts`, the filter
        applies to BOTH plates of a pair: an interface survives only when its
        kind on each plate is in the set. Default ``None`` keeps everything.

        wood does not label its joint areas, so the kinds are recovered
        geometrically by :func:`classify_joint_face`. An interface whose kind
        cannot be determined on either plate is dropped when filtering, since
        it cannot be shown to satisfy the request.
    connections
        Keep only these connection types - a subset of
        :data:`JOINT_CONNECTIONS`, i.e. ``{"face-to-face"}``,
        ``{"side-to-side"}``, ``{"face-to-side"}``. This is the filter to reach
        for: ``{"side-to-side"}`` keeps edge-to-edge joints and skips everything
        landing on a face.
    kind_pairs
        The finer filter, on the exact faces - ``{"top-bottom"}`` for plates
        stacked the same way up only, which ``connections={"face-to-face"}``
        would admit alongside ``top-top``. Rarely needed; prefer ``connections``.
        All filters combine - an interface must satisfy every one given.
    tolerance
        Plane-matching tolerance handed to :func:`classify_joint_face`.

    Returns
    -------
    list[tuple[int, int, :class:`compas.geometry.Polygon`, int, str | None, str | None]]
        ``(index_a, index_b, joint_area, joint_type, kind_a, kind_b)`` per
        interface, where the indices point into ``plates`` and the kinds say
        which face of each plate the area lies on. Turn the kinds into the
        joint's name with :func:`joint_connection`.

    """
    wood_nano = _import_wood()
    if hasattr(wood_nano, "joints"):
        found = _joints_legacy(wood_nano, plates, search_type, quiet)
    else:
        found = _joints_modern(wood_nano, plates, search_type, quiet)

    results = []
    for index_a, index_b, polygon, joint_type in found:
        kind_a = classify_joint_face(plates[index_a], polygon, tolerance=tolerance)
        kind_b = classify_joint_face(plates[index_b], polygon, tolerance=tolerance)
        if face_kinds is not None and not (kind_a in face_kinds and kind_b in face_kinds):
            continue
        if connections is not None and joint_connection(kind_a, kind_b) not in connections:
            continue
        if kind_pairs is not None and joint_face_pair(kind_a, kind_b) not in kind_pairs:
            continue
        results.append((index_a, index_b, polygon, joint_type, kind_a, kind_b))
    return results


FACE_KINDS = ("top", "bottom", "side")


# The joinery vocabulary. A plate has two large faces and a perimeter of narrow
# sides; `_polygon_faces` calls the large ones "top" and "bottom" because that is
# how a plate is lofted, from a top and a bottom polyline. Those names describe
# construction, not orientation: an inner rib stands vertically, so its "top"
# face is a VERTICAL plane. Reporting two ribs meeting as "top-top" reads like a
# modelling error when it is an ordinary face-to-face joint.
#
# So joints are named the way timber joinery names them - and the way wood's own
# search types do (`SEARCH_FACE_TO_FACE`): by whether a large face or a narrow
# side meets another. Both large faces map to `face`, every perimeter quad to
# `side`.
JOINT_SURFACES = {"top": "face", "bottom": "face", "side": "side"}

FACE_TO_FACE = "face-to-face"
FACE_TO_SIDE = "face-to-side"
SIDE_TO_SIDE = "side-to-side"

JOINT_CONNECTIONS = (FACE_TO_FACE, FACE_TO_SIDE, SIDE_TO_SIDE)


def joint_connection(kind_a: Optional[str], kind_b: Optional[str]) -> str:
    """How two plates meet: ``face-to-face``, ``face-to-side`` or ``side-to-side``.

    This is the vocabulary to reach for. It says what the joint IS - one plate
    lying against another, an edge landing on a face, or two edges meeting -
    without the misleading up/down reading of the raw face kinds. It is also
    symmetric: the answer never depends on which element the search visited
    first.

    Use :func:`joint_face_pair` when the distinction between a plate's two large
    faces genuinely matters, e.g. for deciding which side to cut.

    Returns ``"?"`` when either side could not be classified.
    """
    a, b = JOINT_SURFACES.get(kind_a or ""), JOINT_SURFACES.get(kind_b or "")
    if a is None or b is None:
        return "?"
    if a == "face" and b == "face":
        return FACE_TO_FACE
    if a == "side" and b == "side":
        return SIDE_TO_SIDE
    return FACE_TO_SIDE


def joint_face_pair(kind_a: Optional[str], kind_b: Optional[str]) -> str:
    """The precise faces of an interface, as a canonical ``"x-y"`` string.

    Finer than :func:`joint_connection`: it keeps the distinction between a
    plate's two large faces, so ``"top-bottom"`` (one plate lying on another the
    same way up) is told apart from ``"top-top"`` (two plates meeting front to
    front). Both are ``face-to-face`` connections.

    The kinds are ordered by :data:`FACE_KINDS` rather than alphabetically, so
    the string does not depend on which element the search visited first -
    ``(top, side)`` and ``(side, top)`` both give ``"top-side"``.

    An unclassified side is written ``"?"``.
    """
    rank = {kind: index for index, kind in enumerate(FACE_KINDS)}
    first, second = kind_a or "?", kind_b or "?"
    if rank.get(first, len(FACE_KINDS)) > rank.get(second, len(FACE_KINDS)):
        first, second = second, first
    return f"{first}-{second}"


def classify_joint_face(plate: PlateElement, polygon: Polygon, tolerance: float = 1.0, parallel: float = 0.99) -> Optional[str]:
    """Which face of ``plate`` a joint area lies on - ``top``, ``bottom`` or ``side``.

    wood returns a joint area but not which face of each plate produced it, so
    the label the geometric search gets for free
    (:meth:`compas_tf.plate.PlateElement._polygon_faces` tags every face) has to
    be recovered here. A joint area lies on exactly one face of a plate: the one
    whose plane contains it. So match on plane, not on outline - compare
    normals, then check the area's centroid sits on that plane.

    Parameters
    ----------
    plate
        The plate the joint area belongs to.
    polygon
        The joint area, in model space.
    tolerance
        How far the area's centroid may sit off a face plane and still count as
        lying on it, in model units.
    parallel
        Minimum ``|dot|`` of the two unit normals for the planes to count as
        parallel. 0.99 is about 8 degrees. The absolute value is deliberate:
        ``_polygon_faces`` emits outward normals, so the face a contact sits on
        may point either with or against the joint area's own normal.

    Returns
    -------
    str or None
        The face kind, or None when no face plane contains the area - which
        happens when the plate is not actually a party to this joint.

    """
    try:
        joint_normal = polygon.normal
        joint_centroid = polygon.centroid
    except Exception:  # degenerate area - nothing to classify against
        return None

    best, best_distance = None, None
    for points, normal, kind in plate._polygon_faces(plate.modeltransformation):
        if abs(dot_vectors(list(joint_normal), list(normal))) < parallel:
            continue
        origin = centroid_points([list(q) for q in points])
        offset = [joint_centroid[i] - origin[i] for i in range(3)]
        distance = abs(dot_vectors(offset, list(normal)))
        if distance <= tolerance and (best_distance is None or distance < best_distance):
            best, best_distance = kind, distance
    return best


def plate_participants(model, groups: Optional[list[str]] = None) -> list[PlateElement]:
    """The plates of a model, optionally only those under the named groups.

    An element takes part when any ancestor group's name was requested, the same
    rule :meth:`compas_tf.base_model.BaseModel.compute_contacts_between_groups`
    uses, so naming an outer group pulls in all its descendants.
    """
    plates = [element for element in model.elements() if isinstance(element, PlateElement)]
    if groups is None:
        return plates

    names = set(groups)

    def takes_part(element: Element) -> bool:
        node = element.treenode
        parent = node.parent if node is not None else None
        while parent is not None and not parent.is_root:
            if parent.element.name in names:
                return True
            parent = parent.parent
        return False

    return [plate for plate in plates if takes_part(plate)]


def skipped_elements(model) -> dict[str, int]:
    """What a wood search cannot see, counted by type.

    wood reads outline pairs, so everything that is not a
    :class:`compas_tf.plate.PlateElement` is invisible to it. Report this next to
    a wood result so the gap is never silent.
    """
    counts: dict[str, int] = {}
    for element in model.elements():
        if isinstance(element, Group) or isinstance(element, PlateElement):
            continue
        name = type(element).__name__
        counts[name] = counts.get(name, 0) + 1
    return counts


def write_joint_types(path, records) -> str:
    """Write ``(a, b, joint_type, area)`` records beside a contact export."""
    import json

    path = pathlib.Path(path)
    with open(path, "w") as f:
        json.dump({"count": len(records), "joints": records}, f, indent=1)
    return str(path)
