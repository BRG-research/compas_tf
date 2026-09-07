"""Assembly step 1 - build the quarters and the oculus in a jig.

First of the ``example_model_23_assembly_*`` series. Each step writes one
coloured preview to ``data/assembly/``, which the docs publish at ``_models/``
and ``docs/assembly.md`` embeds as a 3D viewer under a title and a description.

This step is the shop, before anything reaches the slab. A quarter frame and the
oculus are built face down in jig boards, so the face that becomes the soffit
points at the ceiling and the beds go on downhand.

Both pieces are placed as ONE rigid body each, not plate by plate:

- the quarter is turned **upside down** - a 180 deg rotation about the X axis
  through its own plan centre line, which leaves its 3000 x 3000 plan footprint
  where it was and lands it on ``z = 0``;
- the oculus is turned **45 deg about Z**, which is what squares its 2000 x 2000
  diamond into a 1414 x 1414 block on the bench, and set down beside the quarter
  across a clear aisle.

The jig board under each piece is its own plan bounding box grown by
:data:`MARGIN` all round and :data:`BOARD` thick, straddling ``z = 0`` - so the
piece sinks half the board's thickness into it. The pocket is cut by a boolean:
``board - pieces``. What that boolean REMOVES is drawn in red, one solid per
plate, because the pocket a plate drops into is the only part of this step that
is not simply the part itself.
"""

import pathlib

import compas
from compas.colors import Color
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_occt import _occt
from compas_occt.brep import OCCBrep
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.plate import PlateElement
from compas_tf.writer import write_colored_obj

data_dir = pathlib.Path(__file__).parent.parent / "data"
assembly_dir = data_dir / "assembly"
assembly_dir.mkdir(parents=True, exist_ok=True)

STEP = "assembly_step1"

TIMBER = Color(0.72, 0.74, 0.76)  # the plates of both pieces
JIG = Color(0.72, 0.74, 0.76, 0.4)  # the jig boards - see-through, so the pocket reads
CUT = Color(0.9, 0.2, 0.2)  # what the boolean takes out of the board: the pockets
BLACK = Color(0.05, 0.05, 0.05)

MARGIN = 100.0  # mm the board is grown past the piece's plan bounding box
BOARD = 50.0  # mm board thickness, centred on z = 0
AISLE = 1200.0  # mm of clear bench between the two pieces

model: TFModel = TFModel.from_model(compas.json_load(data_dir / "cantilevers_model.json"))


def find_node(node, name):
    """The tree node whose element is named ``name``, searched depth-first."""
    element = getattr(node, "element", None)
    if element is not None and getattr(element, "name", None) == name:
        return node
    for child in getattr(node, "children", []) or []:
        found = find_node(child, name)
        if found is not None:
            return found
    return None


def plates_in(node):
    """Every PlateElement at or below ``node``."""
    out = []
    element = getattr(node, "element", None)
    if isinstance(element, PlateElement):
        out.append(element)
    for child in getattr(node, "children", []) or []:
        out.extend(plates_in(child))
    return out


quarter = model.find_group_with_name("quarter_model_0")
beds = set(plates_in(find_node(quarter.tree.root, "beds_0")))
# The frame only: the beds are laid into it later, downhand, so they are not
# in the jig at this point.
frame_plates = [p for p in quarter.elements() if isinstance(p, PlateElement) and p not in beds]
oculus_plates = [p for p in model.find_group_with_name("oculus").elements() if isinstance(p, PlateElement)]


def plate_brep(plate, xform):
    """The plate as a solid Brep: two planar caps plus one quad per edge.

    ``bottom`` / ``top`` are stored in the plate's OWN frame, so the plate's
    ``modeltransformation`` has to be composed under the piece transform - the
    piece move alone would leave every plate at the origin of its own frame.
    """
    placed = xform * plate.modeltransformation
    bottom = [Point(*p).transformed(placed) for p in plate.bottom.points]
    top = [Point(*p).transformed(placed) for p in plate.top.points]
    if bottom[0].distance_to_point(bottom[-1]) < 1e-9:
        bottom = bottom[:-1]
    if top[0].distance_to_point(top[-1]) < 1e-9:
        top = top[:-1]
    rise = Vector.from_start_end(Point(*Polygon(bottom).centroid), Point(*Polygon(top).centroid))
    if rise.dot(Polygon(bottom).normal) < 0:  # keep the winding outward
        bottom = list(reversed(bottom))
        top = list(reversed(top))
    polygons = [Polygon(list(reversed(bottom))), Polygon(top)]
    for i in range(len(bottom)):
        j = (i + 1) % len(bottom)
        polygons.append(Polygon([bottom[i], bottom[j], top[j], top[i]]))
    brep = OCCBrep.from_polygons(polygons, solid=True)
    brep.name = plate.name
    return brep


def vertical_cutter(solid, board, ztop, zbottom):
    """The plate's plan outline, swept straight down - the jig pocket.

    Cutting the board with the PLATE would leave the pocket raked at whatever
    angle the plate sits at, and a raked pocket can be neither cut nor dropped
    into. What a jig board needs is the plate's vertical projection, swept
    through the board, so every wall comes out plumb.

    The projection is taken in 2D and swept ONCE, rather than by sweeping each
    downward-facing face and unioning the results. Both cover the same outline,
    but the per-face version leaves the near-vertical faces of a plate as walls
    raked 5-10 degrees off plumb - it cannot tell a shallow underside from a
    steep flank. Flattening to XY first removes that distinction by
    construction, and it is also what lets a hole in the outline stay a hole:
    the union comes back with interior rings, and each becomes a loop in the
    swept face.

    Only the part of the plate that actually enters the board is projected. The
    piece is a quarter of a doubly curved floor turned over, so most of it is in
    the air: the t-sections sit between z=172 and z=701, clear of a board that
    spans z=-25 to z=+25. Projecting the whole plate would cut their outline into
    a board they never touch - a pocket for the far side of the piece. Clipping
    to the board first restricts the pockets to the 18 plates that reach it.

    Sweeping the plate's ``top`` polyline instead does NOT work, and silently: a
    rib or t-section stands on edge, so that face is vertical and sweeping it
    vertically collapses to zero volume - 13 of this quarter's 16 plates.
    Intersecting the plate's own bottom and top outlines does not work either,
    for the same reason plus one more: on the 20 plates that stand on edge or
    rake, the two outlines project to lines, or miss each other entirely.
    """
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import unary_union

    footprint = OCCBrep.from_boolean_intersection(board, solid)
    if not (footprint.solids or footprint.faces):
        return None  # this plate is on the far side of the piece; it meets no board

    flat = []
    for face in footprint.faces:
        polygon = face.to_polygon()
        if abs(polygon.normal.unitized()[2]) < 1e-9:  # a plumb face projects to a line
            continue
        shape = ShapelyPolygon([(point[0], point[1]) for point in polygon.points])
        if shape.is_valid and shape.area > 1e-9:
            flat.append(shape)
    if not flat:
        return None

    merged = unary_union(flat)
    outlines = list(getattr(merged, "geoms", [merged]))

    def ring_face(ring):
        """A planar face from a shapely ring, or None if it is too thin to build.

        Shapely leaves repeated points where the projected faces met, and OCCT
        refuses a wire with a zero-length edge, so the duplicates go first.
        """
        points = []
        for x, y in ring:
            if not points or abs(points[-1][0] - x) > 1e-6 or abs(points[-1][1] - y) > 1e-6:
                points.append((x, y))
        if len(points) > 1 and abs(points[0][0] - points[-1][0]) < 1e-6 and abs(points[0][1] - points[-1][1]) < 1e-6:
            points.pop()
        if len(points) < 3:
            return None
        try:
            return OCCBrep.from_native(_occt.make_face_polygon([[x, y, ztop] for x, y in points])).faces[0]
        except Exception:
            return None

    prisms = []
    for outline in outlines:
        if outline.area <= 1e-9:
            continue
        outer = ring_face(list(outline.exterior.coords)[:-1])
        if outer is None:
            continue
        for interior in outline.interiors:  # a hole in the outline stays a hole in the pocket
            inner = ring_face(list(interior.coords)[:-1])
            if inner is not None:
                outer.add_loop(inner.outerloop, reverse=True)
        prisms.append(OCCBrep.from_extrusion(outer, Vector(0, 0, zbottom - ztop)))

    if not prisms:
        return None
    swept = prisms[0]
    for prism in prisms[1:]:
        swept = OCCBrep.from_boolean_union(swept, prism)
    return swept


def bounds(plates, xform=None):
    """``(min, max)`` of the plates' placed geometry."""
    points = []
    for plate in plates:
        for point in plate.modelgeometry.vertices_attributes("xyz"):
            points.append(Point(*point).transformed(xform) if xform else Point(*point))
    return ([min(p[k] for p in points) for k in range(3)], [max(p[k] for p in points) for k in range(3)])


# ------------------------------------------------------------------ #
# Turn the quarter upside down, in place: rotate 180 deg about the X axis
# running through its own plan centre (so the plan footprint does not move),
# then drop what was the top down onto z = 0.
# ------------------------------------------------------------------ #
lo, hi = bounds(frame_plates)
y_centre = (lo[1] + hi[1]) * 0.5
quarter_xform = Translation.from_vector([0.0, 2.0 * y_centre, hi[2]]) * Rotation.from_axis_and_angle([1, 0, 0], 3.141592653589793)

# ------------------------------------------------------------------ #
# The oculus is a diamond on the building grid; 45 deg about Z squares it onto
# the bench. Then set it down across the aisle from the quarter, centred on the
# quarter's own y, resting on z = 0.
# ------------------------------------------------------------------ #
q_lo, q_hi = bounds(frame_plates, quarter_xform)
spun = Rotation.from_axis_and_angle([0, 0, 1], 3.141592653589793 / 4)
o_lo, o_hi = bounds(oculus_plates, spun)
oculus_xform = (
    Translation.from_vector(
        [
            q_hi[0] + AISLE - o_lo[0],
            (q_lo[1] + q_hi[1]) * 0.5 - (o_lo[1] + o_hi[1]) * 0.5,
            -o_lo[2],
        ]
    )
    * spun
)

pieces = [("jig_quarter_0", frame_plates, quarter_xform), ("jig_oculus", oculus_plates, oculus_xform)]

breps = []
boards = []
pockets = []
totals = []

for board_name, plates, xform in pieces:
    solids = [plate_brep(plate, xform) for plate in plates]
    breps.extend(solids)

    lo, hi = bounds(plates, xform)
    # Centred on z = 0, so the piece sinks half the board into its own pocket.
    board_box = Box(
        xsize=(hi[0] - lo[0]) + 2 * MARGIN,
        ysize=(hi[1] - lo[1]) + 2 * MARGIN,
        zsize=BOARD,
        frame=Frame([(lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5, 0.0]),
    )
    board = OCCBrep.from_box(board_box)

    # The cutter for each plate is a SIMPLE VERTICAL EXTRUSION, not the plate
    # itself: take the face that was topmost in the building - after the flip it
    # is the plate's bottom-most face - and sweep it straight down through the
    # board. Cutting with the plate would leave the pocket walls raked at
    # whatever angle the plate sits at; sweeping one face vertically gives a
    # pocket with vertical walls, which is the only kind a jig can be cut with.
    cutters = [vertical_cutter(solid, board, BOARD, -BOARD) for solid in solids]

    for solid, cutter in zip(solids, cutters):
        if cutter is None:
            continue
        removed = OCCBrep.from_boolean_intersection(board, cutter)
        if removed.solids or removed.faces:
            removed.name = f"{solid.name}_pocket"
            pockets.append(removed)

    board = OCCBrep.from_boolean_difference(board, [c for c in cutters if c is not None])
    board.name = board_name
    boards.append(board)

    totals.append((board_name, plates, lo, hi, board_box))

# ------------------------------------------------------------------ #
# Write the preview the docs page loads (OBJ + MTL, one colour per role).
# ------------------------------------------------------------------ #
written = write_colored_obj(
    [(brep, TIMBER) for brep in breps]
    + [(board, JIG) for board in boards]
    # The pockets go in LAST and in red: they sit inside the boards, so they
    # only read once the board around them is see-through.
    + [(pocket, CUT) for pocket in pockets],
    assembly_dir / f"{STEP}_preview.obj",
)
print("written: " + ", ".join(str(path) for path in written.values()))

# ------------------------------------------------------------------ #
# And the totals the docs page shows under the viewer.
# ------------------------------------------------------------------ #
(q_name, q_plates, ql, qh, q_board) = totals[0]
(o_name, o_plates, ol, oh, o_board) = totals[1]
bench_x = oh[0] - ql[0]
bench_y = max(qh[1] - ql[1], oh[1] - ol[1])

lines = [
    "<!-- Generated by examples/example_model_23_assembly_step1.py - do not edit.",
    "     The prose around these lists is in docs/assembly.md; only the",
    "     numbers live here. -->",
    "",
    "<!-- --8<-- [start:totals] -->",
    f"- 2 pieces on the bench &mdash; 1 quarter frame, {len(q_plates)} plates ({len(beds)} beds go on later); 1 oculus, {len(o_plates)} plates",
    f"- quarter upside down &mdash; {qh[0] - ql[0]:.0f} &times; {qh[1] - ql[1]:.0f} mm on the bench, {qh[2] - ql[2]:.0f} mm tall",
    f"- oculus face down &mdash; {oh[0] - ol[0]:.0f} &times; {oh[1] - ol[1]:.0f} mm on the bench, {oh[2] - ol[2]:.0f} mm tall",
    f"- {AISLE:.0f} mm clear aisle between them, both set down on `z = 0`",
    f"- {bench_x:.0f} &times; {bench_y:.0f} mm of bench for the two side by side",
    f"- 2 jig boards &mdash; the piece's bounding box offset {MARGIN:.0f} mm all round, {BOARD:.0f} mm thick, the piece cut out of it:"
    f" {q_board.xsize:.0f} &times; {q_board.ysize:.0f} mm under the quarter,"
    f" {o_board.xsize:.0f} &times; {o_board.ysize:.0f} mm under the oculus",
    "<!-- --8<-- [end:totals] -->",
    "",
]
points_file = assembly_dir / f"{STEP}_points.md"
points_file.write_text("\n".join(lines))
print(f"written: {points_file}")

# ------------------------------------------------------------------ #
# Viewer
# ------------------------------------------------------------------ #
viewer = Viewer()

pieces_group = viewer.scene.add_group("pieces_in_the_jig")
for brep in breps:
    viewer.scene.add(brep, name=brep.name, parent=pieces_group, facecolor=TIMBER, linecolor=BLACK)

boards_group = viewer.scene.add_group("jig_boards")
for board in boards:
    viewer.scene.add(board, name=board.name, parent=boards_group, facecolor=JIG, opacity=0.4, linecolor=BLACK)

pockets_group = viewer.scene.add_group("boolean_cutters")
for pocket in pockets:
    viewer.scene.add(pocket, name=pocket.name, parent=pockets_group, facecolor=CUT)

print(f"{len(breps)} plates, {len(boards)} jig boards, {len(pockets)} pockets cut")


viewer.show()
