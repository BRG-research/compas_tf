import math

from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Vector
from compas.geometry import Plane
from compas.geometry import Polyline
from compas.geometry import Polygon
from compas.geometry import Line
from compas.geometry import Translation
from compas.geometry import intersection_plane_plane
from compas.geometry import intersection_line_plane
from compas_model.elements.group import Group
from compas_model.models import Model
from compas_model.models.interactiongraph import InteractionGraph
from compas_model.models.elementtree import ElementNode
from compas_model.elements import ColumnElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.plate import PlateElement

from compas_tf.floor_builder import FloorBuilder
from compas_tf.support import SupportElement
from compas_tf.solid_difference_modifier import SolidDifferenceModifier


class FloorModel(Model):
    """A timber floor model combining a Model tree with a FloorBuilder.

    Uses composition: holds a ``Model`` for the element tree
    and a ``FloorBuilder`` for the parametric geometry.

    Parameters
    ----------
    builder : :class:`FloorBuilder`
        Parametric floor geometry.
    name : str
        Name passed to the inner ``Model``.
    """ 


    @property
    def __data__(self) -> dict:
        data = {
            "transformation": self.transformation,
            "elements": self._elements,
            "materials": self._materials,
            "tree": self._tree.__data__,
            "graph": self._graph.__data__,
            "builder": self.builder.__data__,
            "story_height": self.story_height
        }
        return data

    @classmethod
    def __from_data__(cls, data: dict) -> "Model":
        model = cls(FloorBuilder.__from_data__(data["builder"]), story_height=data["story_height"])

        model._transformation = data["transformation"]
        model._elements = data["elements"]
        model._materials = data["materials"]

        for guid, element in model._elements.items():
            element.model = model

        model._graph = InteractionGraph.__from_data__(data["graph"])
        model._graph.model = model

        graphnode: int
        for graphnode in model._graph.nodes():  # type: ignore
            element = model._graph.node_element(graphnode)
            element.graphnode = graphnode

        def add(nodedata: dict, node: ElementNode) -> None:
            if "children" in nodedata:
                for childdata in nodedata["children"]:
                    name = childdata["name"]
                    guid = childdata["element"]
                    attr = childdata.get("attributes") or {}

                    element = model._elements[guid]
                    childnode = ElementNode(element=element, name=name, **attr)
                    element.treenode = childnode

                    node.add(childnode)
                    add(childdata, childnode)

        nodedata = data["tree"]["root"]
        node = model._tree.root

        add(nodedata, node)
        return model

    def __init__(self, builder, name="session", story_height=3500):
        super(FloorModel, self).__init__(name=name)
        self.builder = builder
        self.story_height = story_height

    # ------------------------------------------------------------------ #
    #  floor block
    # ------------------------------------------------------------------ #
    @staticmethod
    def _intersect_consecutive_planes(planes, reference_plane=None):
        """Find intersection points of consecutive plane pairs with a reference plane.

        Parameters
        ----------
        planes : list[:class:`compas.geometry.Plane`]
            List of planes to intersect pairwise.
        reference_plane : :class:`compas.geometry.Plane`, optional
            Plane to intersect the resulting lines with. Defaults to world XY.

        Returns
        -------
        list[:class:`compas.geometry.Point`]
            Intersection points.
        """
        if reference_plane is None:
            reference_plane = Plane.worldXY()

        intersection_points = []
        for i in range(len(planes) - 1):
            result = intersection_plane_plane(planes[i], planes[i + 1])
            if result:
                line = Line(result[0], result[1])
                pt = intersection_line_plane(line, reference_plane)
                if pt:
                    intersection_points.append(pt)
        return intersection_points
    
    def add_floor_block(self):
        """Add column blocks. """
        
        offset_planes = self.builder.compute_cut_planes(scale=self.builder.head_o, inclination=0)[3:6]
        for i in range(len(offset_planes)):
            offset_planes[i] = offset_planes[i].offset(-SherpaXL120Element.WIDTH*2)
        
        corner_end_plane0 = Plane(self.builder.end_planes[3].point, Vector.Zaxis().cross(self.builder.end_planes[3].normal)).offset(self.builder.thick*-1.5)
        corner_end_plane1 = Plane(self.builder.end_planes[0].point, Vector.Zaxis().cross(self.builder.end_planes[0].normal)).offset(self.builder.thick*1.5)
        cut_planes = [corner_end_plane1] + offset_planes + [corner_end_plane0] + self.builder.compute_cut_planes()[3:6][::-1] + [corner_end_plane1]
        
        top = Polygon(FloorModel._intersect_consecutive_planes(cut_planes, Plane.worldXY())).translated(Vector(0, 0, -self.builder.head_h))
        bottom = top.translated(Vector(0, 0, -self.builder.head_b ))

        plate = PlateElement(top=top, bottom=bottom, name="add_floor_block")
        plate.transformation = Translation.from_vector(Vector(0, 0, self.story_height))
        

        # Rotate 4 times, 90 degress
        quarters = self.find_element_with_name("quarters")
        
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            copy = plate.copy()
            copy.transformation = rot * plate.transformation
            copy.name = f"floor_block{i}"
            self.add_element(copy, parent=quarters)

    # ------------------------------------------------------------------ #
    #  column heads cuts
    # ------------------------------------------------------------------ #

    def add_column_cutter(self):
        """Add column 3 cutter per column. """


        # Columns are ordered 0..3 like the quarters (both rotated j * pi/2).
        columns = self.find_all_elements_of_type(ColumnElement)
        columns_by_index = {int(c.name.split("_")[-1]): c for c in columns}

        # Cutters
        offset_planes = self.builder.compute_cut_planes(scale=self.builder.head_o, inclination=0)[3:6]
        for i in range(len(offset_planes)):
            offset_planes[i] = offset_planes[i].offset(-SherpaXL120Element.WIDTH*2)
        
        corner_end_plane0 = Plane(self.builder.end_planes[3].point, Vector.Zaxis().cross(self.builder.end_planes[3].normal)).offset(self.builder.thick*-1.5)
        corner_end_plane1 = Plane(self.builder.end_planes[0].point, Vector.Zaxis().cross(self.builder.end_planes[0].normal)).offset(self.builder.thick*1.5)
        cut_planes = [corner_end_plane1] + offset_planes + [corner_end_plane0] + self.builder.compute_cut_planes()[3:6][::-1] + [corner_end_plane1]
        top = Polygon(FloorModel._intersect_consecutive_planes(cut_planes, Plane.worldXY())).translated(Vector(0, 0, 0))
            

        for i in range(3):
            p00 = top[i]
            p01 = top[i+1]
            p10 = top[i+1] + Vector(0, 0, -self.builder.head_b-self.builder.head_h)
            p11 = top[i] + Vector(0, 0, -self.builder.head_b-self.builder.head_h)
            v0 = (p01 - p00).unitized()
            p00 = p00 - v0 * self.builder.thick + Vector(0, 0, 10)
            p01 = p01 + v0 * self.builder.thick + Vector(0, 0, 10)
            p10 = p10 + v0 * self.builder.thick 
            p11 = p11 - v0 * self.builder.thick 

            poly0 = Polygon([p11, p10, p01, p00])
            poly1 = poly0.translated(poly0.normal * SherpaXL120Element.WIDTH * 6)
            bot_pl = Polyline(list(poly0.points) + [poly0.points[0]])
            top_pl = Polyline(list(poly1.points) + [poly1.points[0]])
            plate = PlateElement(bottom_polyline=bot_pl, top_polyline=top_pl, name="column_cutter")
            plate.transformation = Translation.from_vector(Vector(0, 0, self.story_height))
            quarters = self.find_element_with_name("quarters")

            for j in range(4):
                rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), j * math.pi / 2, Point(0, 0, 0))
                copy = plate.copy()
                copy.transformation = rot * plate.transformation
                copy.name = f"column_cutter_{i}_{j}"
                self.add_element(copy, parent=quarters)

                column = columns_by_index.get(j)
                if column is not None:
                    self.add_modifier(copy, column, SolidDifferenceModifier())
            




    # ------------------------------------------------------------------ #
    #  quarters
    # ------------------------------------------------------------------ #

    def add_quarter_floor(self, angles=None):
        """Add quarter floor elements for all quarters.

        Parameters
        ----------
        angles : list[float], optional
            Rotation angles in degrees. Default is [0, 90, 180, 270].

        Returns
        -------
        list[QuarterResult]
            Results for each quarter.
        """
        from compas_tf.quarter_floor import QuarterFloorElement

        if angles is None:
            angles = [0, 90, 180, 270]

        quarters_group = self.model.add_group("quarters")
        results = []

        for angle in angles:
            result = QuarterFloorElement.build(self.builder, angle=angle)
            quarter_group = Group(name=f"quarter_{angle}")
            self.model.add_element(quarter_group, parent=quarters_group)

            # Ribs (axes 0, 1, 2, 6)
            ribs_group = Group(name="ribs")
            self.model.add_element(ribs_group, parent=quarter_group)
            for axis_idx in [0, 1, 2, 6]:
                if axis_idx in result.axis_elements:
                    self.model.add_element(result.axis_elements[axis_idx], parent=ribs_group)

            # Boundaries (axes 3, 4, 5)
            boundaries_group = Group(name="boundaries")
            self.model.add_element(boundaries_group, parent=quarter_group)
            for axis_idx in [3, 4, 5]:
                if axis_idx in result.axis_elements:
                    self.model.add_element(result.axis_elements[axis_idx], parent=boundaries_group)

            # T-sections
            tsections_group = Group(name="tsections")
            self.model.add_element(tsections_group, parent=quarter_group)
            for element in result.tsection_elements:
                self.model.add_element(element, parent=tsections_group)

            # Surfaces
            surfaces_group = Group(name="surfaces")
            self.model.add_element(surfaces_group, parent=quarter_group)
            for element in result.surface_elements:
                self.model.add_element(element, parent=surfaces_group)

            # Corner blocks
            corners_group = Group(name="corner_blocks")
            self.model.add_element(corners_group, parent=quarter_group)
            for element in result.corner_block_elements:
                self.model.add_element(element, parent=corners_group)

            # Connectors
            connectors_group = Group(name="connectors")
            self.model.add_element(connectors_group, parent=quarter_group)
            for screw in result.screws:
                self.model.add_element(screw, parent=connectors_group)
            for dowel in result.dowels:
                self.model.add_element(dowel, parent=connectors_group)
            for strip in result.strips:
                self.model.add_element(strip, parent=connectors_group)
            for hilti in result.hilti_joints:
                self.model.add_element(hilti, parent=connectors_group)

            # Interactions
            for connector, element in result.interactions:
                self.model.add_interaction(connector, element)

            # Modifiers
            for source, target, modifier in result.modifiers:
                self.model.add_modifier(source, target, modifier)

            results.append(result)

        return results

    # ------------------------------------------------------------------ #
    #  oculus
    # ------------------------------------------------------------------ #

    def add_oculus(self):
        """Add oculus beam elements using OculusElement.build().

        Returns
        -------
        list
            The oculus elements.
        """
        from compas_tf.oculus import OculusElement

        result = OculusElement.build(self.builder)

        oculus_group = self.add_group("oculus")
        for element in result.oculus_elements:
            self.add_element(element, parent=oculus_group)

        connectors_group = Group(name="oculus_connectors")
        self.add_element(connectors_group, parent=oculus_group)
        for screw in result.screws:
            self.add_element(screw, parent=connectors_group)
        for dowel in result.dowels:
            self.add_element(dowel, parent=connectors_group)
        for strip in result.strips:
            self.add_element(strip, parent=connectors_group)

        for connector, element in result.interactions:
            self.add_interaction(connector, element)

        return result.oculus_elements

    # ------------------------------------------------------------------ #
    #  supports
    # ------------------------------------------------------------------ #

    def add_support(self, column_size=200):
        """Add 4 support elements rotated 90° around centre.

        Parameters
        ----------
        column_size : float
            Column cross-section side length in mm.
        story_height : float
            Story height in mm.
        """
        column_plan = self.builder.corner_point_column(column_size)
        base_frame = Frame([column_plan.x, column_plan.y, 0], [1, 0, 0], [0, 1, 0])
        supports_group = self.add_group("supports")
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            support = SupportElement(rot * Transformation.from_frame(base_frame))
            support.name = f"support_{i}"
            self.add_element(support, parent=supports_group)

    # ------------------------------------------------------------------ #
    #  columns
    # ------------------------------------------------------------------ #

    def add_column(self, column_size=200):
        """Add 4 column elements rotated 90° around centre.

        Parameters
        ----------
        column_size : float
            Column cross-section side length in mm.
        story_height : float
            Story height in mm.
        """
        column_plan = self.builder.corner_point_column(column_size)
        column_height = self.story_height - SupportElement.HEIGHT
        base_frame = Frame([column_plan.x, column_plan.y, SupportElement.HEIGHT], [1, 0, 0], [0, 1, 0])
        columns_group = self.add_group("columns")
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            column = ColumnElement(column_size, column_size, column_height, rot * Transformation.from_frame(base_frame), name=f"column_{i}")
            self.add_element(column, parent=columns_group)



