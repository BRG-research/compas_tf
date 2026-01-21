from typing import Optional, Union

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas.geometry import Vector
from compas.geometry import bestfit_plane
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
        return {
            "polygon": self.polygon,
            "thickness": self.thickness,
            "top": self.top,
            "bottom": self.bottom,
            "top_polyline": self.top_polyline,
            "bottom_polyline": self.bottom_polyline,
            "mesh": self._mesh,
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
            bottom_plane_data = bestfit_plane(bottom_polyline.points)
            top_plane_data = bestfit_plane(top_polyline.points)

            # Get centroid - use polygon centroid for closed polylines (more accurate)
            if bottom_polyline.is_closed:
                bottom_centroid = Point(*Polygon(bottom_polyline.points[:-1]).centroid)
            else:
                bottom_centroid = Point(*bottom_plane_data[0])

            if top_polyline.is_closed:
                top_centroid = Point(*Polygon(top_polyline.points[:-1]).centroid)
            else:
                top_centroid = Point(*top_plane_data[0])

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

            self.top_polyline: Optional[Polyline] = top_polyline
            self.bottom_polyline: Optional[Polyline] = bottom_polyline
            self._bottom_plane: Plane = bottom_plane
            self._top_plane: Plane = top_plane

            # Convert polylines to polygons for compatibility
            self.top = Polygon(top_polyline.points[:-1]) if top_polyline.is_closed else None
            self.bottom = Polygon(bottom_polyline.points[:-1]) if bottom_polyline.is_closed else None
            self.polygon = self.bottom
            # Auto-generate mesh from polylines if not provided
            if self._mesh is None:
                self._mesh = PolylineLoft.to_mesh(top_polyline, bottom_polyline)
        else:
            self.top_polyline = None
            self.bottom_polyline = None
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
                down: Vector = normal * (0.0 * thickness)
                self.bottom = polygon.copy()
                for point in self.bottom.points:
                    point += down

            if top is not None:
                self.top: Polygon = top if isinstance(top, Polygon) else Polygon(top.points[:-1])
            else:
                normal: Vector = polygon.normal
                up: Vector = normal * (-1.0 * thickness)
                self.top = polygon.copy()
                for point in self.top.points:
                    point += up

    @property
    def base_plane(self) -> Plane:
        """Get the base plane from the bottom polyline, with transformation applied.

        The normal points from bottom to top polyline for polyline-based plates.

        Returns
        -------
        :class:`compas.geometry.Plane`
            Best-fit plane of the bottom polyline with normal pointing to top.
        """
        if self._bottom_plane is not None:
            plane = Plane(self._bottom_plane.point, self._bottom_plane.normal)
        else:
            plane = Plane(self.bottom.centroid, self.bottom.normal)

        if self.transformation:
            plane.transform(self.transformation)
        return plane

    @property
    def top_plane(self) -> Plane:
        """Get the top plane from the top polyline, with transformation applied.

        The normal points same direction as base_plane (from bottom to top).

        Returns
        -------
        :class:`compas.geometry.Plane`
            Best-fit plane of the top polyline with normal pointing away from bottom.
        """
        if self._top_plane is not None:
            plane = Plane(self._top_plane.point, self._top_plane.normal)
        else:
            plane = Plane(self.top.centroid, self.top.normal)

        if self.transformation:
            plane.transform(self.transformation)
        return plane

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Compute the shape of the plate from the given polygons or return pre-computed mesh.

        Returns
        -------
        :class:`compas.datastructures.Mesh`

        """
        # Return pre-computed mesh if available
        if self._mesh is not None:
            return self._mesh

        # Compute mesh from polygons
        offset: int = len(self.bottom)
        vertices: list[Point] = self.bottom.points + self.top.points  # type: ignore
        bottom: list[int] = list(range(offset))
        top: list[int] = [i + offset for i in bottom]
        faces: list[list[int]] = [bottom[::-1], top]
        for (a, b), (c, d) in zip(pairwise(bottom + bottom[:1]), pairwise(top + top[:1])):
            faces.append([a, b, d, c])
        mesh: Mesh = Mesh.from_vertices_and_faces(vertices, faces)
        return mesh

    # =============================================================================
    # Implementations of abstract methods
    # =============================================================================

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
