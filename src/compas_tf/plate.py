from typing import Optional
from typing import Union

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
    debug : list, optional
        Construction geometry (in the plate's local frame) for the viewer to
        draw, transformed to model space. Empty by default.

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
            "top_polyline": self._top_polyline,
            "bottom_polyline": self._bottom_polyline,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
            "debug": self.debug,
            "modelgeometry": self._modelgeometry,
        }

    @classmethod
    def __from_data__(cls, data: dict) -> "PlateElement":
        modelgeometry = data.pop("modelgeometry", None)
        plate = cls(**data)
        if modelgeometry is not None:
            plate._modelgeometry = modelgeometry
        return plate

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
        debug: Optional[list] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)

        self._mesh: Optional[Mesh] = mesh
        self.thickness: float = thickness
        # Optional construction geometry (polylines, parabolas, planes, ...) kept
        # in the element's local frame. The viewer draws whatever is in here,
        # transformed to model space - a per-element debug channel.
        self.debug: list = list(debug) if debug else []

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
    def _placement(self) -> Transformation:
        """The transform that places the plate's local geometry where it sits.

        When the plate is in a model this is its :attr:`modeltransformation`
        (own transformation + parent groups + model transformation) - the very
        transform used to build :attr:`modelgeometry`. Without a model the
        tree/parents are unavailable, so it falls back to the plate's own
        transformation. Applying it to the local outlines / base planes keeps
        them aligned with the plate's mesh wherever it is placed.
        """
        if self.model is not None:
            return self.modeltransformation
        return self.transformation or Transformation()

    @property
    def top_polyline(self) -> Optional[Polyline]:
        """Get the top polyline, placed in the plate's model frame."""
        if self._top_polyline is None:
            return None
        return self._top_polyline.transformed(self._placement)

    @property
    def bottom_polyline(self) -> Optional[Polyline]:
        """Get the bottom polyline, placed in the plate's model frame."""
        if self._bottom_polyline is None:
            return None
        return self._bottom_polyline.transformed(self._placement)

    def fabrication_polylines(self) -> tuple[Optional[Polyline], Optional[Polyline]]:
        """Return ``(bottom, top)`` polylines wound the SAME direction.

        For fabrication and lofting the two boundary polylines must be
        co-oriented - vertex ``i`` of the bottom corresponds to vertex ``i`` of
        the top - which is how they are stored. This is deliberately different
        from :meth:`_polygon_faces`, whose face normals point outward (the
        bottom face normal is flipped) for contact detection. Use this accessor
        when generating toolpaths or re-lofting; use the face normals for
        contacts.

        Returns
        -------
        tuple[Polyline | None, Polyline | None]
            The bottom and top polylines in model space, co-wound.
        """
        return self.bottom_polyline, self.top_polyline

    @property
    def computed_thickness(self) -> float:
        """Actual plate thickness, measured as the gap between the top and
        bottom surfaces.

        Plates built from top/bottom polylines keep the default ``thickness``
        attribute (0.1), so the real value is recovered from the geometry here.
        Falls back to ``self.thickness`` when no surfaces are available.
        """
        if self.top is not None and self.bottom is not None:
            return (Point(*self.top.centroid) - Point(*self.bottom.centroid)).length
        return self.thickness

    @property
    def face_polylines(self) -> dict[str, Union[Polyline, list[Polyline]]]:
        """Face outlines as closed polylines.

        Returns
        -------
        dict with keys:
            ``"bottom"`` — closed polyline of the bottom face
            ``"top"``    — closed polyline of the top face
            ``"walls"``  — list of closed polylines, one per side wall
        """
        bot = self.bottom_polyline
        top = self.top_polyline

        if bot is None:
            bot_pts = list(self.bottom.points)
            bot = Polyline(bot_pts + [bot_pts[0]])
        if top is None:
            top_pts = list(self.top.points)
            top = Polyline(top_pts + [top_pts[0]])

        bot_pts = list(bot.points[:-1])
        top_pts = list(top.points[:-1])
        n = len(bot_pts)

        walls = []
        for i in range(n):
            j = (i + 1) % n
            quad = [bot_pts[i], bot_pts[j], top_pts[j], top_pts[i]]
            walls.append(Polyline(quad + [quad[0]]))

        return {
            "bottom": bot,
            "top": top,
            "walls": walls,
        }

    @staticmethod
    def _longest_edge_direction(points) -> Vector:
        """Return the unitized direction of the longest edge in a point sequence.

        A parallelogram-shaped plate has two equal-length, anti-parallel long
        edges, so after a rotation their lengths differ only by float noise and a
        strict ``>`` would pick one or the other at random - flipping the
        direction 180 deg between otherwise-identical rotational copies (e.g. the
        4 oculus wedge plates). Keeping the FIRST edge within a relative
        tolerance of the maximum makes the choice stable across those copies, so
        their base frames stay consistently oriented.
        """
        best_len = -1.0
        best_vec = Vector.from_start_end(points[0], points[1])
        n = len(points)
        for i in range(n):
            j = (i + 1) % n
            v = Vector.from_start_end(points[i], points[j])
            length = v.length
            if length > best_len * (1.0 + 1e-6):
                best_len = length
                best_vec = v
        return best_vec.unitized()

    @property
    def base_frame(self) -> Frame:
        """Get the base frame from the bottom polyline, with transformation applied.

        The z-axis (normal) points from bottom to top polyline.
        The x-axis is aligned to the longest edge of the bottom polyline.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at centroid of bottom polyline with oriented axes.
        """
        if self._bottom_plane is not None and self._bottom_polyline is not None:
            pts = self._bottom_polyline.points[:-1] if self._bottom_polyline.is_closed else self._bottom_polyline.points
            xaxis = PlateElement._longest_edge_direction(pts)
            zaxis = self._bottom_plane.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self._bottom_plane.point, xaxis, yaxis)
        else:
            xaxis = PlateElement._longest_edge_direction(self.bottom.points)
            zaxis = self.bottom.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self.bottom.centroid, xaxis, yaxis)

        frame.transform(self._placement)
        return frame

    @property
    def top_frame(self) -> Frame:
        """Get the top frame from the top polyline, with transformation applied.

        The z-axis (normal) points same direction as base_frame (from bottom to top).
        The x-axis is aligned to the longest edge of the top polyline.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at centroid of top polyline with oriented axes.
        """
        if self._top_plane is not None and self._top_polyline is not None:
            pts = self._top_polyline.points[:-1] if self._top_polyline.is_closed else self._top_polyline.points
            xaxis = PlateElement._longest_edge_direction(pts)
            zaxis = self._top_plane.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self._top_plane.point, xaxis, yaxis)
        else:
            xaxis = PlateElement._longest_edge_direction(self.top.points)
            zaxis = self.top.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self.top.centroid, xaxis, yaxis)

        frame.transform(self._placement)
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
            bottom_poly = Polygon(list(reversed(pts0)))
            for tri in PlateElement._earclip_polygon(bottom_poly):
                faces.append([n0 - 1 - tri[0], n0 - 1 - tri[1], n0 - 1 - tri[2]])
            top_poly = Polygon(pts1)
            for tri in PlateElement._earclip_polygon(top_poly):
                faces.append([tri[0] + n0, tri[1] + n0, tri[2] + n0])

        return Mesh.from_vertices_and_faces(vertices, faces)

    def compute_elementgeometry(self, include_features=True) -> Mesh:
        """Compute the shape of the plate from the given polygons or pre-computed mesh.

        Any cut features (see :meth:`add_cutters`) are then applied as boolean
        differences and their coplanar faces merged, so the plate carries its
        connector pockets in its geometry.

        Returns
        -------
        :class:`compas.datastructures.Mesh`

        """
        if self._mesh is not None:
            mesh = self._mesh
        else:
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
            faces: list[list[int]] = []
            bottom_poly = Polygon(list(reversed(bottom_pts)))
            for tri in PlateElement._earclip_polygon(bottom_poly):
                faces.append([offset - 1 - tri[0], offset - 1 - tri[1], offset - 1 - tri[2]])
            top_poly = Polygon(top_pts)
            for tri in PlateElement._earclip_polygon(top_poly):
                faces.append([tri[0] + offset, tri[1] + offset, tri[2] + offset])
            for (a, b), (c, d) in zip(pairwise(bottom + bottom[:1]), pairwise(top + top[:1])):
                faces.append([a, b, d, c])
            mesh = Mesh.from_vertices_and_faces(vertices, faces)

        if include_features and self._features:
            from compas_tf.solid_difference_modifier import MeshCutFeature
            from compas_tf.solid_difference_modifier import merge_coplanar_faces

            # Gather every cutter solid (a MeshCutFeature stores its meshes; the
            # typed Cylinder/Prism cuts derive theirs from their parametric form)
            # and subtract them in ONE union-then-difference. Applying each
            # feature separately leaves T-junctions and a non-watertight result;
            # unioning the cutters first keeps the carved plate closed.
            cutters = []
            for feature in self._features:
                cutters.extend(getattr(feature, "meshes", None) or [])
            if cutters:
                mesh = MeshCutFeature(cutters).apply(mesh)
            mesh = merge_coplanar_faces(mesh)

        return mesh

    def get_features(self, types: Optional[list] = None, minimal: bool = False) -> list:
        """Return the plate's features, placed in the plate's model frame.

        Filter by type to pull out a specific kind of feature for fabrication or
        inspection, e.g. ``get_features(["MeshCutFeature"])`` to recover just the
        cutter solids.

        The features are stored in the plate's *local* frame (so they travel
        with the plate and survive serialization). This returns independent
        copies whose geometry has been moved into model coordinates by the
        plate's :attr:`modeltransformation` - the same transform used to build
        :attr:`modelgeometry` - so the returned cutters line up with the plate
        wherever it sits, with no transform needed at the call site. The stored
        features are left untouched.

        Parameters
        ----------
        types : list[str | type], optional
            Feature types to keep, given as class names (e.g.
            ``"MeshCutFeature"``) or the classes themselves. ``None`` (default)
            returns every feature, in application order.
        minimal : bool, optional
            If False (default), return the placed feature objects (whose
            ``meshes`` are the boolean cutter solids). If True, return the
            features' *minimal* parametric geometry instead - the axis ``Line``
            of every :class:`CylinderCutFeature` and the ``(bottom, top)``
            polylines of every :class:`PrismCutFeature`, as a flat list. Features
            with no minimal form (a plain mesh cut) are skipped.

        Returns
        -------
        list[:class:`Feature`] or list[:class:`compas.geometry.Geometry`]
        """
        features = self._features
        if types is not None:
            names = {t if isinstance(t, str) else t.__name__ for t in types}
            features = [feature for feature in features if type(feature).__name__ in names]

        # Place each feature the same way the outlines and base planes are placed
        # (see :attr:`_placement`), so they line up with modelgeometry. ``placed``
        # moves the parametric geometry for typed cuts and the meshes otherwise.
        transformation = self._placement
        placed = []
        for feature in features:
            if hasattr(feature, "placed"):
                placed.append(feature.placed(transformation))
            else:
                placed.append(feature.copy())

        if not minimal:
            return placed

        geometries = []
        for feature in placed:
            geometry = getattr(feature, "minimal", None)
            if geometry is None:
                continue
            if isinstance(geometry, (tuple, list)):
                geometries.extend(geometry)
            else:
                geometries.append(geometry)
        return geometries

    def add_feature(self, feature):
        """Append a feature and invalidate cached geometry so the cut recomputes.

        Mirrors :meth:`add_cutters` (which is sugar for a
        :class:`MeshCutFeature`), but takes any pre-built feature - e.g. a
        :class:`CylinderCutFeature` or :class:`PrismCutFeature`.

        Parameters
        ----------
        feature : :class:`compas_model.elements.element.Feature`

        Returns
        -------
        :class:`compas_model.elements.element.Feature`
            The feature that was appended.
        """
        self._features.append(feature)
        self._elementgeometry = None
        self._modelgeometry = None
        return feature

    def add_cutters(self, meshes: list, name: str = "plate_cutters"):
        """Store cutter solids as a difference feature carved into the plate.

        The cutters must be given in the plate's local frame. They are kept as a
        :class:`compas_tf.solid_difference_modifier.MeshCutFeature` - serialized
        in ``__data__`` and copied with the plate - so the pocket stays available
        for fabrication. Contact detection (:meth:`_polygon_faces`) is unaffected,
        as it works from the top/bottom polygons, not this mesh.

        Parameters
        ----------
        meshes : list[:class:`compas.datastructures.Mesh`]
            Closed cutter solids in the plate's local frame.
        name : str, optional
        """
        from compas_tf.solid_difference_modifier import MeshCutFeature

        feature = MeshCutFeature(meshes, name=name)
        self._features.append(feature)
        # Invalidate cached geometry (both element- and model-space) so the cut recomputes.
        self._elementgeometry = None
        self._modelgeometry = None
        return feature

    # ------------------------------------------------------------------ #
    # Implementations of abstract methods
    # ------------------------------------------------------------------ #

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

    def _polygon_faces(self, xform):
        """Return list of (points, normal, kind) for each polygon face in
        world space. ``kind`` is one of ``"top"`` (face from top_polyline),
        ``"bottom"`` (face from bottom_polyline), or ``"side"`` (one quad
        per perimeter edge connecting the two polylines).

        Every ``normal`` points **outward** (away from the plate body), like a
        closed solid: the top and bottom faces therefore point in opposite
        directions. The stored top/bottom polylines are co-wound (same
        orientation) for lofting, so the bottom polygon's raw normal points
        inward - it is flipped here. This outward convention is what contact
        detection relies on (two touching faces then have opposite normals).
        For the co-wound polylines needed by fabrication, use
        :meth:`fabrication_polylines` instead of these face normals.

        No triangulation, regardless of how the mesh was constructed.
        """
        from compas.geometry import centroid_points
        from compas.geometry import dot_vectors
        from compas.geometry import transform_points

        top_pts = [Point(*p) for p in transform_points([list(p) for p in self.top.points], xform)] if self.top is not None else None
        bot_pts = [Point(*p) for p in transform_points([list(p) for p in self.bottom.points], xform)] if self.bottom is not None else None

        tc = centroid_points([list(p) for p in top_pts]) if top_pts else None
        bc = centroid_points([list(p) for p in bot_pts]) if bot_pts else None

        def _away_from(normal, this_c, other_c):
            # Flip the normal so it points away from the opposite face's centroid.
            if other_c is None:
                return normal
            ref = [this_c[0] - other_c[0], this_c[1] - other_c[1], this_c[2] - other_c[2]]
            return normal * -1 if dot_vectors(normal, ref) < 0 else normal

        faces = []

        if top_pts is not None:
            faces.append((top_pts, _away_from(Polygon(top_pts).normal, tc, bc), "top"))

        if bot_pts is not None:
            faces.append((bot_pts, _away_from(Polygon(bot_pts).normal, bc, tc), "bottom"))

        if top_pts is not None and bot_pts is not None:
            # Perimeter is enforced CCW at construction, so the quad winding
            # [bot_i, bot_j, top_j, top_i] already yields outward side normals.
            n = min(len(top_pts), len(bot_pts))
            for i in range(n):
                j = (i + 1) % n
                quad = [bot_pts[i], bot_pts[j], top_pts[j], top_pts[i]]
                faces.append((quad, Polygon(quad).normal, "side"))

        return faces

    def compute_contacts(self, other, tolerance=1e-6, minimum_area=1e-1, contacttype=None, face_kinds=None):
        """Contact detection on true polygon faces — no triangulation.

        Parameters
        ----------
        face_kinds : set[str], optional
            Restrict to these face kinds, a subset of
            ``{"top", "bottom", "side"}``. Applies to BOTH sides of every
            pair. Default ``None`` = all kinds. For ``other`` being a
            non-PlateElement (Mesh source), all its mesh faces are tagged
            ``"side"`` for filtering purposes.
        """
        import inspect

        from compas_model.algorithms.contacts import is_opposite_normal_normal
        from compas_model.algorithms.contacts import polygon_polygon_overlap
        from compas_model.interactions import Contact

        if contacttype is None:
            contacttype = Contact

        # compas_model changed the polygon_polygon_overlap signature across
        # versions. The original (targeted here) takes per-polygon normals,
        # ``(a_pts, a_normal, b_pts, b_normal, tol, min_area)``, and returns
        # ``(points, frame, area)``. Newer releases take a single shared normal,
        # ``(a_pts, b_pts, normal, tol, min_area)``, and return
        # ``(points, frame, area, T_a, T_b)``. Detect which is installed so the
        # plate works against both; the first three return values match either way.
        _legacy_ppo = len(inspect.signature(polygon_polygon_overlap).parameters) >= 6

        a_faces = self._polygon_faces(self.modeltransformation)

        if isinstance(other, PlateElement):
            b_faces = other._polygon_faces(other.modeltransformation)
        elif isinstance(other.modelgeometry, Mesh):
            b_mesh = other.modelgeometry
            b_faces = [(b_mesh.face_coordinates(f), b_mesh.face_normal(f), "side") for f in b_mesh.faces()]
        else:
            raise NotImplementedError

        if face_kinds is not None:
            a_faces = [f for f in a_faces if f[2] in face_kinds]
            b_faces = [f for f in b_faces if f[2] in face_kinds]

        contacts = []
        for a_points, a_normal, _ in a_faces:
            for b_points, b_normal, _ in b_faces:
                # _polygon_faces emits outward normals (and the project's meshes
                # are closed solids), so two faces in real contact always have
                # opposite normals. This cheap dot/cross test skips the expensive
                # polygon_polygon_overlap (two 4x4 matrix inversions) for the
                # ~98% of face pairs that cannot touch - same result, far less work.
                if not is_opposite_normal_normal(a_normal, b_normal):
                    continue
                if _legacy_ppo:
                    result = polygon_polygon_overlap(a_points, a_normal, b_points, b_normal, tolerance, minimum_area)
                else:
                    result = polygon_polygon_overlap(a_points, b_points, a_normal, tolerance, minimum_area)
                if result:
                    points, frame, area = result[0], result[1], result[2]
                    contacts.append(contacttype(points=points, frame=frame, size=area))
        return contacts

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())
