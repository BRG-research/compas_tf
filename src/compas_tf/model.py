from typing import Iterator
from typing import Optional

from compas_model.elements import Group
from compas_model.interactions import Contact
from compas_model.models.bvh import ElementBVH

from compas_tf.base_model import BaseModel
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
            the wood search, which builds no Breps at all, so nothing is cached
            here and the solids are always made fresh
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

    def contact_pairs(self) -> Iterator:
        """``(index, element_a, element_b, contact)`` for every contact.

        The order is the one :meth:`contacts` yields, and it is what makes the
        adjacency sidecar work - see :meth:`contacts_to_json`. Everything that
        writes contacts out goes through here, so the indices always agree.
        """
        index = 0
        for edge in self.graph.edges():
            contacts = self.graph.edge_attribute(edge, name="contacts")
            if not contacts:
                continue
            a = self.graph.node_element(edge[0])
            b = self.graph.node_element(edge[1])
            for contact in contacts:
                yield index, a, b, contact
                index += 1

    def contact_breps(self) -> list:
        """One planar-face Brep per contact, named ``contact_<i>__<a>__<b>``.

        Boundary loop only - holes are dropped, since a contact written this way
        is a surface for inspection, not a solid. The name is for use in memory:
        STEP does not carry it (see :meth:`contacts_to_json`).
        """
        from compas_occt.brep import OCCBrep

        breps = []
        for index, a, b, contact in self.contact_pairs():
            brep = OCCBrep.from_polygons([contact.polygon], solid=False)
            brep.name = f"contact_{index}__{a.name}__{b.name}"
            breps.append(brep)
        return breps

    def contact_adjacency(self) -> list[dict]:
        """Which element each contact joins to which, one record per contact.

        Returns
        -------
        list[dict]
            ``index``, ``a`` / ``b`` (element names), ``a_type`` / ``b_type``,
            ``a_guid`` / ``b_guid``, and ``area``. ``index`` is the position of
            the matching face in :meth:`contacts_to_step`'s output.
        """
        records = []
        for index, a, b, contact in self.contact_pairs():
            records.append(
                {
                    "index": index,
                    "a": a.name,
                    "b": b.name,
                    "a_type": type(a).__name__,
                    "b_type": type(b).__name__,
                    "a_guid": str(a.guid),
                    "b_guid": str(b.guid),
                    "area": contact.polygon.area,
                }
            )
        return records

    def contacts_to_step(self, path: str, author: str = "compas_tf") -> str:
        """Write the contacts to their own STEP file, one face each.

        Separate from :meth:`to_step` on purpose: that file is the shop's, and a
        reader splits it with ``.solids``, which would drop loose faces.

        The faces carry no adjacency - STEP drops the per-shape name (a
        round-trip through ``to_step`` / ``from_step`` returns them all as
        ``OCCBrepFace``, and ``from_step_with_attributes`` collapses the
        compound into one unnamed entry). What it does preserve is the ORDER, so
        pair the file with :meth:`contacts_to_json` and match on index.
        """
        from compas_occt.brep import OCCBrep

        breps = self.contact_breps()
        if not breps:
            raise ValueError("contacts_to_step: the model has no contacts; run a contact search first.")
        compound = OCCBrep.from_breps(breps)
        compound.to_step(str(path), name=f"{self.name or 'compas_tf_model'}_contacts", author=author)
        return str(path)

    def contacts_to_json(self, path: str) -> str:
        """Write the contact adjacency beside the contact STEP.

        Record ``i`` describes face ``i`` of the file
        :meth:`contacts_to_step` wrote, which is the only way to know which two
        elements a face in that file joins.
        """
        import json

        records = self.contact_adjacency()
        with open(path, "w") as f:
            json.dump({"model": self.name, "count": len(records), "contacts": records}, f, indent=1)
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

    def compute_contacts_wood(
        self,
        groups: Optional[list[str]] = None,
        search_type: int = 0,
        minimum_area: float = 1e-2,
        contacttype: type[Contact] = Contact,
        clear: bool = False,
        face_kinds: Optional[set] = None,
        connections: Optional[set] = None,
        kind_pairs: Optional[set] = None,
        tolerance: float = 1.0,
    ) -> dict[int, int]:
        """Detect plate interfaces with ``wood_nano``, keeping each joint's type.

        The geometric searches - :meth:`compute_contacts`,
        :meth:`compas_tf.base_model.BaseModel.compute_contacts_between_groups` -
        intersect element geometry pair by pair and answer only *where* two
        elements touch. ``wood_nano`` takes the whole plate assembly at once, as
        the top/bottom outline pair every plate is modelled from, and returns
        each interface **with a joint type** - the classification a joinery
        solver needs. See :mod:`compas_tf.wood`.

        Only :class:`compas_tf.plate.PlateElement` takes part: wood reads
        outline pairs, and a column, dowel, cylinder or connector has none. Those
        elements are invisible to this search, so keep a geometric search for
        them. The count of what was skipped is reported by
        :func:`compas_tf.wood.skipped_elements`.

        The joint type of each contact is stored on the interaction graph edge
        under ``joint_types``, positionally matching the edge's ``contacts``.

        Measured on one quarter (34 plates): 117 interfaces, the same 117 that
        :meth:`compas_tf.base_model.BaseModel.compute_contacts_within_groups`
        finds and that a brute-force sweep confirms, with an identical breakdown
        per group pair.

        Parameters
        ----------
        groups
            Restrict the search to plates under these named groups. Default
            searches every plate in the model.
        search_type
            wood's search type, passed through unchanged.
        minimum_area
            Drop interfaces whose joint area is smaller than this.
        contacttype
            The contact class to instantiate.
        clear
            Clear the contacts already on the graph first, so the result holds
            only what this search found. See :meth:`clear_contacts`.
        face_kinds
            Keep only interfaces lying on these faces, a subset of
            ``{"top", "bottom", "side"}`` - the same filter
            :meth:`compas_tf.plate.PlateElement.compute_contacts` takes, and
            applied the same way, to both plates of a pair. wood does not label
            its joint areas, so the kinds are recovered geometrically by
            :func:`compas_tf.wood.classify_joint_face`. Default keeps everything.
        connections
            Keep only these joint types, in the joinery vocabulary:
            ``{"face-to-face"}``, ``{"side-to-side"}``, ``{"face-to-side"}``.
            See :data:`compas_tf.wood.JOINT_CONNECTIONS`. This is the filter to
            reach for.
        kind_pairs
            The finer filter, on the exact faces - ``{"top-bottom"}`` for plates
            stacked the same way up only, where ``connections={"face-to-face"}``
            also admits ``top-top``. Rarely needed.
        tolerance
            Plane-matching tolerance for that classification, in model units.

        Returns
        -------
        dict[int, int]
            How many interfaces came back per joint type. The integers are
            wood's own - treat them as opaque keys.

        Raises
        ------
        ImportError
            If ``wood_nano`` is not installed. The message says how to get it.
        ValueError
            If the model has no plates to search.

        """
        from compas_tf.wood import joint_connection
        from compas_tf.wood import joint_face_pair
        from compas_tf.wood import plate_participants
        from compas_tf.wood import wood_joints

        plates = plate_participants(self, groups)
        if not plates:
            raise ValueError("compute_contacts_wood: the model has no PlateElement to search{}.".format(f" under groups {sorted(groups)}" if groups else ""))

        if clear:
            self.clear_contacts()

        histogram: dict[int, int] = {}
        detected = wood_joints(
            plates,
            search_type=search_type,
            face_kinds=face_kinds,
            connections=connections,
            kind_pairs=kind_pairs,
            tolerance=tolerance,
        )
        for index_a, index_b, polygon, joint_type, kind_a, kind_b in detected:
            if polygon.area < minimum_area:
                continue

            a, b = plates[index_a], plates[index_b]
            faces = joint_face_pair(kind_a, kind_b)
            connection = joint_connection(kind_a, kind_b)
            contact = contacttype(points=polygon.points, name=f"wood_joint_{joint_type}__{connection}")

            u, v = a.graphnode, b.graphnode
            if not self.graph.has_edge((u, v), directed=False):
                self.graph.add_edge(
                    u, v, contacts=[contact], joint_types=[joint_type], joint_faces=[faces], joint_connections=[connection]
                )
            else:
                edge = (u, v) if self.graph.has_edge((u, v)) else (v, u)
                contacts = self.graph.edge_attribute(edge, name="contacts") or []
                types = self.graph.edge_attribute(edge, name="joint_types") or []
                stored_faces = self.graph.edge_attribute(edge, name="joint_faces") or []
                stored_conn = self.graph.edge_attribute(edge, name="joint_connections") or []
                self.graph.edge_attribute(edge, name="contacts", value=list(contacts) + [contact])
                self.graph.edge_attribute(edge, name="joint_types", value=list(types) + [joint_type])
                self.graph.edge_attribute(edge, name="joint_faces", value=list(stored_faces) + [faces])
                self.graph.edge_attribute(edge, name="joint_connections", value=list(stored_conn) + [connection])

            histogram[joint_type] = histogram.get(joint_type, 0) + 1

        return histogram

    def joint_type_pairs(self):
        """``(element_a, element_b, contact, joint_type, connection, faces)`` per contact.

        ``connection`` names the joint the way joinery does -
        ``"face-to-face"``, ``"face-to-side"``, ``"side-to-side"``. ``faces`` is
        the finer reading, ``"top-bottom"`` / ``"top-top"`` / ``"side-side"``,
        kept for when the two large faces of a plate must be told apart.

        Only the contacts a wood search wrote carry these; the group searches
        leave ``joint_types`` unset, and those edges are skipped here.
        """
        for edge in self.graph.edges():
            contacts = self.graph.edge_attribute(edge, name="contacts")
            types = self.graph.edge_attribute(edge, name="joint_types")
            if not contacts or not types:
                continue
            faces = self.graph.edge_attribute(edge, name="joint_faces") or [None] * len(contacts)
            conns = self.graph.edge_attribute(edge, name="joint_connections") or [None] * len(contacts)
            a = self.graph.node_element(edge[0])
            b = self.graph.node_element(edge[1])
            for contact, joint_type, connection, face_pair in zip(contacts, types, conns, faces):
                yield a, b, contact, joint_type, connection, face_pair

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
