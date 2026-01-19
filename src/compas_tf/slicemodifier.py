# from typing import Optional
from typing import Union

from compas.datastructures import Mesh
from compas.geometry import Brep
from compas_model.modifiers import Modifier


class SliceModifier(Modifier):
    """Modifier for slicing a geometry with a frame.

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
        """Apply the interaction to the target geometry.

        Parameters
        ----------
        target : :class:`compas.geometry.Brep` | :class:`compas.datastructures.Mesh`
            The target of the modification.

        Returns
        -------
        Brep | Mesh
            The modified target geometry.

        """

        positive, negative = targetgeometry.slice(source.modelgeometry)

        return negative
