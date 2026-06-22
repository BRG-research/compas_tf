"""Orient the quarter to 2D, the simple way.

Only the **beds** (the horizontal floor plates) get special treatment: each row
of beds is **unrolled** (edge-unfolded) flat -- every bed is rotated about the
edge it shares with its neighbour into the neighbour's plane, so the shared
edges stay coincident: the beds touch exactly at their edges with no overlap,
and the real 3D mesh (with thickness) is preserved.

Every other plate is flattened flat onto ``Frame.worldXY`` and arranged in a
plain linear grid with ``compas_nest.pack``, placed next to the unrolled beds.

Run ``example_2_floor_model_booleans.py`` first to produce
``data/floor_model_booleans.json``.
"""

import os
import pathlib

import compas
import compas_nest
from compas.geometry import Frame
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Vector
from compas.geometry import angle_vectors_signed
from compas_model.elements.group import Group

from compas_tf.plate import PlateElement
from compas_tf.viewer import make_viewer

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  Parameters
# ------------------------------------------------------------------ #

PACK_COLUMNS = 6        # columns in the linear grid for the "other" plates
PACK_GAP = 150.0        # gap between packed plates (mm)
MARGIN = 500.0          # gap between the unrolled beds and the packed block (mm)
ROW_GAP = 150.0         # gap between the unrolled bed rows (mm)
BEDS_PER_ROW = 6        # the quarter has three rows of six beds


def family(plate):
    return plate.name.rsplit("_", 1)[0]


# ------------------------------------------------------------------ #
#  Flatten helper (for the packed "other" plates)
# ------------------------------------------------------------------ #


def flatten_to_origin(plate):
    """Flatten a plate true-size onto worldXY with its bbox min at the origin.
    Returns (transform, outline_polyline)."""
    T = Transformation.from_frame_to_frame(plate.base_frame, Frame.worldXY())
    pts = plate.face_polylines["bottom"].transformed(T).points[:-1]
    T = Translation.from_vector([-min(p.x for p in pts), -min(p.y for p in pts), 0.0]) * T
    return T, plate.face_polylines["bottom"].transformed(T)


# ------------------------------------------------------------------ #
#  Edge-unfolding (rotate each bed about its shared edge into the plane of its
#  neighbour, so the shared edges stay coincident -> beds touch exactly)
# ------------------------------------------------------------------ #


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
    """Unfold edge-connected plates into one plane. Builds the shared-edge
    adjacency, spans it with a BFS tree from plates[0] and rotates every plate
    about its hinge edge into its parent's plane (``A[child] = A[parent] *
    R_hinge``). Returns one world->flat transform per plate, or ``None`` if the
    plates are not all edge-connected.
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
        for j, (e0, e1) in adj[i]:
            if A[j] is not None:
                continue
            axis = Vector.from_start_end(e0, e1).unitized()
            theta = angle_vectors_signed(plates[j].base_frame.zaxis, plates[i].base_frame.zaxis, axis)
            R = Rotation.from_axis_and_angle(axis, theta, point=e0)
            A[j] = A[i] * R
            queue.append(j)

    if any(a is None for a in A):
        return None
    T_root = Transformation.from_frame_to_frame(plates[0].base_frame, Frame.worldXY())
    return [T_root * a for a in A]


def all_face_edges(plate):
    """Every boundary edge of every face (bottom, top, side walls) in world space."""
    fp = plate.face_polylines
    out = []
    for pl in [fp["bottom"], fp["top"], *fp["walls"]]:
        pts = list(pl.points[:-1])
        n = len(pts)
        out += [(pts[i], pts[(i + 1) % n]) for i in range(n)]
    return out


def connected(p, q, tol=8.0):
    """True if p and q share an edge across any of their faces."""
    for a0, a1 in all_face_edges(p):
        for b0, b1 in all_face_edges(q):
            if (a0.distance_to_point(b0) < tol and a1.distance_to_point(b1) < tol) or \
               (a0.distance_to_point(b1) < tol and a1.distance_to_point(b0) < tol):
                return True
    return False


def order_others(others):
    """Order the packed plates so every rib sits between the tsection(s) it is
    connected to -- an inner rib has two tsections, so it is placed as
    ``[tsection, rib, tsection]``; an outer rib as ``[tsection, rib]``. Because
    ``pack`` lays parts out in input order, the rib and its tsections land next
    to each other on the sheet."""
    tsecs = [p for p in others if family(p) == "tsections"]
    ribs = [p for p in others if "ribs" in p.name]
    used = set()
    order = []
    for rib in ribs:
        connected_tsecs = [t for t in tsecs if connected(rib, t)]
        if connected_tsecs:                       # first tsection, then the rib,
            order.append(connected_tsecs[0])      # then any remaining tsection(s)
            used.add(id(connected_tsecs[0]))
        order.append(rib)
        used.add(id(rib))
        for t in connected_tsecs[1:]:
            order.append(t)
            used.add(id(t))
    for p in others:           # everything else (beams, wedges, oculus) follows
        if id(p) not in used:
            order.append(p)
            used.add(id(p))
    return order


# ------------------------------------------------------------------ #
#  Load model, split beds from the rest
# ------------------------------------------------------------------ #

model = compas.json_load(data_dir / "floor_model_booleans.json")
roots = [node.element for node in model.tree.root.children]
quarter_group = next(el for el in roots if isinstance(el, Group) and el.name == "floor_guide")


def iter_plates(group):
    for element in group.children:
        if isinstance(element, Group):
            yield from iter_plates(element)
        elif isinstance(element, PlateElement):
            if not (element.name and element.name.startswith("column_cutter")):
                yield element


plates = list(iter_plates(quarter_group))
beds = [p for p in plates if family(p) == "beds"]
others = [p for p in plates if family(p) != "beds"]
print(f"[beds] {len(beds)} beds (kept as plan) + {len(others)} other plates (packed linearly)")

pieces = []  # {"plate", "T"}

# ------------------------------------------------------------------ #
#  Beds: unroll each row flat (edges stay coincident, no overlap), stacked.
# ------------------------------------------------------------------ #

beds = sorted(beds, key=lambda p: int(p.name.rsplit("_", 1)[1]))
rows = [beds[i:i + BEDS_PER_ROW] for i in range(0, len(beds), BEDS_PER_ROW)]

bed_w = 0.0
cursor_y = 0.0
for row in rows:
    transforms = hinge_unfold(row)
    if transforms is None:  # not all edge-connected -> fall back to flat-each
        transforms = [flatten_to_origin(b)[0] for b in row]
    # bbox of this unrolled row, then drop it at the running y-offset
    pts = [q for b, T in zip(row, transforms) for q in b.face_polylines["bottom"].transformed(T).points]
    minx, miny = min(p.x for p in pts), min(p.y for p in pts)
    maxx, maxy = max(p.x for p in pts), max(p.y for p in pts)
    off = Translation.from_vector([-minx, cursor_y - miny, 0.0])
    for b, T in zip(row, transforms):
        pieces.append({"plate": b, "T": off * T})
    cursor_y += (maxy - miny) + ROW_GAP
    bed_w = max(bed_w, maxx - minx)

plan_w = bed_w

# ------------------------------------------------------------------ #
#  Other plates: flatten flat and pack into a linear grid beside the plan
# ------------------------------------------------------------------ #

others = order_others(others)   # keep each rib next to its connected tsection(s)
print("[order]  " + ", ".join(p.name for p in others if family(p) in ("tsections",) or "ribs" in p.name))

geo = compas_nest.nest_geo()
flats = []
for plate in others:
    T0, outline = flatten_to_origin(plate)
    flats.append((plate, T0))
    geo.add_part(outline)

result = compas_nest.pack(geo, columns=PACK_COLUMNS, gap_x=PACK_GAP, gap_y=PACK_GAP)
block_offset = Translation.from_vector([plan_w + MARGIN, 0.0, 0.0])
for sheet in result.placed_polylines():
    for placed in sheet["parts"]:
        plate, T0 = flats[placed["part_index"]]
        pieces.append({"plate": plate, "T": block_offset * placed["transformation"] * T0})

# ------------------------------------------------------------------ #
#  Sheet size + outputs
# ------------------------------------------------------------------ #

allpts = [q for pc in pieces for q in pc["plate"].face_polylines["bottom"].transformed(pc["T"]).points]
sheet_w = max(p.x for p in allpts) - min(p.x for p in allpts)
sheet_h = max(p.y for p in allpts) - min(p.y for p in allpts)
print(f"[layout] sheet {sheet_w:.0f} x {sheet_h:.0f} mm")

# ------------------------------------------------------------------ #
#  Write
# ------------------------------------------------------------------ #

compas.json_dump({"placements": {pc["plate"].name: pc["T"] for pc in pieces},
                  "outlines": {pc["plate"].name: [[round(q.x, 2), round(q.y, 2)]
                               for q in pc["plate"].face_polylines["bottom"].transformed(pc["T"]).points[:-1]]
                               for pc in pieces},
                  "sheet": [sheet_w, sheet_h]},
                 data_dir / "unwrap_beds.json")
print("[out]    data/unwrap_beds.json")


# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

if os.environ.get("HEADLESS"):
    print("[viewer] skipped (HEADLESS set)")
    raise SystemExit

viewer = make_viewer(data_dir)

for pc in pieces:
    plate = pc["plate"]
    T = pc["T"]
    group = viewer.scene.add_group(plate.name)
    # show_lines=False hides the internal (coplanar) mesh triangulation
    viewer.scene.add(plate.modelgeometry.transformed(T), parent=group, show_lines=False)
    # draw the clean face outlines so the real edges still read
    viewer.scene.add(plate.face_polylines["bottom"].transformed(T), parent=group)
    viewer.scene.add(plate.face_polylines["top"].transformed(T), parent=group)

viewer.show()
