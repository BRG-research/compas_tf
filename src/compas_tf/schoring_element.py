import pathlib
from typing import Optional
from typing import Union

from compas import json_load
from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Brep
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Point
from compas.geometry import Transformation
from compas.geometry import Vector

from compas_tf.element import TFElement
from compas_tf.element import TFFeature
from compas_tf.element import baked
from compas_tf.model import TFModel

# from compas_occ import brep


class Dataset(object):
    schoring_foot_0 = "schoring_foot_0.json"
    schoring_head_0 = "schoring_head_0.json"
    schoring_body_start_0 = "schoring_body_start_0.json"
    schoring_body_end_0 = "schoring_body_end_0.json"
    schoring_foot_1 = "schoring_foot_1.json"
    schoring_body_start_1 = "schoring_body_start_1.json"
    schoring_body_end_1 = "schoring_body_end_1.json"
    schoring_head_1 = "schoring_head_1.json"
    schoring_body_start_2 = "schoring_body_start_2.json"
    schoring_body_start_3 = "schoring_body_start_3.json"
    schoring_head_custom = "schoring_head_custom.json"
    schoring_vertical_body_start_0 = "schoring_vertical_body_start_0.json"
    schoring_vertical_body_start_1 = "schoring_vertical_body_start_1.json"
    schoring_vertical_body_start_2 = "schoring_vertical_body_start_2.json"
    schoring_vertical_body_start_3 = "schoring_vertical_body_start_3.json"
    schoring_vertical_body_start_4 = "schoring_vertical_body_start_4.json"
    schoring_vertical_body_start_5 = "schoring_vertical_body_start_5.json"
    schoring_vertical_body_end_0 = "schoring_vertical_body_end_0.json"
    schoring_vertical_body_end_1 = "schoring_vertical_body_end_1.json"
    schoring_vertical_body_end_2 = "schoring_vertical_body_end_2.json"
    schoring_vertical_body_end_3 = "schoring_vertical_body_end_3.json"
    schoring_vertical_body_end_4 = "schoring_vertical_body_end_4.json"
    schoring_vertical_body_end_5 = "schoring_vertical_body_end_5.json"

    @classmethod
    def select_by_type(cls, type="a", target_length=0):
        """Select dataset components by type and target length.

        This method selects appropriate SchoringElement components based on the type
        and finds the best fitting body component based on the target length.

        Parameters
        ----------
        type : str, optional
            The type of dataset to select. Currently only "a" is supported.
            Default is "a".
        target_length : float, optional
            The target length for selecting the appropriate body component.
            Default is 0.

        Returns
        -------
        list[str]
            A list of dataset filenames for the selected SchoringElement components:
            [foot, body_start, body_end, head]
        """
        if type == "a":
            dataset_group = [cls.schoring_foot_0, cls.schoring_body_start_0, cls.schoring_body_end_0, cls.schoring_head_0]

            dataset_choices = [
                cls.schoring_body_start_0,
                cls.schoring_body_start_2,
                cls.schoring_body_start_3,
            ]

            here = pathlib.Path(__file__).parent.parent.parent
            json_file = here / "data" / "SchoringElement" / dataset_group[2]
            data = json_load(json_file)
            end_length = data["extension_length"]

            indices = []
            total_lengths = []
            for idx, dataset_choice in enumerate(dataset_choices):
                here = pathlib.Path(__file__).parent.parent.parent
                json_file = here / "data" / "SchoringElement" / dataset_choice
                data = json_load(json_file)
                start_length = data["extension_length"]
                total_lengths.append(start_length + end_length)
                indices.append(idx)

            # Pair indices with their corresponding total_lengths
            paired = list(zip(indices, total_lengths))
            paired.sort(key=lambda x: x[1])
            indices, total_lengths = zip(*paired)
            indices = list(indices)
            total_lengths = list(total_lengths)

            # Chosen the one that is below the given length
            choice = 0
            for idx, total_length in enumerate(total_lengths):
                if target_length < total_length:
                    choice = indices[idx]
                    break

            # Replace the filename with the given one
            dataset_group[1] = dataset_choices[choice]

            return dataset_group


class SchoringElementFeature(TFFeature):
    pass


class SchoringElement(TFElement):
    """A single shoring component loaded from a JSON dataset file.

    Data structure
    --------------
    Each dataset is a JSON file (e.g. ``schoring_foot_0.json``) that contains:

    - ``meshes``          -- triangulated mesh geometry embedded directly (always present, used by default).
    - ``frames``          -- connection planes: ``frames[0]`` is the base attachment point,
                             ``frames[1]`` is the top attachment point (where the next element connects).
    - ``extension_length``-- the physical extension length of the component in metres (used by
                             ``Dataset.select_by_type`` to pick the right body length).
    - ``step_path``       -- absolute path to the STEP file for exact BREP geometry; only used when
                             ``geometry_as_brep=True``. The path may point to a different machine, so
                             the loader falls back to a local ``data/`` search by stem name.

    OBJ files (``schoring_*.obj``) were generated alongside the JSON files but are redundant because
    the mesh is already embedded in the JSON. They have been removed.

    Parameters
    ----------
    dataset : str, optional
        The dataset filename containing the SchoringElement component data.
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation to apply to the element.
    features : list[:class:`SchoringElementFeature`], optional
        The features of the SchoringElement element.
    name : str, optional
        The name of the SchoringElement element.
    geometry_as_brep : bool, optional
        Whether to load geometry as BREP from STEP file. Default is False.

    Attributes
    ----------
    frames : list
        List of frames from the loaded dataset.
    geometry : :class:`compas.datastructures.Mesh`
        The mesh geometry of the SchoringElement element.
    xsize : float
        The width of the element (X dimension).
    ysize : float
        The length of the element (Y dimension).
    zsize : float
        The height of the element (Z dimension).
    max_extension_length : float
        The maximum extension length from the dataset.
    """

    # Class-level cache for loaded data
    _json_cache = {}
    _brep_cache = {}
    _mesh_cache = {}

    @classmethod
    def _load_json_data(cls, dataset: str) -> dict:
        """Load JSON data from cache or file.

        Parameters
        ----------
        dataset : str
            The dataset filename.

        Returns
        -------
        dict
            The loaded JSON data.
        """
        if dataset not in cls._json_cache:
            here = pathlib.Path(__file__).parent.parent.parent
            json_file = here / "data" / "SchoringElement" / dataset
            cls._json_cache[dataset] = json_load(json_file)
        return cls._json_cache[dataset]

    @classmethod
    def _load_geometry(cls, dataset: str, data: dict, geometry_as_brep: bool):
        """Load geometry from STEP (brep) or embedded JSON mesh."""
        import os

        if geometry_as_brep:
            step_path = data.get("step_path")
            if step_path and not os.path.exists(step_path):
                local_dir = pathlib.Path(__file__).parent.parent.parent / "data" / "SchoringElement"
                stem = pathlib.Path(step_path).stem
                for ext in (".step", ".stp"):
                    candidate = local_dir / f"{stem}{ext}"
                    if candidate.exists():
                        step_path = str(candidate)
                        break
            if step_path and step_path not in cls._brep_cache:
                cls._brep_cache[step_path] = Brep.from_step(step_path)
            if step_path:
                return cls._brep_cache[step_path].copy()
        # Default: mesh embedded in JSON (already in mm)
        if dataset not in cls._mesh_cache:
            cls._mesh_cache[dataset] = data["meshes"][0]
        return cls._mesh_cache[dataset].copy()

    @classmethod
    def clear_cache(cls):
        """Clear all cached data."""
        cls._json_cache.clear()
        cls._brep_cache.clear()
        cls._mesh_cache.clear()

    @property
    def __data__(self) -> dict:
        return {
            "dataset": self.dataset,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
            "geometry_as_brep": self.geometry_as_brep,
            **self._baked_data(),
        }

    def __init__(
        self,
        dataset: str = None,
        transformation: Optional[Transformation] = None,
        features: Optional[list[SchoringElementFeature]] = None,
        name: Optional[str] = None,
        geometry_as_brep: bool = False,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        # print("Element Created: " + dataset)

        self.dataset = dataset
        self.geometry_as_brep = geometry_as_brep

        # Load JSON data from cache or file
        data = self._load_json_data(dataset)

        # Load geometry from cache or file
        self.geometry = self._load_geometry(dataset, data, geometry_as_brep)

        # Simplified: expect only COMPAS Frame objects (dict with dtype/data)
        self.frames = data["frames"]
        # Copy to prevent transformation of cached data (already in mm)
        aabb = self.geometry.aabb()
        self.xsize = aabb.xsize
        self.ysize = aabb.ysize
        self.zsize = abs(self.frames[0].point[2])
        self.max_extension_length = data["extension_length"]

    @baked
    def compute_elementgeometry(self, include_features: bool = False) -> Union[Mesh, Brep]:
        """Compute the shape of the element from the loaded geometry.
        This shape is relative to the frame of the element.

        Parameters
        ----------
        include_features : bool, optional
            If True, the features should be included in the element geometry.

        Returns
        -------
        :class:`compas.datastructures.Mesh` or :class:`compas.geometry.Brep`
            The geometry of the element.

        """
        from compas.geometry import Transformation

        if self.transformation is not None:
            if not isinstance(self.transformation, Transformation):
                print("[DEBUG] self.transformation is not a Transformation:", type(self.transformation), self.transformation)
                raise TypeError(f"self.transformation must be a Transformation or None, got {type(self.transformation)}: {self.transformation}")
            for frame in self.frames:
                frame.transform(self.transformation)
        return self.geometry

    # =============================================================================
    # Implementations of abstract methods
    # =============================================================================

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        """Compute the axis-aligned bounding box of the element.

        Parameters
        ----------
        inflate : float, optional
            Inflation factor to scale the bounding box. Default is 1.0.

        Returns
        -------
        :class:`compas.geometry.Box`
            The axis-aligned bounding box of the element.
        """
        box = self.geometry.aabb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        """Compute the oriented bounding box of the element.

        Parameters
        ----------
        inflate : float, optional
            Inflation factor to scale the bounding box. Default is 1.0.

        Returns
        -------
        :class:`compas.geometry.Box`
            The oriented bounding box of the element.
        """
        box = self.geometry.obb()
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        return box

    def compute_point(self) -> Point:
        """Compute the centroid point of the element.

        Returns
        -------
        :class:`compas.geometry.Point`
            The centroid point of the element's geometry.
        """
        return Point(*self.geometry.centroid())

    def compute_collision_mesh(self, inflate: float = 1.0) -> Mesh:
        """Compute collision mesh - use the same geometry for now."""
        return self.geometry.copy()

    def compute_surface_mesh(self, meshsize_min=None, meshsize_max=None) -> Mesh:
        """Compute surface mesh - use the same geometry for now."""
        return self.geometry.copy()

    def compute_volumetric_mesh(self, meshsize_min=None, meshsize_max=None):
        """Compute volumetric mesh - not implemented for surface meshes."""
        raise NotImplementedError("Volumetric mesh not supported for surface geometry")

    # =============================================================================
    # Configurators
    # =============================================================================

    @staticmethod
    def from_points_and_vectors(
        p0: Point = Point(0, 0, 2500),
        v0: Vector = Vector(0, 0, 1),
        p1: Point = Point(2500, 0, 0),
        v1: Vector = Vector(1, 0, 0),
        dataset_foot: str = Dataset.schoring_foot_0,
        dataset_head: str = Dataset.schoring_head_0,
        dataset_body0: str = Dataset.schoring_body_start_0,
        dataset_body1: str = Dataset.schoring_body_end_0,
        dataset_hat: str = None,
        geometry_as_brep: bool = False,
    ):
        """Create SchoringElement instances for foot and head from given points and vectors."""

        # =============================================================================
        # Feet elements
        # =============================================================================
        foot0 = SchoringElement(dataset_foot, geometry_as_brep=geometry_as_brep, transformation=Transformation.from_frame(Frame(p0, v0, Vector.cross(v0, -(p1 - p0)))))
        foot1 = SchoringElement(dataset_head, geometry_as_brep=geometry_as_brep, transformation=Transformation.from_frame(Frame(p1, v1, Vector.cross(v1, (p1 - p0)))))

        # =============================================================================
        # Intermediate transformations, frames and direction
        # =============================================================================
        xform0 = foot0.transformation * Transformation.from_frame(foot0.frames[0])
        xform1 = foot1.transformation * Transformation.from_frame(foot1.frames[0])
        frame0 = Frame.worldXY().transformed(xform0)
        frame1 = Frame.worldXY().transformed(xform1)
        direction = frame1.point - frame0.point

        # =============================================================================
        # Body elements
        # =============================================================================

        # Elements
        body0 = SchoringElement(dataset_body0, geometry_as_brep=geometry_as_brep)
        body1 = SchoringElement(dataset_body1, geometry_as_brep=geometry_as_brep)

        # Transformations
        body0_frame = Frame(frame0.point, frame0.yaxis, direction.cross(frame0.yaxis))
        body1_frame = Frame(frame1.point - body0_frame.zaxis * body1.frames[0].point[2], frame0.yaxis, direction.cross(frame0.yaxis))

        # Apply transformations
        body0.transformation = Transformation.from_frame(body0_frame)
        body1.transformation = Transformation.from_frame(body1_frame)

        # =============================================================================
        # Additional element on the head
        # =============================================================================

        if dataset_hat:
            hat = SchoringElement(dataset_hat, geometry_as_brep=geometry_as_brep, transformation=Transformation.from_frame(Frame(p1, v1, Vector.cross(v1, -(p1 - p0)))))

        # =============================================================================
        # Model
        # =============================================================================
        model = TFModel("scaffolding")
        scaffolding = model.add_group("scaffolding")
        model.add_element(foot0, scaffolding)
        model.add_element(foot1, scaffolding)
        model.add_element(body0, scaffolding)
        model.add_element(body1, scaffolding)
        if dataset_hat:
            model.add_element(hat, scaffolding)
        model.transformation = Transformation()

        return model

    @staticmethod
    def from_points_and_vectors_no_foot_no_head(
        p0: Point = Point(0, 0, 2500),
        v0: Vector = Vector(0, 0, 1),
        p1: Point = Point(2500, 0, 0),
        v1: Vector = Vector(1, 0, 0),
        dataset_body0: str = Dataset.schoring_body_start_0,
        dataset_body1: str = Dataset.schoring_body_end_0,
        dataset_hat: str = None,
        geometry_as_brep: bool = False,
    ):
        """Create SchoringElement instances for foot and head from given points and vectors."""

        # =============================================================================
        # Intermediate transformations, frames and direction
        # =============================================================================
        footframe = Frame(p0, v0, Vector.cross(v0, -(p1 - p0)))
        headframe = Frame(p1, v1, Vector.cross(v1, (p1 - p0)))
        xform0 = Transformation.from_frame(footframe)
        xform1 = Transformation.from_frame(headframe)
        frame0 = Frame.worldXY().transformed(xform0)
        frame1 = Frame.worldXY().transformed(xform1)
        direction = frame1.point - frame0.point

        # =============================================================================
        # Body elements
        # =============================================================================

        # Elements
        body0 = SchoringElement(dataset_body0, geometry_as_brep=geometry_as_brep)
        body1 = SchoringElement(dataset_body1, geometry_as_brep=geometry_as_brep)

        # Transformations
        body0_frame = Frame(frame0.point, frame0.yaxis, direction.cross(frame0.yaxis))
        body1_frame = Frame(frame1.point - body0_frame.zaxis * body1.frames[0].point[2], frame0.yaxis, direction.cross(frame0.yaxis))

        # Apply transformations
        body0.transformation = Transformation.from_frame(body0_frame)
        body1.transformation = Transformation.from_frame(body1_frame)

        # =============================================================================
        # Additional element on the head
        # =============================================================================

        if dataset_hat:
            hat = SchoringElement(dataset_hat, geometry_as_brep=geometry_as_brep, transformation=Transformation.from_frame(Frame(p1, v1, Vector.cross(v1, -(p1 - p0)))))

        # =============================================================================
        # Model
        # =============================================================================
        model = TFModel("scaffolding")
        scaffolding = model.add_group("scaffolding")
        model.add_element(body0, scaffolding)
        model.add_element(body1, scaffolding)
        if dataset_hat:
            model.add_element(hat, scaffolding)
        model.transformation = Transformation()

        return model

    @staticmethod
    def polylines_to_models(lines_unordered, geometry_as_brep=False):
        """Create a SchoringElement model from a list of lines."""

        # Orient lines vertically
        lines = []
        for ln in lines_unordered:
            if ln[0][2] > ln[1][2]:
                lines.append(Line(ln[1], ln[0]))
            else:
                lines.append(ln)

        # Try to get the x and y axes
        xaxis = Vector(1, 0, 0)
        yaxis = Vector(0, 1, 0)

        if len(lines) > 2:
            return
        elif len(lines) == 2:
            xaxis = lines[1][0] - lines[0][0]
            yaxis = Vector.Zaxis().cross(xaxis)
        else:
            direction = lines[0].direction
            if direction[0] != 0 or direction[1] != 0:
                xaxis = Vector(direction[0], direction[1], 0)
                yaxis = Vector.Zaxis().cross(xaxis)

        # SchoringElement prop parts - without transformation
        model = TFModel("scaffolding")

        groups = []
        for i in range(len(lines)):
            filenames = Dataset.select_by_type("a", lines[i].length)
            # return
            foot = SchoringElement(filenames[0], geometry_as_brep=geometry_as_brep)
            body_start = SchoringElement(filenames[1], geometry_as_brep=geometry_as_brep)
            body_end = SchoringElement(filenames[2], geometry_as_brep=geometry_as_brep)
            head = SchoringElement(filenames[3], geometry_as_brep=geometry_as_brep)

            if i == 0:
                groups.append([foot, body_start, body_end, head])
            else:
                groups.append([foot, body_start, body_end])

        for group in groups:
            model.add_elements(group)

        for idx, group in enumerate(groups):
            foot = group[0]
            body_start = group[1]
            body_end = group[2]
            head = groups[0][3]

            # Target frames
            frame_source = Frame(lines[idx].start, xaxis, yaxis)
            line = Line(lines[idx].start, lines[idx].end)

            frame_target = Frame(line.end, frame_source.xaxis, -frame_source.yaxis)
            xform_frame_source = Transformation.from_frame(frame_source)
            xform_frame_target = Transformation.from_frame(frame_target)

            # Transformation to local foot0 and head0 frames
            frame_source_id = idx
            frame_target_id = idx
            xform_base = Transformation.from_frame(foot.frames[frame_source_id])
            xform_end = Transformation.from_frame(head.frames[frame_target_id])
            xform_base = xform_frame_source * xform_base
            xform_end = xform_frame_target * xform_end

            # Get telescopic prop orientation
            base_point = Point(xform_base.matrix[0][3], xform_base.matrix[1][3], xform_base.matrix[2][3])
            end_point = Point(xform_end.matrix[0][3], xform_end.matrix[1][3], xform_end.matrix[2][3])
            direction = end_point - base_point
            body_start_frame_no_rotation = Frame.worldXY().transformed(xform_base)
            body_start_frame = Frame(base_point, body_start_frame_no_rotation.yaxis, direction.cross(body_start_frame_no_rotation.yaxis))
            xform_body_start = Transformation.from_frame(body_start_frame)

            # Get the second telescopic prop orientation
            body_end_frame = Frame(
                end_point - body_start_frame.zaxis * body_end.frames[0].point[2], body_start_frame_no_rotation.yaxis, direction.cross(body_start_frame_no_rotation.yaxis)
            )
            xform_body_end = Transformation.from_frame(body_end_frame)

            # Apply transformations
            foot.transformation = xform_frame_source
            body_start.transformation = xform_body_start
            body_end.transformation = xform_body_end
            head.transformation = xform_frame_target

        return model
