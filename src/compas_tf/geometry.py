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
from compas.geometry import intersection_line_line
from compas.geometry import intersection_line_plane
from compas.geometry import intersection_plane_plane
from compas.geometry import intersection_plane_plane_plane
from compas.geometry import intersection_segment_plane


def _remove_duplicate_points(points, tolerance=1e-6):
    """Remove consecutive duplicate points and closing point if it matches first."""
    if not points:
        return points
    cleaned = [points[0]]
    for pt in points[1:]:
        if cleaned[-1].distance_to_point(pt) > tolerance:
            cleaned.append(pt)
    # Remove closing point if it matches the first point
    if len(cleaned) > 1 and cleaned[0].distance_to_point(cleaned[-1]) <= tolerance:
        cleaned = cleaned[:-1]
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


class LineOffset:
    """Offset operations for lines."""

    @staticmethod
    def offset_xy(line, distance):
        """Offset a line perpendicular to its direction in XY plane.

        Parameters
        ----------
        line : :class:`compas.geometry.Line`
            Line to offset.
        distance : float
            Offset distance (positive = left, negative = right).

        Returns
        -------
        :class:`compas.geometry.Line`
            Offset line.
        """
        perp = line.direction.cross(Vector.Zaxis()).unitized()
        return Line(Point(*line.start) + perp * distance, Point(*line.end) + perp * distance)

    @staticmethod
    def offset_pair_xy(line, distance):
        """Offset a line in both directions perpendicular to its direction in XY plane.

        Parameters
        ----------
        line : :class:`compas.geometry.Line`
            Line to offset.
        distance : float
            Offset distance (absolute value used for both sides).

        Returns
        -------
        tuple[:class:`compas.geometry.Line`, :class:`compas.geometry.Line`]
            (left_offset, right_offset) lines.
        """
        perp = line.direction.cross(Vector.Zaxis()).unitized()
        left = Line(Point(*line.start) + perp * distance, Point(*line.end) + perp * distance)
        right = Line(Point(*line.start) - perp * distance, Point(*line.end) - perp * distance)
        return left, right

    @staticmethod
    def offset_intersect(line0, line1, distance):
        """Offset line0 in both directions and intersect with line1.

        Creates a line connecting the intersection points of the two offset
        versions of line0 with line1.

        Parameters
        ----------
        line0 : :class:`compas.geometry.Line`
            Line to offset.
        line1 : :class:`compas.geometry.Line`
            Line to intersect with.
        distance : float
            Offset distance.

        Returns
        -------
        :class:`compas.geometry.Line`
            Line connecting the two intersection points.
        """
        left, right = LineOffset.offset_pair_xy(line0, distance)
        p0 = intersection_line_line(left, line1)[0]
        p1 = intersection_line_line(right, line1)[0]
        return Line(Point(*p0), Point(*p1))

    @staticmethod
    def divide(line, count):
        """Divide line into equal segments.

        Parameters
        ----------
        line : :class:`compas.geometry.Line`
            Line to divide.
        count : int
            Number of segments.

        Returns
        -------
        list[:class:`compas.geometry.Point`]
            List of count+1 points along the line.
        """
        return [line.point_at(i / count) for i in range(count + 1)]


class PolylineOffset:
    """Offset operations for polylines and polygons."""

    @staticmethod
    def offset_polygon_reciprocally(polygon: Polygon, offset: float) -> Polygon:
        """Offset a 2d polygon reciprocally by a given distance.

        Parameters
        ----------
        polygon : Polygon
            The input polygon to be offset.
        offset : float
            The distance by which to offset the polygon.

        Returns
        -------
        Polygon
            The offset polygon.
        """

        # 4 boundary planes
        planes = []
        planes_ = []
        for i in range(len(polygon.points)):
            p_curr = polygon.points[i]
            p_next = polygon.points[(i + 1) % len(polygon.points)]
            x_axis = p_next - p_curr
            translation_direction = Vector.Zaxis().cross(x_axis).unitized()
            plane = Plane(p_curr, -translation_direction)
            planes.append(plane)
            planes_.append(plane.offset(-offset))

        polygons = []

        n = len(polygon.points)
        for i in range(n):
            # edge0
            r0 = intersection_plane_plane_plane(polygon.plane, planes[i], planes_[(n + i - 1) % n])
            r1 = intersection_plane_plane_plane(polygon.plane, planes[i], planes[(i + 1) % n])
            # edge1
            r2 = intersection_plane_plane_plane(polygon.plane, planes_[i], planes[(i + 1) % n])
            r3 = intersection_plane_plane_plane(polygon.plane, planes_[i], planes_[(n + i - 1) % n])

            polygons.append(Polygon([r0, r1, r2, r3]))
        return polygons

    @staticmethod
    def offset_quarter_reciprocally(polygon: Polygon, offset: float) -> Polygon:
        """Offset a 2d polygon reciprocally by a given distance.

        Parameters
        ----------
        polygon : Polygon
            The input polygon to be offset.
        offset : float
            The distance by which to offset the polygon.

        Returns
        -------
        Polygon
            The offset polygon.
        """

        # 4 boundary planes
        planes = []
        planes_ = []
        for i in range(len(polygon.points)):
            p_curr = polygon.points[i]
            p_next = polygon.points[(i + 1) % len(polygon.points)]
            x_axis = p_next - p_curr
            translation_direction = Vector.Zaxis().cross(x_axis).unitized()

            plane = Plane(p_curr, -translation_direction)
            planes.append(plane)
            planes_.append(plane.offset(-offset))

        plane_start = Plane(polygon.points[0], polygon.points[1] - polygon.points[0])
        plane_end = Plane(polygon.points[-1], polygon.points[-2] - polygon.points[-1])
        polygons = []

        # Plate0

        r0 = intersection_plane_plane_plane(polygon.plane, planes[0], plane_start)
        r1 = intersection_plane_plane_plane(polygon.plane, planes[0], planes[1])
        r2 = intersection_plane_plane_plane(polygon.plane, planes_[0], planes[1])
        r3 = intersection_plane_plane_plane(polygon.plane, planes_[0], plane_start)
        polygons.append(Polygon([r0, r1, r2, r3]))

        # Plate1

        r0 = intersection_plane_plane_plane(polygon.plane, planes[1], planes_[0])
        r1 = intersection_plane_plane_plane(polygon.plane, planes[1], planes_[2])
        r2 = intersection_plane_plane_plane(polygon.plane, planes_[1], planes_[2])
        r3 = intersection_plane_plane_plane(polygon.plane, planes_[1], planes_[0])
        polygons.append(Polygon([r0, r1, r2, r3]))

        # Plate2
        r0 = intersection_plane_plane_plane(polygon.plane, planes[2], plane_end)
        r1 = intersection_plane_plane_plane(polygon.plane, planes[2], planes[1])
        r2 = intersection_plane_plane_plane(polygon.plane, planes_[2], planes[1])
        r3 = intersection_plane_plane_plane(polygon.plane, planes_[2], plane_end)
        polygons.append(Polygon([r0, r1, r2, r3]))

        # polygons = []
        # print(len(planes))

        # n = len(polygon.points)
        # for i in range(n):

        #     sign = -1 if i == 2 else 1

        #     # edge0
        #     r0 = intersection_plane_plane_plane(polygon.plane, planes[i], planes_[(n + i - 1) % n])
        #     r1 = intersection_plane_plane_plane(polygon.plane, planes[i], planes[(i + 1) % n])
        #     # edge1
        #     r2 = intersection_plane_plane_plane(polygon.plane, planes_[i], planes[(i + 1) % n])
        #     r3 = intersection_plane_plane_plane(polygon.plane, planes_[i], planes_[(n + i - 1) % n])

        #     polygons.append(Polygon([r0, r1, r2, r3]))
        return polygons

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
    def cut_by_plane(polyline, plane, flip=None):
        """Cut polyline by plane.

        By default the side containing the polyline's arc-length midpoint is kept.
        Pass ``flip=False``/``True`` to force the legacy fixed-side behavior
        (keep side opposite to the plane normal, or aligned with it).

        Parameters
        ----------
        polyline : :class:`compas.geometry.Polyline`
            Polyline to cut.
        plane : :class:`compas.geometry.Plane`
            Cutting plane.
        flip : bool, optional
            Manual override of which side to keep. ``None`` (default) picks the
            side containing the polyline's center.

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Cut polyline.
        """
        if len(polyline) < 2:
            return Polyline(list(polyline))

        if flip is None:
            center = polyline.point_at(0.5)
            keep_sign = 1.0 if plane.normal.dot(center - plane.point) >= 0 else -1.0
        else:
            keep_sign = -1.0 if not flip else 1.0

        def on_keep_side(pt):
            return plane.normal.dot(pt - plane.point) * keep_sign >= 0

        points = []
        for i in range(len(polyline) - 1):
            if on_keep_side(polyline[i]):
                points.append(polyline[i])

            line = Line(polyline[i], polyline[i + 1])
            floats = intersection_segment_plane(line, plane)
            if floats:
                points.append(Point(*floats))

        if on_keep_side(polyline[-1]):
            points.append(polyline[-1])

        # Drop consecutive near-duplicate points: a vertex lying on the plane gets
        # accepted by on_keep_side (>= 0) and also returned by intersection_segment_plane.
        tol = 1e-6
        deduped = []
        for p in points:
            if not deduped or deduped[-1].distance_to_point(p) > tol:
                deduped.append(p)

        return Polyline(deduped)

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


def _triangulate_cap(points):
    """Triangulate a cap polygon, falling back to a fan when earclip fails.

    ``earclip_polygon`` returns ``None`` for caps it cannot triangulate (e.g.
    slightly non-planar quads produced by tilted cut planes). For the convex
    quad/strip caps used here a simple fan triangulation is a safe fallback and
    keeps the lofted mesh closed.
    """
    n = len(points)
    if n < 3:
        return []
    try:
        triangles = earclip_polygon(Polygon(points))
    except Exception:
        triangles = None
    if not triangles:
        triangles = [[0, i, i + 1] for i in range(1, n - 1)]
    return triangles


def _orient_closed(mesh):
    """Repair a capped loft into a consistently-oriented closed solid.

    The side walls and the two earclip caps can be emitted with inconsistent
    winding (the top cap may wind the same way as the side walls instead of
    opposite), which leaves the mesh manifold but not watertight by half-edge
    accounting — every edge of one cap ring ends up "naked". When that happens,
    unify the face cycles and flip them if needed so the normals point outward
    (positive signed volume), which the boolean backends (CGAL / Manifold)
    require. Already-closed lofts are returned untouched, so well-formed plates
    (e.g. the ribs) are never disturbed.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`

    Returns
    -------
    :class:`compas.datastructures.Mesh`
    """
    if mesh.is_closed():
        return mesh
    try:
        mesh.unify_cycles()
    except Exception:
        return mesh
    if mesh.is_closed() and mesh.volume() < 0:
        mesh.flip_cycles()
    return mesh


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
            bottom_triangles = _triangulate_cap(list(reversed(pts0)))
            for tri in bottom_triangles:
                faces.append([n0 - 1 - tri[0], n0 - 1 - tri[1], n0 - 1 - tri[2]])
            top_triangles = _triangulate_cap(pts1)
            for tri in top_triangles:
                faces.append([tri[0] + n0, tri[1] + n0, tri[2] + n0])

        mesh = Mesh.from_vertices_and_faces(vertices, faces)
        if cap:
            mesh = _orient_closed(mesh)
        return mesh

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
            num_faces = n0 if close else n0 - 1
            for i in range(num_faces):
                next_i = (i + 1) % n0
                faces.append([offset0 + i, offset0 + next_i, offset1 + next_i, offset1 + i])

        if cap:
            first_polyline = cleaned_polylines[0]
            cap_pts0 = first_polyline.points
            bottom_triangles = _triangulate_cap(cap_pts0)
            for tri in bottom_triangles:
                faces.append([tri[2], tri[1], tri[0]])

            last_polyline = cleaned_polylines[-1]
            last_offset = offsets[-1]
            cap_pts1 = last_polyline.points
            top_triangles = _triangulate_cap(cap_pts1)
            for tri in top_triangles:
                faces.append([tri[0] + last_offset, tri[1] + last_offset, tri[2] + last_offset])

        mesh = Mesh.from_vertices_and_faces(vertices, faces)
        if cap:
            mesh = _orient_closed(mesh)
        return mesh

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
