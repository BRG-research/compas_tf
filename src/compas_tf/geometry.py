"""Geometry operations for polylines and planes.

Classes:
- PolylineOffset: Offset operations for polylines and polygons
- PolylineCut: Cutting and intersection operations
- PolylineLoft: Lofting polylines into meshes
- PlaneIntersect: Plane intersection operations
"""

from compas.datastructures import Mesh
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Vector
from compas.geometry import earclip_polygon
from compas.geometry import intersection_line_plane
from compas.geometry import intersection_plane_plane
from compas.geometry import intersection_plane_plane_plane
from compas.geometry import intersection_segment_plane


def _remove_duplicate_points(points, tolerance=1e-6):
    """Remove consecutive duplicate points from a list of points."""
    if not points:
        return points
    cleaned = [points[0]]
    for pt in points[1:]:
        if cleaned[-1].distance_to_point(pt) > tolerance:
            cleaned.append(pt)
    return cleaned


class PlaneIntersect:
    """Plane intersection and visualization operations."""

    @staticmethod
    def plane_rectangle(plane, scale=100):
        """Create a rectangle polygon and normal line from a plane.

        Parameters
        ----------
        plane : :class:`compas.geometry.Plane`
            The plane to create rectangle on.
        scale : float
            Half-size of the rectangle.

        Returns
        -------
        tuple[:class:`compas.geometry.Polygon`, :class:`compas.geometry.Line`]
            Rectangle polygon and normal line.
        """
        frame = Frame.from_plane(plane)
        p0 = frame.point - frame.xaxis * scale - frame.yaxis * scale
        p1 = frame.point + frame.xaxis * scale - frame.yaxis * scale
        p2 = frame.point + frame.xaxis * scale + frame.yaxis * scale
        p3 = frame.point - frame.xaxis * scale + frame.yaxis * scale
        polygon = Polygon([p0, p1, p2, p3])
        line = Line(plane.point, plane.point + plane.normal * scale)
        return polygon, line

    @staticmethod
    def intersect_consecutive_planes(planes, reference_plane=None):
        """Find intersection points of consecutive plane pairs with a reference plane.

        Parameters
        ----------
        planes : list[:class:`compas.geometry.Plane`]
            List of planes to intersect pairwise.
        reference_plane : :class:`compas.geometry.Plane`, optional
            Plane to intersect the resulting lines with. Defaults to world XY.

        Returns
        -------
        list[:class:`compas.geometry.Point`]
            Intersection points.
        """
        if reference_plane is None:
            reference_plane = Plane.worldXY()

        intersection_points = []
        for i in range(len(planes) - 1):
            result = intersection_plane_plane(planes[i], planes[i + 1])
            if result:
                line = Line(result[0], result[1])
                pt = intersection_line_plane(line, reference_plane)
                if pt:
                    intersection_points.append(pt)
        return intersection_points


class PolylineOffset:
    """Offset operations for polylines and polygons."""

    @staticmethod
    def offset_polygon(polygon, distance, baseplane=None):
        """Offset a polygon by a distance.

        Parameters
        ----------
        polygon : :class:`compas.geometry.Polygon` or list
            Polygon to offset.
        distance : float
            Offset distance (positive = outward).
        baseplane : :class:`compas.geometry.Plane`, optional
            Reference plane. Defaults to world XY.

        Returns
        -------
        :class:`compas.geometry.Polygon`
            Offset polygon.
        """
        if baseplane is None:
            baseplane = Plane.worldXY()

        planes = []
        for line in Polygon(polygon).lines:
            zaxis = Vector.Zaxis().cross(line.direction)
            zaxis.unitize()
            planes.append(Plane(zaxis * distance + line.midpoint, zaxis))

        points = []
        for i in range(len(planes)):
            a = planes[(len(planes) + i - 1) % len(planes)]
            b = planes[i]
            c = baseplane
            result = intersection_plane_plane_plane(a, b, c)
            if not result:
                raise Exception(f"No intersection at offset_polygon. Index: {i}")
            points.append(result)

        return Polygon(points)

    @staticmethod
    def offset_polyline(polyline, distance, baseplane=None):
        """Offset a polyline by a distance in 3D.

        Parameters
        ----------
        polyline : :class:`compas.geometry.Polyline`
            Polyline to offset.
        distance : float
            Offset distance.
        baseplane : :class:`compas.geometry.Plane`, optional
            Reference plane for offset direction. Defaults to world XY.

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Offset polyline.
        """
        if baseplane is None:
            baseplane = Plane.worldXY()

        # End planes
        start_plane = Plane(polyline[0], polyline[1] - polyline[0])
        end_plane = Plane(polyline[-1], polyline[-2] - polyline[-1])

        # Planes for intersection
        planes = [start_plane]
        for line in polyline.lines:
            xaxis = line.direction
            yaxis = baseplane.normal.cross(xaxis)
            zaxis = xaxis.cross(yaxis)
            planes.append(Plane(line.midpoint, zaxis).offset(distance))
        planes.append(end_plane)

        # Base plane
        baseplane = Plane(polyline[0], baseplane.normal.cross(polyline[-1] - polyline[0]))

        # Perform offset by plane intersection
        points = []
        for i in range(len(planes) - 1):
            a = planes[i]
            b = planes[i + 1]
            c = baseplane
            result = intersection_plane_plane_plane(a, b, c)
            if not result:
                raise Exception(f"No intersection at offset_polyline. Index: {i}")
            points.append(result)

        return Polyline(points)

    @staticmethod
    def offset_polyline_xy(polyline, distance):
        """Offset a polyline in the XY plane.

        Parameters
        ----------
        polyline : :class:`compas.geometry.Polyline`
            Polyline to offset.
        distance : float
            Offset distance.

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Offset polyline.
        """
        # End planes (perpendicular to first/last segment)
        start_plane = Plane(polyline[0], polyline[1] - polyline[0])
        end_plane = Plane(polyline[-1], polyline[-2] - polyline[-1])

        # Offset planes for each segment
        planes = [start_plane]
        for line in polyline.lines:
            zaxis = Vector.Zaxis().cross(line.direction)
            zaxis.unitize()
            planes.append(Plane(zaxis * distance + line.midpoint, zaxis))
        planes.append(end_plane)

        # XY baseplane through first point
        baseplane = Plane(polyline[0], Vector.Zaxis())

        # Perform offset by plane intersection
        points = []
        for i in range(len(planes) - 1):
            a = planes[i]
            b = planes[i + 1]
            c = baseplane
            result = intersection_plane_plane_plane(a, b, c)
            if not result:
                raise Exception(f"No intersection at offset_polyline_xy. Index: {i}")
            points.append(result)

        return Polyline(points)


class PolylineCut:
    """Cutting and intersection operations for polylines."""

    @staticmethod
    def cut_by_plane(polyline, plane, flip=False):
        """Cut polyline by plane, keeping points on one side.

        Parameters
        ----------
        polyline : :class:`compas.geometry.Polyline`
            Polyline to cut.
        plane : :class:`compas.geometry.Plane`
            Cutting plane.
        flip : bool
            If True, keep points on opposite side of plane normal.

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Cut polyline.
        """
        points = []
        normal = plane.normal if not flip else -plane.normal

        for i in range(len(polyline) - 1):
            line = Line(polyline[i], polyline[i + 1])

            vector = plane.point - polyline[i]
            if normal.dot(vector) < 0:
                points.append(polyline[i])

            floats = intersection_segment_plane(line, plane)
            if floats:
                points.append(Point(*floats))

        # Check if last point should be included
        vector = plane.point - polyline[-1]
        if normal.dot(vector) < 0:
            points.append(polyline[-1])

        return Polyline(points)

    @staticmethod
    def cut_lines_by_plane(lines, plane):
        """Intersect multiple lines with a plane to create a polyline.

        Parameters
        ----------
        lines : list[:class:`compas.geometry.Line`]
            Lines to intersect.
        plane : :class:`compas.geometry.Plane`
            Intersection plane.

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Polyline of intersection points.
        """
        points = []
        for line in lines:
            floats = intersection_line_plane(line, plane)
            if floats:
                points.append(Point(*floats))
        return Polyline(points)


class BezierCurve:
    """Bezier curve generation utilities."""

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


class PolylineLoft:
    """Lofting polylines into meshes."""

    @staticmethod
    def to_mesh(polyline0, polyline1, cap=True, close=True):
        """Loft two polylines into a mesh.

        Parameters
        ----------
        polyline0 : :class:`compas.geometry.Polyline`
            First polyline (bottom).
        polyline1 : :class:`compas.geometry.Polyline`
            Second polyline (top).
        cap : bool
            If True, add triangulated caps at top and bottom.
        close : bool
            If True, close the polylines by connecting last point to first.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            Lofted mesh.
        """
        pts0 = _remove_duplicate_points(list(polyline0.points))
        pts1 = _remove_duplicate_points(list(polyline1.points))

        if close:
            if pts0[0].distance_to_point(pts0[-1]) > 1e-6:
                pts0.append(pts0[0])
            if pts1[0].distance_to_point(pts1[-1]) > 1e-6:
                pts1.append(pts1[0])

        polyline0 = Polyline(pts0)
        polyline1 = Polyline(pts1)

        vertices = polyline0.points + polyline1.points
        faces = []
        n0 = len(polyline0)

        for i in range(n0 - 1):
            faces.append([i, i + n0, i + n0 + 1, i + 1])

        if cap:
            cap_pts0 = polyline0.points[:-1] if close else polyline0.points
            cap_pts1 = polyline1.points[:-1] if close else polyline1.points

            bottom_triangles = earclip_polygon(Polygon(cap_pts0))
            for tri in bottom_triangles:
                faces.append([tri[2], tri[1], tri[0]])

            top_triangles = earclip_polygon(Polygon(cap_pts1))
            for tri in top_triangles:
                faces.append([tri[0] + n0, tri[1] + n0, tri[2] + n0])

        return Mesh.from_vertices_and_faces(vertices, faces)

    @staticmethod
    def multiple_to_mesh(polylines, cap=True, close=True):
        """Loft multiple polylines into a single mesh.

        Parameters
        ----------
        polylines : list[:class:`compas.geometry.Polyline`]
            List of polylines to loft sequentially.
        cap : bool
            If True, add triangulated caps at first and last polyline.
        close : bool
            If True, close the polylines by connecting last point to first.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            Lofted mesh.
        """
        if len(polylines) < 2:
            return None

        cleaned_polylines = []
        for polyline in polylines:
            pts = _remove_duplicate_points(list(polyline.points))
            if close and pts[0].distance_to_point(pts[-1]) > 1e-6:
                pts.append(pts[0])
            cleaned_polylines.append(Polyline(pts))

        vertices = []
        offsets = []
        for polyline in cleaned_polylines:
            offsets.append(len(vertices))
            vertices.extend(polyline.points)

        faces = []

        for p in range(len(cleaned_polylines) - 1):
            n0 = len(cleaned_polylines[p])
            offset0 = offsets[p]
            offset1 = offsets[p + 1]
            for i in range(n0 - 1):
                faces.append([offset0 + i, offset1 + i, offset1 + i + 1, offset0 + i + 1])

        if cap:
            first_polyline = cleaned_polylines[0]
            cap_pts0 = first_polyline.points[:-1] if close else first_polyline.points
            bottom_triangles = earclip_polygon(Polygon(cap_pts0))
            for tri in bottom_triangles:
                faces.append([tri[2], tri[1], tri[0]])

            last_polyline = cleaned_polylines[-1]
            last_offset = offsets[-1]
            cap_pts1 = last_polyline.points[:-1] if close else last_polyline.points
            top_triangles = earclip_polygon(Polygon(cap_pts1))
            for tri in top_triangles:
                faces.append([tri[0] + last_offset, tri[1] + last_offset, tri[2] + last_offset])

        return Mesh.from_vertices_and_faces(vertices, faces)

    @staticmethod
    def to_lines(polyline0, polyline1):
        """Create lines connecting corresponding points of two polylines.

        Parameters
        ----------
        polyline0 : :class:`compas.geometry.Polyline`
            First polyline.
        polyline1 : :class:`compas.geometry.Polyline`
            Second polyline (must have same number of points).

        Returns
        -------
        list[:class:`compas.geometry.Line`]
            Connecting lines.
        """
        lines = []
        for i in range(len(polyline0)):
            lines.append(Line(polyline0[i], polyline1[i]))
        return lines

    @staticmethod
    def average(polyline0, polyline1):
        """Create a polyline by averaging corresponding points of two polylines.

        Parameters
        ----------
        polyline0 : :class:`compas.geometry.Polyline`
            First polyline.
        polyline1 : :class:`compas.geometry.Polyline`
            Second polyline (must have same number of points).

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Averaged polyline.
        """
        points = []
        for i in range(len(polyline0)):
            points.append((polyline0[i] + polyline1[i]) / 2)
        return Polyline(points)
