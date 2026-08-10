"""A local copy of ``compas_model.models.model``.

compas_tf inherits from this instead of :class:`compas_model.models.Model`
because the Model compas_tf needs does not exist in any compas_model release.
``duplicate``, ``merge``, ``compute_contacts_between_groups`` and
``find_group_with_name`` live only on an unmerged branch - verified by reading
``compas_model/models/model.py`` out of the published 0.9.3 wheel, where all
four are absent. Depending on that branch meant compas_tf only worked against a
local editable checkout.

Everything this module imports FROM compas_model (Element, Group, Contact,
Material, Modifier, KDTree, ElementTree, ElementNode, InteractionGraph, the BVH
node types) does ship in 0.9.3, so only the model class itself is copied.

Kept as a verbatim copy rather than a patch so it can be diffed against
upstream. :class:`compas_tf.model.TFModel` subclasses it. Delete this module and
go back to inheriting from compas_model once that branch is released.

``find_groups_with_names`` is the one method here that is compas_tf's own rather
than the branch's, and belongs upstream with the other four.
"""

from collections.abc import Callable
from collections.abc import Generator
from collections.abc import Iterator
from typing import Optional
from typing import TypeVar
from typing import Union

from compas.datastructures import Datastructure
from compas.geometry import Point
from compas.geometry import Transformation
from compas_model.datastructures import KDTree
from compas_model.elements import Element
from compas_model.elements import Group
from compas_model.interactions import Contact
from compas_model.materials import Material
from compas_model.models.bvh import ElementAABBNode
from compas_model.models.bvh import ElementBVH
from compas_model.models.bvh import ElementOBBNode
from compas_model.models.elementtree import ElementNode
from compas_model.models.elementtree import ElementTree
from compas_model.models.interactiongraph import InteractionGraph
from compas_model.modifiers import Modifier

ElementType = TypeVar("ElementType", bound=Element)


def _element_contacts(a: Element, b: Element, **kwargs) -> list[Contact]:
    """The default ``contactmethod``: whatever the element itself implements.

    For a plain compas_model element that is mesh-face detection; for a
    :class:`compas_tf.plate.PlateElement` it is the plate's own untriangulated
    polygon-face version.
    """
    return a.compute_contacts(b, **kwargs)


def _aabb(element: Element) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """The element's model-space bounding box, as (min, max).

    Not ``Element.aabb``, which is element space and raises on the base class.
    """
    geometry = element.modelgeometry
    if hasattr(geometry, "vertices_attributes"):  # Mesh
        points = geometry.vertices_attributes("xyz")
    else:  # Brep
        points = [vertex.point for vertex in geometry.vertices]
    xs, ys, zs = zip(*points)
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _boxes_overlap(a: tuple, b: tuple) -> bool:
    (amin, amax), (bmin, bmax) = a, b
    return all(amin[i] <= bmax[i] and bmin[i] <= amax[i] for i in range(3))


class ModelError(Exception):
    pass


class ModelElementNotFound(ModelError):
    pass


class BaseModel(Datastructure):
    """Class representing a general model of hierarchically organised elements, with interactions.

    Notes
    -----
    A model has an element tree to store the hierarchical relationships between elements,
    and an interaction graph to store the interactions between pairs of elements.
    BaseModel elements are contained in the tree hierarchy in tree nodes, and in the interaction graph in graph nodes.

    Every model element can appear only once in the tree, and only once in the graph.
    This means that every element can have only one hierarchical parent.
    At the same time, independently of the hierarchy, every element can have many interactions with other elements.

    """

    @property
    def __data__(self) -> dict:
        data = {
            "transformation": self.transformation,
            "elements": self._elements,
            "materials": self._materials,
            "tree": self._tree.__data__,
            "graph": self._graph.__data__,
        }
        return data

    @classmethod
    def __from_data__(cls, data: dict) -> "BaseModel":
        model = cls()

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

    def __init__(self, name: Optional[str] = None, **kwargs: object) -> None:
        super().__init__(name=name)

        self._transformation = None
        self._materials: dict[str, Material] = {}
        self._elements: dict[str, Element] = {}

        self._tree = ElementTree()
        self._graph = InteractionGraph()
        self._graph.model = self

        self._bvh = None
        self._kdtree = None

    def __str__(self) -> str:
        output = "=" * 80 + "\n"
        output += "Spatial Hierarchy\n"
        output += "=" * 80 + "\n"
        output += str(self._tree) + "\n"
        output += "=" * 80 + "\n"
        output += "Element Interactions\n"
        output += "=" * 80 + "\n"
        output += str(self._graph) + "\n"
        output += "=" * 80 + "\n"
        return output

    # =============================================================================
    # Attributes
    # =============================================================================

    @property
    def tree(self) -> ElementTree:
        return self._tree

    @property
    def graph(self) -> InteractionGraph:
        return self._graph

    @property
    def bvh(self) -> ElementBVH:
        if not self._bvh:
            self._bvh = self.compute_bvh()
        return self._bvh

    @property
    def kdtree(self) -> KDTree:
        if not self._kdtree:
            self._kdtree = self.compute_kdtree()
        return self._kdtree

    @property
    def transformation(self) -> Optional[Transformation]:
        return self._transformation

    @transformation.setter
    def transformation(self, transformation: Transformation) -> None:
        self._transformation = transformation

    # =============================================================================
    # Datastructure "abstract" methods
    # =============================================================================

    def transform(self, transformation: Transformation) -> None:
        """Transform the model and all that it contains.

        Parameters
        ----------
        transformation
            The transformation to apply.

        """
        self.transformation = transformation

    # =============================================================================
    # Elements
    # =============================================================================

    def elements(self) -> Iterator[Element]:
        """Iterate over the elements contained in the model.

        Returns
        -------
        Iterator[Element]
            The elements contained in the model.

        """
        return iter(self._elements.values())

    def add_element(
        self,
        element: Union[Element, ElementType],
        parent: Optional[Element] = None,
        material: Optional[Material] = None,
    ) -> Union[Element, ElementType]:
        """Add an element to the model.

        Parameters
        ----------
        element
            The element to add.
        parent
            The parent element of the element.
            If ``None``, the element will be added directly under the root element.
        material
            A material to assign to the element.
            Note that the material should have already been added to the model before it can be assigned.

        Returns
        -------
        Element
            The element added to the model.

        Raises
        ------
        ValueError
            If the parent node is not a GroupNode.
        ValueError
            If a material is provided that is not part of the model.

        """
        guid = str(element.guid)
        if guid in self._elements:
            raise Exception("Element already in the model.")

        if material:
            if not self.has_material(material):
                raise ValueError("The material is not part of the model: {}".format(material))

        self._bvh = None
        self._elements[guid] = element

        self.graph.add_element(element)
        self.tree.add_element(element, parent)

        if material:
            self.assign_material(material=material, element=element)

        element.model = self
        return element

    def add_elements(
        self,
        elements: list[Union[Element, ElementType]],
        parent: Optional[Element] = None,
        material: Optional[Material] = None,
    ) -> list[Union[Element, ElementType]]:
        """Add a list of elements to the model.

        Parameters
        ----------
        elements
            The elements to add.
        parent
            The parent element of the elements.
            If ``None``, the elements will be added directly under the root element.
        material
            A material to assign to the elements.
            Note that the material should have already been added to the model before it can be assigned.

        Returns
        -------
        list[Element]
            The list of elements added to the model.

        Raises
        ------
        ValueError
            If the parent node is not a GroupNode.
        ValueError
            If a material is provided that is not part of the model.

        """
        # try
        # roll back if not all were added
        for element in elements:
            self.add_element(element, parent, material)
        return elements

    def remove_element(self, element: Element) -> None:
        """Remove an element from the model.

        Parameters
        ----------
        element
            The element to remove.

        """
        guid = str(element.guid)
        if guid not in self._elements:
            raise Exception("Element not in the model.")

        del self._elements[guid]

        self.graph.delete_node(element.graphnode)
        self.tree.remove(element.treenode)

    def has_element(self, element: Element) -> bool:
        """Returns True if the model contains the given element.

        Parameters
        ----------
        element
            The element to check.

        Returns
        -------
        bool
            True if the model contains the element.

        """
        guid = str(element.guid)
        return guid in self._elements

    def has_element_with_name(self, name: str) -> bool:
        """Returns True if the model contains an element with the given name.

        Parameters
        ----------
        name
            The name to check.

        Returns
        -------
        bool
            True if the model contains an element with the name.

        """
        return any(element.name == name for element in self.elements())

    def find_element_with_name(self, name: str) -> Optional[Element]:
        """Returns True if the model contains an element with the given name.

        Parameters
        ----------
        name
            The name to check.

        Returns
        -------
        Element or None
            The element with the name, if found.

        """
        for element in self.elements():
            if element.name == name:
                return element

    def find_element_with_name_or_fail(self, name: str) -> Element:
        element = self.find_element_with_name(name)
        if not element:
            raise ModelElementNotFound
        return element

    def find_all_elements_of_type(self, elementtype: type[Element]) -> list[Element]:
        """Find all model elements of a given type.

        Parameters
        ----------
        elementtype
            The type of element.

        Returns
        -------
        list[Element]
            The elements of the requested type.

        """
        elements = []
        for element in self.elements():
            if isinstance(element, elementtype):
                elements.append(element)
        return elements

    def remove_elements_of_type(self, elementtype: type[Element]) -> list[Element]:
        """Remove all model elements of a given type.

        Parameters
        ----------
        elementtype
            The type of element.

        Returns
        -------
        list[Element]
            The removed elements.

        """
        elements = self.find_all_elements_of_type(elementtype)
        for element in elements:
            self.remove_element(element)
        return elements

    # =============================================================================
    # Groups
    # =============================================================================

    def add_group(self, name: Optional[str] = None) -> Group:
        """Add a group to the model.

        Parameters
        ----------
        name
            The name of the group.

        Returns
        -------
        Group
            The group added to the model.

        """
        group = Group(name=name)
        self.add_element(group)
        return group

    # =============================================================================
    # Materials
    # =============================================================================

    def materials(self) -> Iterator[Material]:
        """Iterate over the materials stored in the model.

        Returns
        -------
        Iterator[Material]
            The materials stored in the model.

        """
        return iter(self._materials.values())

    def add_material(self, material: Material) -> None:
        """Add a material to the model.

        Parameters
        ----------
        material
            A material.

        """
        guid = str(material.guid)
        if guid in self._materials:
            raise Exception("Material already in the model.")

        self._materials[guid] = material

    def has_material(self, material: Material) -> bool:
        """Verify that the model contains a specific material.

        Parameters
        ----------
        material
            A model material.

        Returns
        -------
        bool
            True if the model contains the material.

        """
        guid = str(material.guid)
        return guid in self._materials

    def add_or_get_material(self, material: Material) -> Material:
        """Add a material to the model or retrieve an existing instance of the same type.

        Parameters
        ----------
        material
            A material.

        Returns
        -------
        Material
            The added or existing material.

        """
        for existing in self.materials():
            if isinstance(existing, type(material)):
                return existing
        self.add_material(material)
        return material

    def assign_material(
        self,
        material: Material,
        element: Optional[Element] = None,
        elements: Optional[list[Element]] = None,
    ) -> None:
        """Assign a material to an element or a list of elements.

        Parameters
        ----------
        material
            The material.
        element
            The element to assign the material to.
        elements
            The list of elements to assign the material to.

        Raises
        ------
        ValueError
            If neither `element` or `elements` is provided.
        ValueError
            If both `element` and `elements` are provided.
        ValueError
            If the material is not part of the model.
        ValueError
            If the provided element or one of the elements in the provided element list is not part of the model.

        """
        if not self.has_material(material):
            raise ValueError("This material is not part of the model: {}".format(material))
        if not element and not elements:
            raise ValueError("Either an element or a list of elements should be provided.")
        if element and elements:
            raise ValueError("It is not allowed to provide both an element and an element list.")

        if element:
            if not self.has_element(element):
                raise ValueError("This element is not part of the model: {}".format(element))
            element.material = material

        elif elements:
            if any(not self.has_element(element) for element in elements):
                raise ValueError("This element is not part of the model: {}".format(element))

            for element in elements:
                element.material = material

    # =============================================================================
    # Branching
    # =============================================================================

    def duplicate(self) -> "BaseModel":
        """Return a fully independent copy of this model (elements get new guids).

        Unlike :meth:`copy` (and ``deepcopy``), which reproduce each element's
        guid verbatim - so two copies share guids and cannot coexist in one
        model - ``duplicate`` re-clones every element with a fresh guid and
        rewires the tree/graph. The result is independent, so it can be placed
        and :meth:`merge`-d alongside the original.

        Returns
        -------
        BaseModel
            An independent copy of this model.

        """
        new = type(self)(name=self.name)
        new.transformation = self.transformation

        # Materials
        materials: dict[str, Material] = {}
        for material in self.materials():
            materials[str(material.guid)] = new.add_or_get_material(material.copy())

        # Elements (cloned with fresh guids, hierarchy preserved)
        elements: dict[str, Element] = {}

        def _clone(source_node: ElementNode, parent: Optional[Element]) -> None:
            for child in source_node.children:
                source = child.element
                element = source.copy()  # fresh guid -> independent
                new.add_element(element, parent=parent)
                elements[str(source.guid)] = element
                if source._material and str(source._material) in materials:
                    new.assign_material(materials[str(source._material)], element=element)
                _clone(child, element)

        _clone(self.tree.root, None)

        # Interactions (with their modifiers/contacts)
        for edge in self.graph.edges():
            a = elements[str(self.graph.node_element(edge[0]).guid)]
            b = elements[str(self.graph.node_element(edge[1]).guid)]
            new_edge = new.add_interaction(a, b)
            for attr in ("modifiers", "contacts"):
                values = self.graph.edge_attribute(edge, name=attr)
                if values:
                    new.graph.edge_attribute(new_edge, name=attr, value=[v.copy() for v in values])

        return new

    def merge(self, models: list["BaseModel"], parent: Optional[Element] = None) -> "BaseModel":
        """Merge a list of models into this model, each under its own group.

        Each input is added under a new group (named after it) nested under
        ``parent`` - or under the model root when ``parent`` is ``None``. For
        every input its materials, element tree (hierarchy preserved) and
        interactions (with their modifiers/contacts) are brought in. The inputs
        are consumed - their elements are moved in, not copied - so
        :meth:`duplicate` them first if you need to keep the originals (or to
        merge several instances of one model).

        Build a new combined model by merging into a fresh one, optionally in one
        line: ``BaseModel(name="columns").merge(column_models)``. Insert into an
        existing model under a chosen group/element by passing ``parent``.

        Parameters
        ----------
        models
            The list of models to merge into this one.
        parent
            The group/element to nest the merged models under. Root if ``None``.

        Returns
        -------
        BaseModel
            This model (returned for chaining).

        """

        def _move(source_node: ElementNode, target: Optional[Element], materials: dict) -> None:
            for child in source_node.children:
                element = child.element
                self.add_element(element, parent=target)
                if element._material and str(element._material) in materials:
                    self.assign_material(materials[str(element._material)], element=element)
                _move(child, element, materials)

        for other in models:
            group = self.add_element(Group(name=other.name or "model"), parent=parent)
            if other.transformation is not None:
                group.transformation = other.transformation

            # Materials
            materials: dict[str, Material] = {}
            for material in other.materials():
                materials[str(material.guid)] = self.add_or_get_material(material)

            # Elements (moved in, hierarchy preserved)
            _move(other.tree.root, group, materials)

            # Interactions (with their modifiers/contacts)
            for edge in other.graph.edges():
                a = other.graph.node_element(edge[0])
                b = other.graph.node_element(edge[1])
                new_edge = self.add_interaction(a, b)
                for attr in ("modifiers", "contacts"):
                    values = other.graph.edge_attribute(edge, name=attr)
                    if values:
                        self.graph.edge_attribute(new_edge, name=attr, value=list(values))

        return self

    def find_group_with_name(self, name: str) -> Optional["BaseModel"]:
        """Extract a named group's subtree as a new, independent model.

        Search the element tree for a :class:`Group` with the given name and
        return a fresh model holding an independent copy of that group's
        contents - its elements re-cloned with new guids (like
        :meth:`duplicate`), their hierarchy preserved, and any interactions
        (with their modifiers/contacts) that fall entirely within the subtree
        carried along. The source model is left untouched.

        This is the inverse of :meth:`merge`: ``merge`` nests a model under a
        group named after it, while ``find_group_with_name`` lifts such a group
        back out into a standalone model (named after the group). The group's
        full placement in the source hierarchy - the accumulated transformation
        of its ancestors and the source model itself - is baked into the new
        model's transformation, so the extracted geometry keeps its world
        position. The first group matching the name is used.

        Parameters
        ----------
        name
            The name of the group to extract.

        Returns
        -------
        BaseModel or None
            A new model rooted at the group's contents, or ``None`` if no group
            with that name exists.

        """
        node: Optional[ElementNode] = None
        for element in self.elements():
            if isinstance(element, Group) and element.name == name:
                node = element.treenode
                break
        if node is None:
            return None

        new = type(self)(name=name)
        # The group's model transformation already folds in its own transformation
        # plus every ancestor's and the source model's, so the extracted contents
        # keep their place in the world.
        new.transformation = node.element.modeltransformation

        # Materials are carried over lazily - only those actually used in the subtree.
        materials: dict[str, Material] = {}

        def _material_for(source: Element) -> Optional[Material]:
            if not source._material:
                return None
            if source._material not in materials:
                materials[source._material] = new.add_or_get_material(self._materials[source._material].copy())
            return materials[source._material]

        # Elements (cloned with fresh guids, hierarchy preserved). The group node
        # itself is dropped - its children become the new model's top-level elements.
        elements: dict[str, Element] = {}

        def _clone(source_node: ElementNode, parent: Optional[Element]) -> None:
            for child in source_node.children:
                source = child.element
                element = source.copy()  # fresh guid -> independent
                new.add_element(element, parent=parent)
                elements[str(source.guid)] = element
                material = _material_for(source)
                if material is not None:
                    new.assign_material(material, element=element)
                _clone(child, element)

        _clone(node, None)

        # Interactions whose endpoints both lie inside the extracted subtree.
        for edge in self.graph.edges():
            a = self.graph.node_element(edge[0])
            b = self.graph.node_element(edge[1])
            if str(a.guid) in elements and str(b.guid) in elements:
                new_edge = new.add_interaction(elements[str(a.guid)], elements[str(b.guid)])
                for attr in ("modifiers", "contacts"):
                    values = self.graph.edge_attribute(edge, name=attr)
                    if values:
                        new.graph.edge_attribute(new_edge, name=attr, value=[v.copy() for v in values])

        return new

    def find_groups_with_names(
        self,
        names: list[str],
        name: Optional[str] = None,
        neighbors: Union[bool, tuple, Callable] = False,
    ) -> "BaseModel":
        """Extract several named groups at once, as one new independent model.

        The multi-group counterpart of :meth:`find_group_with_name`, for lifting
        an assembly out of a big model - one column plus the quarter it carries,
        say. Because the groups are extracted together, the interactions BETWEEN
        them survive; extracting them one at a time and merging the results
        would lose exactly those, which is the joint you wanted.

        Where :meth:`find_group_with_name` drops the group node and folds its
        placement into the new model's transformation, this keeps each group's
        chain of ancestors - pruned to the groups asked for. So a
        ``quarter_model_0`` under ``floor_model/quarters_model`` comes back at
        the same path, and every group transformation on the way down still
        applies. The elements are re-cloned with fresh guids and the source
        model is left untouched.

        Parameters
        ----------
        names
            The names of the groups to extract. The first group matching each
            name is used.
        name
            Name for the new model. Defaults to the names joined by ``+``.
        neighbors
            Also bring in elements outside the named groups that belong with one
            inside - the loose fasteners a bay is bolted together with, which
            live in their own top-level group rather than in the bay's. Two
            passes: every element that interacts with one inside, and then, for
            the elements that have no interaction at all, every one whose
            bounding box lands inside the bay. Their ancestor groups are
            recreated the same way. The second pass reads ``modelgeometry``.

            ``True`` admits anything that touches, which is rarely what an
            assembly means - the ribs and beams of the quarters next door touch
            a bay across the seam, and so does the oculus. Pass a tuple of
            element types (or a predicate taking an element) to admit only the
            hardware::

                bay = model.find_groups_with_names(
                    ["column_model_0", "quarter_model_0"],
                    neighbors=(ConnectorElement, ConnectorWedgeElement, ...),
                )

        Returns
        -------
        BaseModel
            A new model holding an independent copy of those groups.

        Raises
        ------
        ModelElementNotFound
            If any of the names does not match a group.

        """
        nodes: list[ElementNode] = []
        missing: list[str] = []
        for groupname in names:
            for element in self.elements():
                if isinstance(element, Group) and element.name == groupname:
                    nodes.append(element.treenode)
                    break
            else:
                missing.append(groupname)
        if missing:
            raise ModelElementNotFound(f"no group named {', '.join(missing)}")

        # The elements to carry over, keyed by source guid so the graph can be
        # rewired below. Groups are not collected: they come back only as the
        # ancestors of the elements that need them.
        selected: dict[str, Element] = {}

        def _collect(node: ElementNode) -> None:
            for child in node.children:
                if isinstance(child.element, Group):
                    _collect(child)
                else:
                    selected[str(child.element.guid)] = child.element

        for node in nodes:
            _collect(node)

        if neighbors:
            # What may be admitted. Plain True takes anything that touches the
            # selection, which is rarely what an assembly means: the outer ribs
            # and inner beams of the quarters next door touch a bay across the
            # seam, and so does the oculus, but none of them is part of it. Pass
            # the element types the assembly is bolted together with (or a
            # predicate) to admit only those.
            if neighbors is True:
                accept = lambda element: True  # noqa: E731
            elif isinstance(neighbors, tuple):
                accept = lambda element: isinstance(element, neighbors)  # noqa: E731
            else:
                accept = neighbors

            # Against a snapshot: a neighbour brought in must not itself pull in
            # ITS neighbours, or one edge at a time the whole model comes along.
            inside = set(selected)
            for edge in self.graph.edges():
                a = self.graph.node_element(edge[0])
                b = self.graph.node_element(edge[1])
                inside_a, inside_b = str(a.guid) in inside, str(b.guid) in inside
                if inside_a != inside_b:
                    outsider = b if inside_a else a
                    if accept(outsider):
                        selected[str(outsider.guid)] = outsider

            # An element the contact search skipped has no edge at all, so the
            # walk above is blind to it - the dowels and connector cylinders are
            # 64 such in the cantilevers model, because a faceted shaft touches
            # its own hole once per facet and searching those pairs is 74% of
            # the contacts for no structural information. Geometry is the only
            # signal left for them, so the boxes decide. Restricted to the
            # unlinked, because on elements the graph does describe a box test
            # is far too loose: one diagonal rib's box swallows half the floor.
            unlinked = [
                element for element in self.elements() if not isinstance(element, Group) and str(element.guid) not in selected and self.graph.degree(element.graphnode) == 0
            ]
            if unlinked:
                boxes = {str(element.guid): _aabb(element) for element in list(selected.values()) + unlinked}
                enclosing = [boxes[key] for key in list(selected)]
                for element in unlinked:
                    if accept(element) and any(_boxes_overlap(boxes[str(element.guid)], box) for box in enclosing):
                        selected[str(element.guid)] = element

        new = type(self)(name=name or "+".join(names))
        new.transformation = self.transformation

        materials: dict[str, Material] = {}
        clones: dict[str, Element] = {}

        def _clone(source: Element, parent: Optional[Element]) -> Element:
            element = source.copy()  # fresh guid -> independent
            new.add_element(element, parent=parent)
            clones[str(source.guid)] = element
            if source._material:
                if source._material not in materials:
                    materials[source._material] = new.add_or_get_material(self._materials[source._material].copy())
                new.assign_material(materials[source._material], element=element)
            return element

        def _ancestor(node: ElementNode) -> Optional[Element]:
            """The clone of ``node``'s parent group, creating the chain up to the root."""
            parent: Optional[ElementNode] = node.parent
            # The tree root is a plain TreeNode - it holds no element.
            group = getattr(parent, "element", None) if parent is not None else None
            if group is None:
                return None
            key = str(group.guid)
            if key not in clones:
                _clone(group, _ancestor(parent))
            return clones[key]

        for source in selected.values():
            _clone(source, _ancestor(source.treenode))

        # Interactions whose endpoints both came along.
        for edge in self.graph.edges():
            a = self.graph.node_element(edge[0])
            b = self.graph.node_element(edge[1])
            if str(a.guid) in clones and str(b.guid) in clones:
                new_edge = new.add_interaction(clones[str(a.guid)], clones[str(b.guid)])
                for attr in ("modifiers", "contacts"):
                    values = self.graph.edge_attribute(edge, name=attr)
                    if values:
                        new.graph.edge_attribute(new_edge, name=attr, value=[v.copy() for v in values])

        return new

    def compute_contacts_between_groups(
        self,
        groups: list[str],
        groups_b: Optional[list[str]] = None,
        tolerance: float = 1e-6,
        minimum_area: float = 1e-2,
        contacttype: type[Contact] = Contact,
        contactmethod: Optional[Callable] = None,
    ) -> None:
        """Compute contacts only between elements of *different* named groups.

        Like :meth:`compute_contacts`, this is a spatial (BVH) search that adds
        a contact interaction wherever two element geometries touch. Unlike it,
        only the named groups take part, and pairs within a single group are
        never tested.

        Two modes:

        - **All-pairs** (``groups_b`` omitted): detection runs between every
          unordered pair of *distinct* groups in ``groups``. This is the natural
          companion to :meth:`merge` - every merged sub-model becomes its own
          group, so passing those names finds the seams between the sub-models.

        - **Two-sided** (``groups_b`` given): detection runs only between an
          element of a ``groups`` group and an element of a ``groups_b`` group.
          Pairs within ``groups`` and pairs within ``groups_b`` are skipped.
          Use this to contact one set against another - e.g. columns against
          only the outer ribs - without the ribs also contacting each other.

        Each element is assigned to the *nearest* enclosing group whose name is
        requested, so nested groups behave predictably: pass an outer group name
        to treat all its descendants as one group, or the inner names to keep
        them apart.

        Parameters
        ----------
        groups
            Names of the groups on the first side.
        groups_b
            Names of the groups on the second side. If ``None``, ``groups`` is
            tested against itself (all distinct pairs).
        tolerance
            The distance tolerance.
        minimum_area
            The minimum contact size.
        contacttype
            The contact class to use for the generated contacts.
        contactmethod
            What actually detects the contacts of one accepted pair, called as
            ``contactmethod(a, b, tolerance=, minimum_area=, contacttype=)``.
            Default is ``a.compute_contacts(b, ...)``, i.e. mesh faces. Pass a
            :class:`compas_tf.contacts.BrepContacts` to run on Brep faces instead.

        Raises
        ------
        ValueError
            All-pairs: if fewer than two named groups contain any elements.
            Two-sided: if either side has no elements.

        """
        if contactmethod is None:
            contactmethod = _element_contacts

        groupset_a = set(groups)
        groupset_b = set(groups_b) if groups_b else None
        all_names = groupset_a | (groupset_b or set())

        def group_of(element: Element) -> Optional[str]:
            # Nearest enclosing ancestor group whose name was requested.
            node = element.treenode
            parent = node.parent if node is not None else None
            while parent is not None and not parent.is_root:
                if parent.element.name in all_names:
                    return parent.element.name
                parent = parent.parent
            return None

        keyof: dict[int, str] = {}
        participants: list[Element] = []
        for element in self.elements():
            if isinstance(element, Group):
                continue
            key = group_of(element)
            if key is not None:
                keyof[id(element)] = key
                participants.append(element)

        present = set(keyof.values())
        if groupset_b is None:
            if len(present) < 2:
                raise ValueError(
                    "compute_contacts_between_groups needs at least two non-empty groups to form a pair; found elements only for {} of the requested {}.".format(
                        sorted(present), sorted(groupset_a)
                    )
                )

            def accept(key_u: str, key_v: str) -> bool:
                return key_u != key_v
        else:
            if not (present & groupset_a) or not (present & groupset_b):
                raise ValueError(
                    "compute_contacts_between_groups (two-sided) needs elements on both sides; found {} for side A {} and {} for side B {}.".format(
                        sorted(present & groupset_a), sorted(groupset_a), sorted(present & groupset_b), sorted(groupset_b)
                    )
                )

            def accept(key_u: str, key_v: str) -> bool:
                return (key_u in groupset_a and key_v in groupset_b) or (key_u in groupset_b and key_v in groupset_a)

        # Spatial search over participants only; same dedup logic as compute_contacts.
        bvh = ElementBVH.from_elements(participants)

        for element in participants:
            u = element.graphnode
            key_u = keyof[id(element)]

            for nbr in bvh.nearest_neighbors(element):
                key_v = keyof.get(id(nbr))
                if key_v is None or not accept(key_u, key_v):
                    # a non-participant, same side / same group, or the element itself
                    continue

                v = nbr.graphnode

                if not self.graph.has_edge((u, v), directed=False):
                    contacts = contactmethod(
                        element,
                        nbr,
                        tolerance=tolerance,
                        minimum_area=minimum_area,
                        contacttype=contacttype,
                    )
                    if contacts:
                        self.graph.add_edge(u, v, contacts=contacts)

                else:
                    edge = (u, v) if self.graph.has_edge((u, v)) else (v, u)
                    contacts = self.graph.edge_attribute(edge, name="contacts")
                    if not contacts:
                        contacts = contactmethod(
                            element,
                            nbr,
                            tolerance=tolerance,
                            minimum_area=minimum_area,
                            contacttype=contacttype,
                        )
                        if contacts:
                            self.graph.edge_attribute(edge, name="contacts", value=contacts)

    # =============================================================================
    # Contacts (with contacts a specific type of interaction)
    # =============================================================================

    def contacts(self) -> Generator[Contact, None, None]:
        for edge in self.graph.edges():
            contacts = self.graph.edge_attribute(edge, name="contacts")
            if contacts:
                for contact in contacts:
                    yield contact

    # =============================================================================
    # Interactions
    # =============================================================================

    def add_interaction(self, a: Element, b: Element, modifier: Optional[Modifier] = None) -> tuple[int, int]:
        """Add an interaction between two elements of the model.

        Parameters
        ----------
        a
            The first element.
        b
            The second element.

        Returns
        -------
        tuple[int, int]
            The edge of the interaction graph representing the interaction between the two elements.

        Raises
        ------
        Exception
            If one or both of the elements are not in the graph.

        Notes
        -----
        In future implementations, adding an interaction should implicitly take care of adding modifiers
        onto the interaction edges, based on the registered modifiers of the source nodes.

        In the current implementation, modifiers have to be added explicitly using :meth:`add_modifiers`.
        This method will add an interaction edge from the source of the modifier to its target if needed
        and store the modifier object on it.

        """
        node_a = a.graphnode
        node_b = b.graphnode

        if not self.has_element(a) or not self.has_element(b):
            raise Exception("Please add both elements to the model first.")

        if not self.graph.has_node(node_a) or not self.graph.has_node(node_b):
            raise Exception("Something went wrong: the elements are not in the interaction graph.")

        edge = self.graph.add_edge(node_a, node_b)
        return edge

    def remove_interaction(self, a: Element, b: Element) -> None:
        """Remove the interaction between two elements.

        Parameters
        ----------
        a
        b

        """
        edge = a.graphnode, b.graphnode
        if self.graph.has_edge(edge):
            self.graph.delete_edge(edge)
            return

        edge = b.graphnode, a.graphnode
        if self.graph.has_edge(edge):
            self.graph.delete_edge(edge)
            return

    def has_interaction(self, a: Element, b: Element) -> bool:
        """Returns True if two elements have an interaction set between them.

        Parameters
        ----------
        a
            The first element.
        b
            The second element.

        Returns
        -------
        bool
            True if the elements have an interaction.

        """
        edge = a.graphnode, b.graphnode
        result = self.graph.has_edge(edge)
        if not result:
            edge = b.graphnode, a.graphnode
            result = self.graph.has_edge(edge)
        return result

    # =============================================================================
    # Modifiers (temp)
    # =============================================================================

    def add_modifier(
        self,
        source: Element,
        target: Element,
        modifier: Modifier,
    ) -> list[Modifier]:
        """Add a modifier between two elements, with one the source of the modifier and the other the target.

        Parameters
        ----------
        source
            The source element.
        target
            The target element.
        modifier
            The modifier.

        Returns
        -------
        list[Modifier]
            All modifiers stored on the interaction edge between source and target.

        Notes
        -----
        This element should implement the protocol specified by the modifier.
        The methods of the source element defined by the protocol are used to compute the tools involved in the modification.
        The tools are used by the modifier to apply the modification to the model geometry of the target element.

        The modifier defines the protocol for the modification.
        The protocol should be implemented by the source element.
        The protocol methods of the source element are used to compute the modification tool.
        The modifier applies the modification to the target using this tool.

        """
        edge = self.add_interaction(source, target)
        modifiers = self.graph.edge_attribute(edge, name="modifiers") or []
        modifiers.append(modifier)
        self.graph.edge_attribute(edge, name="modifiers", value=modifiers)
        return modifiers

    # =============================================================================
    # Compute
    # =============================================================================

    def compute_bvh(
        self,
        nodetype: Union[type[ElementAABBNode], type[ElementOBBNode]] = ElementAABBNode,
        max_depth: Optional[int] = None,
        leafsize: int = 1,
    ) -> ElementBVH:
        """Compute the Bounding Volume Hierarchy (BVH) of the elements for fast collision checks.

        Parameters
        ----------
        nodetype
            The type of bounding volume node used in the tree.
        max_depth
            The maximum depth used for constructing the BVH.
        leafsize
            The number of elements contained in a BVH leaf node.

        Returns
        -------
        ElementBVH
            The computed BVH.

        """
        self._bvh = ElementBVH.from_elements(
            self.elements(),
            nodetype=nodetype,
            max_depth=max_depth,
            leafsize=leafsize,
        )
        return self._bvh

    def compute_kdtree(self) -> KDTree:
        """Compute the KD tree of the elements for fast nearest neighbour queries.

        The KD tree is built using the reference points of the elements of the model.

        Returns
        -------
        KDTree
            The computed KD tree.

        """
        self._kdtree = KDTree(list(self.elements()))
        return self._kdtree

    def compute_contacts(self, tolerance: float = 1e-6, minimum_area: float = 1e-2, contacttype: type[Contact] = Contact) -> None:
        """Compute the contacts between the block elements of this model.

        Computing contacts is done independently of the edges of the interaction graph.
        If contacts are found between two elements with an existing edge, the contacts attribute of the edge will be replaced.
        If there is no pre-existing edge, one will be added.
        No element pairs are excluded in the search based on the existence of an edge between their nodes in the interaction graph.

        The search is conducted entirely based on the BVH of the elements contained in the model.
        It is a spatial search that creates topological connections between elements based on their geometrical interaction.

        Parameters
        ----------
        tolerance
            The distance tolerance.
        minimum_area
            The minimum contact size.
        contacttype
            The contact class to use for the generated contacts.

        """
        # somehow this should not take into account past calculations.

        for element in self.elements():
            u = element.graphnode

            for nbr in self.bvh.nearest_neighbors(element):
                v = nbr.graphnode

                if not self.graph.has_edge((u, v), directed=False):
                    # there is no interaction edge between the two elements
                    contacts = element.compute_contacts(
                        nbr,
                        tolerance=tolerance,
                        minimum_area=minimum_area,
                        contacttype=contacttype,
                    )
                    if contacts:
                        self.graph.add_edge(u, v, contacts=contacts)

                else:
                    # there is an existing edge between the two elements
                    edge = (u, v) if self.graph.has_edge((u, v)) else (v, u)
                    contacts = self.graph.edge_attribute(edge, name="contacts")
                    if not contacts:
                        contacts = element.compute_contacts(
                            nbr,
                            tolerance=tolerance,
                            minimum_area=minimum_area,
                            contacttype=contacttype,
                        )
                        if contacts:
                            self.graph.edge_attribute(edge, name="contacts", value=contacts)

    # =============================================================================
    # Other Methods
    # =============================================================================

    def element_nnbrs(self, element: Element, k: int = 1) -> list[tuple[Element, float]]:
        """Find the nearest neighbours to a root element.

        Parameters
        ----------
        element
            The root element.
        k
            The number of nearest neighbours that should be returned.

        Returns
        -------
        list[tuple[Element, float]]
            A list of nearest neighbours,
            with each neighbour defined as an element and the distance of that element to the root element.

        """
        return [nbr for nbr in self.point_nnbrs(element.point, k=k + 1) if nbr[0] is not element]

    def point_nnbrs(self, point: Point, k: int = 1) -> list[tuple[Element, float]]:
        """Find the nearest neighbours to a point.

        Parameters
        ----------
        point
            The root point.
        k
            The number of nearest neighbours that should be returned.

        Returns
        -------
        list[tuple[Element, float]]
            A list of nearest neighbours,
            with each neighbour defined as an element and the distance of that element to the root element.

        """
        if k == 1:
            return [self.kdtree.nearest_neighbor(point)]
        return self.kdtree.nearest_neighbors(point, number=k)
