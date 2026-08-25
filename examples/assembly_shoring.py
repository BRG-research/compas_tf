"""The raking props and the centre tower, shared by two assembly steps.

NOT an example - a helper the ``example_model_23_assembly_*`` scripts import.

The props show up twice in the sequence, and the two have to agree to the
millimetre:

* **Step 1** stakes out where they land on the slab - the prop base plates and
  the tower's four legs. The feet are marked in the
  same session as the column bases, because the total station is already set up
  on the centre of the bay and a second set-up would be a second chance to be
  wrong. By the time the props are carried in, their feet are already on the
  slab.
* **Step 4** stands them up: the props against the columns, the tower on its
  legs. Nothing is measured there - by then the marks are on the floor.

So the layout lives here rather than in either step, and both read the marks off
the SAME geometry: step 1 marks the base plates of these props, step 4 draws
them. A number typed twice is a number that drifts.

The layout is the one ``examples/example_model_10_shoring.py`` uses: two props
per column at right angles, clamped on the column face at ``PROP_HEIGHT`` and
reaching ``PROP_HEIGHT`` along the slab, the pair spun four times about the
centre of the bay. The props rake INBOARD, along the two edges of the bay that
meet at their column, which is the orientation that example places them in.
"""

import math

from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector

from compas_tf.model import TFModel
from compas_tf.schoring_element import Dataset
from compas_tf.schoring_element import SchoringElement
from compas_tf.tower_element import TowerElement

COLUMN_SIZE = 220  # the shaft the raking props clamp on to
PROP_HEIGHT = 2500  # clamp height on the column, and the reach of the foot out onto the slab

# The part of a prop that stands on the slab - the one step 1 stakes out.
BASE_PLATE = Dataset.schoring_head_0


def raking_props(corner):
    """The eight raking props, two per column, in bay coordinates.

    Parameters
    ----------
    corner : :class:`compas.geometry.Point`
        The centre line of one column - the props are laid out around it and the
        pair is then rotated a quarter turn at a time onto the other three.

    Returns
    -------
    list[:class:`compas_tf.model.TFModel`]
        One small model per prop, each holding the prop's parts.
    """
    # ``from_points_and_vectors`` sizes the telescoping bodies to the distance
    # between the two ends, so a prop is placed by naming its ends: the clamp on
    # the face of the column, and the plate out on the slab.
    brace_x = SchoringElement.from_points_and_vectors(
        p0=Point(COLUMN_SIZE / 2, 0, PROP_HEIGHT),
        v0=Vector(0, 0, 1),
        p1=Point(PROP_HEIGHT, 0, 0),
        v1=Vector(1, 0, 0),
        dataset_foot=Dataset.schoring_foot_0,
        dataset_head=BASE_PLATE,
        dataset_body0=Dataset.schoring_body_start_0,
        dataset_body1=Dataset.schoring_body_end_0,
    )
    brace_x.transformation *= Translation.from_vector(Vector(corner.x, corner.y, 0))

    # The second prop on the same column is the first turned a quarter about the
    # column, so it takes the other direction.
    brace_y = brace_x.duplicate()
    brace_y.transformation = Translation.from_vector(Vector(corner.x, corner.y, 0)) * Rotation.from_axis_and_angle(Vector(0, 0, 1), math.pi / 2, Point(0, 0, 0))

    # .duplicate() gives independent copies (new guids), so the pair can be spun
    # round the bay without the four columns sharing elements.
    props = []
    for index in range(4):
        quarter = Rotation.from_axis_and_angle(Vector(0, 0, 1), index * math.pi / 2, Point(0, 0, 0))
        for base in (brace_x, brace_y):
            prop = base.duplicate()
            prop.transformation = quarter * prop.transformation
            props.append(prop)
    return props


def base_plate_mesh(prop):
    """The mesh of the plate this prop stands on."""
    part = next(element for element in prop.elements() if isinstance(element, SchoringElement) and element.dataset == BASE_PLATE)
    return part.modelgeometry


def plate_outline(mesh):
    """Centre and four corners of a base plate, read off its own lowest face.

    The plate sits flat on the slab, so its lowest ring of vertices IS the
    footprint. The four corners are the extreme points of that ring along the
    two diagonals, which finds them whichever way round the plate is turned.
    """
    points = [mesh.vertex_point(vertex) for vertex in mesh.vertices()]
    zmin = min(point.z for point in points)
    lowest = [point for point in points if abs(point.z - zmin) < 1e-6]

    corners = [
        min(lowest, key=lambda point: point.x + point.y),
        min(lowest, key=lambda point: point.x - point.y),
        max(lowest, key=lambda point: point.x + point.y),
        max(lowest, key=lambda point: point.x - point.y),
    ]
    centre = Point(sum(point.x for point in corners) / 4, sum(point.y for point in corners) / 4, zmin)
    return centre, corners


def prop_feet(props):
    """Where every prop meets the slab: ``(centre, corners)`` per prop."""
    return [plate_outline(base_plate_mesh(prop)) for prop in props]


# ------------------------------------------------------------------ #
# The tower at the centre of the bay.
# ------------------------------------------------------------------ #

TOWER_TURN = math.pi / 4  # legs onto the axes of the bay, faces to the columns
CLUSTER = 300.0  # two base vertices closer than this in plan are the same foot


def centre_tower():
    """The scaffold tower on the centre of the bay, as a mesh in bay coordinates.

    Turned 45 degrees, so its legs stand on the axes of the bay and its faces
    look at the four columns. It has to live in a model for ``modelgeometry`` to
    resolve, hence the one-element ``TFModel``.
    """
    tower = TowerElement()
    tower.transformation = Rotation.from_axis_and_angle(Vector(0, 0, 1), TOWER_TURN, Point(0, 0, 0))
    model = TFModel("tower")
    model.add_element(tower)
    mesh = tower.modelgeometry
    mesh.name = "tower"
    return mesh


def tower_feet(mesh):
    """The four legs of the tower: ``(leg point, base plate corners)`` each.

    The bottom ring of vertices is every corner of every leg's base plate. They
    cluster into four groups - one per leg - and the mean of a group is the leg
    point. The legs are then ordered anticlockwise from the +x axis, so the
    numbering is geometric and does not depend on how the mesh is stored.
    """
    points = [mesh.vertex_point(vertex) for vertex in mesh.vertices()]
    zmin = min(point.z for point in points)
    lowest = [point for point in points if abs(point.z - zmin) < 1e-6]

    clusters = []
    for point in lowest:
        for cluster in clusters:
            if (cluster[0].x - point.x) ** 2 + (cluster[0].y - point.y) ** 2 < CLUSTER**2:
                cluster.append(point)
                break
        else:
            clusters.append([point])

    legs = []
    for cluster in clusters:
        centre = Point(sum(point.x for point in cluster) / len(cluster), sum(point.y for point in cluster) / len(cluster), zmin)
        corners = sorted(cluster, key=lambda point: math.atan2(point.y - centre.y, point.x - centre.x))
        legs.append((centre, corners))
    return sorted(legs, key=lambda leg: (math.degrees(math.atan2(leg[0].y, leg[0].x)) + 45) % 360)
