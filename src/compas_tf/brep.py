from typing import Optional

# Tight defaults for the coplanar-face merge (see the volume guard below).
# 1e-6 rad is ~0.00006 deg: only EXACTLY coplanar boolean triangles merge, and a
# lofted rib or t-section keeps its twisted quads.
LINEAR_DEFLECTION = 1e-3
ANGULAR_DEFLECTION = 1e-6

# Relative volume change above which the merge is considered to have distorted
# the solid, and the unsimplified Brep is kept instead.
VOLUME_TOLERANCE = 1e-6


def _brep_volume(brep) -> Optional[float]:
    """Volume of a Brep, or ``None`` if it cannot be evaluated (open shape, ...)."""
    try:
        volume = brep.volume
    except Exception:
        return None
    if not volume:
        return None
    return abs(volume)


def _from_mesh(mesh, solid: bool = True):
    """``OCCBrep.from_mesh`` without the ``fix()`` half of ``heal()``.

    ``OCCBrep.from_mesh`` calls ``heal()``, which is ``sew()`` + ``fix()``.
    Sewing is what turns the loose faces into a connected shell, so it is
    required; ``fix()`` is ShapeFix_Shape, a repair pass for shapes that came in
    malformed. Our faces are built from a closed COMPAS mesh, so there is
    nothing to repair - and on the cantilevers model that pass alone is ~4 s of
    a ~13 s conversion while changing neither the face count nor the volume.

    It is still a real safety net for a mesh that is NOT clean, so it is skipped
    rather than removed: if the cheap path fails to produce a closed solid, the
    shape is rebuilt with the full heal. That costs a second conversion only in
    the case that would otherwise have been wrong.
    """
    from compas_occt import _occt
    from compas_occt.brep import OCCBrep
    from compas_occt.conversions import ngon_to_face
    from compas_occt.conversions import quad_to_face
    from compas_occt.conversions import triangle_to_face

    faces = []
    for face in mesh.faces():
        points = mesh.face_polygon(face)
        if len(points) == 3:
            faces.append(triangle_to_face(points))
        elif len(points) == 4:
            faces.append(quad_to_face(points))
        else:
            faces.append(ngon_to_face(points))

    brep = OCCBrep.from_native(_occt.shell_from_faces(faces))
    brep.sew()
    if solid:
        brep.make_solid()
        if not brep.is_solid:
            # Not clean after all - pay for the full heal.
            return OCCBrep.from_mesh(mesh, solid=solid)
    return brep


def mesh_to_brep(
    mesh,
    solid: bool = True,
    merge_coplanar: bool = True,
    lineardeflection: float = LINEAR_DEFLECTION,
    angulardeflection: float = ANGULAR_DEFLECTION,
    name: Optional[str] = None,
):
    """Convert one COMPAS mesh into a solid OCC Brep with its coplanar faces merged.

    The merge is why the conversion is worth doing: a boolean leaves triangle
    soup, and merging collapses it back into the flat faces the part was
    actually modelled with. A Mesh face cannot carry a hole either, so a drilled
    face has to be fanned into many faces around the hole - a Brep face carries
    its hole loops properly and comes back as ONE face.

    The merge is guarded: OCC's face unification also fuses *nearly* coplanar
    faces, which flattens lofted (twisted-quad) geometry. So the angular
    deflection is tight by default, and if unification changes the solid's
    volume the exact, unsimplified Brep is kept instead.

    Parameters
    ----------
    mesh : :class:`compas.datastructures.Mesh`
        The mesh to convert. Should be closed for ``solid=True``.
    solid : bool, optional
        Sew the faces into a closed solid.
    merge_coplanar : bool, optional
        Merge coplanar faces (and the edges between them) into single faces.
    lineardeflection, angulardeflection : float, optional
        Tolerances handed to ``OCCBrep.simplify``. See the module docstring for
        why the angular default is so tight.
    name : str, optional
        Name given to the resulting Brep.

    Returns
    -------
    :class:`compas_occt.brep.OCCBrep`
    """
    brep = _from_mesh(mesh, solid=solid)

    if merge_coplanar:
        # Measure the Brep BEFORE unification, not the mesh: the twisted-quad
        # loft faces of the ribs and t-sections become curved OCC surfaces, so
        # the Brep's volume legitimately differs from the flat-triangle volume
        # of the mesh it came from. Comparing against the mesh would blame
        # simplify() for that difference and throw the merge away.
        volume = _brep_volume(brep)
        try:
            brep.simplify(
                merge_edges=True,
                merge_faces=True,
                lineardeflection=lineardeflection,
                angulardeflection=angulardeflection,
            )
            # Unification is only allowed to remove edges and faces, never to
            # move geometry. A changed volume means nearly-coplanar faces were
            # fused, so fall back to the exact (unsimplified) Brep.
            distorted = volume is not None and abs(brep.volume - volume) > VOLUME_TOLERANCE * volume
        except Exception:
            distorted = True
        if distorted:
            brep = _from_mesh(mesh, solid=solid)

    if name:
        brep.name = name
    return brep


def meshes_to_brep(meshes: list, name: Optional[str] = None, **kwargs):
    """Convert a list of meshes into ONE Brep - a compound when there are several.

    Parameters
    ----------
    meshes : list[:class:`compas.datastructures.Mesh`]
        The meshes to convert. Empty gives ``None``.
    name : str, optional
        Name given to the resulting Brep.
    **kwargs
        Forwarded to :func:`mesh_to_brep`.

    Returns
    -------
    :class:`compas_occt.brep.OCCBrep` or None
    """
    breps = [mesh_to_brep(mesh, **kwargs) for mesh in meshes if mesh is not None]
    if not breps:
        return None

    if len(breps) == 1:
        brep = breps[0]
    else:
        from compas_occt.brep import OCCBrep

        brep = OCCBrep.from_breps(breps)

    if name:
        brep.name = name
    return brep


class BrepMixin:
    """Gives a class ``get_brep()``: its meshes as a solid, coplanar-merged Brep.

    Mixed into every compas_tf element, feature and model. A subclass only has
    to say WHICH meshes it owns, by overriding :meth:`brep_meshes`; the default
    picks up a ``meshes`` attribute, which is what the cut features carry.
    """

    def brep_meshes(self, variant: Optional[str] = None) -> list:
        """The meshes :meth:`get_brep` converts.

        Parameters
        ----------
        variant : str, optional
            Which geometry to convert, for classes that own more than one (see
            :meth:`compas_tf.element.TFElement.brep_meshes`). Ignored here.

        Returns
        -------
        list[:class:`compas.datastructures.Mesh`]
            Empty when the class carries no geometry (a marker feature, say),
            in which case :meth:`get_brep` returns ``None``.
        """
        meshes = getattr(self, "meshes", None)
        return list(meshes) if meshes else []

    def get_brep(
        self,
        variant: Optional[str] = None,
        merge_coplanar: bool = True,
        solid: bool = True,
        lineardeflection: float = LINEAR_DEFLECTION,
        angulardeflection: float = ANGULAR_DEFLECTION,
    ):
        """This object's geometry as a solid Brep, with coplanar faces merged.

        Parameters
        ----------
        variant : str, optional
            Which baked geometry variant to convert, for elements carrying more
            than one - e.g. ``"ColumnAddFeature"`` for a column's uncut stock.
            Default is the element's finished, placed geometry.
        merge_coplanar : bool, optional
            Merge coplanar faces into single (hole-carrying) faces.
        solid : bool, optional
            Sew the faces into a closed solid.
        lineardeflection, angulardeflection : float, optional
            Tolerances for the coplanar-face merge.

        Returns
        -------
        :class:`compas_occt.brep.OCCBrep` or None
            A single solid, or a compound when the object owns several meshes.
            ``None`` when it owns none.
        """
        return meshes_to_brep(
            self.brep_meshes(variant),
            name=getattr(self, "name", None),
            merge_coplanar=merge_coplanar,
            solid=solid,
            lineardeflection=lineardeflection,
            angulardeflection=angulardeflection,
        )
