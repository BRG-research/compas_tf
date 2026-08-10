********************************************************************************
compas_tf
********************************************************************************

.. rst-class:: lead

    Timber floor development.

.. figure:: /_images/banner.png
     :figclass: figure
     :class: figure-img img-fluid

One bay: four quarters of ribs, beds and t-sections on a column, an oculus at
the centre, and the connectors that hold it together in yellow. Parametric,
boolean-cut, contact-checked, and exportable as STEP.

.. code-block:: python

    import compas

    model = compas.json_load("cantilevers_baked_model.json")

    print(len(list(model.geometry_elements())))   # 237
    print(len(list(model.contacts())))            # 733

    bay = model.find_groups_with_names(["column_model_0", "quarter_model_0"], neighbors=True)
    bay.to_step("bay_0.stp")

There are two ways into this package. **Building** the model runs the parametric
chain - guide, elements, booleans, contact search - and costs minutes.
**Reading** one opens what that chain wrote: the geometry is baked, so nothing
is recomputed and no boolean backend is involved. Most people want the second,
which is the first three :doc:`examples`.


Table of Contents
=================

.. toctree::
   :maxdepth: 3
   :titlesonly:

   Introduction <self>
   installation
   tutorial
   examples
   api
   license


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
