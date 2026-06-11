from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature


class PropFeature(Feature):
    pass


class PropElement(Element):
    """Class representing a diagonal prop/shoring element.

    The prop is oriented along its local Z-axis from z=0 (foot) to
    z=length (head).  The mesh is a single combined geometry with
    three sections:

    * **foot plate** — a wider base plate at the bottom.
    * **body** — the main strut.
    * **head plate** — a wider plate at the top.

    Parameters
    ----------
    width : float
        Body cross-section width in mm.
    depth : float
        Body cross-section depth in mm.
    length : float
        Total length of the prop in mm.
    plate_size : float
        Foot / head plate side length in mm.
    plate_thickness : float
        Foot / head plate thickness in mm.
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the prop element.
    features : list[:class:`PropFeature`], optional
        The features of the prop element.
    name : str, optional
        The name of the prop element.
    """

    @property
    def __data__(self) -> dict:
        return {
            "width": self.width,
            "depth": self.depth,
            "length": self.length,
            "plate_size": self.plate_size,
            "plate_thickness": self.plate_thickness,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        width: float = 60,
        depth: float = 60,
        length: float = 1000,
        plate_size: float = 140,
        plate_thickness: float = 12,
        transformation: Optional[Transformation] = None,
        features: Optional[list[PropFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.width = width
        self.depth = depth
        self.length = length
        self.plate_size = plate_size
        self.plate_thickness = plate_thickness

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self._build_mesh()

    def _build_mesh(self) -> Mesh:
        """Build combined foot-plate + body + head-plate mesh."""
        hw = self.width / 2.0
        hd = self.depth / 2.0
        hp = self.plate_size / 2.0
        pt = self.plate_thickness
        body_start = pt
        body_end = self.length - pt

        # 24 vertices: 8 per section (foot, body, head)
        vertices = [
            # foot plate  (0-7)
            [-hp, -hp, 0],  # 0
            [hp, -hp, 0],  # 1
            [hp, hp, 0],  # 2
            [-hp, hp, 0],  # 3
            [-hp, -hp, pt],  # 4
            [hp, -hp, pt],  # 5
            [hp, hp, pt],  # 6
            [-hp, hp, pt],  # 7
            # body  (8-15)
            [-hw, -hd, body_start],  # 8
            [hw, -hd, body_start],  # 9
            [hw, hd, body_start],  # 10
            [-hw, hd, body_start],  # 11
            [-hw, -hd, body_end],  # 12
            [hw, -hd, body_end],  # 13
            [hw, hd, body_end],  # 14
            [-hw, hd, body_end],  # 15
            # head plate  (16-23)
            [-hp, -hp, body_end],  # 16
            [hp, -hp, body_end],  # 17
            [hp, hp, body_end],  # 18
            [-hp, hp, body_end],  # 19
            [-hp, -hp, self.length],  # 20
            [hp, -hp, self.length],  # 21
            [hp, hp, self.length],  # 22
            [-hp, hp, self.length],  # 23
        ]

        faces = [
            # foot plate
            [0, 3, 2, 1],  # bottom
            [4, 5, 6, 7],  # top
            [0, 1, 5, 4],
            [1, 2, 6, 5],
            [2, 3, 7, 6],
            [3, 0, 4, 7],
            # body
            [8, 11, 10, 9],  # bottom
            [12, 13, 14, 15],  # top
            [8, 9, 13, 12],
            [9, 10, 14, 13],
            [10, 11, 15, 14],
            [11, 8, 12, 15],
            # head plate
            [16, 19, 18, 17],  # bottom
            [20, 21, 22, 23],  # top
            [16, 17, 21, 20],
            [17, 18, 22, 21],
            [18, 19, 23, 22],
            [19, 16, 20, 23],
        ]

        return Mesh.from_vertices_and_faces(vertices, faces)

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
