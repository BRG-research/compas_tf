from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.elements import Element
from compas_model.elements.element import Feature


class ColumnFeature(Feature):
    """Feature that unions a set of capitel boxes onto the column base geometry.

    Parameters
    ----------
    boxes : list[:class:`compas.geometry.Box`]
        The capitel boxes to union onto the column box.
    name : str, optional
        The name of the feature.
    """

    @property
    def __data__(self) -> dict:
        return {
            "boxes": self.boxes,
            "name": self.name,
        }

    def __init__(self, boxes: list = None, name: Optional[str] = None):
        super().__init__(name=name)
        self.boxes = [box.copy() for box in (boxes or [])]

    def apply(self, shape: Mesh) -> Mesh:
        """Boolean-union the capitel boxes onto the column base mesh.

        Parameters
        ----------
        shape : :class:`compas.datastructures.Mesh`
            The base geometry (column box mesh) of the host element.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        if not self.boxes:
            return shape

        from compas_manifold.booleans import boolean_chain

        meshes = [shape.to_vertices_and_faces(True)]
        for box in self.boxes:
            meshes.append(box.to_mesh().to_vertices_and_faces(True))
        operations = ["union"] * (len(meshes) - 1)
        result = boolean_chain(meshes, operations)
        return Mesh.from_vertices_and_faces(result[0], result[1])


class ColumnCutFeature(Feature):
    """Feature that boolean-differences cutter solids out of the column geometry.

    Stored on the column (in its local frame), so the cut travels with the
    element through copy/serialization and the cutter solids stay available for
    fabrication. The capitel (a :class:`ColumnFeature`) is applied first, so the
    cutters carve the already-formed column head.

    Parameters
    ----------
    meshes : list[:class:`compas.datastructures.Mesh`]
        The closed cutter solids to subtract, in the column's local frame.
    name : str, optional
        The name of the feature.
    """

    @property
    def __data__(self) -> dict:
        return {
            "meshes": self.meshes,
            "name": self.name,
        }

    def __init__(self, meshes: list = None, name: Optional[str] = None):
        super().__init__(name=name)
        self.meshes = [mesh.copy() for mesh in (meshes or [])]

    def apply(self, shape: Mesh) -> Mesh:
        """Boolean-subtract the cutter solids from the column mesh.

        The cutters share the wedge-fan planes, so they are unioned into a single
        solid first and then subtracted in one operation - subtracting them one
        by one makes the kernel re-process the repeated coplanar faces.

        Parameters
        ----------
        shape : :class:`compas.datastructures.Mesh`
            The host geometry (column box + capitel) to carve.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        if not self.meshes:
            return shape

        from compas_manifold.booleans import boolean_chain

        from compas_tf.solid_difference_modifier import SolidDifferenceModifier

        cutters = [mesh.to_vertices_and_faces(True) for mesh in self.meshes]
        if len(cutters) > 1:
            unioned = boolean_chain(cutters, ["union"] * (len(cutters) - 1))
            cutters = [unioned]

        result = boolean_chain([shape.to_vertices_and_faces(True), cutters[0]], ["difference"])
        carved = Mesh.from_vertices_and_faces(result[0], result[1])
        # A difference can split the result into disjoint solids (the carved head
        # plus thin slivers); keep only the main body, using the same rule the
        # boolean modifiers apply.
        return SolidDifferenceModifier.largest_piece(carved)


class ColumnElement(Element):
    """Class representing a column element with a square section, constructed from the WorldXY Frame.

    The column is defined in its local frame, where the height corresponds to the
    Z-Axis, the depth to the Y-Axis, and the width to the X-Axis. By default, the
    local frame is set to the WorldXY frame.

    Parameters
    ----------
    width : float
        The width of the column.
    depth : float
        The depth of the column.
    height : float
        The height of the column.
    transformation : Optional[:class:`compas.geometry.Transformation`]
        Transformation applied to the column.
    features : Optional[list[:class:`ColumnFeature`]]
        Features of the column.
    name : Optional[str]
        If no name is defined, the class name is given.
    capitel_width : float
        The width of the capitel (column head) added as a feature.
    capitel_height : float
        The height of the capitel (column head) added as a feature.

    Attributes
    ----------
    width : float
        The width of the column.
    depth : float
        The depth of the column.
    height : float
        The height of the column.
    box : :class:`compas.geometry.Box`
        The base box geometry of the column.
    center_line : :class:`compas.geometry.Line`
        Line axis of the column.
    """

    @property
    def __data__(self) -> dict:
        return {
            "width": self.box.xsize,
            "depth": self.box.ysize,
            "height": self.box.zsize,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
            "capitel_width": self.capitel_width,
            "capitel_height": self.capitel_height,
        }

    def __init__(
        self,
        width: float = 0.4,
        depth: float = 0.4,
        height: float = 3.0,
        transformation: Optional[Transformation] = None,
        features: Optional[list[ColumnFeature]] = None,
        name: Optional[str] = None,
        capitel_width: float = 40,
        capitel_height: float = 650,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.capitel_width = capitel_width
        self.capitel_height = capitel_height
        self._box = Box.from_width_height_depth(width, height, depth)
        self._box.frame = Frame(point=[0, 0, self._box.zsize / 2], xaxis=[1, 0, 0], yaxis=[0, 1, 0])

    # =============================================================================
    # Features
    # =============================================================================

    def compute_features(self) -> list[Feature]:
        """Ensure the capitel feature exists, then return all features in order.

        The capitel is two boxes forming an L-shaped head at the top of the
        column, applied as a union (a :class:`ColumnFeature`). It is created once
        and kept first in the list, so any later features - e.g. a
        :class:`ColumnCutFeature` carving the head - are applied on top of the
        formed capitel.

        Returns
        -------
        list[:class:`Feature`]
        """
        if not any(isinstance(feature, ColumnFeature) for feature in self._features):
            capitel_box0 = Box.from_width_height_depth(self.capitel_width, self.capitel_height, self.depth)
            capitel_box0.translate([self.width * 0.5 + self.capitel_width * 0.5, 0, self.height - self.capitel_height * 0.5])

            capitel_box1 = Box.from_width_height_depth(self.depth + self.capitel_width, self.capitel_height, self.capitel_width)
            capitel_box1.translate([self.capitel_width * 0.5, self.width * 0.5 + self.capitel_width * 0.5, self.height - self.capitel_height * 0.5])

            self._features.insert(0, ColumnFeature([capitel_box0, capitel_box1]))
        return self._features

    def add_cutters(self, meshes: list, name: str = "column_cutters") -> "ColumnCutFeature":
        """Store cutter solids as a difference feature carved into the column head.

        The cutters must be given in the column's local frame. The capitel is
        ensured first (so it is unioned before the cut), then the cutters are
        stored as a :class:`ColumnCutFeature` - serialized in ``__data__`` and
        copied with the column, so they remain available for fabrication.

        Parameters
        ----------
        meshes : list[:class:`compas.datastructures.Mesh`]
            Closed cutter solids in the column's local frame.
        name : str, optional
            Name for the stored feature.

        Returns
        -------
        :class:`ColumnCutFeature`
            The feature that was appended.
        """
        self.compute_features()  # make sure the capitel exists and stays first
        feature = ColumnCutFeature(meshes, name=name)
        self._features.append(feature)
        # Invalidate cached geometry (both element- and model-space) so the cut recomputes.
        self._elementgeometry = None
        self._modelgeometry = None
        return feature

    # =============================================================================
    # Geometry
    # =============================================================================

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
    def height(self) -> float:
        return self.box.zsize

    @height.setter
    def height(self, height: float):
        self.box.zsize = height
        self.box.frame = Frame(point=[0, 0, self.box.zsize / 2], xaxis=[1, 0, 0], yaxis=[0, 1, 0])

    @property
    def center_line(self) -> Line:
        return Line([0, 0, 0], [0, 0, self.box.zsize])

    # =============================================================================
    # Implementations of abstract methods
    # =============================================================================

    def compute_elementgeometry(self, include_features: bool = True) -> Mesh:
        """Compute the mesh shape from the box, applying the column features.

        The capitel union and the cutter difference are boolean ops that emit
        triangle soup; their coplanar faces are merged back into single polygons
        so face-face contact detection does not fragment on the triangulation.

        Parameters
        ----------
        include_features : bool, optional
            If True, apply the column features (capitel union, cutter difference)
            to the base box geometry.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        mesh = self.box.to_mesh(True)
        if include_features:
            from compas_tf.solid_difference_modifier import merge_coplanar_faces

            for feature in self.compute_features():
                mesh = feature.apply(mesh)
            mesh = merge_coplanar_faces(mesh)
        return mesh

    def extend(self, distance: float) -> None:
        """Extend the column.

        Parameters
        ----------
        distance : float
            The distance to extend the column at each end.
        """
        self.box.zsize = self.height + distance * 2
        self.box.frame = Frame(point=[0, 0, self.box.zsize / 2], xaxis=[1, 0, 0], yaxis=[0, 1, 0])

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
        box = self._box.transformed(self.modeltransformation)
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
        """Compute the reference point of the column from the centroid of its geometry.

        Returns
        -------
        :class:`compas.geometry.Point`
        """
        return Point(*self.modelgeometry.centroid())
