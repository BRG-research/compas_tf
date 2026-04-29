from compas.data import Data
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Plane
from compas.geometry import Vector
from compas.geometry import intersection_segment_segment
from compas.geometry import intersection_plane_plane_plane
from compas.geometry import intersection_line_plane
import math

from compas_tf.geometry import BezierCurve
from compas_tf.geometry import PolylineOffset


class FloorGuide(Data):
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

        # parabolas parameters
        self.height = height
        self.rise = rise
        self.static_h = height - rise

        # caches (invalidated lazily)
        self._oculus_pts = None
        self._q_poly = None
        self._c_poly = None
        self._axes = None
        self._bound_parabolas = None
        self._construction_planes = None
        self._quad_planes = None
        self._construction_quads = None

        self.debug = []

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
        }

    @classmethod
    def __from_data__(cls, data: dict) -> "FloorGuide":
        return cls(**data)

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
            self._q_poly = Polygon([
                Point(-self.size_grid_x, -self.size_grid_y, 0),
                Point(0, -self.size_grid_y, 0),

                self.oculus_points[0],
                self.oculus_points[3],

                Point(-self.size_grid_x, 0, 0),
            ])
        return self._q_poly
    
    @property
    def quarter_column_polygon(self):
        """The column head polygon from which the ribs will start."""
        if self._c_poly is None:
            corner = self.quarter_polygon[0]
            self._c_poly = Polygon([
                corner,
                corner + Vector(self.size_column_head, 0, 0),

                corner + Vector(self.size_column_head, self.size_column_head_chamfer, 0),
                corner + Vector(self.size_column_head_chamfer, self.size_column_head, 0),

                corner + Vector(0, self.size_column_head, 0),
            ])
        return self._c_poly
    
    # ------------------------------------------------------------------ #
    # Beams
    # We wont define the floor as axis
    # We will define them as polygon offsets.
    # ------------------------------------------------------------------ #

    @property
    def construction_planes(self, oculus_plane_angle=10):

        """ Plane pairs each corresponds to the long edge of 2d plan plate edges. 
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
            construction_planes["outer_ribs"]=[
                [
                    plane0.copy(),
                    plane0.offset(self.size_outer_ribs),
                ],
                [
                    plane1.copy(),
                    plane1.offset(self.size_outer_ribs)
                ]
            ]

            # 2. inner beams, NOTE the central plane has rotation - oculus_plane_angle
            plane0 = Plane(self.quarter_polygon.lines[1].midpoint, Vector.cross(self.quarter_polygon.lines[1].direction, -Vector.Zaxis()))
            plane1 = Plane(self.quarter_polygon.lines[2].midpoint, Vector.cross(self.quarter_polygon.lines[2].direction, -Vector.Zaxis()))
            plane1.rotate(-oculus_plane_angle* math.pi / 180, self.quarter_polygon.lines[2].direction, self.quarter_polygon.lines[2].midpoint)
            plane2 = Plane(self.quarter_polygon.lines[3].midpoint, Vector.cross(self.quarter_polygon.lines[3].direction, -Vector.Zaxis()))
            construction_planes["inner_beams"]=[
                [
                    plane0.copy(),
                    plane0.offset(self.size_inner_beams),
                ],
                [
                    plane1.copy(),
                    plane1.offset(self.size_inner_beams)
                ],
                [
                    plane2.copy(),
                    plane2.offset(self.size_inner_beams)
                ]
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

            plane0 = Plane((p0+p2)*0.5, Vector.cross(p0-p2, -Vector.Zaxis()))
            plane1 = Plane((p1+p3)*0.5, Vector.cross(p1-p3, Vector.Zaxis()))

            construction_planes["inner_ribs"]=[
                [
                    plane0.copy(),
                    plane0.offset(self.size_inner_ribs),
                ],
                [
                    plane1.copy(),
                    plane1.offset(self.size_inner_ribs)
                ]
            ]

            # 4. wedges
            plane0 = Plane(self.quarter_column_polygon.lines[1].midpoint, Vector.cross(self.quarter_column_polygon.lines[1].direction, Vector.Zaxis()))
            plane1 = Plane(self.quarter_column_polygon.lines[2].midpoint, Vector.cross(self.quarter_column_polygon.lines[2].direction, Vector.Zaxis()))
            plane2 = Plane(self.quarter_column_polygon.lines[3].midpoint, Vector.cross(self.quarter_column_polygon.lines[3].direction, Vector.Zaxis()))

            line0 = Line(p0, self.quarter_column_polygon[2])
            line1 = Line(p1, self.quarter_column_polygon[3])
            plane_p0 = Point(*intersection_line_plane(line0, plane0.offset(self.size_wedge)))
            plane_p1 = Point(*intersection_line_plane(line1, plane2.offset(self.size_wedge)))
            plane1_offset = Plane(plane_p0, Vector.cross(plane_p1-plane_p0, Vector.Zaxis()))
            self.debug.append(plane_p0)
            self.debug.append(plane_p1)

            plane4 = construction_planes["inner_beams"][0][1]
            plane5 = construction_planes["inner_beams"][1][1]
            plane6 = construction_planes["inner_beams"][2][1]

            construction_planes["wedges"]=[
                [
                    plane0.copy(),
                    plane0.offset(self.size_wedge),
                ],
                [
                    plane1.copy(),
                    plane1_offset
                ],
                [
                    plane2.copy(),
                    plane2.offset(self.size_wedge)
                ],
                [
                    plane4.copy(),
                    plane4.offset(self.size_wedge),
                ],
                [
                    plane5.copy(),
                    plane5.offset(self.size_wedge)
                ],
                [
                    plane6.copy(),
                    plane6.offset(self.size_wedge)
                ]
            ]

            # 5. t-sections
            plane0 = Plane((p0+p2)*0.5, Vector.cross(p0-p2, -Vector.Zaxis()))
            plane1 = Plane((p1+p3)*0.5, Vector.cross(p1-p3, -Vector.Zaxis()))

            construction_planes["t_sections"]=[
                [
                    construction_planes["outer_ribs"][0][1].copy(),
                    construction_planes["outer_ribs"][0][1].offset(self.size_tsections)
                ],
                [
                    construction_planes["inner_ribs"][0][0].copy(),
                    construction_planes["inner_ribs"][0][0].offset(-self.size_tsections)
                ],
                [
                    construction_planes["inner_ribs"][0][1].copy(),
                    construction_planes["inner_ribs"][0][1].offset(self.size_tsections)
                ],
                [
                    construction_planes["inner_ribs"][1][0].copy(),
                    construction_planes["inner_ribs"][1][0].offset(-self.size_tsections)
                ],
                [
                    construction_planes["inner_ribs"][1][1].copy(),
                    construction_planes["inner_ribs"][1][1].offset(self.size_tsections)
                ],
                [
                    construction_planes["outer_ribs"][1][1].copy(),
                    construction_planes["outer_ribs"][1][1].offset(self.size_tsections)
                ],

            ]

            self._construction_planes = construction_planes
        return self._construction_planes
    
    
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
        if self._bound_parabolas is None:
            axes = [
                self.construction_quads["outer_ribs"][0].lines[0],
                self.construction_quads["outer_ribs"][1].lines[0],
                self.construction_quads["inner_ribs"][0].lines[0],
                self.construction_quads["inner_ribs"][1].lines[0],
            ]
            divisions = 7
            q1_parabolas = []
            for axis in axes:
                p0 = Vector(0, 0, -self.height) + axis.start
                p1 = Vector(0, 0, -self.static_h) + axis.midpoint
                p2 = Vector(0, 0, -self.static_h) + axis.end
                parabola = BezierCurve.quadratic_points(p0, p1, p2, divisions)
                q1_parabolas.append([
                    parabola,
                    PolylineOffset.offset_polyline(parabola, self.size_tsections),
                    PolylineOffset.offset_polyline(parabola, -self.size_tsections),
                ])
            self._bound_parabolas = q1_parabolas
        return self._bound_parabolas


    # @property
    # def corner_point(self):
    #     """The bottom left corner."""
    #     return Point(-self.size, -self.size, 0)

    # def corner_point_column(self, column_size=200):
    #     """Column base center in plan for one quarter.

    #     Parameters
    #     ----------
    #     column_size : float
    #         Column cross-section side length in mm.

    #     Returns
    #     -------
    #     :class:`compas.geometry.Point`
    #     """
    #     d = self.size - (column_size * 0.5)
    #     return Point(-d, -d, 0)

    # @property
    # def boundary_points(self):
    #     """Points along quarter boundary."""
    #     q1 = self.quarter_polygon
    #     return [q1[i] for i in [1, 2, 3, 4]]

    # # ------------------------------------------------------------------ #
    # #  Axes & parabolas (3D curves along the vault)
    # # ------------------------------------------------------------------ #

    # @property
    # def axes(self):
    #     """Lines of the ribs, with a small offset for the two central axes."""
    #     if self._axes is None:
    #         polygon = self.quarter_polygon
    #         offset_polygon_full = PolylineOffset.offset_polygon(polygon, self.thick)
    #         offset_polygon_half = PolylineOffset.offset_polygon(polygon, self.thick * 0.5)
    #         axes_lines = list(offset_polygon_half.lines)

    #         corner = offset_polygon_half.points[0]
    #         axes_lines.insert(1, Line(corner, offset_polygon_full.points[2]))
    #         axes_lines.insert(2, Line(corner, offset_polygon_full.points[3]))

    #         extended_axes = []
    #         for j in range(len(axes_lines)):
    #             p0, p1 = axes_lines[j].start, axes_lines[j].end
    #             direction = (p1 - p0).unitized()
    #             line = Line(direction * self.thick * 4 + p1, -direction * self.thick * 4 + p0)

    #             intersection_points = []
    #             for k in range(len(polygon)):
    #                 seg = Line(polygon[k], polygon[(k + 1) % len(polygon)])
    #                 pt = intersection_segment_segment(line, seg)
    #                 if pt[0] is not None:
    #                     intersection_points.append(pt[0])

    #             line = Line(intersection_points[0], intersection_points[1])
    #             _, cpt0 = axes_lines[j].closest_point(line.start, True)
    #             _, cpt1 = axes_lines[j].closest_point(line.end, True)
    #             if cpt0 > cpt1:
    #                 line = Line(line.end, line.start)
    #             extended_axes.append(line)

    #         # Move central axes outward a bit to avoid double cut on the plate.
    #         direction0 = Vector.Zaxis().cross(extended_axes[1].direction).unitized() * self.thick * 0.5
    #         extended_axes[1].translate(-direction0)
    #         direction1 = Vector.Zaxis().cross(extended_axes[2].direction).unitized() * self.thick * 0.5
    #         extended_axes[2].translate(direction1)
    #         self._axes = extended_axes

    #     return self._axes

    # @property
    # def boundary_parabolas(self):
    #     """Two boundary parabolas for first and last axes."""
    #     if self._bound_parabolas is None:
    #         divisions = 7
    #         q1_parabolas = []

    #         for j in [0, len(self.axes) - 1]:
    #             if j == 0:
    #                 p0 = Vector(0, 0, -self.height) + self.axes[j].start
    #                 p1 = Vector(0, 0, -self.static_h) + self.axes[j].midpoint
    #                 p2 = Vector(0, 0, -self.static_h) + self.axes[j].end
    #             else:
    #                 p0 = Vector(0, 0, -self.static_h) + self.axes[j].start
    #                 p1 = Vector(0, 0, -self.static_h) + self.axes[j].midpoint
    #                 p2 = Vector(0, 0, -self.height) + self.axes[j].end

    #             bezier = BezierCurve.quadratic_points(p0, p1, p2, divisions)
    #             q1_parabolas.append(bezier)

    #         self._bound_parabolas = q1_parabolas
    #     return self._bound_parabolas
