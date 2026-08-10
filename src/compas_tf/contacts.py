"""Contact detection on Brep faces instead of mesh faces.

A contact is two coplanar, oppositely oriented, overlapping polygons. Where
those polygons come from decides the answer:

- ``mesh_mesh_contacts`` uses ``element.modelgeometry`` - triangles, after a
  boolean. One physical interface comes back as several contact polygons (the
  column/outer-rib joint splits into 8) from an O(faces_a x faces_b) search over
  the soup: 626 x 246 faces, ~13 s for that one pair. It also drops area - on
  one of the 8 identical column/rib joints it returns 50344 mm2 instead of
  62632, invisibly, because the interface is already in pieces.
- ``brep_brep_contacts`` uses Brep faces. :func:`compas_tf.brep.mesh_to_brep`
  merges those triangles back into the modelled faces and a Brep face carries
  its hole loops, so the same joint is 1 contact of the full area in ~0.2 s.

Breps cannot simply be put on the elements - ``Element.compute_aabb`` and the
BVH are Mesh-only - so :class:`BrepContacts` keeps the Mesh model, lets the BVH
prune on the mesh AABBs, and converts only the pairs that survive.

**Local, not upstream.** :func:`brep_brep_contacts` is compas_model's function
with the failures contained: upstream lets one bad face pair kill the whole
element pair, and 23 of 2444 pairs here die inside
``brepface_brepface_overlap_holes`` (shapely: ``GeometryCollection has no
attribute 'interiors'``, ``unable to assign free hole to a shell``) AFTER the
contact polygon computed fine. Each face pair is guarded on its own, so that
costs the holes, not the contact. The geometry itself is still upstream's.

**No tessellation.** ``Brep.overlap`` would prefilter the face pairs for us, but
it works on OCC's *tessellation* and triangulates each Brep on first use - at
``TOL.lineardeflection`` (0.001 mm, a 1 micron chord tolerance on a building)
that meshing alone was 200 s of a 205 s search. It is not needed: a contact
needs two faces with exactly opposite normals whose boundary AABBs meet, and
both are exact tests on the face boundaries. :func:`prepare_faces` takes those
once per Brep and :func:`brep_brep_contacts` filters on them, for identical
results (585 pairs, 2.0921e+07 mm2) 3.8x faster than ``overlap()`` even with its
tessellation already cached.

Do not narrow the prefilter to ``face.is_plane``: these Breps are built from
mesh polygons, so a flat quad comes back as a bilinear surface and the planar
test drops 529 of the 585 pairs.
"""

import inspect
from collections.abc import Callable
from typing import Optional

from compas_model.interactions import Contact

from compas_tf.brep import BrepMixin
from compas_tf.brep import mesh_to_brep


def involving(*types) -> Callable:
    """A ``skip`` predicate that rejects a pair if EITHER element is one of ``types``.

    For dropping whole classes of element from a contact search - typically
    fasteners, whose contacts are a shaft sitting in its own hole. On the
    cantilevers model the dowels and connector cylinders account for 2072 of the
    2805 contacts (each faceted shaft touches its host once per facet), and none
    of them touch each other, so they are pure noise over the 733 real
    interfaces::

        model.compute_contacts_brep(skip=involving(DowelCylinderElement, ConnectorCylinderElement))

    Parameters
    ----------
    *types : type
        Element classes, matched with ``isinstance``.

    Returns
    -------
    callable
        ``(a, b) -> bool``, suitable as :class:`BrepContacts`'s ``skip``.
    """

    def skip(a, b) -> bool:
        return isinstance(a, types) or isinstance(b, types)

    return skip


def between(*types) -> Callable:
    """A ``skip`` predicate that rejects a pair only if BOTH elements are one of ``types``.

    The narrower companion to :func:`involving`: it removes contacts *within* a
    set of elements while keeping the contacts each of them makes with the rest
    of the model.

    Parameters
    ----------
    *types : type
        Element classes, matched with ``isinstance``.

    Returns
    -------
    callable
        ``(a, b) -> bool``, suitable as :class:`BrepContacts`'s ``skip``.
    """

    def skip(a, b) -> bool:
        return isinstance(a, types) and isinstance(b, types)

    return skip


def _polygon_polygon_overlap_is_legacy() -> bool:
    """True if the installed ``polygon_polygon_overlap`` is the pre-0.9.3 signature.

    The original takes per-polygon normals - ``(a_pts, a_normal, b_pts, b_normal,
    tol, min_area)`` - and returns ``(points, frame, area)``. From 0.9.3 it takes
    one shared normal - ``(a_pts, b_pts, normal, tol, min_area)`` - and returns
    the two change-of-basis transformations as well, which is what the hole
    computation needs. Same detection as :meth:`compas_tf.plate.PlateElement.compute_contacts`.
    """
    from compas_model.algorithms.contacts import polygon_polygon_overlap

    return len(inspect.signature(polygon_polygon_overlap).parameters) >= 6


def contact_holes(contact: Contact) -> list:
    """The hole loops of a contact, or an empty list.

    ``Contact`` stores them (and serializes them, and builds them into
    ``contact.brep``) but exposes no accessor, unlike ``contact.polygon``.

    Parameters
    ----------
    contact : :class:`compas_model.interactions.Contact`

    Returns
    -------
    list[:class:`compas.geometry.Polygon`]
    """
    return getattr(contact, "_holes", None) or []


def prepare_faces(brep, minimum_area: float = 1e-1) -> list:
    """``(face, points, normal, aabb)`` per face of a Brep, for the pair loop.

    Do this once per Brep and reuse it across every pair the Brep takes part in;
    :class:`BrepContacts` caches it. Recomputing per pair is what makes the
    naive loop slow, not the intersections.

    Parameters
    ----------
    brep : :class:`compas_occt.brep.OCCBrep`
    minimum_area : float, optional
        Faces smaller than this cannot carry a contact and are dropped here.

    Returns
    -------
    list[tuple]
        ``aabb`` is ``(xmin, ymin, zmin, xmax, ymax, zmax)`` of the face
        boundary.
    """
    prepared = []
    for face in brep.faces:
        if face.area < minimum_area:
            continue
        polygon = face.to_polygon()
        points = polygon.points
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        zs = [point[2] for point in points]
        aabb = (min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))
        prepared.append((face, points, polygon.normal.unitized(), aabb))
    return prepared


def _aabb_overlap(a, b, tolerance: float) -> bool:
    return not (a[3] + tolerance < b[0] or b[3] + tolerance < a[0] or a[4] + tolerance < b[1] or b[4] + tolerance < a[1] or a[5] + tolerance < b[2] or b[5] + tolerance < a[2])


def brep_brep_contacts(
    a,
    b,
    tolerance: float = 1e-6,
    minimum_area: float = 1e-1,
    contacttype: type[Contact] = Contact,
    holes: bool = True,
    errors: Optional[list] = None,
    faces_a: Optional[list] = None,
    faces_b: Optional[list] = None,
):
    """Face-face contacts between two Breps - one contact polygon per interface.

    Parameters
    ----------
    a, b : :class:`compas_occt.brep.OCCBrep`
        The two solids.
    tolerance : float, optional
        Distance tolerance: maximum deviation from the perfectly flat interface
        plane.
    minimum_area : float, optional
        Contacts (and holes) smaller than this are dropped.
    contacttype : type[:class:`compas_model.interactions.Contact`], optional
        The contact class to instantiate.
    holes : bool, optional
        Compute the hole loops of each contact. Turn off to skip the one part
        of the computation that is allowed to fail (see the module docstring).
        Ignored on a compas_model too old to return the transformations.
    errors : list, optional
        Appended to with ``(stage, exception)`` for every face pair that raised,
        instead of the exception propagating. ``stage`` is ``"overlap"`` or
        ``"holes"``.
    faces_a, faces_b : list, optional
        :func:`prepare_faces` output for ``a`` and ``b``, to reuse across pairs.

    Returns
    -------
    list[:class:`compas_model.interactions.Contact`]
    """
    from compas_model.algorithms.contacts import brepface_brepface_overlap_holes
    from compas_model.algorithms.contacts import is_opposite_normal_normal
    from compas_model.algorithms.contacts import polygon_polygon_overlap

    def _record(stage, exc):
        if errors is None:
            raise exc
        errors.append((stage, exc))

    a_prepared = prepare_faces(a, minimum_area) if faces_a is None else faces_a
    b_prepared = prepare_faces(b, minimum_area) if faces_b is None else faces_b
    if not a_prepared or not b_prepared:
        return []

    legacy = _polygon_polygon_overlap_is_legacy()

    contacts = []

    for a_face, a_points, a_normal, a_aabb in a_prepared:
        for b_face, b_points, b_normal, b_aabb in b_prepared:
            # Both necessary conditions for a contact, and both far cheaper than
            # the overlap: exactly opposite normals (the solids are closed, so
            # every normal points outward), and boundary AABBs that meet.
            if not is_opposite_normal_normal(a_normal, b_normal):
                continue
            if not _aabb_overlap(a_aabb, b_aabb, tolerance):
                continue

            try:
                if legacy:
                    result = polygon_polygon_overlap(a_points, a_normal, b_points, b_normal, tolerance, minimum_area)
                else:
                    result = polygon_polygon_overlap(a_points, b_points, a_normal, tolerance, minimum_area)
            except Exception as exc:  # shapely can hand back a GeometryCollection
                _record("overlap", exc)
                continue

            if not result:
                continue

            points, frame, area = result[0], result[1], result[2]

            face_holes = None
            if holes and not legacy and len(result) >= 5:
                try:
                    face_holes = brepface_brepface_overlap_holes(a_face, b_face, result[3], result[4], minimum_area)
                except Exception as exc:
                    # The contact polygon is already valid - keep it without holes.
                    _record("holes", exc)

            contacts.append(contacttype(points=points, frame=frame, size=area, holes=face_holes))

    return contacts


class BrepContacts:
    """Element-pair contact detection on Breps, with a Brep cache.

    Callable with the signature the model's contact search expects
    (``(a, b, tolerance=, minimum_area=, contacttype=) -> list[Contact]``), so it
    goes straight into ``contactmethod=``::

        method = BrepContacts()
        model.compute_contacts(minimum_area=1.0, contactmethod=method)
        print(len(method.breps), "breps,", len(method.errors), "face pairs failed")

    or, the same thing in one call,
    :meth:`compas_tf.model.TFModel.compute_contacts_brep`.

    Each element is converted to a Brep at most once - conversion is the
    expensive half (~55 ms per element on the cantilevers model, vs ~85 ms per
    element PAIR for the detection), and every element takes part in several
    pairs.

    Parameters
    ----------
    holes : bool, optional
        Compute the hole loops of each contact.
    skip : callable, optional
        ``(a, b) -> bool``; a pair it accepts is dropped before either element
        is even converted to a Brep, so skipping is free. :func:`involving` and
        :func:`between` build the usual ones.
    strict : bool, optional
        Let a failing face pair raise instead of being recorded in
        :attr:`errors`.
    **brepkwargs
        Forwarded to ``element.get_brep()`` - e.g. ``merge_coplanar=False``,
        though merging is exactly what makes this worth doing.

    Attributes
    ----------
    breps : dict[int, :class:`compas_occt.brep.OCCBrep`]
        The cache, keyed by ``id(element)``.
    errors : list[tuple[str, str, str, Exception]]
        ``(element_a, element_b, stage, exception)`` per failed face pair.
    skipped : int
        How many pairs ``skip`` rejected.
    """

    def __init__(
        self,
        holes: bool = True,
        skip: Optional[Callable] = None,
        strict: bool = False,
        **brepkwargs,
    ):
        self.holes = holes
        self.skip = skip
        self.strict = strict
        self.brepkwargs = brepkwargs
        self.breps: dict = {}
        self.errors: list = []
        self.skipped: int = 0
        self._faces: dict = {}

    def faces(self, element, minimum_area: float) -> list:
        """:func:`prepare_faces` for an element's Brep, cached."""
        key = (id(element), minimum_area)
        if key not in self._faces:
            brep = self.brep(element)
            self._faces[key] = prepare_faces(brep, minimum_area) if brep is not None else []
        return self._faces[key]

    def brep(self, element):
        """The element's Brep, converting (and caching) on first use.

        Returns ``None`` for an element that has no geometry to convert.
        """
        key = id(element)
        if key not in self.breps:
            if isinstance(element, BrepMixin):
                brep = element.get_brep(**self.brepkwargs)
            else:
                geometry = element.modelgeometry
                brep = mesh_to_brep(geometry, name=element.name, **self.brepkwargs) if geometry is not None else None
            self.breps[key] = brep
        return self.breps[key]

    def __call__(self, a, b, tolerance: float = 1e-6, minimum_area: float = 1e-1, contacttype: type[Contact] = Contact):
        if self.skip is not None and self.skip(a, b):
            self.skipped += 1
            return []

        faces_a = self.faces(a, minimum_area)
        faces_b = self.faces(b, minimum_area)
        if not faces_a or not faces_b:
            return []

        errors = None if self.strict else []
        contacts = brep_brep_contacts(
            self.brep(a),
            self.brep(b),
            tolerance=tolerance,
            minimum_area=minimum_area,
            contacttype=contacttype,
            holes=self.holes,
            errors=errors,
            faces_a=faces_a,
            faces_b=faces_b,
        )
        for stage, exc in errors or []:
            self.errors.append((a.name, b.name, stage, exc))
        return contacts
