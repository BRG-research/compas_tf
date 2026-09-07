import math
from pathlib import Path
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Brep
from compas.geometry import Circle
from compas.geometry import Cylinder
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Transformation
from compas.geometry import Vector

from compas_tf.element import TFElement
from compas_tf.element import TFFeature
from compas_tf.element import baked


def _hex_prism(across_flats: float, bottom: float, top: float) -> Brep:
    """A hexagonal prism about the z axis, given its wrench size.

    A nut is specified across the flats, so that is what this takes; the
    circumradius follows. Built from its own planar faces, which makes the
    result exact - a prism has no curved surface to approximate.
    """
    radius = across_flats / (2 * math.cos(math.pi / 6))
    corners = [(radius * math.cos(index * math.pi / 3), radius * math.sin(index * math.pi / 3)) for index in range(6)]
    low = Polygon([Point(x, y, bottom) for x, y in corners])
    high = Polygon([Point(x, y, top) for x, y in corners])
    sides = [Polygon([low[index], low[(index + 1) % 6], high[(index + 1) % 6], high[index]]) for index in range(6)]
    return Brep.from_polygons([Polygon(list(reversed(low.points)))] + sides + [high])


class SupportFeature(TFFeature):
    pass


class SupportElement(TFElement):
    """Class representing a column-base element constructed from an OBJ file.

    Connection type: Sherpa Power Base 150402_PB_L-140-C.

    From the manufacturer's geometric data table ("SHERPA Power Base C,
    Montageanleitung / Assembly instructions", V2_042015), row *Power Base
    L 140 C*:

    ==========================  ====================================
    Head plate (Kopfplatte)     Ø 106 mm, t = 12 mm
    Base plate (Sockelplatte)   140 x 140 mm, t = 12 mm
    Base plate drilling         4 x Ø 15 mm
    Ground anchors              4 metal expansion dowels or concrete screws
    Column screws               3 x SHERPA 8 x 160 mm (timber >= 120 x 120)
                                or 3 x 8 x 180 mm (timber >= 140 x 140),
                                driven at approx. 25 degrees
    Height adjustment           150 - 200 mm
    Load capacity R1,d          max. 138 kN
    ==========================  ====================================

    So the connector is not just the cast body: **4 anchors down into the slab
    and 3 screws up into the column** are part of it, and they are modelled
    here - see :attr:`ground_anchors` and :attr:`column_screws`.

    References
    ----------
    * Product page:
      https://www.sherpa-connector.com/de/produkte/power-base/power-base-c/3391_306_shop_SHERPA-Power-Base-L-140-C.aspx?LNG=de
    * Assembly instructions (geometric data table):
      https://www.harrer.at/data/db/072017_SHERPA_Montageanleitung_PB_C.pdf
    * "Sherpa Connector Power Base for Post Supports" (video):
      https://www.youtube.com/watch?v=jxFHtDUMXdI

    Notes
    -----
    How far the bundled mesh can be trusted, checked against the two documents
    above:

    * **Right, and more deliberate than it looks.** The shaft's two hexagonal
      sections measure 54.99 and 36.37 mm across the flats - the design guide's
      coupling nut ("open-end wrench 55 mm") and height adjustment ("SW 32
      resp. 36 mm"). Those are real hexagons, not coarse circles, and must not
      be smoothed.
    * **Right.** Base plate 140 x 140 x 12 with four Ø 15 drillings; head plate
      Ø 106 x 12; overall 150 mm, the bottom of the L range.
    * **Too coarse.** The head plate is drawn as a hexagon. :attr:`head_plate`
      rebuilds it round, which is what a Ø 106 pocket has to be cut to.
    * **Missing.** The centring spike on the head plate, its three angled screw
      holes and the three smaller holes between them (all visible in the photo
      on the assembly page), and the cone that seats the plate on the
      substructure. Sherpa publishes no dimensioned drawing of any of them in
      the material reachable here, so the screws are placed from the constants
      above rather than found in the mesh.

    Parameters
    ----------
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the support element.
    features : list[:class:`SupportFeature`], optional
        The features of the support element.
    name : str, optional
        The name of the support element.

    Attributes
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry loaded from the OBJ file.
    top_polygon : :class:`compas.geometry.Polygon`
        The top polygon of the support (circular, Ø 106 mm).
    bottom_polygon : :class:`compas.geometry.Polygon`
        The bottom polygon of the support (square, 140 x 140 mm).
    """

    # Package data, NOT the repo's data/ folder: this mesh is read in
    # __init__, so every deserialization of a model containing a support
    # needs it. Pointing outside the package made an installed compas_tf
    # resolve it to <site-packages>/../../data and fail with FileNotFoundError.
    DATA_DIR = Path(__file__).parent / "data"
    MESH_FILE = "column_base_power_base_sherpa_150402_PB_L-140-C.obj"

    # --- printed in the manufacturer's geometric data table ---
    HEAD_PLATE_DIAMETER = 106  # mm
    HEAD_PLATE_THICKNESS = 12  # mm
    BASE_PLATE_SIZE = 140  # mm
    BASE_PLATE_THICKNESS = 12  # mm
    BASE_PLATE_HOLE_DIAMETER = 15  # mm, the 4 anchor drillings
    ANCHOR_COUNT = 4
    SCREW_COUNT = 3
    SCREW_DIAMETER = 8  # mm
    SCREW_LENGTH = 180  # mm; the 8 x 160 is for timber down to 120 x 120
    SCREW_ANGLE = 25  # degrees, the angle BETWEEN a pair of opposed screws
    HEIGHT = 150  # mm, the bottom of the 150 - 200 adjustment range

    # --- the two wrench sizes, from the design guide ---
    # Cross-checked against the bundled mesh, and they are why its shaft is
    # hexagonal: its two hex sections measure 54.99 and 36.37 mm across the
    # flats, which are these. So those hexagons are the real part, NOT a coarse
    # circle - only the head plate is drawn coarsely there.
    COUPLING_NUT_ACROSS_FLATS = 55  # mm, "open-end wrench 55 mm"
    ADJUSTMENT_NUT_ACROSS_FLATS = 36  # mm, "SW 32 resp. 36 mm"

    # --- the rest of the shaft, off the bundled mesh ---
    ADJUSTMENT_NUT_TOP = 64  # mm, top of the SW 36 nut
    ROD_DIAMETER = 30  # mm, the threaded rod between the two nuts

    # Where the connector comes apart: the coupling nut, 30 mm of it, directly
    # under the head plate.
    COUPLING_NUT_HEIGHT = 30  # mm, off the mesh
    COUPLING_LEVEL = HEIGHT - HEAD_PLATE_THICKNESS - COUPLING_NUT_HEIGHT  # = 108 mm

    # The datasheet recommends letting the head plate into the column end -
    # "das Versenken der Kopfplatte in der Stuetze (t = 12 mm / Ø 96 oder
    # Ø 106 mm)" - which is a pocket the depth of the plate. Assembly steps
    # that show the head on a column use this to sink it in.
    HEAD_PLATE_RECESS = HEAD_PLATE_THICKNESS  # mm
    HEIGHT_RANGE = (150, 200)  # mm
    LOAD_CAPACITY = 138  # kN, R1,d

    # --- NOT printed: derived, so that the fasteners can be drawn ---
    # The datasheet gives the anchors as "four metal expansion dowels or
    # concrete screws" with no size, and prints no hole circle for the three
    # column screws. The screw circle below is not a guess, though: it is the
    # value that reproduces the datasheet's OWN minimum timber sections. With
    # each screw leaning SCREW_ANGLE / 2 off the axis, a screw tip lands
    #
    #     25 + 160 * sin(12.5) = 59.6 mm off the axis -> needs 120 x 120  (v)
    #     25 + 180 * sin(12.5) = 64.0 mm off the axis -> needs 140 x 140  (v)
    #
    # which is exactly the table's two rows. That also settles what the
    # published "approx. 25 degrees" is measured against: the angle between a
    # pair of opposed screws, as the Italian text spells out ("inclinate a
    # circa 25 gradi tra di loro"), NOT the angle of one screw to the column
    # axis - at 25 degrees each, an 8 x 160 would need a 240 mm section.
    ANCHOR_DIAMETER = 12  # mm, an M12 stud through the Ø15 clearance hole
    ANCHOR_EMBEDMENT = 100  # mm into the slab
    SCREW_CIRCLE_DIAMETER = 50  # mm, see above

    @property
    def __data__(self) -> dict:
        return {
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
            **self._baked_data(),
        }

    def __init__(
        self,
        transformation: Optional[Transformation] = None,
        features: Optional[list[SupportFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)

        self.mesh = Mesh.from_obj(self.DATA_DIR / self.MESH_FILE)
        self.top_polygon = Polygon.from_sides_and_radius_xy(32, 106 * 0.5)
        self.top_polygon.translate([0, 0, 150])
        self.bottom_polygon = Polygon.from_rectangle(Point(70, 70, 0), 140, 140)

    @baked
    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Compute the shape of the plate from the given polygons.
        This shape is relative to the frame of the element.

        Returns
        -------
        :class:`compas.datastructures.Mesh`

        """
        return self.mesh

    # =============================================================================
    # Implementations of abstract methods
    # =============================================================================

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.obb
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())

    def _base_plane_points(self, mesh: Optional[Mesh] = None) -> tuple:
        """The mesh vertices lying on the underside of the base plate.

        Returns the points themselves plus the plan extents of that set, which
        is what both :attr:`base_hole_points` and :attr:`base_corner_points`
        sort their vertices against.

        Returns
        -------
        tuple[list[list[float]], list[float], list[float]]
            The points, the ``[xmin, ymin]`` and the ``[xmax, ymax]``.
        """
        mesh = self.modelgeometry if mesh is None else mesh
        points = [mesh.vertex_coordinates(vertex) for vertex in mesh.vertices()]
        zmin = min(point[2] for point in points)
        bottom = [point for point in points if abs(point[2] - zmin) < 1e-6]
        if not bottom:
            return [], [0.0, 0.0], [0.0, 0.0]
        low = [min(point[axis] for point in bottom) for axis in (0, 1)]
        high = [max(point[axis] for point in bottom) for axis in (0, 1)]
        return bottom, low, high

    @staticmethod
    def _counterclockwise(points: list) -> list:
        """Order points around their own centre, so a set is stable per support."""
        if not points:
            return []
        middle = Point(*(sum(point[axis] for point in points) / len(points) for axis in (0, 1, 2)))
        return sorted(points, key=lambda point: math.atan2(point.y - middle.y, point.x - middle.x))

    def _corner_points(self, mesh: Optional[Mesh] = None) -> list:
        """The four corners of the base plate's underside, in model space.

        The outline the plate is set out to, as opposed to the drillings it is
        bolted down through (:attr:`base_hole_points`) - a second, coarser
        check on site that the base landed where it was meant to.

        Found the same way and for the same reason: a corner is a bottom-plane
        vertex that sits on the extent in BOTH directions, which on a
        rectangular plate is exactly the four of them.

        Returns
        -------
        list[:class:`compas.geometry.Point`]
            Ordered counterclockwise around the plate centre.
        """
        bottom, low, high = self._base_plane_points(mesh)
        corners = [Point(*point) for point in bottom if all(abs(point[axis] - low[axis]) < 1e-6 or abs(point[axis] - high[axis]) < 1e-6 for axis in (0, 1))]
        return self._counterclockwise(corners)

    def _hole_points(self, mesh: Optional[Mesh] = None) -> list:
        """Centres of the four bolt holes through the base plate, in model space.

        These, not the support's centre, are what gets marked on the slab: the
        Sherpa power base is fixed with four anchors, so the survey has to put
        four points on the ground per column, not one.

        The holes are found rather than hardcoded, so a different base plate
        mesh needs no change here. Every hole leaves a ring of vertices on the
        mesh's bottom plane - in this mesh a hexagon, the OBJ's approximation
        of a 15 mm drilling. Mesh connectivity cannot separate those rings from
        the plate corners, because the bottom face is triangulated across the
        whole plate, so the rings are found by distance instead: bottom-plane
        vertices are clustered by proximity, and a cluster with three or more
        members is a hole. The plate's own corners come out as singletons and
        drop away.

        Returns
        -------
        list[:class:`compas.geometry.Point`]
            One point per hole, on the underside of the plate, ordered
            counterclockwise around the plate centre so the four are stable
            from one support to the next.
        """
        bottom, low, high = self._base_plane_points(mesh)
        if not bottom:
            return []

        # Drop the plate's own outline first - its corners sit closer to a
        # drilling than the drilling is wide, so leaving them in merges a
        # corner into the hole beside it. A hole is interior by definition;
        # the outline is exactly what touches the bounding extents.
        interior = [point for point in bottom if all(low[axis] + 1e-6 < point[axis] < high[axis] - 1e-6 for axis in (0, 1))]

        # What is left is the rings, far apart next to the plate they sit in,
        # so anything within a fraction of the plate's width is one hole.
        span = max(high[axis] - low[axis] for axis in (0, 1))
        threshold = span * 0.2

        clusters = []
        for point in interior:
            for cluster in clusters:
                if any(math.dist(point[:2], other[:2]) <= threshold for other in cluster):
                    cluster.append(point)
                    break
            else:
                clusters.append([point])

        centers = []
        for cluster in clusters:
            if len(cluster) < 3:  # a plate corner, not a drilling
                continue
            centers.append(Point(*(sum(point[axis] for point in cluster) / len(cluster) for axis in (0, 1, 2))))

        return self._counterclockwise(centers)

    @property
    def base_corner_points(self) -> list:
        """The four corners of the base plate's underside, in model space."""
        return self._corner_points()

    @property
    def base_hole_points(self) -> list:
        """Centres of the four anchor drillings, in model space."""
        return self._hole_points()

    # =============================================================================
    # Fasteners
    # =============================================================================

    @property
    def head_plate_radius(self) -> float:
        """Radius of the circular head plate, in mm (Ø 106 / 2)."""
        return self.HEAD_PLATE_DIAMETER * 0.5

    @property
    def head_plate_circle(self) -> "Circle":
        """The head plate's rim, in model space.

        The top of the connector is a disc, not the hexagon the bundled mesh
        approximates it with, so the circle is built from the published
        diameter rather than read off the geometry.
        """
        frame = Frame(Point(0, 0, self.HEIGHT), Vector.Xaxis(), Vector.Yaxis())
        return Circle(self.head_plate_radius, frame=frame).transformed(self.placement)

    @property
    def ground_anchors(self) -> list:
        """The four anchors that fix the base plate down, in model space.

        One per drilling in the base plate, running from the top of the plate
        straight down into the slab. The datasheet names them - "four metal
        expansion dowels or concrete screws" - but gives no size, so the shank
        is :attr:`ANCHOR_DIAMETER` and the embedment :attr:`ANCHOR_EMBEDMENT`.

        Returns
        -------
        list[:class:`compas.geometry.Brep`]
        """
        anchors = []
        for point in self._hole_points(self.mesh):
            axis = Line(
                Point(point.x, point.y, self.BASE_PLATE_THICKNESS),
                Point(point.x, point.y, -self.ANCHOR_EMBEDMENT),
            )
            anchors.append(Brep.from_cylinder(Cylinder.from_line_and_radius(axis, self.ANCHOR_DIAMETER * 0.5)).transformed(self.placement))
        return anchors

    @property
    def column_screws(self) -> list:
        """The three SHERPA screws that fix the head plate to the column.

        3 x 8 x 180 mm spread outwards from a circle on the head plate,
        starting at the plate's top face - the face the column stands on, the
        one the centring spike sticks out of - and running up into the end
        grain at half of :attr:`SCREW_ANGLE` off the column axis.

        The count, the diameter and the length are the datasheet's. The hole
        circle and the reading of the angle are derived from it, and agree with
        both of its minimum timber sections - see the comment on
        :attr:`SCREW_CIRCLE_DIAMETER`.

        Returns
        -------
        list[:class:`compas.geometry.Brep`]
        """
        screws = []
        radius = self.SCREW_CIRCLE_DIAMETER * 0.5
        tilt = math.radians(self.SCREW_ANGLE * 0.5)  # published angle is between a PAIR
        for index in range(self.SCREW_COUNT):
            angle = 2 * math.pi * index / self.SCREW_COUNT
            outward = Vector(math.cos(angle), math.sin(angle), 0)
            start = Point(outward.x * radius, outward.y * radius, self.HEIGHT)
            direction = outward * math.sin(tilt) + Vector.Zaxis() * math.cos(tilt)
            axis = Line(start, start + direction * self.SCREW_LENGTH)
            screws.append(Brep.from_cylinder(Cylinder.from_line_and_radius(axis, self.SCREW_DIAMETER * 0.5)).transformed(self.placement))
        return screws

    @property
    def head_plate(self) -> Brep:
        """The Ø 106 x 12 mm plate that is screwed to the column, in model space.

        This is the piece step 2 puts on a column: the datasheet's *Kopfplatte*,
        fixed to the end face with three screws, and recessed into it by its own
        thickness (:attr:`HEAD_PLATE_RECESS`). Its solid IS the pocket that has
        to be machined out of the end grain, so it is a Brep - an exact
        cylindrical face, not a polygon count - and a boolean can cut the pocket
        with it directly.

        What is NOT in here is the rest of the connector: the coupling nut, the
        threaded rod, the adjustment nut and the base plate are the half that
        stays in the slab. See :attr:`brep` for all of it.

        Returns
        -------
        :class:`compas.geometry.Brep`
        """
        frame = Frame(Point(0, 0, self.HEIGHT - self.HEAD_PLATE_THICKNESS * 0.5))
        plate = Brep.from_cylinder(Cylinder(self.head_plate_radius, self.HEAD_PLATE_THICKNESS, frame))
        plate.transform(self.placement)
        return plate

    @property
    def brep(self) -> Brep:
        """The whole connector as an exact solid, in model space.

        Built from the dimensions rather than converted from the bundled OBJ.
        Every number in here is either printed by Sherpa or measured off that
        mesh and cross-checked against a printed one (see the class Notes), and
        the result is exact where the part is exact: the base plate's four
        Ø 15 drillings are real cylindrical holes, the two nuts are true
        hexagonal prisms at their published wrench sizes, and the rod and the
        head plate are true cylinders.

        The five pieces are returned as one Brep compound, not unioned - they
        are separate parts of an assembly, and a union would only cost time and
        risk a boolean failure.

        Returns
        -------
        :class:`compas.geometry.Brep`
        """
        plate = Brep.from_box(Box(self.BASE_PLATE_SIZE, self.BASE_PLATE_SIZE, self.BASE_PLATE_THICKNESS, Frame(Point(0, 0, self.BASE_PLATE_THICKNESS * 0.5))))
        # Overshoot the drillings past both faces, so the cut is not coplanar
        # with the plate it goes through.
        depth = self.BASE_PLATE_THICKNESS * 3
        drillings = [
            Brep.from_cylinder(Cylinder(self.BASE_PLATE_HOLE_DIAMETER * 0.5, depth, Frame(Point(point.x, point.y, self.BASE_PLATE_THICKNESS * 0.5))))
            for point in self._hole_points(self.mesh)
        ]
        parts = [Brep.from_boolean_difference(plate, drillings) if drillings else plate]

        parts.append(_hex_prism(self.ADJUSTMENT_NUT_ACROSS_FLATS, self.BASE_PLATE_THICKNESS, self.ADJUSTMENT_NUT_TOP))
        parts.append(
            Brep.from_cylinder(
                Cylinder(self.ROD_DIAMETER * 0.5, self.COUPLING_LEVEL - self.ADJUSTMENT_NUT_TOP, Frame(Point(0, 0, (self.ADJUSTMENT_NUT_TOP + self.COUPLING_LEVEL) * 0.5)))
            )
        )
        parts.append(_hex_prism(self.COUPLING_NUT_ACROSS_FLATS, self.COUPLING_LEVEL, self.COUPLING_LEVEL + self.COUPLING_NUT_HEIGHT))
        parts.append(Brep.from_cylinder(Cylinder(self.head_plate_radius, self.HEAD_PLATE_THICKNESS, Frame(Point(0, 0, self.HEIGHT - self.HEAD_PLATE_THICKNESS * 0.5)))))

        # OCCBrep directly: `Brep.from_breps` is not registered as a compas
        # plugin, so the generic API cannot make a compound.
        from compas_occt.brep import OCCBrep

        connector = OCCBrep.from_breps(parts)
        connector.transform(self.placement)
        return connector

    @property
    def fasteners(self) -> list:
        """Every fastener the connector needs: 4 anchors down, 3 screws up."""
        return self.ground_anchors + self.column_screws

    @property
    def base_frame(self) -> Frame:
        """Get the base frame at the bottom center of the mesh, with transformation applied.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at the bottom center of the mesh with Z-axis pointing up.
        """
        # Get mesh bounding box to find bottom center
        aabb = self.mesh.aabb()
        bottom_center = Point((aabb.xmin + aabb.xmax) / 2, (aabb.ymin + aabb.ymax) / 2, aabb.zmin)
        frame = Frame(bottom_center, Vector.Xaxis(), Vector.Yaxis())
        if self.transformation:
            frame.transform(self.transformation)
        return frame
