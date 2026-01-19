from pathlib import Path
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature


class SupportFeature(Feature):
    pass


class SupportElement(Element):
    """Class representing a column-base element constructed from an OBJ file.

    Connection type: Sherpa Power Base 150402_PB_L-140-C.
    Details: https://www.sherpa-connector.com/de/produkte/power-base/power-base-c/3391_306_shop_SHERPA-Power-Base-L-140-C.aspx?LNG=de
    Head plate: Ø 106 mm x 12 mm
    Base plate: 12 x 140 x 140 mm
    Base plate drilling: 4 x Ø 15 mm

    Parameters
    ----------
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the support element.
    features : list[:class:`SupportFeature`], optional
        The features of the support element.
    name : str, optional
        The name of the support element.

    Attributes
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry loaded from the OBJ file.
    top_polygon : :class:`compas.geometry.Polygon`
        The top polygon of the support (circular, Ø 106 mm).
    bottom_polygon : :class:`compas.geometry.Polygon`
        The bottom polygon of the support (square, 140 x 140 mm).
    """

    DATA_DIR = Path(__file__).parent.parent.parent / "data"
    MESH_FILE = "column_base_power_base_sherpa_150402_PB_L-140-C.obj"
    HEAD_PLATE_DIAMETER = 106  # mm
    BASE_PLATE_SIZE = 140  # mm
    HEIGHT = 150  # mm

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
        features: Optional[list[SupportFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)

        self.mesh = Mesh.from_obj(self.DATA_DIR / self.MESH_FILE)
        self.top_polygon = Polygon.from_sides_and_radius_xy(32, 106*0.5)
        self.top_polygon.translate([0, 0, 150])
        self.bottom_polygon = Polygon.from_rectangle(Point(70, 70, 0), 140, 140)

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Compute the shape of the plate from the given polygons.
        This shape is relative to the frame of the element.

        Returns
        -------
        :class:`compas.datastructures.Mesh`

        """
        return self.mesh

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