from typing import Iterator
from typing import Optional

from compas_model.elements import Group
from compas_model.models import Model

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
