********************************************************************************
Extract one column and one quarter
********************************************************************************

The model tree is a nest of named groups, and any of them can be lifted out as
a model of its own. One column plus the quarter it carries is the unit that gets
assembled on site.

.. literalinclude:: ../../examples/example_model_21_extract_bay.py
    :language: python

.. code-block:: text

    49 of 237 elements, 208 contacts

The result is a model like any other: it writes to JSON, exports to STEP, and
draws. The source is untouched, and the copy is independent - fresh guids - so
it can be placed and merged back alongside the original.


Both groups at once
===================

:meth:`~compas_tf.base_model.BaseModel.find_groups_with_names` takes a list, and
that is the point. The contacts *between* the column and the quarter it carries
survive only if the two come out together. Extracting each with
:meth:`~compas_tf.base_model.BaseModel.find_group_with_name` and merging the
results keeps every contact internal to each group and drops exactly the joint
that connects them.

Each group keeps its ancestor chain, pruned to what was asked for, so
``quarter_model_0`` comes back at
``floor_model/quarters_model/quarter_model_0`` and the transformations along the
way still apply - the bay stays where it is in the building.


``neighbors``
=============

The connectors, dowels and outer-rib connectors live in their own top-level
groups, not inside the bay, so a bay extracted by name alone has no fasteners:

.. code-block:: text

    neighbors=True     49 elements, 208 contacts
    neighbors=False    36 elements, 125 contacts

``neighbors=True`` adds every element that interacts with one inside. It walks
**one step out only** - following the graph again from what it just pulled in
would drag the whole model along one edge at a time.


The groups you can name
=======================

.. code-block:: text

    floor_model                    185 parts
      quarters_model               136
        quarter_model_0 .. _3       34 each
          beds_0, tsections_0, outer_ribs_0, inner_ribs_0,
          wedges_inner_beams_0, inner_beams_0
      oculus_model                   9
      connectors                    40
    columns_model                    8
      column_model_0 .. _3           2 each
    connectors                       8
    connector_cylinders             32
    outer_rib_connectors             4

Printed from the tree with:

.. code-block:: python

    from compas_model.elements import Group

    for element in model.elements():
        if isinstance(element, Group):
            print(element.name)

A name that matches no group raises ``ModelElementNotFound`` rather than quietly
returning the ones that did match.
