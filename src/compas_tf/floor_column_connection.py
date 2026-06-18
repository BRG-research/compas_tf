from pathlib import Path
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature


class FloorColumnConnectionFeature(Feature):
    pass


class FloorColumnConnectionElement(Element):
    """Custom element wrapping the FloorColumnConnection mesh loaded from an OBJ file.

    The mesh is modelled in world coordinates aligned to the bottom-left corner
    column (``column_0``). To place it on the other columns, apply the same
    rotation about the global Z-axis that positions each column.

    Parameters
    ----------
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the connection element.
    features : list[:class:`FloorColumnConnectionFeature`], optional
        The features of the connection element.
    name : str, optional
        The name of the connection element.

    Attributes
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry loaded from the OBJ file.
    """

    DATA_DIR = Path(__file__).parent.parent.parent / "data" / "FloorColumnConnection"
    MESH_FILE = "FloorColumnConnection.obj"

    @property
    def __data__(self) -> dict:
        return {
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        transformation: Optional[Transformation] = None,
        features: Optional[list[FloorColumnConnectionFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.mesh = Mesh.from_obj(self.DATA_DIR / self.MESH_FILE)

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Return the connection mesh relative to the element frame.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        return self.mesh

    # =============================================================================
    # Implementations of abstract methods
    # =============================================================================

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

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())
