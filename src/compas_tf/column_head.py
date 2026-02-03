from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Box
from compas.geometry import Frame
from compas.geometry import Plane
from compas.geometry import Point
from compas.geometry import Polyline
from compas.geometry import Transformation
from compas.geometry import Translation
from compas.geometry import Vector
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.geometry import PlaneIntersect
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
    def build(builder, column_element=None, block_height=100):
        """Build column head geometry from FloorBuilder data.

        Parameters
        ----------
        builder : FloorBuilder
            The floor builder containing geometry parameters.
        column_element : Element, optional
            The column element to connect screws to.

        Returns: (head_element, top_element, connections, interactions, modifiers)
        """
        from compas_tf.joint_sherpaxl120 import SherpaXL120Element
        connection_width = SherpaXL120Element.WIDTH

        #############################################################################################
        # Transformation to origin
        #############################################################################################

        xform = Translation.from_vector([builder.size+builder.beam_w/2, builder.size+builder.beam_w/2, 0])        

        #############################################################################################
        # Bottom block
        #############################################################################################

        pts, pts_offset = builder.column_head_points  # noqa: F841
        _corner = builder.corner_point  # noqa: F841
        _end_planes = builder.end_planes  # noqa: F841
        _head_h = builder.head_h  # noqa: F841
        _beam_w = builder.beam_w  # noqa: F841
        _height = builder.height  # noqa: F841



        corner_end_plane0 = Plane(builder.end_planes[3].point, Vector.Zaxis().cross(builder.end_planes[3].normal)).offset(builder.thick*-1.5)
        corner_end_plane1 = Plane(builder.end_planes[0].point, Vector.Zaxis().cross(builder.end_planes[0].normal)).offset(builder.thick*1.5)
        offset_planes = builder.compute_cut_planes(scale=builder.head_o, inclination=0)[3:6]
        for i in range(len(offset_planes)):
            offset_planes[i] = offset_planes[i].offset(-connection_width)
        cut_planes = [corner_end_plane1] + offset_planes + [corner_end_plane0] + builder.compute_cut_planes()[3:6][::-1] + [corner_end_plane1]
        top = Polyline(PlaneIntersect.intersect_consecutive_planes(cut_planes, Plane.worldXY())).translated(Vector(0, 0, -builder.head_h))
        bottom = top.translated(Vector(0, 0, -builder.head_b ))


        # top = Polyline(builder.top_corner_block_points + [builder.top_corner_block_points[0]])
        
        head_mesh = PolylineLoft.to_mesh(bottom, top, True)
        head_mesh.transform(xform)
        # Transform polylines for PlateElement
        _head_top_polyline = top.transformed(xform)  # noqa: F841
        _head_bottom_polyline = bottom.transformed(xform)  # noqa: F841

        #############################################################################################
        # Top block
        #############################################################################################
        corner_end_plane0 = Plane(builder.end_planes[3].point, Vector.Zaxis().cross(builder.end_planes[3].normal)).offset(builder.thick*-1.5)
        corner_end_plane1 = Plane(builder.end_planes[0].point, Vector.Zaxis().cross(builder.end_planes[0].normal)).offset(builder.thick*1.5)
        offset_planes = builder.compute_cut_planes(scale=builder.head_o, inclination=0)[3:6]
        for i in range(len(offset_planes)):
            offset_planes[i] = offset_planes[i].offset(-connection_width)
        cut_planes = [corner_end_plane1] + offset_planes + [corner_end_plane0, corner_end_plane1]
        top = Polyline(PlaneIntersect.intersect_consecutive_planes(cut_planes, Plane.worldXY()))


        # top = Polyline(builder.top_corner_block_points + [builder.top_corner_block_points[0]])
        bottom = top.translated(Vector(0, 0, -builder.head_h-builder.head_b))
        top_mesh = PolylineLoft.to_mesh(bottom, top, True)
        top_mesh.transform(xform)
        # Transform polylines for PlateElement
        _top_top_polyline = top.transformed(xform)  # noqa: F841
        _top_bottom_polyline = bottom.transformed(xform)  # noqa: F841

        #############################################################################################
        # Joints
        #############################################################################################

        # 2x horizontal screws - column-head-top (parallel to XY plane)
        # Placed symmetrically about the diagonal: one into -X face, one into -Y face
        screw_frames = []
        screw_diameter = 8
        for i in range(2):
            origin = Point(
                -builder.size- builder.thick*1,
                -builder.size- builder.thick*(-2.75+i*3),
                -builder.head_h - builder.head_b)
            z = -builder.head_h - builder.head_b * 0.5 - screw_diameter
            # Screw 1: on -X face, extends in +X
            screw_frames.append(Frame(Point(origin.x-screw_diameter, origin.y, z+screw_diameter*0.5), -Vector.Zaxis(), Vector.Yaxis()))
            screw_frames.append(Frame(Point(origin.y, origin.x-screw_diameter, z-screw_diameter*0.5), Vector.Zaxis(), screw_frames[-1].zaxis))


        # 3x sherpaXL120 - column-head-top
        sherpa_frames = []
        for i in range(3):
            p1 = top[i+1]
            p0 = top[i]
            midpoint = (p0 + p1) * 0.5

            if i == 0 or i == 2:
                direction = (p1 - p0).unitized()
                length = (p1 - p0).length*0.5 - 80*0.5
                direction = direction * length if i == 2 else direction * -length
                midpoint = direction + midpoint 



            frame = Frame(midpoint, p0 - p1, -Vector.Zaxis().cross(p1 - p0))
            # frame = Frame(midpoint, p1 - p0, Vector.Zaxis().cross(p1 - p0))

            # frame.translate(Vector(0, 0, -15))
            sherpa_frames.append(frame)







        #############################################################################################
        # Create the elements
        #############################################################################################
        head_element = ColumnHeadElement(mesh=head_mesh, name="column_head")
        top_element = ColumnHeadElement(mesh=top_mesh, name="column_head_top")

        from compas_tf.joint_screw import ScrewElement

        

        screws = [
            ScrewElement(transformation=xform * Transformation.from_frame(frame), name=f"screw_columnhead_{i}")
            for i, frame in enumerate(screw_frames)
        ]
        
        sherpas = []
        for i, frame in enumerate(sherpa_frames):
            depth = 120 if i == 1 else 80
            sherpa = SherpaXL120Element(depth=depth, transformation=xform * Transformation.from_frame(frame), name=f"sherpaxl120_columnhead_{i}")
            sherpas.append(sherpa)

        connections = screws + sherpas

        #############################################################################################
        # Create interactions
        #############################################################################################
        interactions = []
        if column_element is not None:
            for sherpa in sherpas:
                interactions.append((sherpa, column_element))

        # 2x horizontal screws connect to head_element, top_element, and column
        for screw in screws:
            interactions.append((screw, head_element))
            interactions.append((screw, top_element))
            if column_element is not None:
                interactions.append((screw, column_element))

        modifiers = []
        if column_element is not None:
            modifiers.append((top_element, column_element))

        return head_element, top_element, connections, interactions, modifiers