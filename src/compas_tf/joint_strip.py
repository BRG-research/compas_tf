from typing import Optional

from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas_model.elements import Element


class AlignmentStripElement(Element):
    """Class representing an alignment strip connector as a rectangle polyline.

    The strip is a rectangle in the YZ plane (depth x height), centered at origin.

    Parameters
    ----------
    depth : float
        The depth of the strip (Y-axis).
    height : float
        The height of the strip (Z-axis).
    frame : :class:`compas.geometry.Frame`, optional
        Local frame of the rectangle. Defaults to WorldXY.
    transformation : :class:`compas.geometry.Transformation`, optional
        Transformation applied to the connector.
    name : str, optional
        Name of the element.
    """

    @property
    def __data__(self) -> dict:
        return {
            "depth": self._depth,
            "height": self._height,
            "frame": self._frame,
            "transformation": self.transformation,
            "name": self.name,
        }

    def __init__(
        self,
        depth: float = 20.0,
        height: float = 200.0,
        frame: Optional[Frame] = None,
        transformation: Optional[Transformation] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=None, name=name)
        self._depth = depth
        self._height = height
        self._frame = frame or Frame.worldXY()

    @property
    def depth(self) -> float:
        return self._depth

    @property
    def height(self) -> float:
        return self._height

    @property
    def frame(self) -> Frame:
        return self._frame

    def compute_elementgeometry(self, include_features=False) -> Polyline:
        """Create a rectangle polyline in the YZ plane centered at frame origin.

        Returns
        -------
        :class:`compas.geometry.Polyline`
            Rectangle with depth (Y) and height (Z) dimensions.
        """
        d = self._depth / 2
        h = self._height / 2
        # Rectangle in YZ plane, centered at origin
        points = [
            Point(0, -d, -h),
            Point(0, d, -h),
            Point(0, d, h),
            Point(0, -d, h),
            Point(0, -d, -h),  # Close the rectangle
        ]
        polyline = Polyline(points)
        # Transform to frame
        polyline.transform(Transformation.from_frame(self._frame))
        return polyline

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        polyline = self.modelgeometry
        points = list(polyline.points)
        box = Box.from_bounding_box(points)
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        # For a planar rectangle, OBB is same as AABB in local frame
        return self.compute_aabb(inflate)

    def compute_collision_mesh(self, inflate: float = 1.0):
        raise NotImplementedError

    def compute_point(self) -> Point:
        polyline = self.modelgeometry
        # Centroid of rectangle is the average of first 4 points (excluding closing point)
        pts = list(polyline.points)[:4]
        return Point(
            sum(p.x for p in pts) / 4,
            sum(p.y for p in pts) / 4,
            sum(p.z for p in pts) / 4,
        )
