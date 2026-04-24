from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.modifiers import Modifier


class SolidDifferenceModifier(Modifier):
    """Modifier for boolean difference between two geometries.

    Parameters
    ----------
    name : str
        The name of the modifier.

    """

    @property
    def __data__(self) -> dict:
        return {}

    def apply(
        self,
        source,
        targetgeometry: Union[Brep, Mesh],
    ) -> Union[Brep, Mesh]:
        """Apply the boolean difference to the target geometry.

        Skips the operation if source or target geometry is not a Mesh.

        Parameters
        ----------
        source : Element
            The source element (cutter).
        targetgeometry : :class:`compas.geometry.Brep` | :class:`compas.datastructures.Mesh`
            The target of the modification.

        Returns
        -------
        Brep | Mesh
            The modified target geometry, or original if operation skipped.

        """
        from compas.geometry import Polyhedron
        from compas_cgal.booleans import boolean_difference_mesh_mesh

        # Get source geometry
        source_geom = source.modelgeometry
        source_name = getattr(source, "name", "<unnamed>")

        # Skip if source or target is not a Mesh
        if not isinstance(source_geom, Mesh):
            print(f"[diff] skip '{source_name}': source is {type(source_geom).__name__}, not Mesh")
            return targetgeometry
        if not isinstance(targetgeometry, Mesh):
            print(f"[diff] skip '{source_name}': target is {type(targetgeometry).__name__}, not Mesh")
            return targetgeometry


        # Watertight inputs are required; an open mesh will abort CGAL hard.
        src_closed = source_geom.is_closed()
        tgt_closed = targetgeometry.is_closed()
        print(
            f"[diff] '{source_name}' -> target  "
            f"src V/F/closed={source_geom.number_of_vertices()}/{source_geom.number_of_faces()}/{src_closed}  "
            f"tgt V/F/closed={targetgeometry.number_of_vertices()}/{targetgeometry.number_of_faces()}/{tgt_closed}"
        )
        if not src_closed:
            print(f"[diff] skip '{source_name}': cutter not closed")
            return targetgeometry
        if not tgt_closed:
            print(f"[diff] skip '{source_name}': target not closed")
            return targetgeometry

        SOURCE = source_geom.to_vertices_and_faces(triangulated=True)
        TARGET = targetgeometry.to_vertices_and_faces(triangulated=True)

        try:
            V, F = boolean_difference_mesh_mesh(TARGET, SOURCE)
        except Exception as exc:
            print(f"[diff] CGAL raised for '{source_name}': {exc}")
            return targetgeometry

        vertices = V.tolist()
        faces = F.tolist()

        if not vertices or not faces:
            print(f"[diff] empty result for '{source_name}', keeping original")
            return targetgeometry

        shape = Polyhedron(vertices, faces)
        shape = shape.to_mesh()
        print(f"[diff] '{source_name}' OK  -> result V/F={len(vertices)}/{len(faces)}")
        return shape
