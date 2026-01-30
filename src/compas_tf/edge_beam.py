from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Polyline
from compas.geometry import Projection
from compas.geometry import Reflection
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Vector
from compas.geometry import bestfit_plane
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineCut
from compas_tf.geometry import PolylineLoft


class EdgeBeamFeature(Feature):
    pass


class EdgeBeamElement(Element):
    """Edge beam at floor perimeter connecting adjacent quarters."""

    @property
    def __data__(self) -> dict:
        return {
            "mesh": self.mesh,
            "top_polyline": self._top_polyline,
            "bottom_polyline": self._bottom_polyline,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        mesh: Mesh = None,
        top_polyline: Optional[Polyline] = None,
        bottom_polyline: Optional[Polyline] = None,
        transformation: Optional[Transformation] = None,
        features: Optional[list[EdgeBeamFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.mesh = mesh if mesh else Mesh()
        self._top_polyline = top_polyline
        self._bottom_polyline = bottom_polyline
        self._bottom_plane = None

        # Compute base plane from polylines if available
        if bottom_polyline is not None and top_polyline is not None:
            # Get bestfit planes
            bottom_plane_data = bestfit_plane(bottom_polyline.points)
            top_plane_data = bestfit_plane(top_polyline.points)

            # Compute centroids
            if bottom_polyline.is_closed:
                bottom_centroid = Point(*Polygon(bottom_polyline.points[:-1]).centroid)
            else:
                bottom_centroid = Point(*bottom_plane_data[0])

            if top_polyline.is_closed:
                top_centroid = Point(*Polygon(top_polyline.points[:-1]).centroid)
            else:
                top_centroid = Point(*top_plane_data[0])

            # Orient normal to point from bottom to top
            normal = Vector(*bottom_plane_data[1])
            direction_to_top = Vector.from_start_end(bottom_centroid, top_centroid)
            if direction_to_top.dot(normal) < 0:
                normal = normal * -1

            self._bottom_plane = Plane(bottom_centroid, normal)

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

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self.mesh

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

    @property
    def base_frame(self) -> Frame:
        """Get the base frame from the bottom polyline.

        The z-axis (normal) points from bottom to top polyline.
        The x-axis is aligned to the first edge of the bottom polyline.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at centroid of bottom polyline with oriented axes.
        """
        if self._bottom_plane is not None and self._bottom_polyline is not None:
            xaxis = Vector.from_start_end(self._bottom_polyline.points[0], self._bottom_polyline.points[1]).unitized()
            zaxis = self._bottom_plane.normal
            yaxis = zaxis.cross(xaxis)
            frame = Frame(self._bottom_plane.point, xaxis, yaxis)
            if self.transformation:
                frame.transform(self.transformation)
            return frame
        # Fallback to centroid with Z-axis normal and X-axis
        centroid = Point(*self.modelgeometry.centroid())
        return Frame(centroid, Vector.Xaxis(), Vector.Yaxis())

    @staticmethod
    def build(builder):
        """Build single edge beam. Rotate the result yourself for other edges."""


        #############################################################################################
        # Transformation to origin
        #############################################################################################

        xform = Translation.from_vector([0, builder.size+builder.beam_w/2, 0])

        #############################################################################################
        # Builder
        #############################################################################################

        # Get builder data
        parabola = builder.boundary_parabolas[0]
        axis = builder.axes[0]
        cut_boundary = builder.cut_planes[0]
        cut_corner = builder.cut_planes[3]
        thick = builder.thick
        head_h = builder.head_h
        beam_w = builder.beam_w

        # Offset parabola
        normal = Vector.Zaxis().cross(axis.direction)
        proj = parabola.translated(normal * thick * -0.5)

        # Cut by planes
        cut = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj, cut_corner), cut_boundary)

        # Extend and cut by end plane
        # line = PolylineCut.cut_by_plane(Polyline([cut[0], cut[-1]]).extended([1000, 0]), builder.top_end_planes[0], flip=True)
        end_planes = builder.compute_cut_planes(scale=150, inclination=0)[3:6]
        end_plane = Plane(end_planes[0].point, -end_planes[0].normal)
        line = PolylineCut.cut_by_plane(Polyline([cut[0], cut[-1]]).extended([1000, 0]), end_plane, flip=True)


        # Build step profile: top (z=0) + mid (z=-head_h) + curve
        xy_proj = Projection.from_plane_and_direction(Plane.worldXY(), Vector.Zaxis())
        mid_proj = Projection.from_plane_and_direction(Plane([0, 0, -head_h], [0, 0, 1]), Vector.Zaxis())

        top = line.transformed(xy_proj)
        mid = PolylineCut.cut_by_plane(line.transformed(mid_proj), cut_corner, flip=True)

        poly = Polyline(list(reversed(top.points)) + mid.points + cut.points)
        poly.append(poly.points[0])

        # Merge with reflected copy
        pts0 = poly.points[1:-1]
        reflection = Reflection.from_plane(Plane.worldYZ())
        pts1 = Polyline(poly.transformed(reflection).points[1:-1])
        merged = Polyline(list(pts0) + list(reversed(pts1.points)))
        merged.append(merged.points[0])  # Close the polyline

        polygon = Polygon(merged.points[:-1])
        top_polyline = merged
        bottom_polyline = merged.translated(polygon.normal * beam_w)
        mesh = PolylineLoft.to_mesh(top_polyline, bottom_polyline)
        mesh.transform(xform)

        # Transform polylines
        top_polyline = top_polyline.transformed(xform)
        bottom_polyline = bottom_polyline.transformed(xform)

        return EdgeBeamElement(
            mesh=mesh,
            top_polyline=top_polyline,
            bottom_polyline=bottom_polyline,
            name="edge_beam"
        )
