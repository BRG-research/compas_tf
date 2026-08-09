from typing import Iterator
from typing import Optional

from compas_model.elements import Element
from compas_model.elements import Group
from compas_model.interactions import Contact
from compas_model.materials import Material
from compas_model.models import ElementNode
from compas_model.models import Model
from compas_model.models.bvh import ElementBVH

from compas_tf.brep import BrepMixin
from compas_tf.element import TFElement


class TFModel(Model, BrepMixin):
    """A :class:`compas_model.models.Model` whose geometry survives serialization.

    Two additions, matching the ones on :class:`compas_tf.element.TFElement`:

    - :meth:`bake` walks the model and computes every element's geometry once.
      After that ``compas.json_dump(model, path)`` writes a file that
      ``compas.json_load`` brings back with the booleans already applied to the
      base geometry - no boolean backend needed, and no wait.
    - :meth:`get_brep` converts the whole model into one Brep compound of solid,
      coplanar-merged parts (and :meth:`to_step` writes it out).

    Serialization itself is inherited: ``Model.__data__`` already carries the
    elements, the tree and the interaction graph, and every compas_tf element
    puts its baked geometry in its own ``__data__``.
    """

    # ==========================================================================
    # Elements
    # ==========================================================================

    def geometry_elements(self) -> Iterator:
        """Every element in the model that carries geometry (groups excluded)."""
        for element in self.elements():
            if isinstance(element, Group):
                continue
            yield element

    # ==========================================================================
    # Baking
    # ==========================================================================

    def bake(self, modelgeometry: bool = True) -> "TFModel":
        """Compute every element's default geometry once, and store it on the elements.

        Elements that are not compas_tf elements are still given their
        ``modelgeometry``, which is what the viewer and the Brep/STEP export
        read - they just cannot carry extra variants.

        Parameters
        ----------
        modelgeometry : bool, optional
            Also bake the model-space geometry of every element.

        Returns
        -------
        :class:`TFModel`
            Self, so it chains.
        """
        for element in self.geometry_elements():
            if isinstance(element, TFElement):
                element.bake(modelgeometry=modelgeometry)
            elif modelgeometry:
                element.modelgeometry  # noqa: B018 - the property caches into _modelgeometry
        return self

    def unbake(self) -> "TFModel":
        """Drop the baked geometry of every element."""
        for element in self.geometry_elements():
            if isinstance(element, TFElement):
                element.unbake()
        return self

    @property
    def is_baked(self) -> bool:
        """True if every geometry-carrying element has geometry stored on it."""
        elements = list(self.geometry_elements())
        if not elements:
            return False
        return all(getattr(element, "is_baked", element._modelgeometry is not None) for element in elements)

    # ==========================================================================
    # Brep
    # ==========================================================================

    def element_breps(self, variant: Optional[str] = None, **kwargs) -> list:
        """One solid, coplanar-merged Brep per element, named after the element.

        Parameters
        ----------
        variant : str, optional
            A baked variant key to convert instead of each element's finished
            geometry. Elements that do not carry it are skipped - including any
            element that is not a compas_tf element, since only those can hold
            variants.
        **kwargs
            Forwarded to :meth:`compas_tf.brep.BrepMixin.get_brep`.

        Returns
        -------
        list[:class:`compas_occt.brep.OCCBrep`]
        """
        from compas_tf.brep import mesh_to_brep

        breps = []
        for element in self.geometry_elements():
            name = element.name or type(element).__name__
            if isinstance(element, TFElement):
                if variant is not None and variant not in element.baked_variants():
                    continue
                brep = element.get_brep(variant=variant, **kwargs)
            elif variant is not None:
                continue  # a plain element carries no variants
            elif isinstance(element, BrepMixin):
                brep = element.get_brep(**kwargs)
            else:
                geometry = element.modelgeometry
                brep = mesh_to_brep(geometry, name=name, **kwargs) if geometry is not None else None
            if brep is None:
                continue
            brep.name = name
            breps.append(brep)
        return breps

    def brep_meshes(self, variant: Optional[str] = None) -> list:
        """The model-space mesh of every element - what :meth:`get_brep` converts.

        Parameters
        ----------
        variant : str, optional
            A baked variant key to convert instead of the finished geometry.
            Elements that do not carry it are skipped - including any element
            that is not a compas_tf element, since only those hold variants.
        """
        meshes = []
        for element in self.geometry_elements():
            if not isinstance(element, TFElement):
                if variant is not None:
                    continue
                geometry = element.modelgeometry
            elif variant is None:
                geometry = element.placedgeometry
            elif variant in element.baked_variants():
                geometry = element.brep_meshes(variant)[0]
            else:
                continue
            if geometry is not None:
                meshes.append(geometry)
        return meshes

    def to_step(self, path: str, author: str = "compas_tf", variant: Optional[str] = None, **kwargs) -> str:
        """Write the whole model to a STEP file, one solid per element.

        Parameters
        ----------
        path : str
            Destination ``.stp`` / ``.step`` file.
        author : str, optional
            Author recorded in the STEP header.
        variant : str, optional
            A baked variant key to write instead of the finished geometry (see
            :meth:`element_breps`).
        **kwargs
            Forwarded to :meth:`compas_tf.brep.BrepMixin.get_brep`.

        Returns
        -------
        str
            The path written.
        """
        from compas_occt.brep import OCCBrep

        breps = self.element_breps(variant=variant, **kwargs)
        compound = OCCBrep.from_breps(breps)
        compound.to_step(str(path), name=self.name or "compas_tf_model", author=author)
        return str(path)

    # ==========================================================================
    # Contacts
    # ==========================================================================

    def compute_bvh(self, nodetype=None, max_depth: Optional[int] = None, leafsize: int = 1) -> ElementBVH:
        """Bounding-volume hierarchy over the geometry elements only.

        ``Model.compute_bvh`` feeds ``self.elements()`` to the BVH, which
        includes the :class:`Group`s. A Group carries no geometry, so its
        ``compute_aabb`` is the base-class ``raise NotImplementedError`` - and
        the BVH asks every element for its ``aabb``. Any model built with
        :meth:`merge` therefore has groups in it and cannot build a BVH at all,
        which makes ``compute_contacts()`` fail outright.

        ``compute_contacts_between_groups`` never hit this because it builds its
        own BVH from the participating elements, skipping groups explicitly.
        Filtering here fixes plain ``compute_contacts()`` the same way.
        """
        from compas_model.models.bvh import ElementAABBNode

        self._bvh = ElementBVH.from_elements(
            list(self.geometry_elements()),
            nodetype=nodetype or ElementAABBNode,
            max_depth=max_depth,
            leafsize=leafsize,
        )
        return self._bvh

    def compute_contacts(self, tolerance: float = 1e-6, minimum_area: float = 1e-2, contacttype: type[Contact] = Contact) -> None:
        """Compute the contacts between the geometry elements of this model.

        Overridden only to iterate :meth:`geometry_elements` instead of
        ``elements()``: a :class:`Group` has no geometry, so asking the BVH
        for its neighbours calls the base-class ``compute_aabb`` and raises
        NotImplementedError. See :meth:`compute_bvh` for the same fix on the
        other side. Body otherwise verbatim from compas_model.

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

        for element in self.geometry_elements():
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

    # ==========================================================================
    # Branching
    #
    # duplicate / merge / compute_contacts_between_groups / find_group_with_name
    # are vendored from an UNMERGED compas_model branch. The released
    # compas_model on PyPI (0.9.3) has none of them - verified by reading
    # compas_model/models/model.py out of the published wheel - so anything that
    # relied on compas_model providing them only worked against a local editable
    # checkout, and broke for everyone else. Keeping them on TFModel is what lets
    # compas_tf and its examples run against stock compas_model from PyPI.
    #
    # Delete these and inherit from Model again once that branch is released.
    # ==========================================================================

    def duplicate(self) -> "TFModel":
        """Return a fully independent copy of this model (elements get new guids).

        Unlike :meth:`copy` (and ``deepcopy``), which reproduce each element's
        guid verbatim - so two copies share guids and cannot coexist in one
        model - ``duplicate`` re-clones every element with a fresh guid and
        rewires the tree/graph. The result is independent, so it can be placed
        and :meth:`merge`-d alongside the original.

        Returns
        -------
        TFModel
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

    def merge(self, models: list["Model"], parent: Optional[Element] = None) -> "TFModel":
        """Merge a list of models into this model, each under its own group.

        Each input is added under a new group (named after it) nested under
        ``parent`` - or under the model root when ``parent`` is ``None``. For
        every input its materials, element tree (hierarchy preserved) and
        interactions (with their modifiers/contacts) are brought in. The inputs
        are consumed - their elements are moved in, not copied - so
        :meth:`duplicate` them first if you need to keep the originals (or to
        merge several instances of one model).

        Build a new combined model by merging into a fresh one, optionally in one
        line: ``Model(name="columns").merge(column_models)``. Insert into an
        existing model under a chosen group/element by passing ``parent``.

        Parameters
        ----------
        models
            The list of models to merge into this one.
        parent
            The group/element to nest the merged models under. Root if ``None``.

        Returns
        -------
        TFModel
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

    def compute_contacts_between_groups(
        self,
        groups: list[str],
        groups_b: Optional[list[str]] = None,
        tolerance: float = 1e-6,
        minimum_area: float = 1e-2,
        contacttype: type[Contact] = Contact,
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

        Raises
        ------
        ValueError
            All-pairs: if fewer than two named groups contain any elements.
            Two-sided: if either side has no elements.

        """
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
                    contacts = element.compute_contacts(
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
                        contacts = element.compute_contacts(
                            nbr,
                            tolerance=tolerance,
                            minimum_area=minimum_area,
                            contacttype=contacttype,
                        )
                        if contacts:
                            self.graph.edge_attribute(edge, name="contacts", value=contacts)

    def find_group_with_name(self, name: str) -> Optional["TFModel"]:
        """Extract a named group's subtree as a new, independent model.

        Search the element tree for a :class:`Group` with the given name and
        return a fresh model holding an independent copy of that group's
        contents - its elements re-cloned with new guids (like
        ``Model.duplicate``), their hierarchy preserved, and any interactions
        (with their modifiers/contacts) that fall entirely within the subtree
        carried along. The source model is left untouched.

        This is the inverse of ``Model.merge``: ``merge`` nests a model under a
        group named after it, while this lifts such a group back out into a
        standalone model (named after the group). The group's full placement in
        the source hierarchy - the accumulated transformation of its ancestors
        and the source model itself - is baked into the new model's
        transformation, so the extracted geometry keeps its world position. The
        first group matching the name is used.

        One of the four model methods vendored here - see the note on
        :meth:`duplicate`.

        Parameters
        ----------
        name : str
            The name of the group to extract.

        Returns
        -------
        :class:`TFModel` or None
            A new model rooted at the group's contents, or ``None`` if no group
            with that name exists.
        """
        node = None
        for element in self.elements():
            if isinstance(element, Group) and element.name == name:
                node = element.treenode
                break
        if node is None:
            return None

        new = type(self)(name=name)
        # The group's model transformation already folds in its own
        # transformation plus every ancestor's and the source model's, so the
        # extracted contents keep their place in the world.
        new.transformation = node.element.modeltransformation

        # Materials are carried over lazily - only those actually used in the subtree.
        materials: dict = {}

        def _material_for(source):
            if not source._material:
                return None
            if source._material not in materials:
                materials[source._material] = new.add_or_get_material(self._materials[source._material].copy())
            return materials[source._material]

        # Elements (cloned with fresh guids, hierarchy preserved). The group node
        # itself is dropped - its children become the new model's top-level elements.
        elements: dict = {}

        def _clone(source_node, parent) -> None:
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

    # ==========================================================================
    # Construction
    # ==========================================================================

    @classmethod
    def from_model(cls, model: Model, name: Optional[str] = None) -> "TFModel":
        """Re-wrap a plain :class:`compas_model.models.Model` as a :class:`TFModel`.

        The elements are shared, not copied - the tree and the interaction graph
        are rebuilt around them by ``Model.__from_data__``.

        Parameters
        ----------
        model : :class:`compas_model.models.Model`
        name : str, optional

        Returns
        -------
        :class:`TFModel`
        """
        tfmodel = cls.__from_data__(model.__data__)
        tfmodel.name = name or model.name
        return tfmodel
