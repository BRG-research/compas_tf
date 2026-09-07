"""Write a :class:`compas_tf.model.TFModel` to a session ``.pb``.

Every element becomes ONE ``session_py.Element`` carrying its mesh plus a type
tag, so a consumer reads what a thing *is* off ``element_type`` rather than
guessing from its name:

===================================  ==============  ==========================
compas_tf class                      element_type    element_data
===================================  ==============  ==========================
PlateElement, ConnectorWedgeElement  ``"Plate"``     bottom + top outline pair
ColumnElement                        ``"Column"``    axis + section
everything else                      ``"Solid"``     (empty - the mesh is all)
===================================  ==============  ==========================

The group hierarchy (quarters, columns, oculus, connectors) is mirrored into the
session tree, and every element is parented under its group.

This replaces the old STEP route. That one wrote the model to ``.stp``, re-matched
solids back to names by bounding-box centre, and emitted untyped meshes - so the
plate's bottom/top pair, which this model *has*, never reached the consumer.

``session_py`` is imported lazily, so importing ``compas_tf`` does not require it.
Install with ``pip install session_py``.
"""

import json

__all__ = ["model_to_session", "write_session"]

PLATE = "Plate"
COLUMN = "Column"
SOLID = "Solid"


def _import_session():
    """session_py, or an ImportError that says how to get it."""
    try:
        import session_py as sp
    except ImportError:
        raise ImportError(
            "compas_tf.session needs session_py.\n"
            "    pip install session_py"
        )
    return sp


def _sp_polyline(sp, points, name):
    """A closed session_py Polyline from compas points."""
    polyline = sp.Polyline([sp.Point(float(p[0]), float(p[1]), float(p[2])) for p in points])
    polyline.name = name
    return polyline


def _mesh(sp, compas_mesh):
    """compas Mesh -> session_py Mesh, faces kept as n-gons."""
    vertices, faces = compas_mesh.to_vertices_and_faces()
    return sp.Mesh.from_vertices_and_faces(
        [sp.Point(float(x), float(y), float(z)) for x, y, z in vertices], faces
    )


def _plate_payload(sp, element):
    """``{"type","bottom","top","reversed"}`` for a plate, or None if it is not one.

    ``fabrication_polylines`` (plates) and ``end_polylines`` (wedges) both return a
    world-space, closed, co-wound ``(bottom, top)`` pair whose vertex *i* on one
    side corresponds to vertex *i* on the other - which is exactly the
    representation wood rebuilds a plate from.

    The pair is only usable if the two loops have the same length. Nothing in
    compas_tf enforces that (the polygon constructor does no count check, and
    ``loft`` de-duplicates each loop independently), so it is checked here rather
    than assumed: a mismatched plate is reported and exported as a plain solid.
    """
    pair = None
    if hasattr(element, "fabrication_polylines"):
        pair = element.fabrication_polylines()
    elif hasattr(element, "end_polylines"):
        pair = element.end_polylines()
    if not pair:
        return None

    bottom, top = pair
    if bottom is None or top is None or len(bottom) != len(top) or len(bottom) < 4:
        return None

    return {
        "type": PLATE,
        "bottom": _sp_polyline(sp, bottom, "bottom").__jsondump__(),
        "top": _sp_polyline(sp, top, "top").__jsondump__(),
        # compas_tf co-orients the pair at construction (bottom wound CCW about
        # the bottom -> top direction), which is already wood's convention.
        "reversed": False,
    }


def _column_payload(sp, element):
    """``{"type","axis","section"}`` for a column, or None.

    ``center_line`` and the width/depth section are stored in the column's own
    frame; the placement lives on the ancestor group nodes, so both are pushed
    through ``modeltransformation`` to land in world space beside the mesh.
    """
    line = getattr(element, "center_line", None)
    if line is None:
        return None

    transformation = element.modeltransformation
    start, end = line.start, line.end
    if transformation is not None:
        start = start.transformed(transformation)
        end = end.transformed(transformation)

    axis = sp.Line(
        float(start[0]), float(start[1]), float(start[2]),
        float(end[0]), float(end[1]), float(end[2]),
    )
    axis.name = "axis"

    payload = {"type": COLUMN, "axis": axis.__jsondump__()}

    # The section is the stock rectangle about the axis start, in the column's
    # own frame, transformed with it. Absent width/depth just omits it.
    width = getattr(element, "width", None)
    depth = getattr(element, "depth", None)
    if width and depth:
        from compas.geometry import Point as CPoint

        half_w, half_d = float(width) / 2.0, float(depth) / 2.0
        corners = [
            CPoint(-half_w, -half_d, 0.0), CPoint(half_w, -half_d, 0.0),
            CPoint(half_w, half_d, 0.0), CPoint(-half_w, half_d, 0.0),
        ]
        corners.append(corners[0])
        if transformation is not None:
            corners = [c.transformed(transformation) for c in corners]
        payload["section"] = _sp_polyline(sp, corners, "section").__jsondump__()

    return payload


def _group_path(element):
    """Ancestor group names, root first: ``("floor_model", "quarters_model", ...)``.

    The tree node chain runs leaf -> root and ends at a node with no element (the
    tree root itself), which is dropped.
    """
    node = getattr(element, "treenode", None)
    if node is None:
        return ()
    names = []
    for ancestor in node.ancestors:
        group = getattr(ancestor, "element", None)
        if group is None:
            break
        names.append(group.name)
    return tuple(reversed(names))


def _ensure_group(sp, session, groups, path):
    """The TreeNode for `path`, creating it and its parents once each. () is the root.

    Session.add_group always attaches to the root, so nesting goes through
    Session.add(node, parent) instead.
    """
    if not path:
        return None
    if path not in groups:
        parent = _ensure_group(sp, session, groups, path[:-1])
        node = sp.TreeNode(path[-1])
        session.add(node, parent)
        groups[path] = node
    return groups[path]


def model_to_session(model, name=None):
    """Build a session_py Session from `model`, one tagged Element per element."""
    sp = _import_session()

    session = sp.Session(name or "model")
    groups = {}
    counts = {PLATE: 0, COLUMN: 0, SOLID: 0}
    demoted = []

    for element in model.geometry_elements():
        geometry = element.modelgeometry
        if geometry is None:
            continue

        payload = _plate_payload(sp, element)
        if payload is not None:
            element_type = PLATE
        else:
            payload = _column_payload(sp, element)
            element_type = COLUMN if payload is not None else SOLID
            # A plate-shaped class that failed the pair check is a real problem
            # worth naming, not a silent demotion to Solid.
            if element_type == SOLID and hasattr(element, "fabrication_polylines"):
                demoted.append(element.name)

        out = sp.Element(_mesh(sp, geometry), element.name)
        out._element_type = element_type
        out._element_data = (
            json.dumps(payload, separators=(",", ":")).encode() if payload else b""
        )
        session.add_element(out, _ensure_group(sp, session, groups, _group_path(element)))
        counts[element_type] += 1

    print(
        "{} elements ({} plates, {} columns, {} solids) in {} groups".format(
            sum(counts.values()), counts[PLATE], counts[COLUMN], counts[SOLID], len(groups)
        )
    )
    if demoted:
        print("  {} plate(s) had a mismatched outline pair, exported as solids: {}".format(
            len(demoted), ", ".join(sorted(set(demoted)))
        ))
    return session


def write_session(model, path, name=None):
    """Write `model` to a session .pb at `path`. Returns the path."""
    import os

    session = model_to_session(model, name)
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    session.pb_dump(str(path))
    print("-> {} ({:.1f} MB)".format(path, os.path.getsize(path) / 1e6))
    return str(path)
