from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements.element import Element
from compas_model.elements.element import Feature


class WedgeFeature(Feature):
    pass


class WedgeElement(Element):
    """Class representing a wedge connector built from a lofted triangular profile.

    The wedge is a triangular prism: the profile (a triangle in the local YZ
    plane) is copied to ``x = -HALF_WIDTH`` and ``x = +HALF_WIDTH`` and lofted
    into a closed mesh. A screw / dowel axis runs through the body along the
    local Y direction.

    Parameters
    ----------
    transformation : :class:`compas.geometry.Transformation`, optional
        Transformation applied to the wedge.
    features : list[:class:`WedgeFeature`], optional
        Features of the wedge.
    name : str, optional
        Name of the element.
    """

    # Triangular profile in the local YZ plane (x = 0).
    PROFILE = [
        Point(0, 0, -197),
        Point(0, -31.75593, 11.530606),
        Point(0, 31.75593, 11.530606),
    ]

    # The profile is copied to x = -HALF_WIDTH and x = +HALF_WIDTH, then lofted.
    HALF_WIDTH = 80.0
    # Screw / dowel axis endpoints (local coordinates).
    DOWEL_START = Point(0, -80.0, -100)
    DOWEL_END = Point(0, 80.0, -100)

    _mesh_cache: Optional[Mesh] = None
    _line_cache: Optional[Line] = None

    def build_mesh(self) -> Mesh:
        """Loft the triangular profile between x = -HALF_WIDTH and +HALF_WIDTH."""
        hw = 0.5 * self.target_length
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

    def _load_mesh(self) -> Mesh:
        if self._mesh_cache is None:
            self._mesh_cache = self.build_mesh()
        return self._mesh_cache.copy()

    def _load_line(self) -> Line:
        if self._line_cache is None:
            self._line_cache = Line(self.DOWEL_START, self.DOWEL_END)
        return self._line_cache.copy()

    @property
    def __data__(self) -> dict:
        return {
            "transformation": self.transformation,
            "target_length": self.target_length,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        transformation: Optional[Transformation] = None,
        target_length: Optional[float] = 80.0,
        features: Optional[list[WedgeFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.target_length = target_length
        self.mesh = self._load_mesh()

    @property
    def boolean_geometry(self) -> Mesh:
        """Boolean cutter mesh with transformation applied."""
        if self.transformation:
            return self.mesh.transformed(self.transformation)
        return self.mesh

    @property
    def boolean_geometries(self) -> list[Mesh]:
        """Boolean cutter meshes contributed by the wedge."""
        return [self.boolean_geometry]

    def dowel_lines(self, step=80) -> list[Line]:
        """Dowel axis lines distributed along the wedge length (local X)."""
        line = self._load_line()
        divisions = max(int(self.target_length / step), 1)
        hw = 0.5 * self.target_length
        lines = []
        for i in range(divisions):
            x = -hw + (i + 0.5) * (self.target_length / divisions)
            lines.append(line.translated(Vector(x, 0, 0)))
        return lines

    def create_dowels(self, width=20, step=80):
        """Create DowelElements positioned along the screw axes.

        Each dowel transformation composes the screw axis' local placement with
        this wedge's own transformation.

        Parameters
        ----------
        width : float
            Dowel diameter in mm.
        step : float
            Spacing used to split the wedge into multiple dowel axes.

        Returns
        -------
        list[:class:`compas_tf.joint_dowel.DowelElement`]
        """
        from compas_tf.joint_dowel import DowelElement

        dowels = []
        local_lines = self.dowel_lines(step=step)

        for local_line in local_lines:
            direction = Vector.from_start_end(local_line.start, local_line.end)
            height = direction.length
            z = direction.unitized()

            ref = Vector(1, 0, 0)
            if abs(z.dot(ref)) > 0.99:
                ref = Vector(0, 0, 1)
            x = z.cross(ref).unitized()
            y = z.cross(x).unitized()

            dowel_frame = Frame(local_line.start, x, y)
            dowel_xform = Transformation.from_frame(dowel_frame)

            if self.transformation:
                dowel_xform = self.transformation * dowel_xform

            dowels.append(DowelElement(width=width, depth=width, height=height, transformation=dowel_xform))

        return dowels

    def create_dowel(self, width=20, step=80):
        """Backward-compatible single-dowel accessor.

        Returns the first generated dowel when older callers still expect a
        single element.
        """
        dowels = self.create_dowels(width=width, step=step)
        return dowels[0] if dowels else None

    def dowel_meshes(self, width=20, step=80) -> list[Mesh]:
        """Detailed boolean meshes for all generated dowels."""
        meshes = []
        for dowel in self.create_dowels(width=width, step=step):
            mesh = dowel.compute_mesh()
            if dowel.transformation:
                mesh = mesh.transformed(dowel.transformation)
            meshes.append(mesh)
        return meshes

    def compute_elementgeometry(self, include_features: bool = False) -> Mesh:
        return self.mesh

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self.mesh.aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self.mesh.obb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*self.mesh.centroid())
