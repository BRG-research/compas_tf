import math

from compas.data import Data
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements.column import ColumnElement
from compas_model.elements.group import Group
from compas_model.models import Model

from compas_tf.floor_builder import FloorBuilder
from compas_tf.support import SupportElement


class FloorModel(Data):
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

    def __init__(self, builder=None, name="session"):
        super().__init__()
        self.builder = builder or FloorBuilder()
        self.model = Model(name=name)

    @property
    def __data__(self) -> dict:
        return {
            "builder": self.builder.__data__,
            "model": self.model.__data__,
            "model_name": self.model.name,
        }

    @classmethod
    def __from_data__(cls, data):
        builder = FloorBuilder.__from_data__(data["builder"])
        obj = cls(builder=builder, name=data.get("model_name", "session"))
        obj.model = Model.__from_data__(data["model"])
        obj.model.name = data.get("model_name", "session")
        return obj



    # ------------------------------------------------------------------ #
    #  supports
    # ------------------------------------------------------------------ #

    def add_support(self, column_size=200, story_height=3000):
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
        supports_group = self.model.add_group("supports")
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            support = SupportElement(rot * Transformation.from_frame(base_frame))
            support.name = f"support_{i}"
            self.model.add_element(support, parent=supports_group)

    # ------------------------------------------------------------------ #
    #  columns
    # ------------------------------------------------------------------ #

    def add_column(self, column_size=200, story_height=3000):
        """Add 4 column elements rotated 90° around centre.

        Parameters
        ----------
        column_size : float
            Column cross-section side length in mm.
        story_height : float
            Story height in mm.
        """
        column_plan = self.builder.corner_point_column(column_size)
        column_h = story_height + self.builder.height - SupportElement.HEIGHT
        base_frame = Frame([column_plan.x, column_plan.y, SupportElement.HEIGHT], [1, 0, 0], [0, 1, 0])
        columns_group = self.model.add_group("columns")
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            column = ColumnElement(column_size, column_size, column_h, rot * Transformation.from_frame(base_frame))
            column.name = f"column_{i}"
            self.model.add_element(column, parent=columns_group)


    # ------------------------------------------------------------------ #
    #  column_heads
    # ------------------------------------------------------------------ #

    def add_column_head(self, column_element=None):
        """Add column head elements using ColumnHeadElement.build().

        Parameters
        ----------
        column_element : Element, optional
            The column element for cross-element interactions.

        Returns
        -------
        tuple
            (head_element, top_element)
        """
        from compas_tf.column_head import ColumnHeadElement

        head_element, top_element, connections, interactions, modifiers = (
            ColumnHeadElement.build(self.builder, column_element=column_element)
        )

        head_group = self.model.add_group("column_heads")
        self.model.add_element(head_element, parent=head_group)
        self.model.add_element(top_element, parent=head_group)

        connectors_group = Group(name="column_head_connectors")
        self.model.add_element(connectors_group, parent=head_group)
        for conn in connections:
            self.model.add_element(conn, parent=connectors_group)

        for a, b in interactions:
            self.model.add_interaction(a, b)

        for source, target in modifiers:
            self.model.add_interaction(source, target)

        return head_element, top_element

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

        oculus_group = self.model.add_group("oculus")
        for element in result.oculus_elements:
            self.model.add_element(element, parent=oculus_group)

        connectors_group = Group(name="oculus_connectors")
        self.model.add_element(connectors_group, parent=oculus_group)
        for screw in result.screws:
            self.model.add_element(screw, parent=connectors_group)
        for dowel in result.dowels:
            self.model.add_element(dowel, parent=connectors_group)
        for strip in result.strips:
            self.model.add_element(strip, parent=connectors_group)

        for connector, element in result.interactions:
            self.model.add_interaction(connector, element)

        return result.oculus_elements

    # ------------------------------------------------------------------ #
    #  scaffolding
    # ------------------------------------------------------------------ #