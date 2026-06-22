"""Free-standing connector elements usable as boolean cutters or joiners.

Three light parametric solids that mirror the shapes already produced inside the
floor model, but exposed as standalone, reusable elements:

- :class:`ConnectorBoxElement`      — a box (width x depth x height).
- :class:`ConnectorCylinderElement` — a cylinder from an axis line + radius.
- :class:`ConnectorWedgeElement`    — a triangular wedge prism, like the
  contact wedges placed between the quarter slabs and the oculus.

Each one implements the standard :class:`compas_model.elements.Element`
interface and additionally exposes ``boolean_geometry`` / ``boolean_geometries``
(the transformed cutter mesh), so it can drive a
:class:`compas_tf.solid_difference_modifier.SolidDifferenceModifier` exactly like
:class:`compas_tf.wedge.WedgeElement` and
:class:`compas_tf.joint_dowel.DowelElement` do.
"""

import math
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineLoft


def _merge_collinear_points(points, angle_tol=1e-3):
    """Drop points that lie on the straight line through their closed neighbours.

    Keeps the contact polygon from carrying machine-collinear vertices that would
    otherwise split one real interface edge into several tiny ones.
    """
    pts = [Point(*p) for p in points]
    while True:
        n = len(pts)
        if n < 3:
            return pts
        kept, dropped = [], False
        for i in range(n):
            prev, curr, nxt = pts[(i - 1) % n], pts[i], pts[(i + 1) % n]
            v1, v2 = curr - prev, nxt - curr
            l1, l2 = v1.length, v2.length
            if l1 < 1e-9:
                dropped = True
                continue
            if l2 < 1e-9:
                kept.append(curr)
                continue
            if v1.cross(v2).length / (l1 * l2) < angle_tol:
                dropped = True
                continue
            kept.append(curr)
        if not dropped:
            return kept
        pts = kept


def _placed_geometry(element) -> Mesh:
    """Geometry to bound for aabb/obb/point.

    Model-space (``modelgeometry``) when the element is in a model tree, else the
    element geometry placed by its own ``transformation`` — so the connectors
    also work standalone (``modelgeometry`` raises without a tree).
    """
    if getattr(element, "treenode", None) is None:
        mesh = element.compute_elementgeometry()
        return mesh.transformed(element.transformation) if element.transformation else mesh
    return element.modelgeometry


# ===================================================================== #
#  Box
# ===================================================================== #


class ConnectorBoxFeature(Feature):
    pass


class ConnectorBoxElement(Element):
    """A box-shaped connector centred on the element's local frame.

    Parameters
    ----------
    width : float
        Box size along local X.
    depth : float
        Box size along local Y.
    height : float
        Box size along local Z.
    transformation : :class:`compas.geometry.Transformation`, optional
        Placement of the box in the model.
    features : list[:class:`ConnectorBoxFeature`], optional
        Features of the connector.
    name : str, optional
        Name of the element.
    """

    @property
    def __data__(self) -> dict:
        return {
            "width": self.width,
            "depth": self.depth,
            "height": self.height,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        width: float = 100.0,
        depth: float = 100.0,
        height: float = 100.0,
        transformation: Optional[Transformation] = None,
        features: Optional[list] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.width = width
        self.depth = depth
        self.height = height

    @property
    def box(self) -> Box:
        """Box geometry in the element's local frame (centred on the origin)."""
        return Box(self.width, self.depth, self.height, frame=Frame.worldXY())

    def compute_elementgeometry(self, include_features: bool = False) -> Mesh:
        return self.box.to_mesh()

    @property
    def boolean_geometry(self) -> Mesh:
        """Cutter mesh with the element transformation applied."""
        mesh = self.compute_elementgeometry()
        if self.transformation:
            return mesh.transformed(self.transformation)
        return mesh

    @property
    def boolean_geometries(self) -> list:
        """Cutter meshes contributed by the connector (one box)."""
        return [self.boolean_geometry]

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = _placed_geometry(self).aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = _placed_geometry(self).obb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*_placed_geometry(self).centroid())


# ===================================================================== #
#  Cylinder
# ===================================================================== #


class ConnectorCylinderFeature(Feature):
    pass


class ConnectorCylinderElement(Element):
    """A cylinder connector built from an axis line and a radius.

    The cylinder is lofted between two ``sides``-gon circles centred on the ends
    of ``line`` (given in the element's local frame), perpendicular to it.

    Parameters
    ----------
    line : :class:`compas.geometry.Line`, optional
        Cylinder axis in the element's local frame. Defaults to a 100 mm long
        axis along local Z.
    radius : float
        Cylinder radius.
    sides : int
        Number of polygon sides approximating the circle.
    transformation : :class:`compas.geometry.Transformation`, optional
        Placement of the cylinder in the model.
    features : list[:class:`ConnectorCylinderFeature`], optional
        Features of the connector.
    name : str, optional
        Name of the element.
    """

    @property
    def __data__(self) -> dict:
        return {
            "line": self.line,
            "radius": self.radius,
            "sides": self.sides,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        line: Optional[Line] = None,
        radius: float = 50.0,
        sides: int = 16,
        transformation: Optional[Transformation] = None,
        features: Optional[list] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.line = line if line is not None else Line(Point(0, 0, 0), Point(0, 0, 100))
        self.radius = radius
        self.sides = sides

    @property
    def axis(self) -> Line:
        """Axis line with the element transformation applied."""
        if self.transformation:
            return self.line.transformed(self.transformation)
        return self.line

    def compute_mesh(self) -> Mesh:
        """Loft two circles along the axis line into a closed cylinder mesh."""
        start = Point(*self.line.start)
        end = Point(*self.line.end)
        direction = Vector.from_start_end(start, end)
        length = direction.length
        z = direction.unitized()

        # A reference not parallel to the axis, to seed the circle plane.
        ref = Vector(1, 0, 0)
        if abs(z.dot(ref)) > 0.99:
            ref = Vector(0, 0, 1)
        x = z.cross(ref).unitized()
        y = z.cross(x).unitized()

        r, n = self.radius, self.sides
        bottom = []
        for k in range(n):
            a = 2.0 * math.pi * k / n
            bottom.append(start + x * (r * math.cos(a)) + y * (r * math.sin(a)))
        circle_bottom = Polyline(bottom + [bottom[0]])
        circle_top = circle_bottom.translated(z * length)
        return PolylineLoft.to_mesh(circle_bottom, circle_top)

    def compute_elementgeometry(self, include_features: bool = False) -> Mesh:
        return self.compute_mesh()

    @property
    def boolean_geometry(self) -> Mesh:
        """Cutter mesh with the element transformation applied."""
        mesh = self.compute_mesh()
        if self.transformation:
            return mesh.transformed(self.transformation)
        return mesh

    @property
    def boolean_geometries(self) -> list:
        """Cutter meshes contributed by the connector (one cylinder)."""
        return [self.boolean_geometry]

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = _placed_geometry(self).aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = _placed_geometry(self).obb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*self.axis.midpoint)


# ===================================================================== #
#  Wedge
# ===================================================================== #


class ConnectorWedgeFeature(Feature):
    pass


class ConnectorWedgeElement(Element):
    """The floor contact wedge (copied from :class:`compas_tf.wedge.WedgeElement`),
    exposed as a free connector that is sized and placed from an interface line.

    The fixed triangular ``PROFILE`` (local YZ plane) is copied to
    ``x = -length/2`` and ``x = +length/2`` and lofted into a closed triangular
    prism — the exact wedge geometry used in
    ``example_2_floor_model_booleans.py``. The dowel axis (``DOWEL_START`` ->
    ``DOWEL_END``) runs along local Y, and :meth:`create_cylinders` distributes
    :class:`ConnectorCylinderElement` dowels along the wedge length.

    Parameters
    ----------
    length : float
        Prism length along local X (the wedge "target_length"). Usually set from
        the interface edge via :meth:`from_interface` / :meth:`from_contact`.
    cylinder_radius : float
        Radius of the dowel cylinders.
    cylinder_spacing : float
        Approximate spacing between dowels along the wedge length.
    cylinder_sides : int
        Polygon resolution of the dowel cylinders.
    transformation : :class:`compas.geometry.Transformation`, optional
        Placement of the wedge in the model.
    features : list[:class:`ConnectorWedgeFeature`], optional
        Features of the connector.
    name : str, optional
        Name of the element.
    """

    # Triangular profile in the local YZ plane (x = 0) — identical to WedgeElement.
    PROFILE = [
        Point(0, 0, -197),
        Point(0, -31.75593, 11.530606),
        Point(0, 31.75593, 11.530606),
    ]
    # Screw / dowel axis endpoints (local coordinates), along local Y.
    DOWEL_START = Point(0, -80.0, -100)
    DOWEL_END = Point(0, 80.0, -100)

    @property
    def __data__(self) -> dict:
        return {
            "length": self.length,
            "cylinder_radius": self.cylinder_radius,
            "cylinder_spacing": self.cylinder_spacing,
            "cylinder_sides": self.cylinder_sides,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        length: float = 160.0,
        cylinder_radius: float = 10.0,
        cylinder_spacing: float = 320.0,
        cylinder_sides: int = 12,
        transformation: Optional[Transformation] = None,
        features: Optional[list] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.length = length
        # Dowel cylinders run along local Y (the contact normal, through both
        # joined parts) on the DOWEL axis, distributed along local X.
        self.cylinder_radius = cylinder_radius
        self.cylinder_spacing = cylinder_spacing
        self.cylinder_sides = cylinder_sides

    # ----------------------------------------------------------------- #
    #  Construction from a contact / interface line
    # ----------------------------------------------------------------- #

    @staticmethod
    def interface_line(contact):
        """Return ``(start, end, normal)`` for a contact's longest *top* edge.

        Mirrors the floor model's pick: collinear vertices are merged, edges
        whose midpoint is at/above the polygon centroid count as "top", and the
        longest such edge wins. ``normal`` is the contact polygon normal.

        Parameters
        ----------
        contact : :class:`compas_model.interactions.Contact`

        Returns
        -------
        tuple(:class:`compas.geometry.Point`, :class:`compas.geometry.Point`, :class:`compas.geometry.Vector`)
        """
        pts = _merge_collinear_points(list(contact.polygon.points))
        n = len(pts)
        normal = contact.polygon.normal
        centroid_z = sum(p[2] for p in pts) / n
        scored = []
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            is_top = 0.5 * (a[2] + b[2]) >= centroid_z
            scored.append((is_top, (b - a).length, a, b))
        scored.sort(key=lambda e: (not e[0], -e[1]))
        _, _, start, end = scored[0]
        return start, end, normal

    @classmethod
    def from_interface(cls, start, end, normal, length_margin=0.0, **kwargs):
        """Create a wedge centred on an interface edge.

        The wedge frame is ``X = edge direction``, ``Y = normal``,
        ``Z = X cross Y``, placed at the edge midpoint. The wedge ``length`` is
        the edge length minus ``2 * length_margin`` (e.g. plate thickness), so
        it is driven by the interface line length.

        Parameters
        ----------
        start, end : point-like
            Endpoints of the interface edge.
        normal : vector-like
            Contact normal (becomes the wedge's local Y / cylinder axis).
        length_margin : float
            Amount trimmed off each end of the edge to size the wedge length.
        **kwargs
            Forwarded to ``__init__`` (cross-section + cylinder parameters).
        """
        start, end = Point(*start), Point(*end)
        vec = Vector.from_start_end(start, end)
        edge_length = vec.length
        direction = vec.unitized()
        midpoint = start + direction * (0.5 * edge_length)
        frame = Frame(midpoint, direction, Vector(*normal))
        length = max(edge_length - 2.0 * length_margin, 1e-6)
        return cls(length=length, transformation=Transformation.from_frame(frame), **kwargs)

    @classmethod
    def from_contact(cls, contact, length_margin=0.0, **kwargs):
        """Create a wedge from a contact's longest top edge (see :meth:`interface_line`)."""
        start, end, normal = cls.interface_line(contact)
        return cls.from_interface(start, end, normal, length_margin=length_margin, **kwargs)

    # ----------------------------------------------------------------- #
    #  Cylinders (dowels) generated along the interface length
    # ----------------------------------------------------------------- #

    def create_cylinders(self):
        """Distribute :class:`ConnectorCylinderElement` dowels along the wedge.

        Mirrors ``WedgeElement.dowel_lines``: the ``DOWEL`` axis (local Y) is
        copied to ``max(int(length / spacing), 1)`` evenly-spaced stations along
        local X. Each cylinder shares the wedge's transformation so it lands in
        the same model frame.

        Returns
        -------
        list[:class:`ConnectorCylinderElement`]
        """
        n = max(int(self.length / self.cylinder_spacing), 1) if self.cylinder_spacing > 0 else 1
        half_len = 0.5 * self.length
        base = Line(self.DOWEL_START, self.DOWEL_END)
        cylinders = []
        for i in range(n):
            x = -half_len + (i + 0.5) * (self.length / n)
            line = base.translated(Vector(x, 0, 0))
            cylinders.append(
                ConnectorCylinderElement(
                    line=line,
                    radius=self.cylinder_radius,
                    sides=self.cylinder_sides,
                    transformation=self.transformation,
                    name=f"{self.name or 'wedge'}_cylinder_{i}",
                )
            )
        return cylinders

    def build_mesh(self) -> Mesh:
        """Loft the fixed PROFILE between x = -length/2 and +length/2 (WedgeElement)."""
        hw = 0.5 * self.length
        n = len(self.PROFILE)
        neg = [[-hw, p.y, p.z] for p in self.PROFILE]
        pos = [[hw, p.y, p.z] for p in self.PROFILE]
        vertices = neg + pos  # 0..n-1 = neg cap, n..2n-1 = pos cap

        faces = [list(range(n))]  # neg end cap
        faces.append([n + i for i in reversed(range(n))])  # pos end cap (reversed)
        for i in range(n):  # side quads
            j = (i + 1) % n
            faces.append([j, i, n + i, n + j])
        return Mesh.from_vertices_and_faces(vertices, faces)

    def compute_elementgeometry(self, include_features: bool = False) -> Mesh:
        return self.build_mesh()

    def cutter_box(self, through: float = 400.0, margin: float = 0.0) -> Mesh:
        """Oriented BOX cutter aligned to the wedge — its cutting geometry.

        The box is built in the wedge's local frame so its biggest face (local
        X-Z, ``length`` x profile-depth) coincides with the wedge's biggest side.
        It is made massive along local Y (``through``, the joint normal) so it
        slices clean through both plates, producing a straight rectangular slot
        rather than a triangular one. Size is intentionally generous — the
        boolean only removes the intersection.

        Parameters
        ----------
        through : float
            Box extent along local Y (the cut-through direction).
        margin : float
            Extra added to the X (length) and Z (depth) extents.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            The box cutter, with the wedge transformation applied (model space).
        """
        zs = [p.z for p in self.PROFILE]
        zmin, zmax = min(zs), max(zs)
        xsize = self.length + 2.0 * margin
        zsize = (zmax - zmin) + 2.0 * margin
        center = Point(0.0, 0.0, 0.5 * (zmin + zmax))
        box = Box(xsize, through, zsize, frame=Frame(center, Vector.Xaxis(), Vector.Yaxis()))
        mesh = box.to_mesh()
        if self.transformation:
            mesh = mesh.transformed(self.transformation)
        return mesh

    @property
    def boolean_geometry(self) -> Mesh:
        """Cutting geometry of the wedge — the wedge solid itself (model space),
        so a plate carved by it is identical to the WedgeElement cut in
        example_2. Use :meth:`cutter_box` instead for a box-shaped slot."""
        mesh = self.build_mesh()
        if self.transformation:
            return mesh.transformed(self.transformation)
        return mesh

    @property
    def boolean_geometries(self) -> list:
        """Cutter meshes contributed by the connector (the wedge solid)."""
        return [self.boolean_geometry]

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = _placed_geometry(self).aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = _placed_geometry(self).obb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*_placed_geometry(self).centroid())
