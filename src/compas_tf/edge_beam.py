from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature


class EdgeBeamFeature(Feature):
    pass


class EdgeBeamElement(Element):
    """Class representing an edge beam element.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry of the edge beam.
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the edge beam.
    features : list[:class:`EdgeBeamFeature`], optional
        The features of the edge beam.
    name : str, optional
        The name of the edge beam.

    Attributes
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry.
    """

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
        features: Optional[list[EdgeBeamFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.mesh = mesh if mesh else Mesh()

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
