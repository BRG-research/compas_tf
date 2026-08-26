"""Small accessors for :class:`compas_model.interactions.Contact`.

This module used to carry the Brep contact detector - ``BrepContacts``,
``brep_brep_contacts``, ``prepare_faces`` and the ``between`` / ``involving``
pair filters - which backed ``TFModel.compute_contacts_brep``. Contact
detection now goes through ``wood_nano`` only, so all of that is gone; see
:mod:`compas_tf.wood` and
:meth:`compas_tf.model.TFModel.compute_contacts_wood`.

What remains is the one piece that was never about Brep detection: reading the
hole loops off a contact, whatever produced it.
"""

from compas_model.interactions import Contact


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
