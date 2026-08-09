import math

from compas.data import Data
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Projection
from compas.geometry import Rotation
from compas.geometry import Translation
from compas.geometry import Vector
from compas.geometry import intersection_line_plane
from compas.geometry import intersection_plane_plane
from compas.geometry import intersection_plane_plane_plane

from compas_tf.brep import BrepMixin
from compas_tf.geometry import BezierCurve
from compas_tf.geometry import PolylineCut
from compas_tf.geometry import PolylineOffset
from compas_tf.plate import PlateElement


class FloorGuide(Data, BrepMixin):
    """Provides geometry parameters for building column heads and edge beams.

    Depending if the column is bigger than column head, there is either cutters of a beam of a separate block.
    """

    def __init__(
        self,
        size_grid_x=3000,
        size_grid_y=3000,
        size_column_head=250,
        size_column_head_chamfer=100,
        size_outer_ribs=100,
        size_inner_ribs=60,
        size_inner_beams=60,
        size_wedge=100,
        size_tsections=27,
        height=650,
        rise=453,
        size_oculus=1000,
        wedge_plane_angle=-10,
        bay_height=3000,
    ):
        super().__init__()

        self.size_grid_x = size_grid_x
        self.size_grid_y = size_grid_y

        self.size_column_head = size_column_head
        self.size_column_head_chamfer = size_column_head_chamfer

        self.size_oculus = size_oculus
        self.size_oculus_x = size_oculus * size_grid_x / size_grid_y
        self.size_oculus_y = size_oculus * size_grid_y / size_grid_x

        self.size_outer_ribs = size_outer_ribs
        self.size_inner_ribs = size_inner_ribs
        self.size_inner_beams = size_inner_beams
        self.size_wedge = size_wedge
        self.size_tsections = size_tsections

        # Gentle tilt (degrees) of the wedge planes that cut the ribs / wedges /
        # beds / t-sections. The plane pivots about its top edge (at z=0), so
        # the cut leans away from vertical going downward.
        self.wedge_plane_angle = wedge_plane_angle

        # Vertical distance between stacked floors (column + support height).
        # Used to lift the floor plates to the top of the columns; consumed by
        # FloorModel.story_height and by the examples that stack quarters.
        self.bay_height = bay_height

        # parabolas parameters
        self.height = height
        self.rise = rise
        self.static_h = height - rise
        self.column_head_lowest_height = -730

        # caches (invalidated lazily)
        self._oculus_pts = None
        self._q_poly = None
        self._c_poly = None
        self._axes = None
        self._boundary_parabolas = None
        self._construction_planes = None
        self._quad_planes = None
        self._construction_quads = None
        self._block_level_bottom = None
        self._block_level_top = None

        self.debug = []

        # on/off elements
        self.output_wedges = False

    @property
    def __data__(self) -> dict:
        return {
            "size_grid_x": self.size_grid_x,
            "size_grid_y": self.size_grid_y,
            "size_column_head": self.size_column_head,
            "size_column_head_chamfer": self.size_column_head_chamfer,
            "size_outer_ribs": self.size_outer_ribs,
            "size_inner_ribs": self.size_inner_ribs,
            "size_inner_beams": self.size_inner_beams,
            "size_wedge": self.size_wedge,
            "size_tsections": self.size_tsections,
            "height": self.height,
            "rise": self.rise,
            "size_oculus": self.size_oculus,
            "wedge_plane_angle": self.wedge_plane_angle,
            "bay_height": self.bay_height,
        }

    # The plate groups the guide produces, in the order a quarter is assembled.
    PLATE_GROUPS = ("outer_ribs", "inner_ribs", "inner_beams", "tsections", "beds", "oculus", "column_cutters")

    def plates(self) -> list:
        """Every :class:`compas_tf.plate.PlateElement` the guide produces, flattened.

        Each group is a lazy property, so this builds them all on first call.
        """
        plates = []
        for group in self.PLATE_GROUPS:
            value = getattr(self, group, None)
            if value is None:
                continue
            plates.extend(value if isinstance(value, (list, tuple)) else [value])
        return [plate for plate in plates if isinstance(plate, PlateElement)]

    def brep_meshes(self, variant=None) -> list:
        """The geometry of every plate the guide produces - what :meth:`get_brep` converts."""
        return [plate.placedgeometry for plate in self.plates()]

    @classmethod
    def __from_data__(cls, data: dict) -> "FloorGuide":
        return cls(**data)

    # ------------------------------------------------------------------ #
    #  Column grid
    # ------------------------------------------------------------------ #

    def corner_point_column(self, column_size=200):
        """Column base center in plan for one quarter (the grid corner).

        Mirrors the position the columns and supports are placed at: the
        bottom-left corner of the quarter grid, inset by half the column size.

        Parameters
        ----------
        column_size : float
            Column cross-section side length in mm.

        Returns
        -------
        :class:`compas.geometry.Point`
        """
        return Point(
            -(self.size_grid_x - column_size * 0.5),
            -(self.size_grid_y - column_size * 0.5),
            0,
        )

    # ------------------------------------------------------------------ #
    #  Floor plan geometry (2D)
    # ------------------------------------------------------------------ #

    @property
    def oculus_points(self):
        """Four points whose distance is sqrt(2) * oculus."""
        if self._oculus_pts is None:
            self._oculus_pts = [
                Point(0, -self.size_oculus_y, 0),
                Point(self.size_oculus_x, 0, 0),
                Point(0, self.size_oculus_y, 0),
                Point(-self.size_oculus_x, 0, 0),
            ]
        return self._oculus_pts

    @property
    def quarter_polygon(self):
        """The main polygon of the floor."""
        if self._q_poly is None:
            self._q_poly = Polygon(
                [
                    Point(-self.size_grid_x, -self.size_grid_y, 0),
                    Point(0, -self.size_grid_y, 0),
                    self.oculus_points[0],
                    self.oculus_points[3],
                    Point(-self.size_grid_x, 0, 0),
                ]
            )
        return self._q_poly

    @property
    def quarter_column_polygon(self):
        """The column head polygon from which the ribs will start."""
        if self._c_poly is None:
            corner = self.quarter_polygon[0]
            self._c_poly = Polygon(
                [
                    corner,
                    corner + Vector(self.size_column_head, 0, 0),
                    corner + Vector(self.size_column_head, self.size_column_head_chamfer, 0),
                    corner + Vector(self.size_column_head_chamfer, self.size_column_head, 0),
                    corner + Vector(0, self.size_column_head, 0),
                ]
            )
        return self._c_poly

    # ------------------------------------------------------------------ #
    # Beams
    # We wont define the floor as axis
    # We will define them as polygon offsets.
    # ------------------------------------------------------------------ #

    @property
    def construction_planes(self, oculus_plane_angle=5):
        """Plane pairs each corresponds to the long edge of 2d plan plate edges.
        In the next function we would make two other pair polylines form indicies to construct rectangles."""

        if self._construction_planes is None:
            construction_planes = {
                "outer_ribs": [],
                "inner_beams": [],
                "inner_ribs": [],
                "wedges": [],
                "t_sections": [],
            }

            # 1. outer rib
            plane0 = Plane(self.quarter_polygon.lines[0].midpoint, Vector.cross(self.quarter_polygon.lines[0].direction, -Vector.Zaxis()))
            plane1 = Plane(self.quarter_polygon.lines[4].midpoint, Vector.cross(self.quarter_polygon.lines[4].direction, -Vector.Zaxis()))
            construction_planes["outer_ribs"] = [
                [
                    plane0.copy(),
                    plane0.offset(self.size_outer_ribs),
                ],
                [plane1.copy(), plane1.offset(self.size_outer_ribs)],
            ]

            # 2. inner beams, NOTE the central plane has rotation - oculus_plane_angle
            plane0 = Plane(self.quarter_polygon.lines[1].midpoint, Vector.cross(self.quarter_polygon.lines[1].direction, -Vector.Zaxis()))
            plane1 = Plane(self.quarter_polygon.lines[2].midpoint, Vector.cross(self.quarter_polygon.lines[2].direction, -Vector.Zaxis()))
            plane1_rotated = plane1.copy()
            plane1_rotated.rotate(-oculus_plane_angle * math.pi / 180, self.quarter_polygon.lines[2].direction, self.quarter_polygon.lines[2].midpoint)
            plane2 = Plane(self.quarter_polygon.lines[3].midpoint, Vector.cross(self.quarter_polygon.lines[3].direction, -Vector.Zaxis()))
            construction_planes["inner_beams"] = [
                [
                    plane0.copy(),
                    plane0.offset(self.size_inner_beams),
                ],
                [plane1_rotated.copy(), plane1.offset(self.size_inner_beams)],
                [plane2.copy(), plane2.offset(self.size_inner_beams)],
            ]

            # 3. inner ribs, NOTE the side plane must be constructed from innter beam plane intersection
            planexy = Plane.worldXY()
            plane0 = construction_planes["inner_beams"][0][1]
            plane1 = construction_planes["inner_beams"][1][1]
            plane2 = construction_planes["inner_beams"][2][1]
            p0 = Point(*intersection_plane_plane_plane(planexy, plane0, plane1))
            p1 = Point(*intersection_plane_plane_plane(planexy, plane1, plane2))
            p2 = self.quarter_column_polygon[2]
            p3 = self.quarter_column_polygon[3]

            plane0 = Plane((p0 + p2) * 0.5, Vector.cross(p0 - p2, -Vector.Zaxis()))
            plane1 = Plane((p1 + p3) * 0.5, Vector.cross(p1 - p3, Vector.Zaxis()))

            construction_planes["inner_ribs"] = [
                [
                    plane0.copy(),
                    plane0.offset(self.size_inner_ribs),
                ],
                [plane1.copy(), plane1.offset(self.size_inner_ribs)],
            ]

            # 4. wedges
            plane0 = Plane(self.quarter_column_polygon.lines[1].midpoint, Vector.cross(self.quarter_column_polygon.lines[1].direction, Vector.Zaxis()))
            plane1 = Plane(self.quarter_column_polygon.lines[2].midpoint, Vector.cross(self.quarter_column_polygon.lines[2].direction, Vector.Zaxis()))
            plane2 = Plane(self.quarter_column_polygon.lines[3].midpoint, Vector.cross(self.quarter_column_polygon.lines[3].direction, Vector.Zaxis()))

            # Tilt each wedge plane by wedge_plane_angle, pivoting about its top
            # edge (column-head polygon edge at z=0). The tilt propagates into
            # the offset planes and the central plane1_offset built below, so all
            # cuts derived from the wedge planes (ribs, wedges, beds, t-sections)
            # use the tilted plane.
            wedge_angle = self.wedge_plane_angle * math.pi / 180
            # plane0.rotate(wedge_angle, self.quarter_column_polygon.lines[1].direction, self.quarter_column_polygon.lines[1].midpoint)
            plane1.rotate(wedge_angle, self.quarter_column_polygon.lines[2].direction, self.quarter_column_polygon.lines[2].midpoint)
            result0 = intersection_plane_plane(construction_planes["inner_ribs"][0][1], plane1)
            result1 = intersection_plane_plane(construction_planes["inner_ribs"][1][1], plane1)
            line0 = Line(result0[0], result0[1])
            line2 = Line(result1[1], result1[0])
            line0 = Line(line0.start, line0.end + line0.direction * 1000)
            line2 = Line(line2.start, line2.end + line2.direction * 1000)
            plane0 = Plane(plane0.point, Vector.cross(line0.direction, self.quarter_column_polygon.lines[1].direction))
            plane2 = Plane(plane2.point, Vector.cross(line2.direction, self.quarter_column_polygon.lines[3].direction))

            line0 = Line(p0, self.quarter_column_polygon[2])
            line1 = Line(p1, self.quarter_column_polygon[3])
            plane_p0 = Point(*intersection_line_plane(line0, plane0.offset(self.size_wedge)))
            plane_p1 = Point(*intersection_line_plane(line1, plane2.offset(self.size_wedge)))
            plane1_offset = Plane(plane_p0, Vector.cross(plane_p1 - plane_p0, Vector.Zaxis()))  # noqa: F841  (reference offset for the plane1 wedge, see below)

            plane4 = construction_planes["inner_beams"][0][1]
            plane5 = construction_planes["inner_beams"][1][1]
            plane6 = construction_planes["inner_beams"][2][1]

            construction_planes["wedges"] = [
                [plane0.copy(), plane0.offset(self.size_wedge)],
                [plane1.copy(), plane1.copy().offset(self.size_wedge * 1.25)],  # plane1_offset
                [plane2.copy(), plane2.offset(self.size_wedge)],
                [plane4.copy(), plane4.offset(self.size_inner_beams)],
                [plane5.copy(), plane5.offset(self.size_inner_beams)],
                [plane6.copy(), plane6.offset(self.size_inner_beams)],
            ]

            # 5. t-sections
            plane0 = Plane((p0 + p2) * 0.5, Vector.cross(p0 - p2, -Vector.Zaxis()))
            plane1 = Plane((p1 + p3) * 0.5, Vector.cross(p1 - p3, -Vector.Zaxis()))

            construction_planes["t_sections"] = [
                [construction_planes["outer_ribs"][0][1].copy(), construction_planes["outer_ribs"][0][1].offset(self.size_tsections)],
                [construction_planes["inner_ribs"][0][0].copy(), construction_planes["inner_ribs"][0][0].offset(-self.size_tsections)],
                [construction_planes["inner_ribs"][0][1].copy(), construction_planes["inner_ribs"][0][1].offset(self.size_tsections)],
                [construction_planes["inner_ribs"][1][0].copy(), construction_planes["inner_ribs"][1][0].offset(-self.size_tsections)],
                [construction_planes["inner_ribs"][1][1].copy(), construction_planes["inner_ribs"][1][1].offset(self.size_tsections)],
                [construction_planes["outer_ribs"][1][1].copy(), construction_planes["outer_ribs"][1][1].offset(self.size_tsections)],
            ]

            self._construction_planes = construction_planes

        return self._construction_planes

    def column_cutters_for(self, column_height):
        """Column-head cutter solids in a column's LOCAL frame.

        :attr:`column_cutters` are authored in the guide's world frame - at the
        bay corner, with the head top near z=0. This recentres them on the
        column axis (xy -> 0) and lifts the head top to the column top
        (z = ``column_height``), which is the frame a column feature is applied
        in. Pass the result straight to
        :meth:`compas_tf.column.ColumnElement.add_cutters`.

        Parameters
        ----------
        column_height : float
            Local height of the target column; its head top sits at this z.

        Returns
        -------
        list[:class:`compas.datastructures.Mesh`]
            Closed cutter solids in the column's local frame.
        """
        corner = self.corner_point_column(self.size_column_head)
        to_local = Translation.from_vector([-corner[0], -corner[1], column_height])
        return [cutter.compute_elementgeometry().transformed(to_local) for cutter in self.column_cutters]

    @property
    def column_cutters(self):
        """PlateElements that carve the column head as boolean-difference cutters.

        Built from the three wedge construction planes plus the two side planes
        of the quarter column polygon. The plane fan is intersected with three
        horizontal levels (top at z=0, and two lower levels) to produce six
        cutter quads, each lofted into a closed ``PlateElement`` so it can be
        registered as a ``SolidDifferenceModifier`` source against the column.

        The cutters are authored in the guide's local frame (column head near
        z=0); ``FloorModel.add_floor_guide`` applies the guide transformation so
        they line up with the column at the correct elevation.

        Returns
        -------
        list[:class:`compas_tf.plate.PlateElement`]
        """
        # Rebuilt fresh on each access (no caching) so the same guide can be
        # reused across quarters — each add_floor_guide call gets new elements,
        # mirroring `sherpas` / `beds`.
        cp = self.construction_planes

        plane_xy0 = Plane.worldXY()
        plane_xy1 = Plane(Point(0, 0, -self.height - self.size_tsections * 1.65), Vector.Zaxis())
        plane_xy2 = Plane(Point(0, 0, self.column_head_lowest_height), Vector.Zaxis())
        side_plane0 = Plane(self.quarter_column_polygon.lines[0].midpoint, Vector.cross(self.quarter_column_polygon.lines[0].direction, -Vector.Zaxis()))
        side_plane1 = Plane(self.quarter_column_polygon.lines[-1].midpoint, Vector.cross(self.quarter_column_polygon.lines[-1].direction, -Vector.Zaxis()))

        wedge_planes_top = [
            side_plane0,
            cp["wedges"][0][0],
            cp["wedges"][1][0],
            cp["wedges"][2][0],
            side_plane1,
        ]
        wedge_planes_bottom = [
            side_plane0,
            Plane(self.quarter_column_polygon.lines[1].midpoint, Vector.cross(self.quarter_column_polygon.lines[1].direction, -Vector.Zaxis())),
            Plane(self.quarter_column_polygon.lines[3].midpoint, Vector.cross(self.quarter_column_polygon.lines[3].direction, -Vector.Zaxis())),
            side_plane1,
        ]

        points0 = []
        points1 = []
        points2 = []
        for i in range(len(wedge_planes_top) - 1):
            plane0 = wedge_planes_top[i]
            plane1 = wedge_planes_top[i + 1]
            points0.append(Point(*intersection_plane_plane_plane(plane_xy0, plane0, plane1)))
            points1.append(Point(*intersection_plane_plane_plane(plane_xy1, plane0, plane1)))

        for i in range(len(wedge_planes_bottom) - 1):
            plane0 = wedge_planes_bottom[i]
            plane1 = wedge_planes_bottom[i + 1]
            points2.append(Point(*intersection_plane_plane_plane(plane_xy2, plane0, plane1)))

        # Six cutter quads spanning the plane fan across the three levels.
        polylines = [
            Polygon([points0[0], points0[1], points1[1], points1[0]]),
            Polygon([points0[1], points0[2], points1[2], points1[1]]),
            Polygon([points0[2], points0[3], points1[3], points1[2]]),
            Polygon([points1[0], points1[1], points2[1], points2[0]]),
            Polygon([points1[1], points1[2], points2[1] + (points2[2] - points2[0]) * 0.25, points2[1] - (points2[2] - points2[0]) * 0.25]),
            Polygon([points1[2], points1[3], points2[2], points2[1]]),
        ]

        # Extend each quad in-plane and offset along its normal to give the
        # cutter plate a finite thickness (closed solid for the boolean).
        polylines_offset = []
        for idx, polyline in enumerate(polylines):
            dir0 = polylines[idx].points[1] - polylines[idx].points[0]
            dir1 = polylines[idx].points[3] - polylines[idx].points[2]
            dir0.unitize()
            dir1.unitize()
            dir0 *= 100
            dir1 *= 100

            polylines[idx][0] = polylines[idx][0] - dir0
            polylines[idx][1] = polylines[idx][1] + dir0
            polylines[idx][2] = polylines[idx][2] - dir1
            polylines[idx][3] = polylines[idx][3] + dir1
            dir2 = polylines[idx].points[2] - polylines[idx].points[1]
            dir3 = polylines[idx].points[0] - polylines[idx].points[3]

            # if idx in (0, 3):  # for the top and bottom quads, extend the other two edges instead of these ones, to avoid self-intersection
            if idx in (0, 1, 2):
                dir2.unitize()
                dir3.unitize()
                dir2 *= 100
                dir3 *= 100
                polylines[idx][0] = polylines[idx][0] - dir2
                polylines[idx][1] = polylines[idx][1] - dir2
                polylines[idx][2] = polylines[idx][2] - dir3
                polylines[idx][3] = polylines[idx][3] - dir3
            else:
                dir2.unitize()
                dir3.unitize()
                # polylines[idx][2] = polylines[idx][2] - dir3
                # polylines[idx][3] = polylines[idx][3] - dir3

                dir2 *= 100
                dir3 *= 100
                polylines[idx][0] = polylines[idx][0] - dir2
                polylines[idx][1] = polylines[idx][1] - dir2

            z_axis = Vector.cross(polylines[idx].lines[1].direction, polylines[idx].lines[0].direction)
            z_axis.unitize()
            polylines_offset.append(polyline.translated(z_axis * 100))

        plates = []
        for i in range(len(polylines)):
            top = Polyline(list(polylines[i].points) + [polylines[i].points[0]])
            bottom = Polyline(list(polylines_offset[i].points) + [polylines_offset[i].points[0]])
            plates.append(PlateElement(top_polyline=top, bottom_polyline=bottom))

        return plates

    @property
    def quad_planes(self):
        if self._quad_planes is None:
            cp = self.construction_planes
            self._quad_planes = {
                "outer_ribs": [
                    [
                        cp["outer_ribs"][0][0],
                        cp["inner_beams"][0][0],
                        cp["outer_ribs"][0][1],
                        cp["wedges"][0][0],
                    ],
                    [
                        cp["outer_ribs"][1][0],
                        cp["inner_beams"][2][0],
                        cp["outer_ribs"][1][1],
                        cp["wedges"][2][0],
                    ],
                ],
                "inner_beams": [
                    [
                        cp["inner_beams"][0][0],
                        cp["inner_beams"][1][0],
                        cp["inner_beams"][0][1],
                        cp["outer_ribs"][0][1],
                    ],
                    [
                        cp["inner_beams"][1][0],
                        cp["inner_beams"][2][1],
                        cp["inner_beams"][1][1],
                        cp["inner_beams"][0][1],
                    ],
                    [
                        cp["inner_beams"][2][0],
                        cp["outer_ribs"][1][1],
                        cp["inner_beams"][2][1],
                        cp["inner_beams"][1][0],
                    ],
                ],
                "inner_ribs": [
                    [
                        cp["inner_ribs"][0][1],
                        cp["inner_beams"][1][1],
                        cp["inner_ribs"][0][0],
                        cp["wedges"][1][0],
                    ],
                    [
                        cp["inner_ribs"][1][1],
                        cp["inner_beams"][1][1],
                        cp["inner_ribs"][1][0],
                        cp["wedges"][1][0],
                    ],
                ],
                "wedges": [
                    [
                        cp["wedges"][0][0],
                        cp["outer_ribs"][0][1],
                        cp["wedges"][0][1],
                        cp["inner_ribs"][0][0],
                    ],
                    [
                        cp["wedges"][1][0],
                        cp["inner_ribs"][0][1],
                        cp["wedges"][1][1],
                        cp["inner_ribs"][1][1],
                    ],
                    [
                        cp["wedges"][2][0],
                        cp["inner_ribs"][1][0],
                        cp["wedges"][2][1],
                        cp["outer_ribs"][1][1],
                    ],
                    [
                        cp["wedges"][3][0],
                        cp["inner_ribs"][0][0],
                        cp["wedges"][3][1],
                        cp["outer_ribs"][0][1],
                    ],
                    [
                        cp["wedges"][4][0],
                        cp["inner_ribs"][1][1],
                        cp["wedges"][4][1],
                        cp["inner_ribs"][0][1],
                    ],
                    [
                        cp["wedges"][5][0],
                        cp["outer_ribs"][1][1],
                        cp["wedges"][5][1],
                        cp["inner_ribs"][1][0],
                    ],
                ],
                "t_sections": [
                    [
                        cp["t_sections"][0][0],
                        cp["inner_beams"][0][1],
                        cp["t_sections"][0][1],
                        cp["wedges"][0][1],
                    ],
                    [
                        cp["t_sections"][1][0],
                        cp["inner_beams"][0][1],
                        cp["t_sections"][1][1],
                        cp["wedges"][0][1],
                    ],
                    [
                        cp["t_sections"][2][0],
                        cp["inner_beams"][1][1],
                        cp["t_sections"][2][1],
                        cp["wedges"][1][1],
                    ],
                    [
                        cp["t_sections"][3][0],
                        cp["inner_beams"][2][1],
                        cp["t_sections"][3][1],
                        cp["wedges"][2][1],
                    ],
                    [
                        cp["t_sections"][4][0],
                        cp["inner_beams"][1][1],
                        cp["t_sections"][4][1],
                        cp["wedges"][1][1],
                    ],
                    [
                        cp["t_sections"][5][0],
                        cp["inner_beams"][2][1],
                        cp["t_sections"][5][1],
                        cp["wedges"][2][1],
                    ],
                ],
            }
        return self._quad_planes

    @property
    def construction_quads(self):
        if self._construction_quads is None:
            quad_polygons = {
                "outer_ribs": [],
                "inner_beams": [],
                "inner_ribs": [],
                "wedges": [],
                "t_sections": [],
            }

            plane_xy = Plane.worldXY()
            for key, planes_lists in self.quad_planes.items():
                for planes in planes_lists:
                    if len(planes) != 4:
                        continue
                    p0 = Point(*intersection_plane_plane_plane(plane_xy, planes[0], planes[3]))
                    p1 = Point(*intersection_plane_plane_plane(plane_xy, planes[0], planes[1]))
                    p2 = Point(*intersection_plane_plane_plane(plane_xy, planes[1], planes[2]))
                    p3 = Point(*intersection_plane_plane_plane(plane_xy, planes[2], planes[3]))

                    quad_polygons[key].append(Polygon([p0, p1, p2, p3]))
            self._construction_quads = quad_polygons
        return self._construction_quads

    # ------------------------------------------------------------------- #
    # 3D geometry (not implemented yet)
    # ------------------------------------------------------------------- #

    @staticmethod
    def quadratic_points(p0, p1, p2, divisions=7):
        """Generate points along a quadratic Bezier curve (parabola).

        Parameters
        ----------
        p0 : :class:`compas.geometry.Point`
            Start point.
        p1 : :class:`compas.geometry.Point`
            Control point.
        p2 : :class:`compas.geometry.Point`
            End point.
        divisions : int
            Number of points to generate along the curve.

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Polyline of points along the Bezier curve.
        """
        points = []
        for k in range(divisions):
            t = k / (divisions - 1)
            pt = (1 - t) ** 2 * p0 + 2 * (1 - t) * t * p1 + t**2 * p2
            points.append(pt)
        return Polyline(points)

    @property
    def boundary_parabolas(self):
        """Boundary parabolas along the outer and inner rib axes,
        each flanked by two t-section offsets at +/- size_tsections."""

        def _trim_end(line, amount):
            u = (line.end - line.start).unitized()
            return Line(line.start + u * amount, line.end)

        if self._boundary_parabolas is None:
            axes = [
                _trim_end(self.construction_quads["outer_ribs"][0].lines[0], self.size_wedge),
                _trim_end(self.construction_quads["outer_ribs"][1].lines[0], self.size_wedge),
            ]

            divisions = 7
            q1_parabolas = []
            for axis in axes:
                p0 = Vector(0, 0, -self.height) + axis.start
                p1 = Vector(0, 0, -self.static_h) + axis.midpoint
                p2 = Vector(0, 0, -self.static_h) + axis.end
                parabola = BezierCurve.quadratic_points(p0, p1, p2, divisions)
                q1_parabolas.append(
                    [
                        parabola,
                        PolylineOffset.offset_polyline(parabola, self.size_tsections),
                        PolylineOffset.offset_polyline(parabola, 2 * self.size_tsections),
                    ]
                )

            # Inner parabolas are projections
            projection0 = Projection.from_plane_and_direction(self.construction_planes["inner_ribs"][0][0], self.construction_planes["outer_ribs"][0][0].normal)
            projection1 = Projection.from_plane_and_direction(self.construction_planes["inner_ribs"][1][0], self.construction_planes["outer_ribs"][1][0].normal)

            q1_parabolas.append(
                [
                    q1_parabolas[0][0].transformed(projection0),
                    q1_parabolas[0][1].transformed(projection0),
                    q1_parabolas[0][2].transformed(projection0),
                ]
            )
            q1_parabolas.append(
                [
                    q1_parabolas[1][0].transformed(projection1),
                    q1_parabolas[1][1].transformed(projection1),
                    q1_parabolas[1][2].transformed(projection1),
                ]
            )

            self._boundary_parabolas = q1_parabolas

        return self._boundary_parabolas

    @property
    def block_level_bottom(self):
        """Bottom level of the block - used for ribs and wedges."""
        if self._block_level_bottom is None:
            cut = PolylineCut.cut_by_plane(
                self.boundary_parabolas[2][0],
                self.construction_planes["wedges"][1][1],
            )
            cut = PolylineCut.cut_by_plane(
                cut,
                self.construction_planes["inner_beams"][1][1],
            )
            self._block_level_bottom = cut[0].z
        return self._block_level_bottom

    @property
    def block_level_top(self):
        """Top level of the block - used for ribs and wedges."""
        if self._block_level_top is None:
            self._block_level_top = self._block_level_bottom + self.size_wedge
        return self._block_level_top

    @property
    def outer_ribs_bottom(self):
        """Lowest z coordinate reached by the outer rib plates.

        Used as the bottom level of the boolean blocks that cut the column, so
        the column is cut down exactly to the deepest point of the outer ribs.
        """
        return min(pt[2] for plate in self.outer_ribs for poly in (plate.top_polyline, plate.bottom_polyline) if poly is not None for pt in poly.points)

    @property
    def beds(self):
        """Bed plates as a flat list, three panels (rows) deep.

        Each plate is tagged with ``plate.bed_row`` (0, 1 or 2) so a consumer
        can split the beds into their three rows without having to know the
        panel boundaries.
        """

        # 1. Project polylines to planes
        # 2. Cut the projected polylines by side planes

        def panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection1):
            def _extend_polyline_ends(pl, amount=1e6):
                pts = list(pl.points)
                d0 = (pts[0] - pts[1]).unitized() * amount
                d1 = (pts[-1] - pts[-2]).unitized() * amount
                pts[0] = pts[0] + d0
                pts[-1] = pts[-1] + d1
                return Polyline(pts)

            cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(parabola0, amount=1000), cut_plane0), cut_plane1)
            cut1 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(parabola1, amount=1000), cut_plane0), cut_plane1)

            cut00 = cut0.transformed(projection0)
            cut01 = cut0.transformed(projection1)
            cut10 = cut1.transformed(projection0)
            cut11 = cut1.transformed(projection1)

            plates = []
            for i in range(len(cut00.points) - 1):
                # The cut00/cut01 face is physically the LOWER face of the bed and
                # cut10/cut11 the upper one, so assign cut00/cut01 -> bottom and
                # cut10/cut11 -> top. That makes the plate's base-plane normal point
                # UP (out of the floor), consistent with the other plate families,
                # instead of down (which had top/bottom inverted).
                bottom = Polyline(
                    [
                        cut00.points[i],
                        cut00.points[i + 1],
                        cut01.points[i + 1],
                        cut01.points[i],
                        cut00.points[i],
                    ]
                )
                top = Polyline(
                    [
                        cut10.points[i],
                        cut10.points[i + 1],
                        cut11.points[i + 1],
                        cut11.points[i],
                        cut10.points[i],
                    ]
                )
                plates.append(PlateElement(top_polyline=top, bottom_polyline=bottom))
            return plates

        plates = []

        # The beds are built as three panels (rows). Tag each plate with its
        # row index so consumers can group the three bed rows separately, while
        # ``beds`` itself stays a flat list (like the other plate properties).
        def _add_row(row_plates, row_index):
            for plate in row_plates:
                plate.bed_row = row_index
            plates.extend(row_plates)

        # Panel 1
        parabola0 = self.boundary_parabolas[0][1]
        parabola1 = self.boundary_parabolas[0][2]
        projection0 = Projection.from_plane_and_direction(
            self.construction_planes["inner_ribs"][0][0],
            self.construction_planes["outer_ribs"][0][0].normal,
        )
        projection1 = Projection.from_plane_and_direction(
            self.construction_planes["outer_ribs"][0][1],
            self.construction_planes["outer_ribs"][0][0].normal,
        )
        cut_plane0 = self.construction_planes["inner_beams"][0][1]
        cut_plane1 = self.construction_planes["wedges"][0][0]
        _add_row(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection1), 0)

        # Panel 2
        parabola0 = self.boundary_parabolas[2][1]
        parabola1 = self.boundary_parabolas[2][2]
        projection0 = Projection.from_plane_and_direction(
            self.construction_planes["inner_ribs"][0][1],
            self.construction_planes["inner_ribs"][0][0].normal - self.construction_planes["inner_ribs"][1][0].normal,
        )
        projection1 = Projection.from_plane_and_direction(
            self.construction_planes["inner_ribs"][1][1],
            self.construction_planes["inner_ribs"][0][0].normal - self.construction_planes["inner_ribs"][1][0].normal,
        )
        cut_plane0 = self.construction_planes["inner_beams"][1][1]
        cut_plane1 = self.construction_planes["wedges"][1][0]
        _add_row(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection1), 1)

        # Panel 3
        parabola0 = self.boundary_parabolas[1][1]
        parabola1 = self.boundary_parabolas[1][2]
        projection0 = Projection.from_plane_and_direction(
            self.construction_planes["inner_ribs"][1][0],
            self.construction_planes["outer_ribs"][1][0].normal,
        )
        projection1 = Projection.from_plane_and_direction(
            self.construction_planes["outer_ribs"][1][1],
            self.construction_planes["outer_ribs"][1][0].normal,
        )
        cut_plane0 = self.construction_planes["inner_beams"][2][1]
        cut_plane1 = self.construction_planes["wedges"][2][0]
        _add_row(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection1), 2)

        return plates

    @property
    def bed_top_planes(self):
        """Best-fit top plane of each bed panel, ordered to match the 3 wedges.

        The beds are the last (bottom) plate layer; each bed panel sits under
        one wedge. The boolean wedge bottoms are cut by these planes so the
        wedges land on the beds instead of stopping in the air. Mirrors the
        per-panel construction in :pyattr:`beds`.
        """
        from compas.geometry import bestfit_plane

        cp = self.construction_planes

        def _extend(pl, amount=1000):
            pts = list(pl.points)
            pts[0] = pts[0] + (pts[0] - pts[1]).unitized() * amount
            pts[-1] = pts[-1] + (pts[-1] - pts[-2]).unitized() * amount
            return Polyline(pts)

        def _panel_top_plane(parabola0, cut_plane0, cut_plane1, projection0, projection1):
            cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend(parabola0), cut_plane0), cut_plane1)
            pts0 = cut0.transformed(projection0).points
            pts1 = cut0.transformed(projection1).points
            # Fit the plane to the wedge-end (deepest) bed quad only, so it
            # matches the bed locally under the wedge rather than averaging in
            # the panel's rising oculus end.
            if pts0[0][2] > pts0[-1][2]:
                pts0, pts1 = pts0[::-1], pts1[::-1]
            top_pts = pts0[:2] + pts1[:2]
            origin, normal = bestfit_plane(top_pts)
            return Plane(origin, normal)

        # Panel 1 -> wedge 0  (boundary_parabolas[k][2] is the bed's upper face)
        plane0 = _panel_top_plane(
            self.boundary_parabolas[0][2],
            cp["inner_beams"][0][1],
            cp["wedges"][0][0],
            Projection.from_plane_and_direction(cp["inner_ribs"][0][0], cp["outer_ribs"][0][0].normal),
            Projection.from_plane_and_direction(cp["outer_ribs"][0][1], cp["outer_ribs"][0][0].normal),
        )
        # Panel 2 (central) -> wedge 1
        plane1 = _panel_top_plane(
            self.boundary_parabolas[2][2],
            cp["inner_beams"][1][1],
            cp["wedges"][1][0],
            Projection.from_plane_and_direction(cp["inner_ribs"][0][1], cp["inner_ribs"][0][0].normal - cp["inner_ribs"][1][0].normal),
            Projection.from_plane_and_direction(cp["inner_ribs"][1][1], cp["inner_ribs"][0][0].normal - cp["inner_ribs"][1][0].normal),
        )
        # Panel 3 -> wedge 2
        plane2 = _panel_top_plane(
            self.boundary_parabolas[1][2],
            cp["inner_beams"][2][1],
            cp["wedges"][2][0],
            Projection.from_plane_and_direction(cp["inner_ribs"][1][0], cp["outer_ribs"][1][0].normal),
            Projection.from_plane_and_direction(cp["outer_ribs"][1][1], cp["outer_ribs"][1][0].normal),
        )
        return [plane0, plane1, plane2]

    @property
    def tsections(self):
        """Create the tsections geometry"""

        def panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection10, projection11):
            cut00 = parabola0.transformed(projection0)  # face 0 top
            cut10 = parabola1.transformed(projection0)  # face 0 bottom

            cut01 = cut00.transformed(projection10)  # face 1 top
            cut11 = cut10.transformed(projection11)  # face 1 bottom

            def _extend_polyline_ends(pl, amount=1e6):
                pts = list(pl.points)
                d0 = (pts[0] - pts[1]).unitized() * amount
                d1 = (pts[-1] - pts[-2]).unitized() * amount
                pts[0] = pts[0] + d0
                pts[-1] = pts[-1] + d1
                return Polyline(pts)

            cut00 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(cut00, amount=1000), cut_plane0), cut_plane1)
            cut01 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(cut01, amount=1000), cut_plane0), cut_plane1)
            cut10 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(cut10, amount=1000), cut_plane0), cut_plane1)
            cut11 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(cut11, amount=1000), cut_plane0), cut_plane1)

            top = Polyline(cut00.points + cut10.points[::-1] + [cut00.points[0]])
            bottom = Polyline(cut01.points + cut11.points[::-1] + [cut01.points[0]])
            self.debug.append(top)
            self.debug.append(bottom)
            return [PlateElement(top_polyline=top, bottom_polyline=bottom)]

        plates = []

        # T-section 1 same T-section 4
        parabola0 = self.boundary_parabolas[0][0]
        parabola1 = self.boundary_parabolas[0][1]
        dir = self.construction_planes["outer_ribs"][0][0].normal
        projection0 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][0][0], dir)
        projection1 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][0][1], dir)
        cut_plane0 = self.construction_planes["inner_beams"][0][1]
        cut_plane1 = self.construction_planes["wedges"][0][0]
        plates.extend(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection1, projection1))

        # T-section 2a same as T-section 4
        parabola0 = self.boundary_parabolas[0][0]
        parabola1 = self.boundary_parabolas[0][1]
        dir0 = self.construction_planes["outer_ribs"][0][0].normal
        dir1 = self.construction_planes["inner_ribs"][0][0].normal - self.construction_planes["inner_ribs"][1][0].normal
        projection0 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][1][0], dir0)
        projection10 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][1][1], dir1)
        projection11 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][1][1], dir0)
        cut_plane0 = self.construction_planes["inner_beams"][0][1]
        cut_plane1 = self.construction_planes["wedges"][0][0]
        plates.extend(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection10, projection11))

        # T-section 2b
        parabola0 = self.boundary_parabolas[2][0]
        parabola1 = self.boundary_parabolas[2][1]
        dir0 = self.construction_planes["inner_ribs"][0][0].normal - self.construction_planes["inner_ribs"][1][0].normal
        projection0 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][2][0], dir0)
        projection10 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][2][1], dir0)
        projection11 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][2][1], dir0)
        cut_plane0 = self.construction_planes["inner_beams"][1][1]
        cut_plane1 = self.construction_planes["wedges"][1][0]
        plates.extend(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection10, projection11))

        # T-section 3a
        parabola0 = self.boundary_parabolas[3][0]
        parabola1 = self.boundary_parabolas[3][1]
        dir0 = self.construction_planes["inner_ribs"][0][0].normal - self.construction_planes["inner_ribs"][1][0].normal
        dir1 = self.construction_planes["t_sections"][4][1].normal
        projection0 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][4][0], dir0)
        projection10 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][4][1], dir0)
        projection11 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][4][1], dir0)
        cut_plane0 = self.construction_planes["inner_beams"][1][1]
        cut_plane1 = self.construction_planes["wedges"][1][0]
        plates.extend(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection10, projection11))

        # T-section 3b
        parabola0 = self.boundary_parabolas[1][0]
        parabola1 = self.boundary_parabolas[1][1]
        dir0 = self.construction_planes["outer_ribs"][1][0].normal
        dir1 = self.construction_planes["inner_ribs"][0][0].normal - self.construction_planes["inner_ribs"][1][0].normal
        projection0 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][3][0], dir0)
        projection10 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][3][1], dir1)
        projection11 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][3][1], dir0)
        cut_plane0 = self.construction_planes["inner_beams"][2][1]
        cut_plane1 = self.construction_planes["wedges"][2][0]
        plates.extend(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection10, projection11))

        # T-section 4
        parabola0 = self.boundary_parabolas[1][0]
        parabola1 = self.boundary_parabolas[1][1]
        dir = self.construction_planes["outer_ribs"][1][0].normal
        projection0 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][5][0], dir)
        projection1 = Projection.from_plane_and_direction(self.construction_planes["t_sections"][5][1], dir)
        cut_plane0 = self.construction_planes["inner_beams"][2][1]
        cut_plane1 = self.construction_planes["wedges"][2][0]
        plates.extend(panel_quads(parabola0, parabola1, cut_plane0, cut_plane1, projection0, projection1, projection1))

        return plates

    @property
    def outer_ribs(self):
        """Create the ribs geometry"""

        plates = []

        def outline_polyline(parabola, projection, cut_plane0, cut_plane1):
            # Implementation for creating outline polyline

            def _extend_polyline_ends(pl, amount=1e6):
                pts = list(pl.points)
                d0 = (pts[0] - pts[1]).unitized() * amount
                d1 = (pts[-1] - pts[-2]).unitized() * amount
                pts[0] = pts[0] + d0
                pts[-1] = pts[-1] + d1
                return Polyline(pts)

            # Extend generously so the parabola reaches the base wedge plane
            # (wedges[k][0]); a small extension stops short and the cut is skipped.
            cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(parabola, amount=1000), cut_plane0), cut_plane1)

            # Normalize so cut0[0] is the wedge-plane (cut_plane0) end regardless
            # of the parabola's orientation.
            d0 = abs((Point(*cut0[0]) - cut_plane0.point).dot(cut_plane0.normal))
            d1 = abs((Point(*cut0[-1]) - cut_plane0.point).dot(cut_plane0.normal))
            if d0 > d1:
                cut0 = Polyline(list(cut0.points)[::-1])

            # Clean rib: follow the trimmed parabola down to a flat base at z=0,
            # without the raised wedge-block seat tab. The wedge-end base point
            # is placed on cut_plane0 (which may be tilted) within the rib's own
            # vertical plane, so the end face follows the cut instead of staying
            # vertical. At 0deg tilt this is identical to dropping straight down.
            dxy = Vector(cut0[-1][0] - cut0[0][0], cut0[-1][1] - cut0[0][1], 0)
            rib_plane = Plane(Point(*cut0[0]), dxy.cross(Vector(0, 0, 1)))
            p0 = Point(*intersection_plane_plane_plane(cut_plane0, Plane.worldXY(), rib_plane))
            p1 = Point(cut0[-1][0], cut0[-1][1], 0)

            polyline0 = Polyline([p1, p0] + cut0.points + [p1])
            pollyine1 = polyline0.transformed(projection)
            plate = PlateElement(top_polyline=polyline0, bottom_polyline=pollyine1)
            return plate

        projection0 = Projection.from_plane_and_direction(
            self.construction_planes["outer_ribs"][0][1],
            self.construction_planes["outer_ribs"][0][1].normal,
        )
        projection1 = Projection.from_plane_and_direction(
            self.construction_planes["outer_ribs"][1][1],
            self.construction_planes["outer_ribs"][1][1].normal,
        )
        plates.append(outline_polyline(self.boundary_parabolas[0][0], projection0, self.construction_planes["wedges"][0][0], self.construction_planes["inner_beams"][0][0]))
        plates.append(outline_polyline(self.boundary_parabolas[1][0], projection1, self.construction_planes["wedges"][2][0], self.construction_planes["inner_beams"][2][0]))

        return plates

    @property
    def inner_ribs(self):
        """Create the ribs geometry"""

        plates = []

        def outline_polyline(parabola, projection, cut_plane0, cut_plane1):
            # Implementation for creating outline polyline

            def _extend_polyline_ends(pl, amount=1e6):
                pts = list(pl.points)
                d0 = (pts[0] - pts[1]).unitized() * amount
                d1 = (pts[-1] - pts[-2]).unitized() * amount
                pts[0] = pts[0] + d0
                pts[-1] = pts[-1] + d1
                return Polyline(pts)

            # Extend generously so the parabola reaches the base wedge plane
            # (wedges[k][0]); a small extension stops short and the cut is skipped.
            cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(_extend_polyline_ends(parabola, amount=1000), cut_plane0), cut_plane1)

            # Normalize so cut0[0] is the wedge-plane (cut_plane0) end regardless
            # of the parabola's orientation.
            d0 = abs((Point(*cut0[0]) - cut_plane0.point).dot(cut_plane0.normal))
            d1 = abs((Point(*cut0[-1]) - cut_plane0.point).dot(cut_plane0.normal))
            if d0 > d1:
                cut0 = Polyline(list(cut0.points)[::-1])

            # Clean rib: follow the trimmed parabola down to a flat base at z=0,
            # without the raised wedge-block seat tab. The wedge-end base point
            # is placed on cut_plane0 (which may be tilted) within the rib's own
            # vertical plane, so the end face follows the cut instead of staying
            # vertical. At 0deg tilt this is identical to dropping straight down.
            dxy = Vector(cut0[-1][0] - cut0[0][0], cut0[-1][1] - cut0[0][1], 0)
            rib_plane = Plane(Point(*cut0[0]), dxy.cross(Vector(0, 0, 1)))
            p0 = Point(*intersection_plane_plane_plane(cut_plane0, Plane.worldXY(), rib_plane))
            p1 = Point(cut0[-1][0], cut0[-1][1], 0)
            p1 = Point(*intersection_line_plane(Line(p0, p1), cut_plane1))

            polyline0 = Polyline([p1, p0] + cut0.points + [p1])
            pollyine1 = polyline0.transformed(projection)
            plate = PlateElement(top_polyline=polyline0, bottom_polyline=pollyine1)
            return plate

        projection0 = Projection.from_plane_and_direction(
            self.construction_planes["inner_ribs"][0][1],
            self.construction_planes["inner_ribs"][0][1].normal - self.construction_planes["inner_ribs"][1][1].normal,
        )
        projection1 = Projection.from_plane_and_direction(
            self.construction_planes["inner_ribs"][1][1],
            self.construction_planes["inner_ribs"][0][1].normal - self.construction_planes["inner_ribs"][1][1].normal,
        )
        plates.append(outline_polyline(self.boundary_parabolas[2][0], projection0, self.construction_planes["wedges"][1][0], self.construction_planes["inner_beams"][1][1]))
        plates.append(outline_polyline(self.boundary_parabolas[3][0], projection1, self.construction_planes["wedges"][1][0], self.construction_planes["inner_beams"][1][1]))

        return plates

    @property
    def wedge_block(self):
        # Create a block for the wedge geometry, which is used to cut the ribs and beams.
        # The block is defined by the planes of the outer ribs and the planes of the inner beams.

        planes = [
            self.construction_planes["outer_ribs"][0][0],
            self.construction_planes["wedges"][0][0],
            self.construction_planes["wedges"][1][0],
            self.construction_planes["wedges"][2][0],
            self.construction_planes["outer_ribs"][1][0],
            self.construction_planes["wedges"][2][1],
            self.construction_planes["wedges"][1][1],
            self.construction_planes["wedges"][0][1],
        ]

        bottom_plane = Plane((0, 0, self.block_level_bottom), Vector(0, 0, 1))
        top_plane = Plane((0, 0, self.block_level_top), Vector(0, 0, 1))

        def _corners(h_plane):
            pts = []
            n = len(planes)
            for i in range(n):
                a = planes[i]
                b = planes[(i + 1) % n]
                result = intersection_plane_plane_plane(a, b, h_plane)
                if result:
                    pts.append(Point(*result))
            return pts

        bottom_corners = _corners(bottom_plane)
        top_corners = _corners(top_plane)

        bottom_polyline = Polyline(bottom_corners + [bottom_corners[0]])
        top_polyline = Polyline(top_corners + [top_corners[0]])
        return []
        return [PlateElement(top_polyline=top_polyline, bottom_polyline=bottom_polyline)]

    @property
    def wedges_inner_beams(self):
        """3 wedges + 2 sherpa connections + 3 collumn cutting blocks"""

        top_plane = Plane((0, 0, 0), Vector(0, 0, 1))
        # Each wedge bottom is cut by its bed panel's top plane (the beds are
        # the bottom plate layer) so the wedges sit on the beds, not in the air.
        bed_planes = self.bed_top_planes
        bottom_plane1 = Plane((0, 0, -self.static_h + self.size_tsections * 2), Vector(0, 0, 1))

        def _wedge(planes, bottom_plane, top_plane):
            pts_bottom, pts_top = [], []
            n = len(planes)
            for i in range(n):
                a = planes[i]
                b = planes[(i + 1) % n]
                rb = intersection_plane_plane_plane(a, b, bottom_plane)
                rt = intersection_plane_plane_plane(a, b, top_plane)
                if rb:
                    pts_bottom.append(Point(*rb))
                if rt:
                    pts_top.append(Point(*rt))
            return PlateElement(
                top_polyline=Polyline(pts_top + [pts_top[0]]),
                bottom_polyline=Polyline(pts_bottom + [pts_bottom[0]]),
            )

        cp = self.construction_planes
        rib_pairs = [
            (cp["outer_ribs"][0][1], cp["inner_ribs"][0][0]),
            (cp["inner_ribs"][0][1], cp["inner_ribs"][1][1]),
            (cp["inner_ribs"][1][0], cp["outer_ribs"][1][1]),
        ]

        wedges = []
        if self.output_wedges:
            for group, bot in [(range(3, 6), bottom_plane1)]:
                for i in group:
                    left, right = rib_pairs[i % 3]
                    wedges.append(
                        _wedge(
                            [left, bot, right, top_plane],
                            bottom_plane=cp["wedges"][i][0],
                            top_plane=cp["wedges"][i][1],
                        )
                    )

        for i in range(3):
            left, right = rib_pairs[i]
            wedges.append(
                _wedge(
                    [left, bed_planes[i], right, top_plane],
                    bottom_plane=cp["wedges"][i][0],
                    top_plane=cp["wedges"][i][1],
                )
            )

        return wedges

    @property
    def inner_beams(self):
        """Flip the middle beam."""

        # Beam1

        def _wedge(planes, bottom_plane, top_plane):
            pts_bottom, pts_top = [], []
            n = len(planes)
            for i in range(n):
                a = planes[i]
                b = planes[(i + 1) % n]
                rb = intersection_plane_plane_plane(a, b, bottom_plane)
                rt = intersection_plane_plane_plane(a, b, top_plane)
                if rb:
                    pts_bottom.append(Point(*rb))
                if rt:
                    pts_top.append(Point(*rt))
            return PlateElement(
                top_polyline=Polyline(pts_top + [pts_top[0]]),
                bottom_polyline=Polyline(pts_bottom + [pts_bottom[0]]),
            )

        side0 = Plane((0, 0, 0), Vector(0, 0, 1))
        side1 = Plane((0, 0, -self.static_h), Vector(0, 0, 1))

        wedges = [
            _wedge(
                [
                    self.construction_planes["outer_ribs"][0][1],
                    side0,
                    self.construction_planes["inner_beams"][1][0],
                    side1,
                ],
                bottom_plane=self.construction_planes["inner_beams"][0][0],
                top_plane=self.construction_planes["inner_beams"][0][1],
            ),
            _wedge(
                [
                    self.construction_planes["inner_beams"][0][1],
                    side0,
                    self.construction_planes["inner_beams"][2][1],
                    side1,
                ],
                bottom_plane=self.construction_planes["inner_beams"][1][0],
                top_plane=self.construction_planes["inner_beams"][1][1],
            ),
            _wedge(
                [
                    self.construction_planes["outer_ribs"][1][1],
                    side0,
                    self.construction_planes["inner_beams"][1][0],
                    side1,
                ],
                bottom_plane=self.construction_planes["inner_beams"][2][0],
                top_plane=self.construction_planes["inner_beams"][2][1],
            ),
        ]

        return wedges

    @property
    def oculus(self):
        """Oculus constructed from the inner beam 2 beam first plane rotated around origin 4 times.
        Oculus is made from 5 plates elements:
        4x boundary beams
        1x inner plate connecting the 4 beams
        """

        def _wedge(planes, bottom_plane, top_plane, flip=False):
            pts_bottom, pts_top = [], []
            n = len(planes)
            for i in range(n):
                a = planes[i]
                b = planes[(i + 1) % n]
                rb = intersection_plane_plane_plane(a, b, bottom_plane)
                rt = intersection_plane_plane_plane(a, b, top_plane)
                if rb:
                    pts_bottom.append(Point(*rb))
                if rt:
                    pts_top.append(Point(*rt))
            top = Polyline(pts_top + [pts_top[0]])
            bottom = Polyline(pts_bottom + [pts_bottom[0]])
            if flip:  # swap which face is top vs bottom (for the 8 side plates)
                top, bottom = bottom, top
            return PlateElement(top_polyline=top, bottom_polyline=bottom)

        cp = self.construction_planes
        side0 = Plane((0, 0, 0), Vector(0, 0, 1))
        side1 = Plane((0, 0, -self.static_h + self.size_tsections), Vector(0, 0, 1))
        side2 = Plane((0, 0, -self.static_h), Vector(0, 0, 1))
        side3 = Plane((0, 0, -self.static_h + self.size_tsections * 2), Vector(0, 0, 1))

        rotated = [cp["inner_beams"][1][0].transformed(Rotation.from_axis_and_angle([0, 0, 1], i * math.pi / 2)) for i in range(4)]

        rotated_inner = [cp["inner_beams"][1][1].offset(-self.size_inner_beams * 2).transformed(Rotation.from_axis_and_angle([0, 0, 1], i * math.pi / 2)) for i in range(4)]

        # inner = [r.offset(-self.size_inner_beams) for r in rotated]

        plates = []

        # 4 boundary beams (side plates - top/bottom swapped)
        for i in range(4):
            plates.append(
                _wedge(
                    [side2, rotated[(i + 1) % 4], side0, rotated_inner[(i - 1) % 4]],
                    bottom_plane=rotated[i],
                    top_plane=rotated_inner[i],
                    flip=True,
                )
            )

        # 4 boundary inner wedges beams
        if self.output_wedges:
            for i in range(4):
                plates.append(
                    _wedge(
                        [side3, rotated_inner[(i + 1) % 4], side0, rotated_inner[(i - 1) % 4].offset(-self.size_inner_beams)],
                        bottom_plane=rotated_inner[i],
                        top_plane=rotated_inner[i].offset(-self.size_inner_beams),
                    )
                )

        # 4 boundary inner bottom wedges beams.
        # Loft between the two horizontal planes (side2 -> side1) with the slanted
        # inner-beam planes as the side walls, so the bottom/top faces - hence the
        # base_frame - are the large HORIZONTAL faces (normal +Z) and the plate
        # lays flat. (Same solid as lofting between the slanted faces, just a
        # different choice of which faces are bottom/top.)
        for i in range(4):
            plates.append(
                _wedge(
                    [
                        rotated_inner[i],
                        rotated_inner[(i + 1) % 4],
                        rotated_inner[i].offset(-self.size_tsections),
                        rotated_inner[(i - 1) % 4].offset(-self.size_tsections),
                    ],
                    bottom_plane=side2,
                    top_plane=side1,
                )
            )

        # 1 inner plate – center diamond bounded by the 4 oculus faces
        plates.append(_wedge(rotated_inner, bottom_plane=side1, top_plane=side3))
        return plates
