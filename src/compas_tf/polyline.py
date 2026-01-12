"""Backwards compatibility - imports from geometry.py

Deprecated: Import directly from geometry instead:
    from compas_tf.geometry import PolylineOffset, PolylineCut, PolylineLoft, PlaneIntersect
"""

from compas_tf.geometry import (
    PolylineOffset,
    PolylineCut,
    PolylineLoft,
    PlaneIntersect,
)


# Legacy class for backwards compatibility
class Loft:
    """Deprecated: Use PolylineLoft, PolylineCut, PolylineOffset, PlaneIntersect instead."""

    # Loft operations
    loft_polylines = staticmethod(PolylineLoft.to_mesh)
    loft_multiple_polylines = staticmethod(PolylineLoft.multiple_to_mesh)
    loft_polylines_to_lines = staticmethod(PolylineLoft.to_lines)
    average_polyline = staticmethod(PolylineLoft.average)

    # Cut operations
    cut_polyline_plane = staticmethod(PolylineCut.cut_by_plane)
    cut_lines_by_plane = staticmethod(PolylineCut.cut_lines_by_plane)

    # Offset operations
    offset_polygon = staticmethod(PolylineOffset.offset_polygon)
    offset_polyline = staticmethod(PolylineOffset.offset_polyline)
    offset_polyline_xy = staticmethod(PolylineOffset.offset_polyline_xy)

    # Plane operations
    plane_rectangle = staticmethod(PlaneIntersect.plane_rectangle)
    intersect_consecutive_planes_with_xy = staticmethod(PlaneIntersect.intersect_consecutive_planes)
