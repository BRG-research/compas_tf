"""Unroll the unique floor parts into 2D strips and pack the strips with
``compas_nest.pack``.

The floor is built from four identical quarters, so only the unique parts are
oriented: one quarter of the slab, the oculus and one column.

Within a quarter the plates belong to **strips** (a quarter has three beds, the
t-sections, the ribs, the inner beams ...). A strip is *unrolled* by flattening
each of its plates onto ``Frame.worldXY`` and laying them in a row, so the
plates of one strip stay next to each other and are clearly read as a unit.
``pack`` then arranges those strip-blocks on the sheet.

Two levels of layout:

    1. unroll  — each strip's plates flattened (own base frame) and placed in a row
    2. pack    — the strip blocks arranged in a grid, each strip kept together

For every plate the viewer shows a group with its bottom polyline, top polyline
and the mesh; the column keeps its real ``modelgeometry`` (with the boolean
cuts).

Run ``example_2_floor_model_booleans.py`` first to produce
``data/floor_model_booleans.json``.

Reference: https://github.com/petrasvestartas/compas_nest
"""

import pathlib

import compas
from compas.colors import Color
from compas.geometry import Frame
from compas.geometry import Polyline
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Vector
from compas.geometry import angle_vectors_signed
from compas_model.elements.group import Group
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

import compas_nest
from compas_tf.plate import PlateElement

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Parameters
# ------------------------------------------------------------------ #

STRIP_COLUMNS = 4       # strip-blocks per row on the final sheet
STRIP_GAP = 200.0       # gap between strip-blocks
ROW_GAP = 60.0          # gap between plates inside a strip (the unrolled row)
BEDS_PER_STRIP = 6      # a quarter has three beds of six plates each

PALETTE = [
    Color(0.20, 0.45, 0.85), Color(0.95, 0.55, 0.10), Color(0.30, 0.70, 0.35),
    Color(0.85, 0.25, 0.30), Color(0.55, 0.35, 0.75), Color(0.20, 0.65, 0.70),
    Color(0.80, 0.60, 0.10), Color(0.50, 0.50, 0.50), Color(0.90, 0.40, 0.65),
    Color(0.35, 0.55, 0.20),
]
BOTTOM_COLOR = Color.black()
TOP_COLOR = Color.white()

# ------------------------------------------------------------------ #
#  Helpers
# ------------------------------------------------------------------ #


def _longest_edge_direction(points) -> Vector:
    best_len, best = -1.0, Vector.from_start_end(points[0], points[1])
    n = len(points)
    for i in range(n):
        v = Vector.from_start_end(points[i], points[(i + 1) % n])
        if v.length > best_len:
            best_len, best = v.length, v
    return best.unitized()


def face_frame(points, normal) -> Frame:
    xaxis = _longest_edge_direction(points)
    return Frame(points[0], xaxis, Vector(*normal).cross(xaxis))


def bbox_xy(polylines):
    xs = [p.x for pl in polylines for p in pl.points]
    ys = [p.y for pl in polylines for p in pl.points]
    return min(xs), min(ys), max(xs), max(ys)


def iter_plates(group):
    for element in group.children:
        if isinstance(element, Group):
            yield from iter_plates(element)
        elif isinstance(element, PlateElement):
            if not (element.name and element.name.startswith("column_cutter")):
                yield element


# ------------------------------------------------------------------ #
#  A "member" is one plate's geometry + the transform that takes it from
#  world into its place inside the unrolled strip.
# ------------------------------------------------------------------ #


def plate_member(plate):
    faces = plate.face_polylines
    T_flat = Transformation.from_frame_to_frame(plate.base_frame, Frame.worldXY())
    return {"plate": plate, "bottom": faces["bottom"], "top": faces["top"],
            "mesh": plate.modelgeometry, "T_flat": T_flat}


def column_member(column):
    """Column kept as its real cut mesh; bottom/top polylines from its box.

    ``box`` is in element-local space while ``modelgeometry`` is already in
    world space, so the box is moved to world first to keep both aligned.
    """
    box_mesh = column.box.to_mesh().transformed(column.modeltransformation)
    faces = list(box_mesh.faces())
    base = max(faces, key=box_mesh.face_area)
    base_n = box_mesh.face_normal(base)
    top = min((f for f in faces if f != base), key=lambda f: base_n.dot(box_mesh.face_normal(f)))

    def ring(f):
        pts = box_mesh.face_coordinates(f)
        return Polyline(pts + [pts[0]])

    T_flat = Transformation.from_frame_to_frame(face_frame(box_mesh.face_coordinates(base), base_n), Frame.worldXY())
    return {"plate": None, "bottom": ring(base), "top": ring(top), "mesh": column.modelgeometry, "T_flat": T_flat}


# --- edge-unfolding (topological surgery for discrete plates) ------- #


def _plate_edges(plate):
    pts = list(plate.face_polylines["bottom"].points[:-1])
    n = len(pts)
    return [(pts[i], pts[(i + 1) % n]) for i in range(n)]


def shared_edge(p, q, tol=5.0):
    """The edge (two world points) shared by plates p and q, or None."""
    for a0, a1 in _plate_edges(p):
        for b0, b1 in _plate_edges(q):
            if (a0.distance_to_point(b0) < tol and a1.distance_to_point(b1) < tol) or \
               (a0.distance_to_point(b1) < tol and a1.distance_to_point(b0) < tol):
                return a0, a1
    return None


def hinge_unfold(plates):
    """Unfold a set of edge-connected plates into one plane.

    Builds the shared-edge adjacency, spans it with a BFS tree from plates[0],
    and rotates every plate about its hinge edge into its parent's plane
    (``A[child] = A[parent] * R_hinge``). The whole assembly is then flattened
    to worldXY by the root's frame. Returns one transform per plate (world ->
    placed), or ``None`` if the plates are not all edge-connected.
    """
    n = len(plates)
    adj = {i: [] for i in range(n)}
    for i in range(n):
        for j in range(i + 1, n):
            e = shared_edge(plates[i], plates[j])
            if e is not None:
                adj[i].append((j, e))
                adj[j].append((i, e))

    A = [None] * n
    A[0] = Transformation()
    queue = [0]
    while queue:
        i = queue.pop(0)
        for j, (e0, e1) in [(j, e) for j, e in adj[i]]:
            if A[j] is not None:
                continue
            axis = Vector.from_start_end(e0, e1).unitized()
            n_parent = plates[i].base_frame.zaxis
            n_child = plates[j].base_frame.zaxis
            theta = angle_vectors_signed(n_child, n_parent, axis)
            R = Rotation.from_axis_and_angle(axis, theta, point=e0)
            A[j] = A[i] * R
            queue.append(j)

    if any(a is None for a in A):
        return None  # disconnected -> caller falls back to row layout

    T_root = Transformation.from_frame_to_frame(plates[0].base_frame, Frame.worldXY())
    return [T_root * a for a in A]


def layout_strip(members, gap=ROW_GAP):
    """Lay out a strip and write ``local_T`` (world -> strip-local) per member.

    Prefers an edge-unfold (plates hinged about their shared edges, faithful to
    the original and neighbour-adjacent); falls back to a simple row when the
    plates are not edge-connected (e.g. stacked or single-member strips).
    """
    plates = [m["plate"] for m in members]
    transforms = None
    if len(members) >= 2 and all(p is not None for p in plates):
        transforms = hinge_unfold(plates)

    if transforms is None:  # row fallback
        transforms, cursor = [], 0.0
        for m in members:
            flat = m["bottom"].transformed(m["T_flat"])
            minx, miny, maxx, maxy = bbox_xy([flat])
            transforms.append(Translation.from_vector([cursor - minx, -miny, 0.0]) * m["T_flat"])
            cursor += (maxx - minx) + gap
        method = "row"
    else:
        method = "unfold"

    # shift the whole block so its bbox starts at the origin
    placed = [m["bottom"].transformed(t) for m, t in zip(members, transforms)]
    minx, miny, maxx, maxy = bbox_xy(placed)
    shift = Translation.from_vector([-minx, -miny, 0.0])
    for m, t in zip(members, transforms):
        m["local_T"] = shift * t
    outline = Polyline([(0, 0, 0), (maxx - minx, 0, 0), (maxx - minx, maxy - miny, 0), (0, maxy - miny, 0), (0, 0, 0)])
    return outline, method


# ------------------------------------------------------------------ #
#  Load model and collect strips
# ------------------------------------------------------------------ #

model = compas.json_load(data_dir / "floor_model_booleans.json")
roots = [node.element for node in model.tree.root.children]
quarter_group = next(el for el in roots if isinstance(el, Group) and el.name == "floor_guide")
column = next(el for el in model.elements() if type(el).__name__ == "ColumnElement")

# Build strips: every subgroup is one strip, except `beds` which is the three
# beds of the quarter (chunks of BEDS_PER_STRIP), kept as separate strips.
strips = []  # list of {name, members}
for sub in quarter_group.children:
    if not isinstance(sub, Group):
        continue
    plates = sorted(iter_plates(sub), key=lambda p: int(p.name.rsplit("_", 1)[1]))
    if not plates:
        continue
    if sub.name == "beds":
        for i in range(0, len(plates), BEDS_PER_STRIP):
            strips.append({"name": f"bed_{i // BEDS_PER_STRIP}", "members": [plate_member(p) for p in plates[i:i + BEDS_PER_STRIP]]})
    else:
        strips.append({"name": sub.name, "members": [plate_member(p) for p in plates]})

strips.append({"name": "column", "members": [column_member(column)]})

print(f"[strips] {len(strips)}: " + ", ".join(f"{s['name']}({len(s['members'])})" for s in strips))

# ------------------------------------------------------------------ #
#  Level 1: unroll each strip into a row
# ------------------------------------------------------------------ #

geo = compas_nest.nest_geo()
for strip in strips:
    outline, method = layout_strip(strip["members"])
    strip["method"] = method
    geo.add_part(outline)
print("[layout] " + ", ".join(f"{s['name']}:{s['method']}" for s in strips))

# ------------------------------------------------------------------ #
#  Level 2: pack the strip-blocks (each strip stays together)
# ------------------------------------------------------------------ #

result = compas_nest.pack(geo, columns=STRIP_COLUMNS, gap_x=STRIP_GAP, gap_y=STRIP_GAP)
result.to_json(data_dir / "orient_2d.json")
sheets = result.placed_polylines()
print(f"[pack] sheets: {len(sheets)} | strips placed: {sum(len(s['parts']) for s in sheets)}")

# ------------------------------------------------------------------ #
#  Viewer — one group per strip; each plate keeps bottom/top polyline + mesh
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

for sheet in sheets:
    sheet_group = viewer.scene.add_group(f"sheet_{sheet['sheet_id']}")
    for placed in sheet["parts"]:
        strip = strips[placed["part_index"]]
        T_place = placed["transformation"]          # strip-local -> sheet
        color = PALETTE[placed["part_index"] % len(PALETTE)]
        strip_group = viewer.scene.add_group(strip["name"], parent=sheet_group)
        for m in strip["members"]:
            T = T_place * m["local_T"]               # world -> placed
            viewer.scene.add(m["mesh"].transformed(T), parent=strip_group, facecolor=color, show_lines=False)
            viewer.scene.add(m["bottom"].transformed(T), parent=strip_group, linecolor=BOTTOM_COLOR, linewidth=2)
            viewer.scene.add(m["top"].transformed(T), parent=strip_group, linecolor=TOP_COLOR, linewidth=1)

viewer.show()
