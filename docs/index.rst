********************************************************************************
compas_tf
********************************************************************************

.. rst-class:: lead

    Timber floor development. A parametric model of a timber floor - columns,
    ribs, beds, t-sections, oculus and the connectors that hold them together -
    that you can build, cut, measure, extract from and hand to a shop as STEP.

.. figure:: /_images/model4.png
     :figclass: figure
     :class: figure-img img-fluid


There are two ways into this package, and they are quite different.

**Building the model** means running the parametric chain: a
:class:`~compas_tf.FloorGuide` lays out the geometry, elements are placed and
grouped into a :class:`~compas_tf.TFModel`, boolean features cut the capitels,
pockets and dowel holes, and a contact search finds every joint. It is the whole
of :doc:`examples` up to example 18, it needs a boolean backend, and on the
cantilevers model it costs a few minutes.

**Reading the model** means opening what that chain wrote. The geometry is
*baked* before it is written - every boolean already evaluated and stored on the
element - so a model loads in well under a second, with no boolean backend
involved and nothing recomputed. That is what most people need, and it is what
the first three example pages cover:

.. code-block:: python

    import compas

    model = compas.json_load("cantilevers_baked_model.json")

    print(len(list(model.geometry_elements())))   # 237
    print(len(list(model.contacts())))            # 733

    bay = model.find_groups_with_names(["column_model_0", "quarter_model_0"], neighbors=True)
    bay.to_step("bay_0.stp")


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
