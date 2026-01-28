import math
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Line
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Reflection
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Vector
from compas.geometry import intersection_line_plane
from compas.geometry import intersection_polyline_plane
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PolylineLoft


class ColumnHeadFeature(Feature):
    pass


class ColumnHeadElement(Element):
    """Class representing a column head element.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry of the column head.
    transformation : :class:`compas.geometry.Transformation`, optional
        The transformation of the column head.
    features : list[:class:`ColumnHeadFeature`], optional
        The features of the column head.
    name : str, optional
        The name of the column head.

    Attributes
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh geometry.
    """

    @property
    def __data__(self) -> dict:
        return {
            "mesh": self.mesh,
            "transformation": self.transformation,
            "features": self._features,
            "name": self.name,
        }

    def __init__(
        self,
        mesh: Mesh = None,
        transformation: Optional[Transformation] = None,
        features: Optional[list[ColumnHeadFeature]] = None,
        name: Optional[str] = None,
    ):
        super().__init__(transformation=transformation, features=features, name=name)
        self.mesh = mesh if mesh else Mesh()

    def compute_elementgeometry(self, include_features=False) -> Mesh:
        return self.mesh

    def compute_aabb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.aabb
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._aabb = box
        return box

    def compute_obb(self, inflate: float = 1.0) -> Box:
        box = self.modelgeometry.obb
        if inflate != 1.0:
            box.xsize *= inflate
            box.ysize *= inflate
            box.zsize *= inflate
        self._obb = box
        return box

    def compute_point(self) -> Point:
        return Point(*self.modelgeometry.centroid())

    @property
    def base_frame(self) -> Frame:
        """Get the base frame at the leftmost bottommost corner of the mesh bounding box.

        The frame is computed from untransformed geometry and then transformed.

        Returns
        -------
        :class:`compas.geometry.Frame`
            Frame at bottom left corner of mesh with Z-axis pointing up.
        """
        # Use untransformed mesh, then apply transformation
        aabb = self.mesh.aabb()
        bottom_left = Point(aabb.xmin, aabb.ymin, aabb.zmin)
        frame = Frame(bottom_left, Vector.Xaxis(), Vector.Yaxis())
        if self.transformation:
            frame.transform(self.transformation)
        return frame

    @staticmethod
    def build(builder, column_element=None):
        """Build column head geometry from FloorBuilder data.

        Parameters
        ----------
        builder : FloorBuilder
            The floor builder containing geometry parameters.
        column_element : Element, optional
            The column element to connect screws to.

        Returns: (head_element, top_element, connections, interactions, modifiers)
        """

        #############################################################################################
        # Transformation to origin
        #############################################################################################

        xform = Translation.from_vector([builder.size+builder.beam_w/2, builder.size+builder.beam_w/2, 0])        

        #############################################################################################
        # Bottom block
        #############################################################################################

        pts, pts_offset = builder.column_head_points
        corner = builder.corner_point
        _end_planes = builder.end_planes  # noqa: F841
        head_h = builder.head_h
        beam_w = builder.beam_w
        height = builder.height

        # Column head the bottom height is the intersection between parabola and the cut plane
        parabola = builder.rib_parabolas[0]  # First boundary parabola
        cut_plane = builder.cut_planes[3]  # First cut plane
        result = intersection_polyline_plane(parabola,cut_plane, 1)
        head_bottom = result[0][2]


        plane_top = Plane([0, 0, -head_h], Vector.Zaxis())
        plane_bottom = Plane([0, 0, head_bottom], Vector.Zaxis())

        top_pts = [Point(*intersection_line_plane(Line(pts[i], pts_offset[i]), plane_top)) for i in range(4)]
        bottom_pts = [Point(*intersection_line_plane(Line(pts[i], pts_offset[i]), plane_bottom)) for i in range(4)]

        polyline_top = Polyline(top_pts).extended([beam_w, beam_w])
        polyline_bottom = Polyline(bottom_pts).extended([beam_w, beam_w])

        direction = -polyline_top.lines[0].direction * beam_w + polyline_bottom.lines[-1].direction * beam_w
        corner = direction + corner

        for poly, z_off in [(polyline_top, -head_h), (polyline_bottom, head_bottom)]:
            poly.append(Vector(0, 0, z_off) + corner)
            poly.points = poly.points[-1:] + poly.points[:-1]
            poly.append(poly[0])

        # Bottom rectangle
        taper = polyline_bottom.translated(Vector(0, 0, -(height + head_bottom)))
        xaxis = taper.lines[0].direction * beam_w
        yaxis = taper.lines[-1].direction * beam_w
        center = taper[0]
        taper = Polyline([center, center + xaxis, center + xaxis - yaxis * 0.99, center + xaxis * 0.99 - yaxis, center - yaxis, center])

        head_mesh = PolylineLoft.multiple_to_mesh([taper, polyline_bottom, polyline_top])
        head_mesh.transform(xform)
        # Transform polylines for PlateElement
        _head_top_polyline = polyline_top.transformed(xform)  # noqa: F841
        _head_bottom_polyline = taper.transformed(xform)  # noqa: F841

        #############################################################################################
        # Top block
        #############################################################################################

        top = Polyline(builder.top_corner_block_points + [builder.top_corner_block_points[0]])
        bottom = top.translated(Vector(0, 0, -head_h))
        top_mesh = PolylineLoft.to_mesh(bottom, top, True)
        top_mesh.transform(xform)
        # Transform polylines for PlateElement
        _top_top_polyline = top.transformed(xform)  # noqa: F841
        _top_bottom_polyline = bottom.transformed(xform)  # noqa: F841

        #############################################################################################
        # Joints
        #############################################################################################

        # 4x screws column-head-bottom - column
        screw_frames = []
        origin = Point(-builder.size - builder.beam_w / 2, -builder.size - builder.beam_w / 2, -builder.head_h)
        offset = 40
        corner_offsets = [(-1, -1), (1, -1), (1, 1), (-1, 1)]
        
        for sx, sy in corner_offsets:
            x = sx * (builder.beam_w / 2 - offset)
            y = sy * (builder.beam_w / 2 - offset)
            frame = Frame(origin + Vector(x, y, 0), -Vector.Xaxis(), Vector.Yaxis())
            screw_frames.append(frame)

        # 4x inclined screws - within column-head-bottom (along taper edge)
        taper_point0 = taper[1]
        taper_point1 = polyline_bottom[1]
        taper_point_025 = taper_point0 + 0.2 * (taper_point1 - taper_point0)
        taper_point_075 = taper_point0 + 0.8 * (taper_point1 - taper_point0)

        frame0 = Frame(Vector.Yaxis()*builder.beam_w / 2 + taper_point_025, taper_point1 - taper_point0, -Vector.Xaxis().cross(taper_point1 - taper_point0))
        screw_frames.append(frame0)
        frame1 = Frame(Vector.Yaxis()*builder.beam_w / 2 + taper_point_075, taper_point1 - taper_point0, -Vector.Xaxis().cross(taper_point1 - taper_point0))
        screw_frames.append(frame1)
        # OPTIONAL
        # frame2 = Frame(Vector.Yaxis()*builder.beam_w / 2 + taper_point_075 + Vector.Yaxis()*(builder.beam_w+builder.thick),  # noqa: E501
        #     taper_point1 - taper_point0, -Vector.Xaxis().cross(taper_point1 - taper_point0))
        # screw_frames.append(frame2)

        diagonal_plane = Plane(origin, Vector(1, -1, 0))
        reflection = Reflection.from_plane(diagonal_plane)
        frame0_reflected = frame0.transformed(reflection)
        frame1_reflected = frame1.transformed(reflection)
        
        screw_frames.append(Frame(frame0_reflected.point, -frame0_reflected.xaxis, frame0_reflected.yaxis))
        screw_frames.append(Frame(frame1_reflected.point, -frame1_reflected.xaxis, frame1_reflected.yaxis))
        # OPTIONAL
        # frame2_reflected = frame2.transformed(reflection)
        # frame2_reflected_flipped = Frame(frame2_reflected.point, -frame2_reflected.xaxis, frame2_reflected.yaxis)
        # screw_frames.append(frame2_reflected_flipped)

        # OPTIONAL Average frame between frame2 and frame2_reflected_flipped
        # avg_origin = Point((frame2.point.x + frame2_reflected_flipped.point.x) / 2,  # noqa: E501
        #     (frame2.point.y + frame2_reflected_flipped.point.y) / 2, (frame2.point.z + frame2_reflected_flipped.point.z) / 2)
        # avg_frame = Frame(avg_origin, Vector.Xaxis(), Vector.Yaxis())
        # screw_frames.append(avg_frame)

        # 1x connector - collumn-head-bottom - collumn-head-top
        connector_frame = Frame(origin)

        # 1x screw - collumn-head-bottom - connector
        origin = Point(-builder.size - builder.beam_w / 2, -builder.size - builder.beam_w / 2, -builder.height)
        screw_frames.append(Frame(origin, Vector.Xaxis(), Vector.Yaxis()))

        # 2x screws - column-head-top - connector
        screw_diameter = 8
        origin_side = Point(-builder.size - builder.beam_w, -builder.size - builder.beam_w/2 - screw_diameter, -builder.head_h+40-screw_diameter)
        screw_frames.append(Frame(origin_side, -Vector.Zaxis(), Vector.Yaxis()))
        screw_frames.append(screw_frames[-1].rotated(math.pi/2, Vector.Zaxis(), origin).translated(Vector(0, 0, +screw_diameter)))

        # 3x sherpaXL120 - column-head-top
        sherpa_frames = []
        for i in range(3):
            p1 = top[i+1]
            p0 = top[i]
            frame = Frame((p0+p1)*0.5, p1 - p0, Vector.Zaxis().cross(p1 - p0))
            sherpa_frames.append(frame)







        #############################################################################################
        # Create the elements
        #############################################################################################
        head_element = ColumnHeadElement(mesh=head_mesh, name="column_head")
        top_element = ColumnHeadElement(mesh=top_mesh, name="column_head_top")

        from compas_tf.joint_connector import ConnectorElement
        from compas_tf.joint_screw import ScrewElement
        from compas_tf.joint_sherpaxl120 import SherpaXL120Element

        

        screws = [
            ScrewElement(transformation=xform * Transformation.from_frame(frame), name=f"screw_columnhead_{i}")
            for i, frame in enumerate(screw_frames)
        ]
        
        connector = ConnectorElement(transformation=xform * Transformation.from_frame(connector_frame), name="connector_columnhead")
        
        sherpas = []
        for i, frame in enumerate(sherpa_frames):
            sherpa = SherpaXL120Element(transformation=xform * Transformation.from_frame(frame), name=f"sherpaxl120_columnhead_{i}")
            sherpas.append(sherpa)

        connections = screws + [connector] + sherpas

        #############################################################################################
        # Create interactions
        #############################################################################################
        interactions = []
        interactions.append((connector, head_element))
        interactions.append((connector, top_element))
        for sherpa in sherpas:
            interactions.append((sherpa, top_element))

        # Screw interactions by index ranges
        SCREWS_HEAD_COLUMN = slice(0, 4)       # 4x screws column-head-bottom - column
        SCREWS_HEAD_INCLINED = slice(4, 8)     # 4x inclined screws within column-head-bottom
        SCREW_HEAD_CONNECTOR = 8               # 1x screw column-head-bottom - connector
        SCREWS_TOP_CONNECTOR = slice(9, 11)    # 2x screws column-head-top - connector

        for screw in screws[SCREWS_HEAD_COLUMN]:
            interactions.append((screw, head_element))
            if column_element is not None:
                interactions.append((screw, column_element))

        for screw in screws[SCREWS_HEAD_INCLINED]:
            interactions.append((screw, head_element))
            # Note: These screws are entirely within head_element (along taper edge),
            # they do NOT connect to top_element

        # Screw-connector interactions (previously modifiers)
        interactions.append((screws[SCREW_HEAD_CONNECTOR], head_element))
        interactions.append((screws[SCREW_HEAD_CONNECTOR], connector))

        for screw in screws[SCREWS_TOP_CONNECTOR]:
            interactions.append((screw, top_element))
            interactions.append((screw, connector))

        modifiers = []

        return head_element, top_element, connections, interactions, modifiers