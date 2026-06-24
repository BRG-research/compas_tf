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
from compas.geometry import Cylinder
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Polygon as GeomPolygon
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas.geometry import Translation
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

    def end_polylines(self):
        """The wedge's two triangular end faces as co-wound closed polylines.

        The prism is the PROFILE copied to ``x = -length/2`` (bottom) and
        ``x = +length/2`` (top); both use the same PROFILE order, so vertex *i*
        of the bottom matches vertex *i* of the top (same winding), exactly the
        ``(bottom, top)`` representation a plate uses. Returned in model space
        (the wedge ``transformation`` applied), to match :attr:`boolean_geometry`.

        Returns
        -------
        tuple(:class:`compas.geometry.Polyline`, :class:`compas.geometry.Polyline`)
            The ``(bottom, top)`` end-face polylines.
        """
        hw = 0.5 * self.length
        neg = [Point(-hw, p.y, p.z) for p in self.PROFILE]
        pos = [Point(hw, p.y, p.z) for p in self.PROFILE]
        bottom = Polyline(neg + [neg[0]])
        top = Polyline(pos + [pos[0]])
        if self.transformation:
            bottom = bottom.transformed(self.transformation)
            top = top.transformed(self.transformation)
        return bottom, top

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

    def inclined_face_boxes(self, depth=100.0, margin=0.0):
        """One oriented box per INCLINED wedge face (the two slants A-B, A-C).

        Each box's large face lies on the incline (box X = wedge length, box Y =
        the slant edge), and the box extends ``depth`` along that face's OUTWARD
        normal - into the plate the face meets. Returned in model space (wedge
        transform applied), so the box follows the inclined face exactly, with no
        extra transform needed. The two boxes are returned in face order
        ``[A-B, A-C]`` - one for each neighbour the wedge joins.
        """
        A, B, C = (Point(*p) for p in self.PROFILE)  # tip, top-left, top-right
        centroid = Point((A.x + B.x + C.x) / 3.0, (A.y + B.y + C.y) / 3.0, (A.z + B.z + C.z) / 3.0)

        boxes = []
        for P0, P1 in [(A, B), (A, C)]:  # the two inclined edges (skip top B-C)
            slant = Vector.from_start_end(P0, P1)
            edge_len = slant.length
            yaxis = slant.unitized()
            xaxis = Vector(1, 0, 0)  # along the wedge length
            normal = xaxis.cross(yaxis).unitized()  # box frame z = X x Y
            face_center = Point(0.0, 0.5 * (P0.y + P1.y), 0.5 * (P0.z + P1.z))
            # make the normal point AWAY from the wedge interior (out into the plate)
            if normal.dot(Vector.from_start_end(centroid, face_center)) < 0:
                normal, yaxis = normal.scaled(-1.0), yaxis.scaled(-1.0)
            center = face_center + normal * (0.5 * -depth)  # box sits on the plate side of the face
            frame = Frame(center, xaxis, yaxis)  # z-axis = x cross y = normal
            box = Box(self.length + 2 * margin, edge_len + 2 * margin, depth, frame=frame).to_mesh()
            if self.transformation:
                box = box.transformed(self.transformation)
            boxes.append(box)
        return boxes

    def inclined_face_box_outlines(self, depth=100.0, margin=0.0):
        """The (bottom, top) rectangle outlines of each inclined-face box.

        Same boxes as :meth:`inclined_face_boxes`, but as their two large-face
        rectangles - ``bottom`` lying ON the incline, ``top`` ``depth`` into the
        plate - returned co-wound (vertex *i* of ``bottom`` matches vertex *i* of
        ``top``), in model space. This is the minimal, parametric drilling /
        fabrication form: feed a pair to a
        :class:`compas_tf.solid_difference_modifier.PrismCutFeature` to get both
        the box cutter (the loft) and the outlines (its ``minimal``). One pair
        per inclined face, in order ``[A-B, A-C]``.
        """
        A, B, C = (Point(*p) for p in self.PROFILE)  # tip, top-left, top-right
        centroid = Point((A.x + B.x + C.x) / 3.0, (A.y + B.y + C.y) / 3.0, (A.z + B.z + C.z) / 3.0)

        pairs = []
        for P0, P1 in [(A, B), (A, C)]:
            slant = Vector.from_start_end(P0, P1)
            yaxis = slant.unitized()
            xaxis = Vector(1, 0, 0)
            normal = xaxis.cross(yaxis).unitized()
            face_center = Point(0.0, 0.5 * (P0.y + P1.y), 0.5 * (P0.z + P1.z))
            if normal.dot(Vector.from_start_end(centroid, face_center)) < 0:
                normal, yaxis = normal.scaled(-1.0), yaxis.scaled(-1.0)
            hx = 0.5 * (self.length + 2 * margin)
            hy = 0.5 * (slant.length + 2 * margin)
            # the large face ON the incline (bottom) and the one depth in (top),
            # corners in the same order -> co-wound.
            corners = [
                face_center - xaxis * hx - yaxis * hy,
                face_center + xaxis * hx - yaxis * hy,
                face_center + xaxis * hx + yaxis * hy,
                face_center - xaxis * hx + yaxis * hy,
            ]
            bottom = Polyline(corners + [corners[0]])
            shifted = [c - normal * depth for c in corners]
            top = Polyline(shifted + [shifted[0]])
            if self.transformation:
                bottom = bottom.transformed(self.transformation)
                top = top.transformed(self.transformation)
            pairs.append((bottom, top))
        return pairs

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

    WIDTH = 30.00  # Y, along the contact face
    BACK = 220.0  # -X, into the column
    FRONT = 265.0  # +X, into the rib (longest extent -> toward the rib)
    HEIGHT = 250.0  # -Z, downward from the top
    RADIUS = 25.0  # cylinder dowel radius
    EDGE_MARGIN_X = 6.05  # dowel centre this many radii IN from the column/rib ends (-BACK / +FRONT)
    EDGE_MARGIN_Z = 3.0  # dowel centre this many radii IN from the top/bottom (one radius less than X)

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

    def cutter_mesh(self, overshoot: float = 0.0) -> Mesh:
        """The connector box in world coordinates (for boolean cutting).

        ``overshoot`` grows the box ONLY at the top (local +Z, above ``z = 0``)
        by that amount. The box top sits at the contact's top edge, which is
        coplanar with the column/rib top face - a cutter cap exactly coplanar
        with a target face makes the mesh boolean difference unreliable (the same
        reason the dowel cylinders overshoot, see :meth:`cylinder_cutters`), so
        the top is pushed past that surface. The bottom (``z = -HEIGHT``) is a
        BLIND pocket floor buried inside the material - extending it there would
        only cut the pocket deeper than the connector, so it is left flush. The
        in-plane (X/Y) footprint is unchanged. ``overshoot=0`` returns the exact
        box (legacy behaviour).

        Parameters
        ----------
        overshoot : float
            Extra length added at the TOP cap so the cut clears the coplanar top
            face cleanly (e.g. 25). The bottom is not extended.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        if not overshoot:
            mesh = self._box.to_mesh()
        else:
            zmax = overshoot  # top grows above z = 0 to clear the coplanar top face
            zmin = -self.HEIGHT  # bottom stays flush (blind pocket floor, buried in material)
            center = Point((self.FRONT - self.BACK) * 0.5, 0.0, 0.5 * (zmax + zmin))
            box = Box(self.BACK + self.FRONT, self.WIDTH, zmax - zmin, frame=Frame(center))
            mesh = box.to_mesh()
        if self.transformation:
            mesh = mesh.transformed(self.transformation)
        return mesh

    def _dowel_grid(self) -> tuple:
        """The dowel layout - the SINGLE source the cutter holes
        (:meth:`cylinder_cutters`) and the real dowels (:meth:`cylinder_elements`)
        both read, so a hole and its dowel can never drift apart.

        Positions are taken as a fixed MARGIN IN FROM THE BOX BOUNDARIES (not
        scaled from the centre), with SEPARATE horizontal and vertical margins so
        the dowels can be inset more along the joint than over the height: the
        horizontal margin is ``EDGE_MARGIN_X * RADIUS`` and the vertical margin is
        ``EDGE_MARGIN_Z * RADIUS`` (kept one radius smaller). In the connector's
        local frame the box spans ``x in [-BACK, +FRONT]`` and ``z in [-HEIGHT,
        0]``, so:

        - column dowels sit ``mx`` in from the column end ``x = -BACK`` -> ``-BACK + mx``
        - rib dowels sit ``mx`` in from the rib end ``x = +FRONT``      -> ``+FRONT - mx``
        - the upper row sits ``mz`` below the top ``z = 0``             -> ``-mz``
        - the lower row sits ``mz`` above the bottom ``z = -HEIGHT``    -> ``-HEIGHT + mz``

        Returns
        -------
        tuple[list[tuple[str, float]], list[float]]
            ``(sides, rows)`` where ``sides`` is ``[(name, x), ...]`` and ``rows``
            is the two local-Z heights.
        """
        mx = self.EDGE_MARGIN_X * self.RADIUS
        mz = self.EDGE_MARGIN_Z * self.RADIUS
        sides = [("column", -self.BACK + mx), ("rib", self.FRONT - mx)]
        rows = [-mz, -self.HEIGHT + mz]
        return sides, rows

    def cylinder_cutters(self, length: float, overshoot: float = 25.0):
        """Cylindrical dowel cutters: two per side (column and rib).

        A cylinder sits at each of the four positions from :meth:`_dowel_grid`
        (two sides x two rows), each held in from the box boundaries by
        ``EDGE_MARGIN_X * RADIUS`` horizontally and ``EDGE_MARGIN_Z * RADIUS``
        vertically - column side near ``x = -BACK``, rib side near ``x = +FRONT``.
        Each cylinder's axis runs along the connector width
        (local Y), with the given ``length`` and radius :attr:`RADIUS`. The two
        sides carry the same vertical rows, just on opposite sides (so the
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
        sides, rows = self._dowel_grid()
        cut_length = length + 2.0 * overshoot

        def at_side(x):
            cutters = []
            for z in rows:
                frame = Frame([x, 0.0, z], [0, 0, 1], [1, 0, 0])  # cylinder axis = local +Y
                mesh = Cylinder(self.RADIUS, cut_length, frame=frame).to_mesh()
                if self.transformation:
                    mesh = mesh.transformed(self.transformation)
                cutters.append(mesh)
            return cutters

        side_x = dict(sides)
        return at_side(side_x["column"]), at_side(side_x["rib"])

    def cylinder_elements(self, length: float):
        """The four dowel cylinders as placed model elements (nominal length).

        Same positions as :meth:`cylinder_cutters` - the shared
        :meth:`_dowel_grid` (a margin in from the box boundaries, axis along
        local Y) - but at the nominal ``length`` (no cutter overshoot); these
        are the real dowels, added to the model like the wedge components.

        Parameters
        ----------
        length : float
            Cylinder length (e.g. the rib thickness).

        Returns
        -------
        list[:class:`DowelCylinderElement`]
        """
        sides, rows = self._dowel_grid()
        elements = []
        for side, x in sides:
            for j, z in enumerate(rows):
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
