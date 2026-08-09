import functools
import inspect
from typing import Optional

from compas.datastructures import Mesh
from compas.geometry import Transformation
from compas_model.elements.element import Element
from compas_model.elements.element import Feature

from compas_tf.brep import BrepMixin

# Keys under which geometry variants are baked.
ALL = "all"  # every feature applied - the finished part
BASE = "base"  # no features - the raw parametric stock


def bakekey(include_features: bool = True, types: Optional[list] = None) -> str:
    """Canonical cache key for a geometry variant.

    Mirrors the ``compute_elementgeometry`` arguments: no features is
    :data:`BASE`, all features is :data:`ALL`, and a type filter is the sorted
    feature-class names joined with ``+`` (e.g. ``"ColumnAddFeature"`` for a
    column's uncut stock).

    Parameters
    ----------
    include_features : bool, optional
        Whether features are applied.
    types : list[str | type], optional
        Feature types applied, as class names or classes.

    Returns
    -------
    str
    """
    if not include_features:
        return BASE
    if types is None:
        return ALL
    return "+".join(sorted(t if isinstance(t, str) else t.__name__ for t in types))


def _callkey(signature, args, kwargs) -> str:
    """The :func:`bakekey` for one ``compute_elementgeometry`` call.

    Binds the call against the subclass's OWN signature and applies its OWN
    defaults, so ``compute_elementgeometry()`` and ``bake()`` agree on the key
    even though the subclasses disagree on the default of ``include_features``
    (True on the elements that carry features, False on the plain solids).
    """
    bound = signature.bind(*args, **kwargs)
    bound.apply_defaults()
    return bakekey(bound.arguments.get("include_features", True), bound.arguments.get("types"))


def baked(fn):
    """Decorator for ``compute_elementgeometry``: serve the baked mesh if there is one.

    Reads the ``(include_features, types)`` the caller asked for - whatever the
    subclass's signature happens to be - turns them into a :func:`bakekey`, and
    returns the stored mesh for that key instead of running the booleans. A miss
    falls through to the real implementation, so an unbaked element behaves
    exactly as before.
    """
    signature = inspect.signature(fn)

    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        cache = getattr(self, "_bakedgeometry", None)
        if cache:
            geometry = cache.get(_callkey(signature, (self,) + args, kwargs))
            if geometry is not None:
                return geometry
        return fn(self, *args, **kwargs)

    wrapper.__bakedsignature__ = signature
    return wrapper


class TFElement(Element, BrepMixin):
    """Base class for every compas_tf element: baked geometry + ``get_brep``.

    A compas_tf element is parametric: its geometry is a boolean of its base
    shape with its features (capitel unions, cutter differences). Recomputing
    that on every load is slow, needs the boolean backends installed, and is not
    what a *fabrication* model is for - the shape is already decided.
    :meth:`bake` runs the booleans once and stores the result ON the element,
    and :meth:`_baked_data` puts it in ``__data__``, so a baked element
    round-trips through plain ``compas.json_dump`` / ``compas.json_load`` and
    comes back with its geometry already applied to its base geometry - no
    boolean recomputed, and the parameters and features still there beside it.

    More than one variant can be baked, because fabrication needs more than the
    finished part: :meth:`bake` is keyed by the same
    ``(include_features, types)`` arguments ``compute_elementgeometry`` takes,
    so a column can carry both its uncut stock (``types=["ColumnAddFeature"]``)
    and its carved final shape.

    ``get_brep()`` comes from :class:`compas_tf.brep.BrepMixin`: meshes to a
    solid Brep with coplanar faces merged, via ``compas_occt``.

    Subclasses stay ordinary ``compas_model`` elements; they only have to

    1. splice :meth:`_baked_data` into their ``__data__``
       (``**self._baked_data()``), and
    2. decorate their ``compute_elementgeometry`` with :func:`baked`.

    Deserialization is handled here: :meth:`__from_data__` pulls the baked
    meshes back out and puts them where the ``elementgeometry`` /
    ``modelgeometry`` properties find them, so nothing recomputes.
    """

    def __init__(self, *args, **kwargs):
        # Before super(), because Element.__init__ assigns _elementgeometry and
        # the setter below reaches for this dict.
        self._bakedgeometry: dict = {}  # bakekey -> mesh, in the element's LOCAL frame
        super().__init__(*args, **kwargs)

    # ==========================================================================
    # Cache invalidation
    # ==========================================================================
    # ``_elementgeometry`` is where compas_model caches the computed geometry,
    # and EVERY invalidation path nulls it: add_feature and add_cutters here in
    # compas_tf, and the @reset_computed decorator on Element.transform
    # upstream. Hooking that one write is therefore the single place that
    # catches them all - without it a baked element would keep serving its
    # pre-edit shape and a newly added cutter would silently do nothing.

    @property
    def _elementgeometry(self) -> Optional[Mesh]:
        return self.__dict__.get("_tf_elementgeometry")

    @_elementgeometry.setter
    def _elementgeometry(self, geometry: Optional[Mesh]) -> None:
        self.__dict__["_tf_elementgeometry"] = geometry
        if geometry is None:
            # The variants were derived from it, so they go with it.
            self.__dict__["_bakedgeometry"] = {}

    # ==========================================================================
    # Serialization
    # ==========================================================================

    def _baked_data(self) -> dict:
        """The baked-geometry part of ``__data__``.

        Splice into every subclass's ``__data__`` with ``**self._baked_data()``.

        Baking is EXPLICIT: both keys are ``None`` unless :meth:`bake` was
        called, so merely drawing an element or querying its contacts - which
        populates the ordinary ``_elementgeometry`` / ``_modelgeometry`` caches -
        does not quietly freeze a parametric model into a baked one.

        Returns
        -------
        dict
        """
        if not self._bakedgeometry:
            return {"bakedgeometry": None, "modelgeometry": None}
        return {
            "bakedgeometry": dict(self._bakedgeometry),
            "modelgeometry": self._modelgeometry,
        }

    @classmethod
    def __from_data__(cls, data: dict) -> "TFElement":
        """Rebuild the element and restore its baked geometry.

        The baked keys are popped before the constructor call, so subclasses
        keep their plain parametric ``__init__`` signature.
        """
        data = dict(data)
        geometries = data.pop("bakedgeometry", None) or {}
        modelgeometry = data.pop("modelgeometry", None)

        element = cls(**data)

        # Order matters: assigning a non-None _elementgeometry does not clear
        # the cache, but it must be set AFTER the dict so the default variant
        # lands on an already-populated cache.
        element._bakedgeometry = dict(geometries)
        # Put the default variant where the ``elementgeometry`` property looks,
        # so it is returned as-is instead of being recomputed.
        default = element._bakedgeometry.get(element.default_bakekey())
        if default is not None:
            element._elementgeometry = default
        element._modelgeometry = modelgeometry
        return element

    # ==========================================================================
    # Baking
    # ==========================================================================

    def _bakedsignature(self):
        """The signature of this class's own ``compute_elementgeometry``.

        Taken from the undecorated function stashed by :func:`baked`, so the
        subclass's real parameter names and defaults are used - that is what
        makes :meth:`bake` and ``compute_elementgeometry`` agree on the key.
        """
        method = type(self).compute_elementgeometry
        signature = getattr(method, "__bakedsignature__", None)
        return signature or inspect.signature(method)

    def default_bakekey(self) -> str:
        """The :func:`bakekey` a plain ``compute_elementgeometry()`` resolves to.

        Not always :data:`ALL`: the elements that carry no features declare
        ``include_features=False``, so their default variant is :data:`BASE`.
        This is the variant the ``elementgeometry`` property serves.
        """
        return _callkey(self._bakedsignature(), (self,), {})

    def bake(self, *args, modelgeometry: Optional[bool] = None, **kwargs) -> Mesh:
        """Compute a geometry variant once and store it for serialization.

        Takes exactly the arguments ``compute_elementgeometry`` takes and passes
        them straight through; the result is stored under the matching
        :func:`bakekey` and served from there afterwards - by
        ``compute_elementgeometry`` (through the :func:`baked` decorator), by the
        ``elementgeometry`` property, and by ``__data__``.

        Bake more than once to keep more than one variant, e.g. a column's uncut
        stock next to its carved shape::

            column.bake(types=["ColumnAddFeature"])  # stock
            column.bake()  # finished part

        Parameters
        ----------
        *args, **kwargs
            Forwarded to ``compute_elementgeometry`` (``include_features``,
            and ``types`` on the elements that support it).
        modelgeometry : bool, optional
            Also bake the model-space geometry (see :meth:`bake_modelgeometry`).
            By default this happens only when baking the element's DEFAULT
            variant - model geometry is built from that one, so asking for it
            while baking a side variant would run the very boolean the call was
            trying to avoid.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
            The baked mesh, in the element's local frame.
        """
        key = _callkey(self._bakedsignature(), (self,) + args, kwargs)
        isdefault = key == self.default_bakekey()

        geometry = self._bakedgeometry.get(key)
        if geometry is None and isdefault:
            # Already computed by a viewer/contact query - reuse it rather than
            # running the boolean a second time.
            geometry = self._elementgeometry
        if geometry is None:
            geometry = self.compute_elementgeometry(*args, **kwargs)
        self._bakedgeometry[key] = geometry
        if isdefault:
            self._elementgeometry = geometry

        if modelgeometry is None:
            modelgeometry = isdefault
        if modelgeometry:
            self.bake_modelgeometry()
        return geometry

    def bake_modelgeometry(self) -> Mesh:
        """Compute and store the element's geometry in MODEL coordinates.

        This is the geometry with the model transformation and any interaction
        modifiers already applied - the shape as it sits in the assembly. Stored
        in ``__data__`` so a reloaded model draws without touching a boolean
        backend. Falls back to the placed element geometry when the element is
        not (yet) in a model.

        Returns
        -------
        :class:`compas.datastructures.Mesh`
        """
        if self._modelgeometry is None:
            if self.model is not None and self.graphnode is not None:
                self._modelgeometry = self.compute_modelgeometry()
            else:
                geometry = self.elementgeometry
                self._modelgeometry = geometry.transformed(self.transformation) if self.transformation else geometry.copy()
        return self._modelgeometry

    def unbake(self) -> None:
        """Drop every baked mesh, so the geometry is recomputed from the parameters."""
        self._elementgeometry = None  # the setter clears _bakedgeometry with it
        self._modelgeometry = None

    @property
    def is_baked(self) -> bool:
        """True if :meth:`bake` has stored geometry that no longer needs recomputing."""
        return bool(self._bakedgeometry)

    def baked_variants(self) -> list:
        """The :func:`bakekey` of every geometry variant stored on the element."""
        return sorted(self._bakedgeometry)

    # ==========================================================================
    # Geometry
    # ==========================================================================

    @property
    def placement(self) -> Transformation:
        """The transformation that takes the element's local geometry to model space.

        The element's ``modeltransformation`` when it sits in a model; its own
        ``transformation`` (or the identity) when it is loose - so features and
        baked variants can be placed either way.
        """
        if self.model is not None and self.graphnode is not None:
            return self.modeltransformation
        return self.transformation or Transformation()

    @property
    def placedgeometry(self) -> Mesh:
        """The element geometry in model coordinates, without requiring a model.

        Same as ``modelgeometry`` for an element inside a model; for a loose
        element it is the element geometry moved by its own transformation.
        """
        if self._modelgeometry is not None:
            return self._modelgeometry
        if self.model is not None and self.graphnode is not None:
            return self.modelgeometry
        geometry = self.elementgeometry
        return geometry.transformed(self.transformation) if self.transformation else geometry

    def brep_meshes(self, variant: Optional[str] = None) -> list:
        """The element's model-space mesh - what :meth:`get_brep` converts.

        Parameters
        ----------
        variant : str, optional
            A baked variant key (see :func:`bakekey` and
            :meth:`baked_variants`) to convert instead of the finished
            geometry - e.g. ``"ColumnAddFeature"`` for a column's uncut stock.
            The variant is stored in the local frame, so it is placed here.

        Returns
        -------
        list[:class:`compas.datastructures.Mesh`]

        Raises
        ------
        ValueError
            If ``variant`` is not baked on this element.
        """
        if variant is None:
            geometry = self.placedgeometry
        else:
            local = self._bakedgeometry.get(variant)
            if local is None:
                raise ValueError(f"'{variant}' is not baked on {self.name}; baked variants: {self.baked_variants()}")
            geometry = local.transformed(self.placement)
        return [geometry] if geometry is not None else []


class TFFeature(Feature, BrepMixin):
    """Base class for every compas_tf feature.

    Adds ``get_brep()``, which converts whatever solids the feature carries -
    its ``meshes`` - into a Brep. For a cut feature that is the cutter solid,
    which is exactly what a fabricator needs to see next to the stock.
    """
