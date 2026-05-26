from pathlib import Path
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
    """Class representing a wedge connector loaded from an OBJ file.

    The OBJ contains two objects: a wedge mesh and a line (bspline deg 1)
    representing the dowel axis. Both are loaded and cached.

    Parameters
    ----------
    transformation : :class:`compas.geometry.Transformation`, optional
        Transformation applied to the wedge.
    features : list[:class:`WedgeFeature`], optional
        Features of the wedge.
    name : str, optional
        Name of the element.
    """

    DATA_DIR = Path(__file__).parent.parent.parent / "data" / "Wedge"
    MESH_FILE = "wedge_minimal.obj"
    BOOLEAN_FILE = "wedge_boolean.obj"

    _mesh_cache: Optional[Mesh] = None
    _boolean_cache: Optional[Mesh] = None
    _line_cache: Optional[Line] = None
    _parsed: bool = False

    @staticmethod
    def _clean_mesh(mesh: Mesh) -> Mesh:
        face_verts = set()
        for f in mesh.faces():
            face_verts.update(mesh.face_vertices(f))
        for v in set(mesh.vertices()) - face_verts:
            mesh.delete_vertex(v)
        return mesh

    @classmethod
    def _parse_obj(cls):
        """Parse OBJ once: extract visual mesh, boolean mesh, and curve line."""
        if cls._parsed:
            return
        cls._mesh_cache = cls._clean_mesh(Mesh.from_obj(cls.DATA_DIR / cls.MESH_FILE))
        cls._boolean_cache = cls._clean_mesh(Mesh.from_obj(cls.DATA_DIR / cls.BOOLEAN_FILE))

        vertices = []
        curve_indices = None
        with open(cls.DATA_DIR / cls.MESH_FILE) as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("v "):
                    parts = line.split()
                    vertices.append(Point(float(parts[1]), float(parts[2]), float(parts[3])))
                elif line.startswith("curv "):
                    parts = line.split()
                    curve_indices = [int(p) for p in parts[3:]]

        if curve_indices and len(curve_indices) >= 2:
            p0 = vertices[curve_indices[0] - 1]
            p1 = vertices[curve_indices[1] - 1]
            cls._line_cache = Line(p0, p1)

        cls._parsed = True

    @classmethod
    def _load_mesh(cls) -> Mesh:
        cls._parse_obj()
        return cls._mesh_cache.copy()

    @classmethod
    def _load_boolean_mesh(cls) -> Mesh:
        cls._parse_obj()
        return cls._boolean_cache.copy()

    @classmethod
    def _load_line(cls) -> Optional[Line]:
        cls._parse_obj()
        return cls._line_cache

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
        features: Optional[list[WedgeFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.mesh = self._load_mesh()
        self._boolean_mesh = self._load_boolean_mesh()

    @property
    def boolean_geometry(self) -> Mesh:
        """Boolean cutter mesh (from wedge_boolean.obj) with transformation applied."""
        if self.transformation:
            return self._boolean_mesh.transformed(self.transformation)
        return self._boolean_mesh

    @property
    def dowel_line(self) -> Optional[Line]:
        """The dowel axis line in local coordinates."""
        return self._load_line()

    def create_dowel(self, width=20):
        """Create a DowelElement positioned along the OBJ curve line.

        The dowel's transformation composes the line's local placement
        with this wedge's own transformation.

        Parameters
        ----------
        width : float
            Dowel diameter in mm.

        Returns
        -------
        :class:`compas_tf.joint_dowel.DowelElement` or None
        """
        from compas_tf.joint_dowel import DowelElement

        local_line = self._load_line()
        if local_line is None:
            return None

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

        return DowelElement(width=width, depth=width, height=height, transformation=dowel_xform)

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
