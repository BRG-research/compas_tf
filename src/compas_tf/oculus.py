from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineLoft
from compas_tf.geometry import PolylineOffset


def _closed_polyline(points: list) -> Polyline:
    """Create a closed polyline from points."""
    return Polyline(list(points) + [points[0]])


def _rect_outline(p0, p1, z0, z1) -> Polyline:
    """Create rectangular outline from two points at two heights."""
    return Polyline([
        p0.translated([0, 0, z0]),
        p1.translated([0, 0, z0]),
        p1.translated([0, 0, z1]),
        p0.translated([0, 0, z1]),
        p0.translated([0, 0, z0]),
    ])


class OculusFeature(Feature):
    pass


class OculusElement(Element):
    """Central oculus beam element."""

    @property
    def __data__(self) -> dict:
        return {
            "mesh": self.mesh,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        mesh: Mesh = None,
        transformation: Optional[Transformation] = None,
        features: Optional[list[OculusFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.mesh = mesh if mesh else Mesh()

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self.mesh

    def _inflate_box(self, box: Box, inflate: float) -> Box:
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        return box

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        self._aabb = self._inflate_box(self.modelgeometry.aabb, inflate)
        return self._aabb

    def compute_obb(self, inflate: float = 1.0) -> Box:
        self._obb = self._inflate_box(self.modelgeometry.obb, inflate)
        return self._obb

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())

    @staticmethod
    def build(builder):
        """Build oculus beam geometry from FloorBuilder data.

        Parameters
        ----------
        builder : FloorBuilder
            The floor builder containing base geometry parameters.

        Returns
        -------
        list[OculusElement]
            The oculus beam elements.
        """
        # Precompute depths
        base_depth = -builder.height + builder.rise
        z_top, z_bot = 0, base_depth
        z_flange_top, z_flange_bot = base_depth, base_depth + builder.thick

        # Create offset polylines
        op = builder.oculus_points
        top = _closed_polyline(op)
        inner = _closed_polyline(PolylineOffset.offset_polygon(top, builder.thick).points)
        outer = _closed_polyline(PolylineOffset.offset_polygon(top, builder.thick * 2).points)

        # Build segment elements
        elements = []
        for i in range(len(top.points) - 1):
            pt, pi, po = top.points[i], inner.points[i], outer.points[i]
            pt_next, pi_next, po_next = top.points[i + 1], inner.points[i + 1], outer.points[i + 1]

            # Vertical wall segment
            wall_outer = _rect_outline(pt, pt_next, z_top, z_bot)
            wall_inner = _rect_outline(pi, pi_next, z_top, z_bot)
            elements.append(OculusElement(
                mesh=PolylineLoft.to_mesh(wall_outer, wall_inner),
                name=f"oculus_wall_{i}"
            ))

            # Bottom flange segment
            flange_inner = _rect_outline(pi, pi_next, z_flange_top, z_flange_bot)
            flange_outer = _rect_outline(po, po_next, z_flange_top, z_flange_bot)
            elements.append(OculusElement(
                mesh=PolylineLoft.to_mesh(flange_inner, flange_outer),
                name=f"oculus_flange_{i}"
            ))

        # Central ring
        ring_top = inner.translated([0, 0, z_flange_bot])
        ring_bot = inner.translated([0, 0, z_flange_bot + builder.thick])
        elements.append(OculusElement(
            mesh=PolylineLoft.to_mesh(ring_top, ring_bot),
            name="oculus_central"
        ))

        return elements
