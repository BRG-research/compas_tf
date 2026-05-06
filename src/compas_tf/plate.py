from typing import Optional
from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Projection
from compas.geometry import Transformation
from compas.geometry import Vector
from compas.geometry import bestfit_plane
from compas.geometry import intersection_segment_plane
from compas.geometry.triangulation_earclip import Earcut
from compas.itertools import pairwise
from compas_model.elements.element import Element
from compas_model.elements.element import Feature
from compas_tf.geometry import PolylineLoft


class PlateFeature(Feature):
    pass


def _is_clockwise_on_plane(polyline: Polyline, plane: Plane) -> bool:
    """Check if polyline is clockwise when viewed from plane normal direction.

    Uses the shoelace formula on the XY projection after transforming to the plane's frame.

    Parameters
    ----------
    polyline : :class:`compas.geometry.Polyline`
        The polyline to check.
    plane : :class:`compas.geometry.Plane`
        The plane to project onto.

    Returns
    -------
    bool
        True if clockwise, False if counter-clockwise.
    """
    frame = Frame.from_plane(plane)
    world_to_local = Transformation.from_frame_to_frame(frame, Frame.worldXY())

    local_points = [Point(*p).transformed(world_to_local) for p in polyline.points]

    total = 0.0
    for i in range(len(local_points) - 1):
        total += (local_points[i + 1].x - local_points[i].x) * (local_points[i + 1].y + local_points[i].y)

    return total > 0


def _flip_polyline(polyline: Polyline) -> Polyline:
    """Reverse the order of points in a polyline."""
    return Polyline(list(reversed(polyline.points)))


class PlateElement(Element):
    """Class representing a plate element constructed from top/bottom polylines or polygons.

    Can be constructed in two ways:
    1. From polygon + thickness: The polygon is extruded in the opposite direction of the normal.
    2. From top/bottom polylines + mesh: The mesh is pre-computed (e.g., lofted from polylines).

    Parameters
    ----------
    polygon : :class:`compas.geometry.Polygon`, optional
        The base polygon of the plate (used when not providing polylines).
    thickness : float
        The total offset thickness above and below the polygon.
    top : :class:`compas.geometry.Polygon` or :class:`compas.geometry.Polyline`, optional
        The top boundary of the plate.
    bottom : :class:`compas.geometry.Polygon` or :class:`compas.geometry.Polyline`, optional
        The bottom boundary of the plate.
    top_polyline : :class:`compas.geometry.Polyline`, optional
        The top polyline of the plate (for lofted plates).
    bottom_polyline : :class:`compas.geometry.Polyline`, optional
        The bottom polyline of the plate (for lofted plates).
    mesh : :class:`compas.datastructures.Mesh`, optional
        Pre-computed mesh (overrides compute_elementgeometry if provided).
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the plate.
    features : list[:class:`PlateFeature`], optional
        The features of the plate.
    name : str, optional
        The name of the plate.

    Attributes
    ----------
    polygon : :class:`compas.geometry.Polygon`
        The base polygon of the plate.
    bottom : :class:`compas.geometry.Polygon`
        The bottom polygon of the plate.
    top : :class:`compas.geometry.Polygon`
        The top polygon of the plate.
    top_polyline : :class:`compas.geometry.Polyline`
        The top polyline of the plate.
    bottom_polyline : :class:`compas.geometry.Polyline`
        The bottom polyline of the plate.
    thickness : float
        The total offset thickness above and below the polygon.

    """

    @property
    def __data__(self) -> dict:
        # Don't serialize mesh - let it regenerate with winding correction
        return {
            "polygon": self.polygon,
            "thickness": self.thickness,
            "top": self.top,
            "bottom": self.bottom,
            "top_polyline": self._top_polyline,
            "bottom_polyline": self._bottom_polyline,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        polygon: Polygon = None,
        thickness: float = 0.1,
        top: Optional[Union[Polygon, Polyline]] = None,
        bottom: Optional[Union[Polygon, Polyline]] = None,
        top_polyline: Optional[Polyline] = None,
        bottom_polyline: Optional[Polyline] = None,
        mesh: Optional[Mesh] = None,
        transformation: Optional[Transformation] = None,
        features: Optional[list[PlateFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)

        self._mesh: Optional[Mesh] = mesh
        self.thickness: float = thickness

        # Handle polyline-based construction
        if top_polyline is not None and bottom_polyline is not None:
            # Create best-fit planes for both polylines
            # Use polygon centroid for closed polylines, bestfit centroid for open
            # bestfit_plane fails when all points are coplanar at constant Z,
            # so fall back to a horizontal plane in that case.
            def _safe_bestfit_plane(points):
                zvals = [p.z for p in points]
                if max(zvals) - min(zvals) < 1e-6:
                    centroid = Point(
                        sum(p.x for p in points) / len(points),
                        sum(p.y for p in points) / len(points),
                        zvals[0],
                    )
                    return (centroid, (0, 0, 1))
                return bestfit_plane(points)

            bottom_plane_data = _safe_bestfit_plane(bottom_polyline.points)
            top_plane_data = _safe_bestfit_plane(top_polyline.points)

            # Get centroid - use polygon centroid for closed polylines (more accurate)
            # Fall back to bestfit centroid if polygon has too few unique points
            def _safe_centroid(polyline, plane_data):
                if polyline.is_closed:
                    unique_pts = polyline.points[:-1]
                    if len(unique_pts) >= 3:
                        return Point(*Polygon(unique_pts).centroid)
                return Point(*plane_data[0])

            bottom_centroid = _safe_centroid(bottom_polyline, bottom_plane_data)
            top_centroid = _safe_centroid(top_polyline, top_plane_data)

            bottom_plane = Plane(bottom_centroid, Vector(*bottom_plane_data[1]))
            top_plane = Plane(top_centroid, Vector(*top_plane_data[1]))

            # Orient bottom plane normal to point towards top plane
            direction_to_top = Vector.from_start_end(bottom_plane.point, top_plane.point)
            if direction_to_top.dot(bottom_plane.normal) < 0:
                bottom_plane = Plane(bottom_plane.point, bottom_plane.normal * -1)

            # Orient top plane normal to point same direction as bottom (away from bottom)
            if bottom_plane.normal.dot(top_plane.normal) < 0:
                top_plane = Plane(top_plane.point, top_plane.normal * -1)

            # Check winding - if clockwise, flip both polylines to make CCW (consistent with normal)
            if _is_clockwise_on_plane(bottom_polyline, bottom_plane):
                bottom_polyline = _flip_polyline(bottom_polyline)
                top_polyline = _flip_polyline(top_polyline)

            self._top_polyline: Optional[Polyline] = top_polyline
            self._bottom_polyline: Optional[Polyline] = bottom_polyline
            self._bottom_plane: Plane = bottom_plane
            self._top_plane: Plane = top_plane

            # Convert polylines to polygons for compatibility
            self.top = Polygon(top_polyline.points[:-1]) if top_polyline.is_closed else None
            self.bottom = Polygon(bottom_polyline.points[:-1]) if bottom_polyline.is_closed else None
            self.polygon = self.bottom
            # Auto-generate mesh from polylines if not provided
            if self._mesh is None:
                self._mesh = PolylineLoft.to_mesh(bottom_polyline, top_polyline)
        else:
            self._top_polyline = None
            self._bottom_polyline = None
            self._bottom_plane = None
            self._top_plane = None

            # Handle polygon-based construction
            if polygon is None:
                polygon = Polygon.from_sides_and_radius_xy(4, 1.0)

            self.polygon: Polygon = polygon

            if bottom is not None:
                self.bottom: Polygon = bottom if isinstance(bottom, Polygon) else Polygon(bottom.points[:-1])
            else:
                normal: Vector = polygon.normal
                down: Vector = normal * (-0.5 * thickness)
                self.bottom = polygon.copy()
                for point in self.bottom.points:
                    point += down

            if top is not None:
                self.top: Polygon = top if isinstance(top, Polygon) else Polygon(top.points[:-1])
            else:
                normal: Vector = polygon.normal
                up: Vector = normal * (0.5 * thickness)
                self.top = polygon.copy()
                for point in self.top.points:
                    point += up

            # Auto-loft mesh from top/bottom if both were provided by the caller.
            if self._mesh is None and top is not None and bottom is not None:
                bottom_pl = Polyline(list(self.bottom.points) + [self.bottom.points[0]])
                top_pl = Polyline(list(self.top.points) + [self.top.points[0]])
                self._mesh = PlateElement.loft(bottom_pl, top_pl, cap=True, close=True)

    @property
    def top_polyline(self) -> Optional[Polyline]:
        """Get top polyline with transformation applied."""
        if self._top_polyline is None:
            return None
        if self.transformation:
            return self._top_polyline.transformed(self.transformation)
        return self._top_polyline

    @property
    def bottom_polyline(self) -> Optional[Polyline]:
        """Get bottom polyline with transformation applied."""
        if self._bottom_polyline is None:
            return None
        if self.transformation:
            return self._bottom_polyline.transformed(self.transformation)
        return self._bottom_polyline

    @property
    def base_frame(self) -> Frame:
        """Get the base frame from the bottom polyline, with transformation applied.

        The z-axis (normal) points from bottom to top polyline.
        The x-axis is aligned to the first edge of the bottom polyline.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at centroid of bottom polyline with oriented axes.
        """
        if self._bottom_plane is not None and self._bottom_polyline is not None:
            # Get first edge direction as x-axis
            xaxis = Vector.from_start_end(self._bottom_polyline.points[0], self._bottom_polyline.points[1]).unitized()
            zaxis = self._bottom_plane.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self._bottom_plane.point, xaxis, yaxis)
        else:
            # Fallback for polygon-based plates
            xaxis = Vector.from_start_end(self.bottom.points[0], self.bottom.points[1]).unitized()
            zaxis = self.bottom.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self.bottom.centroid, xaxis, yaxis)

        if self.transformation:
            frame.transform(self.transformation)
        return frame

    @property
    def top_frame(self) -> Frame:
        """Get the top frame from the top polyline, with transformation applied.

        The z-axis (normal) points same direction as base_frame (from bottom to top).
        The x-axis is aligned to the first edge of the top polyline.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at centroid of top polyline with oriented axes.
        """
        if self._top_plane is not None and self._top_polyline is not None:
            # Get first edge direction as x-axis
            xaxis = Vector.from_start_end(self._top_polyline.points[0], self._top_polyline.points[1]).unitized()
            zaxis = self._top_plane.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self._top_plane.point, xaxis, yaxis)
        else:
            # Fallback for polygon-based plates
            xaxis = Vector.from_start_end(self.top.points[0], self.top.points[1]).unitized()
            zaxis = self.top.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self.top.centroid, xaxis, yaxis)

        if self.transformation:
            frame.transform(self.transformation)
        return frame

    @staticmethod
    def _remove_duplicate_points(points, tolerance=1e-6):
        """Remove consecutive duplicate points and closing point if it matches first."""
        if not points:
            return points
        cleaned = [points[0]]
        for pt in points[1:]:
            if cleaned[-1].distance_to_point(pt) > tolerance:
                cleaned.append(pt)
        if len(cleaned) > 1 and cleaned[0].distance_to_point(cleaned[-1]) <= tolerance:
            cleaned = cleaned[:-1]
        return cleaned

    @staticmethod
    def _earclip_polygon(polygon):
        """Triangulate a planar polygon using the ear-clipping method.

        Parameters
        ----------
        polygon : :class:`compas.geometry.Polygon`

        Returns
        -------
        list[[int, int, int]]
        """
        frame = Frame.from_plane(Plane(polygon.points[0], polygon.normal))
        xform = Transformation.from_frame_to_frame(frame, Frame.worldXY())
        points = [point.transformed(xform) for point in polygon.points]

        sum_val = 0.0
        for p0, p1 in zip(points, points[1:] + [points[0]]):
            sum_val += (p1[0] - p0[0]) * (p1[1] + p0[1])

        if sum_val > 0.0:
            points.reverse()

        ear_cut = Earcut(points)
        triangles = ear_cut.triangulate()

        if sum_val > 0.0:
            n = len(points) - 1
            for i in range(len(triangles)):
                triangles[i] = [abs(triangles[i][j % 3] - n) for j in range(3)]
        return triangles

    @staticmethod
    def loft(polyline0, polyline1, cap=True, close=True):
        """Loft two polylines into a mesh with earclip-triangulated caps.

        Parameters
        ----------
        polyline0 : :class:`compas.geometry.Polyline`
            Bottom polyline.
        polyline1 : :class:`compas.geometry.Polyline`
            Top polyline.
        cap : bool
            If True, add triangulated caps at top and bottom.
        close : bool
            If True, close the side loop by connecting last point to first.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        pts0 = PlateElement._remove_duplicate_points(list(polyline0.points))
        pts1 = PlateElement._remove_duplicate_points(list(polyline1.points))

        polyline0 = Polyline(pts0)
        polyline1 = Polyline(pts1)

        vertices = polyline0.points + polyline1.points
        faces = []
        n0 = len(polyline0)

        num_faces = n0 if close else n0 - 1
        for i in range(num_faces):
            next_i = (i + 1) % n0
            faces.append([i, next_i, next_i + n0, i + n0])

        if cap:
            # Triangle and quad caps stay as a single n-gon face (no earclip).
            # Larger polygons fall back to earclip triangulation.
            if n0 <= 4:
                faces.append(list(range(n0 - 1, -1, -1)))
                faces.append(list(range(n0, 2 * n0)))
            else:
                bottom_triangles = PlateElement._earclip_polygon(Polygon(polyline0.points))
                for tri in bottom_triangles:
                    faces.append([tri[2], tri[1], tri[0]])

                top_triangles = PlateElement._earclip_polygon(Polygon(polyline1.points))
                for tri in top_triangles:
                    faces.append([tri[0] + n0, tri[1] + n0, tri[2] + n0])

        return Mesh.from_vertices_and_faces(vertices, faces)

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Compute the shape of the plate from the given polygons or return pre-computed mesh.

        Returns
        -------
        :class:`compas.datastructures.Mesh`

        """
        # Return pre-computed mesh if available
        if self._mesh is not None:
            return self._mesh

        bottom_pts = list(self.bottom.points)
        top_pts = list(self.top.points)

        # Ensure outward-facing winding: the vector from bottom centroid to
        # top centroid must align with the right-hand-rule normal of the
        # bottom loop. If it doesn't, reverse both loops in lockstep.
        b_centroid = Point(*self.bottom.centroid)
        t_centroid = Point(*self.top.centroid)
        up_dir = Vector.from_start_end(b_centroid, t_centroid)
        if up_dir.dot(self.bottom.normal) < 0:
            bottom_pts = list(reversed(bottom_pts))
            top_pts = list(reversed(top_pts))

        offset: int = len(bottom_pts)
        vertices: list[Point] = bottom_pts + top_pts  # type: ignore
        bottom: list[int] = list(range(offset))
        top: list[int] = [i + offset for i in bottom]
        faces: list[list[int]] = [bottom[::-1], top]
        for (a, b), (c, d) in zip(pairwise(bottom + bottom[:1]), pairwise(top + top[:1])):
            faces.append([a, b, d, c])
        mesh: Mesh = Mesh.from_vertices_and_faces(vertices, faces)
        return mesh

    # ------------------------------------------------------------------ #
    # Implementations of abstract methods
    # ------------------------------------------------------------------ #

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.aabb
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