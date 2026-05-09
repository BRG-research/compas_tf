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
from compas.geometry import intersection_line_line
from compas_model.elements.group import Group
from compas_model.models import Model
from compas_model.models.interactiongraph import InteractionGraph
from compas_model.models.elementtree import ElementNode
from compas_model.elements import ColumnElement
from compas_tf.joint_dowel import DowelElement
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
    #  floor guide (plates + sherpas)
    # ------------------------------------------------------------------ #

    def add_floor_guide(self, guide, column_index=0, transformation=None, include_oculus=True):
        """Add all FloorGuide plate elements and sherpas to the model.

        Follows the element sequence of example_2_floorguide.py: beds,
        tsections, outer_ribs, inner_ribs, wedge_block, wedges_column,
        inner_beams, and sherpas.

        FloorGuide geometry is authored at z=0 (floor top surface). Pass
        ``transformation`` to place the guide at the correct elevation in the
        model — typically a translation by ``story_height`` so the plates sit
        at the top of the columns:

        .. code-block:: python

            from compas.geometry import Translation, Vector
            floor_model.add_floor_guide(
                guide,
                transformation=Translation.from_vector(Vector(0, 0, floor_model.story_height)),
            )

        SherpaXL120Element and PlateElement objects in the sherpas list are
        all registered as SolidDifferenceModifier cutters against the column
        at ``column_index``.

        Parameters
        ----------
        guide : :class:`compas_tf.floor_guide.FloorGuide`
            Quarter floor guide that owns the plate geometry.
        column_index : int
            Which column (by name suffix) the sherpa cutting blocks target.
            Default is 0 (the bottom-left corner column).
        transformation : :class:`compas.geometry.Transformation`, optional
            Transformation applied to every plate and sherpa element so the
            guide sits at the correct height in the model.  When *None* the
            geometry remains at the z=0 origin of the FloorGuide.

        Returns
        -------
        :class:`compas_model.elements.group.Group`
            The top-level floor_guide group added to the model.
        """
        from compas_tf.joint_sherpaxl120 import SherpaXL120Element
        from compas_tf.plate import PlateElement

        guide_group = self.add_group("floor_guide")

        plate_sections = [
            ("beds", guide.beds),
            ("tsections", guide.tsections),
            ("outer_ribs", guide.outer_ribs),
            ("inner_ribs", guide.inner_ribs),
            ("wedge_block", guide.wedge_block),
            ("wedges_column", guide.wedges_column),
            ("inner_beams", guide.inner_beams),
        ]
        if include_oculus:
            plate_sections.append(("oculus", guide.oculus))
        elements_by_group = {}
        dowels_group = Group(name="dowels")
        self.add_element(dowels_group, parent=guide_group)
        for group_name, plates in plate_sections:
            sub = Group(name=group_name)
            self.add_element(sub, parent=guide_group)
            group_elements = []
            dowel_index = 0
            for i, plate in enumerate(plates):
                if isinstance(plate, DowelElement):
                    plate.name = f"dowel_{dowel_index}"
                    dowel_index += 1
                    if transformation is not None:
                        if plate.transformation is not None:
                            plate.transformation = transformation * plate.transformation
                        else:
                            plate.transformation = transformation
                    self.add_element(plate, parent=dowels_group)
                else:
                    plate.name = f"{group_name}_{i}"
                    if transformation is not None:
                        if plate.transformation is not None:
                            plate.transformation = transformation * plate.transformation
                        else:
                            plate.transformation = transformation
                    self.add_element(plate, parent=sub)
                group_elements.append(plate)
            elements_by_group[group_name] = group_elements

        # Dowels cut through inner beam plates and wedges starting from index 3
        # Dowels on line_index 1 (middle) also cut oculus side plates
        dowels = [e for e in elements_by_group.get("wedges_column", []) if isinstance(e, DowelElement)]
        wedge_plates = [e for e in elements_by_group.get("wedges_column", []) if isinstance(e, PlateElement)]
        base_targets = wedge_plates[3:] + elements_by_group.get("inner_beams", [])
        oculus_targets = elements_by_group.get("oculus", [])[:-1]  # side plates only
        for dowel in dowels:
            targets = base_targets + (oculus_targets if getattr(dowel, "line_index", None) == 1 else [])
            for target in targets:
                self.add_modifier(dowel, target, SolidDifferenceModifier())

        # Sherpas: SherpaXL120Element → joint elements,
        #          PlateElement → column cutter (SolidDifferenceModifier)
        sherpas_group = Group(name="sherpas")
        self.add_element(sherpas_group, parent=guide_group)

        columns = self.find_all_elements_of_type(ColumnElement)
        columns_by_index = {int(c.name.split("_")[-1]): c for c in columns}
        target_column = columns_by_index.get(column_index)

        for i, sherpa in enumerate(guide.sherpas):
            if not getattr(sherpa, "name", None):
                sherpa.name = f"sherpa_{i}"
            if transformation is not None:
                sherpa.transformation = transformation
            sherpa.skip_contacts = True
            self.add_element(sherpa, parent=sherpas_group)
            if isinstance(sherpa, (PlateElement, SherpaXL120Element)) and target_column is not None:
                self.add_modifier(sherpa, target_column, SolidDifferenceModifier())

        return guide_group

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

    # ------------------------------------------------------------------ #
    #  BVH / contact detection (skip Group elements — they have no geometry)
    # ------------------------------------------------------------------ #

    def _skip_contacts(self, element):
        """Return True if the element should be excluded from contact detection."""
        return isinstance(element, (Group, DowelElement)) or getattr(element, "skip_contacts", False)

    def compute_bvh(self, nodetype=None, max_depth=None, leafsize=1):
        from compas_model.models.bvh import ElementBVH, ElementAABBNode
        if nodetype is None:
            nodetype = ElementAABBNode
        valid = [el for el in self.elements() if not self._skip_contacts(el)]
        self._bvh = ElementBVH.from_elements(valid, nodetype=nodetype, max_depth=max_depth, leafsize=leafsize)
        return self._bvh

    def compute_contacts(self, tolerance=1e-6, minimum_area=1e-2, contacttype=None):
        from compas_model.interactions.contact import Contact
        if contacttype is None:
            contacttype = Contact
        for element in self.elements():
            if self._skip_contacts(element):
                continue
            u = element.graphnode
            for nbr in self.bvh.nearest_neighbors(element):
                if self._skip_contacts(nbr):
                    continue
                v = nbr.graphnode
                try:
                    if not self.graph.has_edge((u, v), directed=False):
                        contacts = element.compute_contacts(nbr, tolerance=tolerance, minimum_area=minimum_area, contacttype=contacttype)
                        if contacts:
                            self.graph.add_edge(u, v, contacts=contacts)
                    else:
                        edge = (u, v) if self.graph.has_edge((u, v)) else (v, u)
                        existing = self.graph.edge_attribute(edge, name="contacts")
                        if not existing:
                            contacts = element.compute_contacts(nbr, tolerance=tolerance, minimum_area=minimum_area, contacttype=contacttype)
                            if contacts:
                                self.graph.edge_attribute(edge, name="contacts", value=contacts)
                except NotImplementedError:
                    pass

    # ------------------------------------------------------------------ #
    #  batch boolean pre-computation
    # ------------------------------------------------------------------ #

    def precompute_boolean_modifiers(self):
        """Batch all boolean difference/union modifiers per element using boolean_chain.

        Groups all SolidDifferenceModifier and SolidUnionModifier sources for each
        target element and sends them to CGAL in a single call, avoiding repeated
        Python↔C++ round-trips. Non-boolean modifiers are applied individually after.

        Must be called after all elements and modifiers are registered, and before
        any element geometry is first accessed (e.g., before viewer.show()).
        """
        from compas.datastructures import Mesh
        from compas_tf.solid_difference_modifier import SolidDifferenceModifier
        from compas_tf.solid_union_modifier import SolidUnionModifier

        for element in self.elements():
            # Collect boolean modifiers in order: (mesh, operation)
            bool_sources = []   # list of (Mesh, operation_str)
            union_sources = []  # SolidUnionModifier sources (merged separately)
            other_modifiers = []  # (source_element, modifier)

            for nbr in self.graph.neighbors_in(element.graphnode):
                modifiers = self.graph.edge_attribute((nbr, element.graphnode), name="modifiers") or []
                source = self.graph.node_element(nbr)
                for modifier in modifiers:
                    if isinstance(modifier, SolidDifferenceModifier):
                        src_geom = source.modelgeometry
                        op = getattr(modifier, "operation", "difference")
                        if op == "union":
                            # union via boolean modifier goes into the chain too
                            if isinstance(src_geom, Mesh):
                                bool_sources.append((src_geom, "union"))
                        elif isinstance(src_geom, Mesh) and src_geom.is_closed():
                            bool_sources.append((src_geom, op))
                        else:
                            print(f"[precompute] skip '{op}' source for '{getattr(element, 'name', '?')}': not a closed Mesh")
                    elif isinstance(modifier, SolidUnionModifier):
                        src_geom = source.modelgeometry
                        if isinstance(src_geom, Mesh):
                            union_sources.append(src_geom)
                    else:
                        other_modifiers.append((source, modifier))

            if not bool_sources and not union_sources:
                continue

            xform = element.modeltransformation
            geometry = element.elementgeometry.transformed(xform)

            if not isinstance(geometry, Mesh):
                continue

            if bool_sources and geometry.is_closed():
                meshes = [m for m, _ in bool_sources]
                operations = [op for _, op in bool_sources]
                geometry = SolidDifferenceModifier.apply_batch(meshes, geometry, operations)

            if union_sources:
                geometry = SolidUnionModifier.apply_batch(union_sources, geometry)

            for source, modifier in other_modifiers:
                geometry = modifier.apply(source, geometry)

            # Inject into cache so compute_modelgeometry() is never called for this element
            element._modelgeometry = geometry



