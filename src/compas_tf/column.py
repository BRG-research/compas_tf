from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.elements.element import Feature

from compas_tf.element import TFElement
from compas_tf.element import TFFeature
from compas_tf.element import baked


class ColumnAddFeature(TFFeature):
    """Additive feature: boolean-unions a set of capitel boxes onto the column.

    This is the additive half of the column feature pair; its subtractive
    counterpart is :class:`ColumnCutFeature`. Retrieve either kind by name with
    :meth:`ColumnElement.get_features`.

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

    def brep_meshes(self, variant: Optional[str] = None) -> list:
        """The capitel boxes as meshes - what :meth:`get_brep` converts."""
        return [box.to_mesh() for box in self.boxes]

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


# Backwards-compatible alias: models serialized before the add/cut rename store
# the capitel feature under the dtype ``compas_tf.column/ColumnFeature``. Keeping
# the name bound here lets those JSON files still deserialize.
ColumnFeature = ColumnAddFeature


class ColumnCutFeature(TFFeature):
    """Feature that boolean-differences cutter solids out of the column geometry.

    Stored on the column (in its local frame), so the cut travels with the
    element through copy/serialization and the cutter solids stay available for
    fabrication. The capitel (a :class:`ColumnAddFeature`) is applied first, so
    the cutters carve the already-formed column head.

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


class ColumnElement(TFElement):
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
    features : Optional[list[:class:`ColumnAddFeature` | :class:`ColumnCutFeature`]]
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
            **self._baked_data(),
        }

    def __init__(
        self,
        width: float = 0.4,
        depth: float = 0.4,
        height: float = 3.0,
        transformation: Optional[Transformation] = None,
        features: Optional[list[Feature]] = None,
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

    @staticmethod
    def _type_names(types) -> set:
        """Normalize a ``types`` argument (class names and/or classes) to a name set."""
        return {t if isinstance(t, str) else t.__name__ for t in types}

    def get_features(self, types: Optional[list] = None, placed: bool = False) -> list[Feature]:
        """Return the column's features, optionally filtered by feature type.

        This is pure retrieval - no geometry is built and the lazy capitel is
        NOT created (use :meth:`compute_features` for that). Filter by type to
        pull out a specific kind of feature for modelling, fabrication or
        inspection, e.g. ``get_features(["ColumnCutFeature"])`` to recover just
        the cutter solids.

        Parameters
        ----------
        types : list[str | type], optional
            Feature types to keep, given as class names (e.g.
            ``"ColumnCutFeature"``) or the classes themselves. ``None`` (default)
            returns every feature, in application order.
        placed : bool, optional
            If True, return independent copies whose geometry has been moved
            into model coordinates by the column's ``modeltransformation`` - the
            same transform that builds ``modelgeometry``, so the returned
            cutters line up with the column wherever it sits. The stored
            features are left untouched. Default is False: the features as
            stored, in the column's local frame.

        Returns
        -------
        list[:class:`Feature`]
        """
        if types is None:
            features = list(self._features)
        else:
            names = self._type_names(types)
            features = [feature for feature in self._features if type(feature).__name__ in names]

        if not placed:
            return features

        return [self._place(feature, self.placement) for feature in features]

    @staticmethod
    def _place(feature: Feature, transformation: Transformation) -> Feature:
        """An independent copy of ``feature`` with its geometry moved by ``transformation``."""
        if hasattr(feature, "placed"):
            return feature.placed(transformation)
        placed = feature.copy()
        if getattr(placed, "meshes", None):
            placed.meshes = [mesh.transformed(transformation) for mesh in placed.meshes]
        if getattr(placed, "boxes", None):
            placed.boxes = [box.transformed(transformation) for box in placed.boxes]
        return placed

    def compute_features(self, types: Optional[list] = None) -> list[Feature]:
        """Ensure the capitel feature exists, then return the features to apply.

        The capitel is two boxes forming an L-shaped head at the top of the
        column, applied as a union (a :class:`ColumnAddFeature`). It is created
        once and kept first in the list, so any later
        :class:`ColumnCutFeature` carving the head is applied on top of the
        formed capitel.

        Unlike :meth:`get_features`, this ensures the lazy capitel exists. The
        ``types`` filter selects which feature types are *applied to the main
        geometry* by :meth:`compute_elementgeometry`: e.g.
        ``types=["ColumnAddFeature"]`` yields the uncut head (capitel only),
        ``types=["ColumnCutFeature"]`` only the cuts.

        Parameters
        ----------
        types : list[str | type], optional
            Feature types to apply (see :meth:`get_features`). ``None`` (default)
            applies every feature.

        Returns
        -------
        list[:class:`Feature`]
        """
        if not any(isinstance(feature, ColumnAddFeature) for feature in self._features):
            capitel_box0 = Box.from_width_height_depth(self.capitel_width, self.capitel_height, self.depth)
            capitel_box0.translate([self.width * 0.5 + self.capitel_width * 0.5, 0, self.height - self.capitel_height * 0.5])

            capitel_box1 = Box.from_width_height_depth(self.depth + self.capitel_width, self.capitel_height, self.capitel_width)
            capitel_box1.translate([self.capitel_width * 0.5, self.width * 0.5 + self.capitel_width * 0.5, self.height - self.capitel_height * 0.5])

            self._features.insert(0, ColumnAddFeature([capitel_box0, capitel_box1]))
        return self.get_features(types)

    def add_feature(self, feature: Feature) -> Feature:
        """Append a feature and invalidate cached geometry so it recomputes.

        The capitel is forced to index 0 by :meth:`compute_features`, so additive
        and subtractive features can be appended in any order and the union still
        precedes the cuts. Overrides the base ``add_feature`` only to drop the
        cached element/model geometry.

        Parameters
        ----------
        feature : :class:`Feature`
            Any column feature (:class:`ColumnAddFeature`,
            :class:`ColumnCutFeature`, ...).

        Returns
        -------
        :class:`Feature`
            The feature that was appended.
        """
        self._features.append(feature)
        self._elementgeometry = None
        self._modelgeometry = None
        return feature

    def add_cutters(self, meshes: list, name: str = "column_cutters") -> "ColumnCutFeature":
        """Convenience wrapper: store cutter solids as a :class:`ColumnCutFeature`.

        Equivalent to ``self.add_feature(ColumnCutFeature(meshes, name=name))`` -
        kept so callers need not import the feature class. The cutters must be in
        the column's local frame; they are serialized in ``__data__`` and copied
        with the column, so the cut stays available for fabrication.

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
        return self.add_feature(ColumnCutFeature(meshes, name=name))

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

    @baked
    def compute_elementgeometry(self, include_features: bool = True, types: Optional[list] = None) -> Mesh:
        """Compute the mesh shape from the box, applying the column features.

        The capitel union and the cutter difference are boolean ops that emit
        triangle soup; their coplanar faces are merged back into single polygons
        so face-face contact detection does not fragment on the triangulation.

        Parameters
        ----------
        include_features : bool, optional
            If True, apply the column features to the base box geometry.
        types : list[str | type], optional
            Restrict which feature types are applied (see
            :meth:`compute_features`). ``None`` (default) applies every feature;
            ``["ColumnAddFeature"]`` yields the uncut head. Ignored when
            ``include_features`` is False.

        Returns
        -------
        :class:`compas.datastructures.Mesh`

        Notes
        -----
        Decorated with :func:`compas_tf.element.baked`: if this exact variant
        has been baked (see :meth:`compas_tf.element.TFElement.bake` /
        :meth:`bake_stock`), the stored mesh is returned and no boolean runs.
        """
        mesh = self.box.to_mesh(True)
        if include_features:
            from compas_tf.solid_difference_modifier import merge_coplanar_faces

            for feature in self.compute_features(types):
                mesh = feature.apply(mesh)
            mesh = merge_coplanar_faces(mesh)
        return mesh

    # The feature filter that yields the uncut stock: the capitel union applied,
    # the cuts not yet. Kept as a constant so the bake key and the lookup agree.
    STOCK_TYPES = ["ColumnAddFeature"]

    @property
    def stock(self) -> Mesh:
        """The UNCUT column: base box + capitel, before any cutter is applied.

        The fabrication starting point - the raw glulam blank the cuts are made
        in. Served from the bake cache once :meth:`bake_stock` has run.
        """
        return self.compute_elementgeometry(types=self.STOCK_TYPES)

    def bake_stock(self) -> Mesh:
        """Compute the uncut :attr:`stock` once and store it for serialization.

        Sugar for ``bake(types=ColumnElement.STOCK_TYPES)``. Bake this next to
        the plain :meth:`compas_tf.element.TFElement.bake` to carry both the
        blank and the carved part in the JSON.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        return self.bake(types=self.STOCK_TYPES)

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
