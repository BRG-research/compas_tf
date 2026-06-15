import math

from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_model.elements import ColumnElement
from compas_model.elements.group import Group
from compas_model.models import Model
from compas_model.models.elementtree import ElementNode
from compas_model.models.interactiongraph import InteractionGraph

from compas_tf.floor_builder import FloorBuilder
from compas_tf.joint_dowel import DowelElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.plate import PlateElement
from compas_tf.solid_difference_modifier import SolidDifferenceModifier
from compas_tf.support import SupportElement


def merge_collinear_points(points, angle_tol=1e-3, closed=True):
    """Drop intermediate points that lie on the line through their neighbors.

    Iterates until a fixed point. Compas has no built-in for this.

    Parameters
    ----------
    points : sequence of Point
        Input vertices.
    angle_tol : float
        Collinearity tolerance expressed as ``sin(angle)`` between
        consecutive edge directions. 1e-3 ≈ 0.057° (tight, only drops
        machine-collinear points). Raise to merge near-collinear runs.
    closed : bool
        If True, treat the input as a closed polygon (wrap-around when
        evaluating the first/last vertex). If False, the endpoints are
        always kept.

    Returns
    -------
    list[Point]
    """
    pts = list(points)
    while True:
        n = len(pts)
        if n < 3:
            return pts
        kept = []
        dropped = False
        for i, curr in enumerate(pts):
            if not closed and (i == 0 or i == n - 1):
                kept.append(curr)
                continue
            prev = pts[(i - 1) % n]
            nxt = pts[(i + 1) % n]
            v1 = curr - prev
            v2 = nxt - curr
            l1, l2 = v1.length, v2.length
            if l1 < 1e-9:
                dropped = True
                continue
            if l2 < 1e-9:
                kept.append(curr)
                continue
            sin_angle = v1.cross(v2).length / (l1 * l2)
            if sin_angle < angle_tol:
                dropped = True
                continue
            kept.append(curr)
        if not dropped:
            return kept
        pts = kept


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
            "story_height": self.story_height,
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
        self.debug = []  # debug geometry pushed by internal steps; iterate from caller (e.g. viewer)

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

        guide_group = self.add_group("floor_guide")

        plate_sections = [
            ("beds", guide.beds),
            ("tsections", guide.tsections),
            ("outer_ribs", guide.outer_ribs),
            ("inner_ribs", guide.inner_ribs),
            ("wedge_block", guide.wedge_block),
            ("wedges_inner_beams", guide.wedges_inner_beams),
            ("inner_beams", guide.inner_beams),
        ]
        if include_oculus:
            plate_sections.append(("oculus", guide.oculus))

        for group_name, plates in plate_sections:
            sub = Group(name=group_name)
            self.add_element(sub, parent=guide_group)
            for i, plate in enumerate(plates):
                plate.name = f"{group_name}_{i}"
                plate.contact_group = group_name
                if transformation is not None:
                    if plate.transformation is not None:
                        plate.transformation = transformation * plate.transformation
                    else:
                        plate.transformation = transformation
                self.add_element(plate, parent=sub)

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

    def add_column(self, column_size=200, capitel_width = 120, capitel_height = 750):
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
            column = ColumnElement(column_size, column_size, column_height, rot * Transformation.from_frame(base_frame), name=f"column_{i}", capitel_width=capitel_width, capitel_height=capitel_height)
            self.add_element(column, parent=columns_group)

    # ------------------------------------------------------------------ #
    #  BVH / contact detection (skip Group elements — they have no geometry)
    # ------------------------------------------------------------------ #

    def _skip_contacts(self, element):
        """Return True if the element should be excluded from contact detection."""
        from compas_tf.wedge import WedgeElement

        return isinstance(element, (Group, DowelElement, WedgeElement)) or getattr(element, "skip_contacts", False)

    def compute_bvh(self, nodetype=None, max_depth=None, leafsize=1, where=None):
        """Build a BVH from elements that pass _skip_contacts and the optional
        ``where`` predicate. With ``where`` set, the BVH is returned but NOT
        cached on the model, so subsequent unrestricted queries are unaffected.

        Parameters
        ----------
        where : callable[(element), bool], optional
            Predicate to further restrict which elements enter the BVH.
            Example: ``where=lambda el: getattr(el, "contact_group", None) == "inner_beams"``.
        """
        from compas_model.models.bvh import ElementAABBNode
        from compas_model.models.bvh import ElementBVH

        if nodetype is None:
            nodetype = ElementAABBNode
        valid = [el for el in self.elements() if not self._skip_contacts(el) and (where is None or where(el))]
        bvh = ElementBVH.from_elements(valid, nodetype=nodetype, max_depth=max_depth, leafsize=leafsize)
        if where is None:
            self._bvh = bvh
        return bvh

    def compute_contacts_inner_beams(self, tolerance=1.0, minimum_area=1.0, contacttype=None, wedge_spacing=700, single_wedge_or_division=True):
        """Contact detection restricted to the 16 plates that form the
        inner_beam/oculus joint ring:

        - 12 ``inner_beams`` plates (3 per quarter × 4 quarters)
        - 4 oculus boundary plates (``oculus_0`` .. ``oculus_3``)

        Only the two large PlateElement faces (top_polyline / bottom_polyline)
        participate. The thin perimeter quads ("side" faces) are skipped on
        both sides of every pair.

        After detection, places a ``WedgeElement`` along each contact's
        **longest top edge**, subdivided by ``wedge_spacing``. Each wedge body
        and its dowels are registered as ``SolidDifferenceModifier`` cutters
        against the two plates that form the contact, so both the wedge slot
        and the dowel holes are produced as boolean differences.

        Parameters
        ----------
        wedge_spacing : float
            Approximate spacing between wedges along each contact's top edge.
            Set to 0 or negative to disable wedge placement.
        """

        def _filter(el):
            cg = getattr(el, "contact_group", None)
            if cg == "inner_beams":
                return True
            if cg == "oculus":
                name = getattr(el, "name", "") or ""
                if name.startswith("oculus_"):
                    try:
                        return int(name.rsplit("_", 1)[-1]) < 4
                    except ValueError:
                        return False
            return False

        self.compute_contacts(
            tolerance=tolerance,
            minimum_area=minimum_area,
            contacttype=contacttype,
            where=_filter,
            face_kinds={"top", "bottom"},
        )

        if wedge_spacing and wedge_spacing > 0:
            if single_wedge_or_division:
                self._add_single_wedge_per_contact()
            else:
                self._add_wedges_along_contacts(wedge_spacing=wedge_spacing)

    def _add_wedge_dowels(self, wedge, group, cut_elements=(), width=20, step=320):
        """Add dowel elements into *group* and register them as cutters.

        Dowels are placed as siblings of the wedge (not children) so that the
        model transformation is not compounded with the wedge's own transform.
        Each dowel is registered as a ``SolidDifferenceModifier`` cutter against
        every element in ``cut_elements`` (typically the two plates that form
        the contact), so dowels drill holes through the plates as a boolean
        difference, exactly like the wedge body.
        """
        for index, dowel in enumerate(wedge.create_dowels(width=width, step=step)):
            dowel.name = f"{wedge.name}_dowel_{index}"
            self.add_element(dowel, parent=group)
            for el in cut_elements:
                self.add_modifier(dowel, el, SolidDifferenceModifier())

    def _add_single_wedge_per_contact(self):
        """Place WedgeElements along the longest top edge of every contact.
        Each wedge body and its dowels are registered as SolidDifferenceModifier
        cutters against the two plates that form the contact, so the dowels
        drill holes through the plates as a boolean difference.

        Frame orientation:
            X axis = edge direction (along the longest top edge)
            Y axis = contact polygon normal
            Z axis = X cross Y
        """
        from compas.geometry import Frame
        from compas.geometry import Polygon as GeomPolygon
        from compas.geometry import Transformation

        from compas_tf.wedge import WedgeElement

        # Snapshot edges with contacts before mutating the graph.
        edge_contacts = []
        for edge in self.graph.edges():
            contacts = self.graph.edge_attribute(edge, name="contacts")
            if contacts:
                u, v = edge
                el_a = self.graph.node_element(u)
                el_b = self.graph.node_element(v)
                for contact in contacts:
                    edge_contacts.append((el_a, el_b, contact))

        wedges_group = self.add_group("contact_wedges")
        dowels_group = self.add_group("contact_dowels")
        wedge_idx = 0

        for el_a, el_b, contact in edge_contacts:
            polygon = getattr(contact, "polygon", None)
            if polygon is None:
                continue
            pts = list(polygon.points)
            pts = merge_collinear_points(pts, angle_tol=1e-3, closed=True)
            n_pts = len(pts)
            if n_pts < 3:
                continue

            contact_normal = GeomPolygon(pts).normal

            centroid_z = sum(p[2] for p in pts) / n_pts
            scored = []
            for i in range(n_pts):
                a, b = pts[i], pts[(i + 1) % n_pts]
                mid_z = (a[2] + b[2]) / 2
                length = (b - a).length
                is_top = mid_z >= centroid_z
                scored.append((is_top, length, a, b))
            scored.sort(key=lambda e: (not e[0], -e[1]))
            _, length, start, end = scored[0]
            if length < 1e-6:
                continue

            direction = (end - start).unitized()

            # One wedge at the midpoint of the longest top edge, scaled along
            # the edge so its length matches the contact length minus twice the
            # plate thickness.

            pt = start + direction * (length / 2)
            frame = Frame(pt, direction, contact_normal)

            plate_thickness = max(el_a.computed_thickness, el_b.computed_thickness)
            target_length = max(length - 3.0 * plate_thickness, 1e-6)

            xform = Transformation.from_frame(frame)

            wedge = WedgeElement(target_length=target_length, transformation=xform)
            wedge.name = f"contact_wedge_{wedge_idx}"
            self.add_element(wedge, parent=wedges_group)
            self._add_wedge_dowels(wedge, dowels_group, cut_elements=(el_a, el_b))

            self.add_modifier(wedge, el_a, SolidDifferenceModifier())
            self.add_modifier(wedge, el_b, SolidDifferenceModifier())

            wedge_idx += 1

        self.precompute_boolean_modifiers()
        return wedges_group

    def _add_wedges_along_contacts(self, wedge_spacing=700):
        """Place WedgeElements along the longest top edge of every contact.
        Each wedge body and its dowels are registered as SolidDifferenceModifier
        cutters against the two plates that form the contact, so the dowels
        drill holes through the plates as a boolean difference.

        Frame orientation:
            X axis = edge direction (along the longest top edge)
            Y axis = contact polygon normal
            Z axis = X cross Y
        """
        from compas.geometry import Frame
        from compas.geometry import Polygon as GeomPolygon
        from compas.geometry import Transformation

        from compas_tf.wedge import WedgeElement

        # Snapshot edges with contacts before mutating the graph.
        edge_contacts = []
        for edge in self.graph.edges():
            contacts = self.graph.edge_attribute(edge, name="contacts")
            if contacts:
                u, v = edge
                el_a = self.graph.node_element(u)
                el_b = self.graph.node_element(v)
                for contact in contacts:
                    edge_contacts.append((el_a, el_b, contact))

        wedges_group = self.add_group("contact_wedges")
        dowels_group = self.add_group("contact_dowels")
        wedge_idx = 0

        for el_a, el_b, contact in edge_contacts:
            polygon = getattr(contact, "polygon", None)
            if polygon is None:
                continue
            pts = list(polygon.points)
            pts = merge_collinear_points(pts, angle_tol=1e-3, closed=True)
            n_pts = len(pts)
            if n_pts < 3:
                continue

            contact_normal = GeomPolygon(pts).normal

            centroid_z = sum(p[2] for p in pts) / n_pts
            scored = []
            for i in range(n_pts):
                a, b = pts[i], pts[(i + 1) % n_pts]
                mid_z = (a[2] + b[2]) / 2
                length = (b - a).length
                is_top = mid_z >= centroid_z
                scored.append((is_top, length, a, b))
            scored.sort(key=lambda e: (not e[0], -e[1]))
            _, length, start, end = scored[0]
            if length < 1e-6:
                continue

            direction = (end - start).unitized()

            n = round(length / (wedge_spacing / 2))
            n = n if n % 2 == 0 else n + 1
            if n == 0:
                continue
            new_spacing = length / n

            for k in range(1, n):
                if k % 2 == 0:
                    continue
                pt = start + direction * (new_spacing * k)
                frame = Frame(pt, direction, contact_normal)

                wedge = WedgeElement(transformation=Transformation.from_frame(frame))
                wedge.name = f"contact_wedge_{wedge_idx}"
                self.add_element(wedge, parent=wedges_group)
                self._add_wedge_dowels(wedge, dowels_group, cut_elements=(el_a, el_b))

                self.add_modifier(wedge, el_a, SolidDifferenceModifier())
                self.add_modifier(wedge, el_b, SolidDifferenceModifier())

                wedge_idx += 1

        self.precompute_boolean_modifiers()
        return wedges_group

    def compute_contacts(self, tolerance=1e-6, minimum_area=1e-2, contacttype=None, where=None, face_kinds=None):
        """Compute pairwise contacts. With ``where`` set, only elements that
        match the predicate participate on both sides (subject and neighbor),
        and a temporary filtered BVH is built so neighbor queries stay tight.

        Parameters
        ----------
        where : callable[(element), bool], optional
            Predicate to restrict the contact set. Example to detect contacts
            only among inner_beams plates (tagged via ``plate.contact_group``)::

                model.compute_contacts(
                    where=lambda el: getattr(el, "contact_group", None) == "inner_beams",
                )

            The full-model cached BVH (if any) is not invalidated by a
            filtered call.

        face_kinds : set[str], optional
            Forwarded to ``element.compute_contacts``. Restrict pair
            evaluation to a subset of ``{"top", "bottom", "side"}`` —
            e.g. ``{"top", "bottom"}`` keeps only the two large
            PlateElement faces and drops the thin perimeter quads.
            Only elements whose ``compute_contacts`` accepts ``face_kinds``
            (currently ``PlateElement``) will honor it.
        """
        from compas_model.interactions.contact import Contact

        if contacttype is None:
            contacttype = Contact

        if where is None:
            bvh = self.bvh
            subjects = (el for el in self.elements() if not self._skip_contacts(el))
        else:
            bvh = self.compute_bvh(where=where)
            subjects = (el for el in self.elements() if not self._skip_contacts(el) and where(el))

        extra = {}
        if face_kinds is not None:
            extra["face_kinds"] = face_kinds

        for element in subjects:
            u = element.graphnode
            for nbr in bvh.nearest_neighbors(element):
                if self._skip_contacts(nbr):
                    continue
                if where is not None and not where(nbr):
                    continue
                v = nbr.graphnode
                try:
                    if not self.graph.has_edge((u, v), directed=False):
                        contacts = element.compute_contacts(nbr, tolerance=tolerance, minimum_area=minimum_area, contacttype=contacttype, **extra)
                        if contacts:
                            self.graph.add_edge(u, v, contacts=contacts)
                    else:
                        edge = (u, v) if self.graph.has_edge((u, v)) else (v, u)
                        existing = self.graph.edge_attribute(edge, name="contacts")
                        if not existing:
                            contacts = element.compute_contacts(nbr, tolerance=tolerance, minimum_area=minimum_area, contacttype=contacttype, **extra)
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
            bool_sources = []  # list of (Mesh, operation_str)
            union_sources = []  # SolidUnionModifier sources (merged separately)
            other_modifiers = []  # (source_element, modifier)

            for nbr in self.graph.neighbors_in(element.graphnode):
                modifiers = self.graph.edge_attribute((nbr, element.graphnode), name="modifiers") or []
                source = self.graph.node_element(nbr)
                for modifier in modifiers:
                    if isinstance(modifier, SolidDifferenceModifier):
                        op = getattr(modifier, "operation", "difference")
                        src_geoms = getattr(source, "boolean_geometries", None)
                        if src_geoms is None:
                            src_geom = getattr(source, "boolean_geometry", None) or source.modelgeometry
                            src_geoms = [src_geom]

                        for src_geom in src_geoms:
                            if op == "union":
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
