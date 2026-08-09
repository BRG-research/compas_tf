"""Geometry operations for polylines.

Classes:
- PolylineOffset: Offset operations for polylines
- PolylineCut: Cutting operations for polylines
- BezierCurve: Quadratic Bezier sampling
- PolylineLoft: Lofting polylines into meshes
"""

from compas.datastructures import Mesh
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import earclip_polygon
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


class PolylineOffset:
    """Offset operations for polylines."""

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


class PolylineCut:
    """Cutting operations for polylines."""

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
