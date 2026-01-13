from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature


class ColumnHeadFeature(Feature):
    pass


class ColumnHeadElement(Element):
    """Class representing a column head element.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry of the column head.
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the column head.
    features : list[:class:`ColumnHeadFeature`], optional
        The features of the column head.
    name : str, optional
        The name of the column head.

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
        features: Optional[list[ColumnHeadFeature]] = None,
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
