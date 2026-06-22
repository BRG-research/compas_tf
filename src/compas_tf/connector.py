from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Cylinder
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Translation
from compas.geometry import Polygon as GeomPolygon
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements.element import Element
from compas_model.elements.element import Feature


class ConnectorFeature(Feature):
    pass


class DowelCylinderElement(Element):
    """A cylindrical dowel connector.

    Like the wedge components, this is a real model element (visible, serialized)
    that is also used as a boolean cutter against the elements it joins. The
    cylinder is built along the local Y axis, centred at the origin, and placed
    by ``transformation``.

    Parameters
    ----------
    radius : float
        Cylinder radius.
    length : float
        Cylinder length (the nominal dowel length, e.g. the rib thickness).
    transformation : :class:`compas.geometry.Transformation`, optional
    features : list[:class:`Feature`], optional
    name : str, optional
    """

    @property
    def __data__(self) -> dict:
        return {
            "radius": self.radius,
            "length": self.length,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(self, radius=25.0, length=100.0, transformation=None, features=None, name=None):
        super().__init__(transformation=transformation, features=features, name=name)
        self.radius = radius
        self.length = length
        self._mesh = Cylinder(radius, length, frame=Frame([0, 0, 0], [0, 0, 1], [1, 0, 0])).to_mesh()

    def compute_elementgeometry(self, include_features: bool = False) -> Mesh:
        return self._mesh

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.obb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())


class ConnectorElement(Element):
    """Rectangular connector box straddling the contact between two elements.

    Local frame (before ``transformation``):

    - ``+X`` runs across the joint, toward the rib. The box spans
      ``[-BACK, +FRONT] = [-140, +265]`` along X (140 into the column, 265 into
      the rib), split at the contact plane (local ``x = 0``). The total length
      (405) is the longest dimension, so it points toward the rib.
    - ``+Y`` is horizontal along the contact face; the box is ``WIDTH = 21`` wide,
      centred on the placement point.
    - ``+Z`` is up; the box top face is at local ``z = 0`` and the body hangs down
      to ``z = -HEIGHT = -350``.

    Build one oriented to a contact with :meth:`from_contact`: the placement
    frame sits at the contact polygon's topmost point, with ``+X`` along the
    horizontal contact normal (flipped to point toward the rib) and ``+Z`` along
    world up.

    Parameters
    ----------
    transformation : :class:`compas.geometry.Transformation`, optional
        Places the local box in the model (typically a world frame).
    features : list[:class:`ConnectorFeature`], optional
    name : str, optional
    """

    WIDTH = 21.0      # Y, along the contact face
    BACK = 140.0      # -X, into the column
    FRONT = 265.0     # +X, into the rib (longest extent -> toward the rib)
    HEIGHT = 350.0    # -Z, downward from the top
    RADIUS = 25.0     # cylinder dowel radius

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
        features: Optional[list] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        # Box centred so x in [-BACK, FRONT], y in [-WIDTH/2, WIDTH/2], z in [-HEIGHT, 0].
        center = Point((self.FRONT - self.BACK) * 0.5, 0.0, -self.HEIGHT * 0.5)
        self._box = Box(self.BACK + self.FRONT, self.WIDTH, self.HEIGHT, frame=Frame(center))

    @classmethod
    def from_contact(cls, contact, toward, name: Optional[str] = None) -> "ConnectorElement":
        """Create a connector oriented to a contact polygon.

        Parameters
        ----------
        contact : :class:`compas_model.interactions.Contact`
            The contact whose polygon defines the placement.
        toward : :class:`compas.geometry.Point`
            A point on the rib side (e.g. the rib element's centroid). The local
            ``+X`` axis (the contact normal, projected horizontal) is flipped to
            point toward it, so the longer 265 mm extent goes into the rib.
        name : str, optional

        Returns
        -------
        :class:`ConnectorElement`
        """
        pts = list(contact.polygon.points)
        normal = GeomPolygon(pts).normal

        # X = horizontal component of the contact normal, pointing toward the rib.
        xaxis = Vector(normal[0], normal[1], 0.0)
        if xaxis.length < 1e-9:
            # Near-horizontal contact: fall back to the horizontal direction to the rib.
            centroid = Point(*[sum(p[i] for p in pts) / len(pts) for i in range(3)])
            xaxis = Vector(toward[0] - centroid[0], toward[1] - centroid[1], 0.0)
        xaxis.unitize()

        centroid = Point(*[sum(p[i] for p in pts) / len(pts) for i in range(3)])
        if xaxis.dot(Vector(toward[0] - centroid[0], toward[1] - centroid[1], 0.0)) < 0:
            xaxis = xaxis * -1.0

        # Z = world up; Y = Z x X (horizontal tangent). Frame zaxis resolves to world up.
        zaxis = Vector(0, 0, 1)
        yaxis = zaxis.cross(xaxis)
        yaxis.unitize()

        # Anchor at the MIDDLE of the contact's TOP EDGE - where the 165/265
        # split and the box top sit. Take the points along the top edge (those
        # within a tolerance of the highest z) and use the centre of their
        # extent. This is the true top-edge midpoint, not a corner and not the
        # contact's mid-depth (which would shift the box on an inclined contact).
        top_z = max(p[2] for p in pts)
        z_extent = top_z - min(p[2] for p in pts)
        tol = max(1.0, 0.02 * z_extent)
        top_pts = [p for p in pts if top_z - p[2] <= tol]
        origin = Point(*[0.5 * (min(p[i] for p in top_pts) + max(p[i] for p in top_pts)) for i in range(3)])
        frame = Frame(origin, xaxis, yaxis)
        return cls(transformation=Transformation.from_frame(frame), name=name)

    def cutter_mesh(self) -> Mesh:
        """The connector box in world coordinates (for boolean cutting)."""
        mesh = self._box.to_mesh()
        if self.transformation:
            mesh = mesh.transformed(self.transformation)
        return mesh

    def cylinder_cutters(self, length: float, overshoot: float = 25.0):
        """Cylindrical dowel cutters: two per side (column and rib).

        The connector height is divided into three; a cylinder sits at each of
        the two interior levels (1/3 and 2/3 down). They are centred on each
        side - ``x = -BACK/2`` (column side) and ``x = +FRONT/2`` (rib side) -
        so the connector knows BACK (140) is toward the column and FRONT (265)
        toward the rib. Each cylinder's axis runs along the connector width
        (local Y), with the given ``length`` and radius :attr:`RADIUS`. The two
        sides carry the same vertical division, just on opposite sides (so the
        female/male distinction does not change the geometry).

        Each *cutter* is extended by ``overshoot`` at both ends so its flat caps
        clear the element surfaces: a cap exactly flush (coplanar) with a face
        makes the boolean difference unreliable. The clipped hole still spans the
        element; only the cutter overshoots, the nominal dowel length is ``length``.

        Parameters
        ----------
        length : float
            Cylinder length (e.g. the rib thickness).
        overshoot : float
            Extra length added at each cap so the cut passes cleanly through.

        Returns
        -------
        tuple[list[:class:`compas.datastructures.Mesh`], list[:class:`compas.datastructures.Mesh`]]
            ``(column_cutters, rib_cutters)`` as closed meshes in world
            coordinates - to subtract from the column and the rib respectively.
        """
        levels = [-self.HEIGHT / 3.0, -2.0 * self.HEIGHT / 3.0]
        cut_length = length + 2.0 * overshoot

        def at_side(x):
            cutters = []
            for z in levels:
                frame = Frame([x, 0.0, z], [0, 0, 1], [1, 0, 0])  # cylinder axis = local +Y
                mesh = Cylinder(self.RADIUS, cut_length, frame=frame).to_mesh()
                if self.transformation:
                    mesh = mesh.transformed(self.transformation)
                cutters.append(mesh)
            return cutters

        return at_side(-self.BACK / 2.0), at_side(self.FRONT / 2.0)

    def cylinder_elements(self, length: float):
        """The four dowel cylinders as placed model elements (nominal length).

        Same positions as :meth:`cylinder_cutters` (column side at ``-BACK/2``,
        rib side at ``+FRONT/2``, at the two height thirds, axis along local Y),
        but at the nominal ``length`` (no cutter overshoot) - these are the real
        dowels, added to the model like the wedge components.

        Parameters
        ----------
        length : float
            Cylinder length (e.g. the rib thickness).

        Returns
        -------
        list[:class:`DowelCylinderElement`]
        """
        levels = [-self.HEIGHT / 3.0, -2.0 * self.HEIGHT / 3.0]
        elements = []
        for side, x in (("column", -self.BACK / 2.0), ("rib", self.FRONT / 2.0)):
            for j, z in enumerate(levels):
                xform = Translation.from_vector([x, 0.0, z])
                if self.transformation:
                    xform = self.transformation * xform
                elements.append(DowelCylinderElement(self.RADIUS, length, transformation=xform, name=f"cylinder_{side}_{j}"))
        return elements

    # ==========================================================================
    # Implementations of abstract methods
    # ==========================================================================

    def compute_elementgeometry(self, include_features: bool = True) -> Mesh:
        mesh = self._box.to_mesh()
        if include_features and self._features:
            # Apply the dowel-cylinder cuts. No coplanar-face merge here: the
            # connector is not used for contact detection, and skipping the merge
            # keeps the cylinder holes manifold.
            for feature in self._features:
                mesh = feature.apply(mesh)
        return mesh

    def add_cutters(self, meshes: list, name: str = "connector_cutters"):
        """Store cutter solids (e.g. the dowel cylinders) as a difference feature.

        The meshes must be in the connector's local frame. Stored as a
        :class:`compas_tf.solid_difference_modifier.MeshCutFeature` so the holes
        travel with the connector through copy/serialization.
        """
        from compas_tf.solid_difference_modifier import MeshCutFeature

        feature = MeshCutFeature(meshes, name=name)
        self._features.append(feature)
        self._elementgeometry = None
        self._modelgeometry = None
        return feature

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = Box.from_bounding_box(self._box.transformed(self.modeltransformation).points)
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self._box.transformed(self.modeltransformation)
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())
