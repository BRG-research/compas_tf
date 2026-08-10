********************************************************************************
Read the model
********************************************************************************

``compas.json_load`` gives back the whole thing: elements, features, materials,
the element tree, and the interaction graph with the contacts on it.

.. literalinclude:: ../../examples/example_model_19_read_model.py
    :language: python

.. code-block:: text

    237 elements, 733 contacts

The geometry was **baked** before the file was written - every boolean already
evaluated and stored on the element - so this runs no boolean, needs no boolean
backend, and takes 0.60 s for 3.9 MB. A raw ``json.loads`` of the same bytes is
0.09 s, so nearly all of it is deserialization.

``model.elements()`` yields the groups too; ``geometry_elements()`` is the
leaves only. ``model.contacts()`` reads what the contact search stored - it does
not search again. To redo it:

.. code-block:: python

    model.compute_contacts_brep(minimum_area=1.0, clear=True)

Contacts come back whole - polygon, frame, size and holes. ``contact_holes(contact)``
gets the hole loops, and ``model.contact_pairs()`` hands back the two elements
joined as objects rather than names.
