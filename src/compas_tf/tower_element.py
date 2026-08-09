import pathlib
from typing import Optional

from compas import json_load
from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Transformation

from compas_tf.element import TFElement
from compas_tf.element import TFFeature
from compas_tf.element import baked


class TowerElementFeature(TFFeature):
    pass


class TowerElement(TFElement):
    """A single tower floor element loaded from a JSON dataset file.

    The element contains one mesh oriented relative to a world-XY base frame.
    A transformation places it in the scene.

    Parameters
    ----------
    dataset : str, optional
        Filename (relative to ``data/TowerElement/``) of the JSON data file.
    transformation : :class:`compas.geometry.Transformation`, optional
        Transformation applied when placing the element in the scene.
    features : list[:class:`TowerElementFeature`], optional
        Features of the element.
    name : str, optional
        Name of the element.
    """

    _json_cache: dict = {}
    _mesh_cache: dict = {}

    floor_tower_0 = "floor_tower_0.json"

    @classmethod
    def _load(cls, dataset: str) -> dict:
        if dataset not in cls._json_cache:
            here = pathlib.Path(__file__).parent.parent.parent
            cls._json_cache[dataset] = json_load(here / "data" / "TowerElement" / dataset)
        return cls._json_cache[dataset]

    @classmethod
    def clear_cache(cls):
        cls._json_cache.clear()
        cls._mesh_cache.clear()

    @property
    def __data__(self) -> dict:
        return {
            "dataset": self.dataset,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
            **self._baked_data(),
        }

    def __init__(
        self,
        dataset: str = floor_tower_0,
        transformation: Optional[Transformation] = None,
        features: Optional[list] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.dataset = dataset
        data = self._load(dataset)
        self.base_frame: Frame = data["frames"][0]
        if dataset not in self._mesh_cache:
            self._mesh_cache[dataset] = data["meshes"][0]
        self.geometry: Mesh = self._mesh_cache[dataset].copy()

    @baked
    def compute_elementgeometry(self, include_features: bool = False) -> Mesh:
        if self.transformation is not None:
            self.base_frame.transform(self.transformation)
        return self.geometry

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self.geometry.aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self.geometry.obb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        return box

    def compute_point(self) -> Point:
        return Point(*self.geometry.centroid())

    def compute_collision_mesh(self, inflate: float = 1.0) -> Mesh:
        return self.geometry.copy()

    def compute_surface_mesh(self, meshsize_min=None, meshsize_max=None) -> Mesh:
        return self.geometry.copy()

    def compute_volumetric_mesh(self, meshsize_min=None, meshsize_max=None):
        raise NotImplementedError
