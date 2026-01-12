from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Plane
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

# from compas_model.interactions import BooleanModifier
# from compas_model.interactions import Modifier
# from compas_model.interactions import SlicerModifier


class ColumnHeadFeature(Feature):
    pass


class ColumnHeadElement(Element):
    """Class representing a column head element.
    
    Parameters
    ----------
    width : float
        The width of the beam.
    depth : float
        The depth of the beam.
    length : float
        The length of the beam.
    transformation : Optional[:class:`compas.geometry.Transformation`]
        Transformation applied to the beam.
    features : Optional[list[:class:`compas_model.features.BeamFeature`]]
        Features of the beam.
    name : Optional[str]
        If no name is defined, the class name is given.

    Attributes
    ----------
    box : :class:`compas.geometry.Box`
        The box geometry of the beam.
    width : float
        The width of the beam.
    depth : float
        The depth of the beam.
    length : float
        The length of the beam.
    center_line : :class:`compas.geometry.Line`
        Line axis of the beam.
    """

    @property
    def __data__(self) -> dict:
        return {
            "width": self.box.xsize,
            "depth": self.box.ysize,
            "length": self.box.zsize,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        width: float = 0.1,
        depth: float = 0.2,
        length: float = 3.0,
        transformation: Optional[Transformation] = None,
        features: Optional[list[ColumnHeadFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self._box = Box.from_width_height_depth(width, length, depth)

        self._box.frame = Frame(point=[0,0, self._box.zsize / 2], xaxis=[1, 0, 0], yaxis=[0, 1, 0])

    @property
    def length_plane0() -> Plane:
        plane = Plane.worldYZ().offset(self.width*0.5)
        plane.transform(self.transformation)
        return plane

        

    @property
    def box(self) -> Box:
        return self._box

    @property
    def width(self) -> float:
        return self.box.xsize

    @width.setter
    def width(self, width: float):
        self.box.xsize = width

    @property
    def depth(self) -> float:
        return self.box.ysize

    @depth.setter
    def depth(self, depth: float):
        self.box.ysize = depth

    @property
    def length(self) -> float:
        return self.box.zsize

    @length.setter
    def length(self, length: float):
        self.box.zsize = length
        self.box.frame = Frame(point=[0, 0, self.box.zsize / 2], xaxis=[1, 0, 0], yaxis=[0, 1, 0])

    @property
    def center_line(self) -> Line:
        return Line([0, 0, 0], [0, 0, self.box.height])

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        """Compute the mesh shape from a box.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        return self.box.to_mesh()

    def extend(self, distance: float) -> None:
        """Extend the beam.

        Parameters
        ----------
        distance : float
            The distance to extend the beam.
        """
        self._box.zsize = self.length + distance * 2
        self._box.frame = Frame(point=[0, 0, self.box.zsize / 2 - distance], xaxis=[1, 0, 0], yaxis=[0, 1, 0])

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        """Compute the axis-aligned bounding box of the element.

        Parameters
        ----------
        inflate : float, optional
            The inflation factor of the bounding box.

        Returns
        -------
        :class:`compas.geometry.Box`
            The axis-aligned bounding box.
        """
        box = self.box.transformed(self.modeltransformation)
        box = Box.from_bounding_box(box.points)
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        """Compute the oriented bounding box of the element.

        Parameters
        ----------
        inflate : float, optional
            The inflation factor of the bounding box.

        Returns
        -------
        :class:`compas.geometry.Box`
            The oriented bounding box.
        """
        box = self.box.transformed(self.modeltransformation)
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_collision_mesh(self, inflate: float = 1.0) -> Mesh:
        """Compute the collision mesh of the element.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            The collision mesh.
        """
        raise NotImplementedError

    def compute_point(self) -> Point:
        """Compute the reference point of the beam from the centroid of its geometry.

        Returns
        -------
        :class:`compas.geometry.Point`

        """
        return Point(*self.modelgeometry.centroid())

    # =============================================================================
    # Custom implementations
    # =============================================================================
    def get_long_lines(self):

        line0 = Line(self.box.corner(0), self.box.corner(4)) # Bottom
        line1 = Line(self.box.corner(1), self.box.corner(5)) # Top
        line2 = Line(self.box.corner(2), self.box.corner(6)) # Top
        line3 = Line(self.box.corner(3), self.box.corner(7)) # Bottom
        lines = [line2, line1, line3, line0]
        for line in lines:
            line.transform(self.transformation)
        return lines

    