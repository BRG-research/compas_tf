from collections.abc import Callable
from typing import Iterator
from typing import Optional

from compas_model.elements import Group
from compas_model.interactions import Contact
from compas_model.models.bvh import ElementBVH

from compas_tf.base_model import BaseModel
from compas_tf.base_model import _element_contacts
from compas_tf.brep import BrepMixin
from compas_tf.element import TFElement


class TFModel(BaseModel, BrepMixin):
    """A :class:`compas_tf.base_model.BaseModel` whose geometry survives serialization.

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

    def element_breps(self, variant: Optional[str] = None, cache: Optional[dict] = None, **kwargs) -> list:
        """One solid, coplanar-merged Brep per element, named after the element.

        Parameters
        ----------
        variant : str, optional
            A baked variant key to convert instead of each element's finished
            geometry. Elements that do not carry it are skipped - including any
            element that is not a compas_tf element, since only those can hold
            variants.
        cache : dict[int, :class:`compas_occt.brep.OCCBrep`], optional
            Already-converted Breps keyed by ``id(element)``, reused instead of
            being rebuilt. This is the ``.breps`` of a
            :class:`compas_tf.contacts.BrepContacts`, so a model that has just
            had its contacts computed on Breps does not pay for the conversion
            twice. Ignored when ``variant`` is given, since the cache holds the
            finished geometry.
        **kwargs
            Forwarded to :meth:`compas_tf.brep.BrepMixin.get_brep`.

        Returns
        -------
        list[:class:`compas_occt.brep.OCCBrep`]
        """
        from compas_tf.brep import mesh_to_brep

        if variant is not None:
            cache = None

        breps = []
        for element in self.geometry_elements():
            name = element.name or type(element).__name__
            cached = cache.get(id(element)) if cache else None
            if cached is not None:
                cached.name = name
                breps.append(cached)
                continue
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

    def to_step(self, path: str, author: str = "compas_tf", variant: Optional[str] = None, cache: Optional[dict] = None, **kwargs) -> str:
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
        cache : dict[int, :class:`compas_occt.brep.OCCBrep`], optional
            Already-converted Breps to reuse - see :meth:`element_breps`.
        **kwargs
            Forwarded to :meth:`compas_tf.brep.BrepMixin.get_brep`.

        Returns
        -------
        str
            The path written.
        """
        from compas_occt.brep import OCCBrep

        breps = self.element_breps(variant=variant, cache=cache, **kwargs)
        compound = OCCBrep.from_breps(breps)
        compound.to_step(str(path), name=self.name or "compas_tf_model", author=author)
        return str(path)

    def contact_breps(self) -> list:
        """One planar-face Brep per contact, named ``contact_<i>``.

        Boundary loop only - holes are dropped, since a contact written this way
        is a surface for inspection, not a solid.
        """
        from compas_occt.brep import OCCBrep

        breps = []
        for index, contact in enumerate(self.contacts()):
            brep = OCCBrep.from_polygons([contact.polygon], solid=False)
            brep.name = f"contact_{index}"
            breps.append(brep)
        return breps

    def contacts_to_step(self, path: str, author: str = "compas_tf") -> str:
        """Write the contacts to their own STEP file, one face each.

        Separate from :meth:`to_step` on purpose: that file is the shop's, and a
        reader splits it with ``.solids``, which would drop loose faces.
        """
        from compas_occt.brep import OCCBrep

        breps = self.contact_breps()
        if not breps:
            raise ValueError("contacts_to_step: the model has no contacts; run a contact search first.")
        compound = OCCBrep.from_breps(breps)
        compound.to_step(str(path), name=f"{self.name or 'compas_tf_model'}_contacts", author=author)
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

    def compute_contacts(
        self,
        tolerance: float = 1e-6,
        minimum_area: float = 1e-2,
        contacttype: type[Contact] = Contact,
        contactmethod: Optional[Callable] = None,
    ) -> None:
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
        contactmethod
            What detects the contacts of one candidate pair, called as
            ``contactmethod(a, b, tolerance=, minimum_area=, contacttype=)``.
            Default is ``a.compute_contacts(b, ...)``, i.e. mesh faces. Pass a
            :class:`compas_tf.contacts.BrepContacts` to run on Brep faces
            instead, or use :meth:`compute_contacts_brep`.

        """
        # somehow this should not take into account past calculations.

        if contactmethod is None:
            contactmethod = _element_contacts

        for element in self.geometry_elements():
            u = element.graphnode

            for nbr in self.bvh.nearest_neighbors(element):
                v = nbr.graphnode

                if not self.graph.has_edge((u, v), directed=False):
                    # there is no interaction edge between the two elements
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
                    # there is an existing edge between the two elements
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

    def clear_contacts(self) -> "TFModel":
        """Drop every contact stored on the interaction graph, keeping the edges.

        Contact searches never remove a contact - they only fill in edges that
        have none (see :meth:`compute_contacts`). So a model loaded from file
        keeps whatever contacts were computed when it was written, and a fresh
        search has to start from a clean graph to report only its own result.
        """
        for edge in list(self.graph.edges()):
            self.graph.edge_attribute(edge, name="contacts", value=[])
        return self

    def compute_contacts_brep(
        self,
        tolerance: float = 1e-6,
        minimum_area: float = 1e-1,
        groups: Optional[list[str]] = None,
        groups_b: Optional[list[str]] = None,
        contacttype: type[Contact] = Contact,
        clear: bool = False,
        **kwargs,
    ):
        """Contacts on Brep faces rather than mesh faces - one polygon per interface.

        The same spatial search as :meth:`compute_contacts`, with
        :class:`compas_tf.contacts.BrepContacts` doing the detection: the BVH
        still prunes on the mesh AABBs, but each surviving pair is converted to a
        solid Brep with its coplanar faces merged (``element.get_brep()``) and
        intersected face against face. A boolean-triangulated interface therefore
        comes back as ONE contact carrying its hole loops, instead of one contact
        per triangle - see :mod:`compas_tf.contacts` for the numbers.

        Parameters
        ----------
        tolerance : float, optional
            The distance tolerance.
        minimum_area : float, optional
            The minimum contact size. The 1e-2 default of the mesh search is
            below the noise of a merged Brep face; 1.0 mm2 is a sane floor for
            this model.
        groups : list[str], optional
            Restrict the search to these named groups, as in
            :meth:`compas_tf.base_model.BaseModel.compute_contacts_between_groups`.
            Default searches every pair of geometry elements.
        groups_b : list[str], optional
            The second side of a two-sided group query. Requires ``groups``.
        contacttype : type[:class:`compas_model.interactions.Contact`], optional
            The contact class to instantiate.
        clear : bool, optional
            Clear the contacts already on the graph first, so the result holds
            only what this search found. See :meth:`clear_contacts`.
        **kwargs
            Forwarded to :class:`compas_tf.contacts.BrepContacts` - ``holes``,
            ``strict``, ``skip``, and any ``get_brep()`` keyword.
            ``skip=involving(DowelCylinderElement, ConnectorCylinderElement)``
            drops the fastener contacts, which on this model are 74% of the
            total and are all a shaft touching its own hole.

        Returns
        -------
        :class:`compas_tf.contacts.BrepContacts`
            The detector, holding the Brep cache it built (``.breps``) and the
            face pairs that failed (``.errors``).
        """
        from compas_tf.contacts import BrepContacts

        if groups_b and not groups:
            raise ValueError("compute_contacts_brep: groups_b needs groups; it is the second side of a two-sided query.")

        if clear:
            self.clear_contacts()

        method = BrepContacts(**kwargs)

        if groups:
            self.compute_contacts_between_groups(
                groups,
                groups_b=groups_b,
                tolerance=tolerance,
                minimum_area=minimum_area,
                contacttype=contacttype,
                contactmethod=method,
            )
        else:
            self.compute_contacts(
                tolerance=tolerance,
                minimum_area=minimum_area,
                contacttype=contacttype,
                contactmethod=method,
            )

        return method

    # ==========================================================================
    # Construction
    # ==========================================================================

    @classmethod
    def from_model(cls, model: BaseModel, name: Optional[str] = None) -> "TFModel":
        """Re-wrap a plain model as a :class:`TFModel`.

        Accepts a :class:`compas_model.models.Model` too - only ``__data__`` is
        read, and that is the same on both.

        The elements are shared, not copied - the tree and the interaction graph
        are rebuilt around them by ``Model.__from_data__``.

        Parameters
        ----------
        model : :class:`compas_tf.base_model.BaseModel` or :class:`compas_model.models.Model`
        name : str, optional

        Returns
        -------
        :class:`TFModel`
        """
        tfmodel = cls.__from_data__(model.__data__)
        tfmodel.name = name or model.name
        return tfmodel
