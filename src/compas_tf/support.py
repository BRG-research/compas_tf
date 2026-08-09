from pathlib import Path
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Polygon
from compas.geometry import Transformation
from compas.geometry import Vector

from compas_tf.element import TFElement
from compas_tf.element import TFFeature
from compas_tf.element import baked


class SupportFeature(TFFeature):
    pass


class SupportElement(TFElement):
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

    # Package data, NOT the repo's data/ folder: this mesh is read in
    # __init__, so every deserialization of a model containing a support
    # needs it. Pointing outside the package made an installed compas_tf
    # resolve it to <site-packages>/../../data and fail with FileNotFoundError.
    DATA_DIR = Path(__file__).parent / "data"
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
            **self._baked_data(),
        }

    def __init__(
        self,
        transformation: Optional[Transformation] = None,
        features: Optional[list[SupportFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)

        self.mesh = Mesh.from_obj(self.DATA_DIR / self.MESH_FILE)
        self.top_polygon = Polygon.from_sides_and_radius_xy(32, 106 * 0.5)
        self.top_polygon.translate([0, 0, 150])
        self.bottom_polygon = Polygon.from_rectangle(Point(70, 70, 0), 140, 140)

    @baked
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

    @property
    def base_frame(self) -> Frame:
        """Get the base frame at the bottom center of the mesh, with transformation applied.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at the bottom center of the mesh with Z-axis pointing up.
        """
        # Get mesh bounding box to find bottom center
        aabb = self.mesh.aabb()
        bottom_center = Point((aabb.xmin + aabb.xmax) / 2, (aabb.ymin + aabb.ymax) / 2, aabb.zmin)
        frame = Frame(bottom_center, Vector.Xaxis(), Vector.Yaxis())
        if self.transformation:
            frame.transform(self.transformation)
        return frame
