from compas_tf.connectors import ConnectorWedgeElement


def test_wedge_boolean_geometry_is_a_single_closed_solid():
    """The wedge cuts its host with ONE closed mesh.

    The debug dowel cylinders it can also draw are not part of the boolean, so
    a plate carved by this element gets the wedge pocket and nothing else.
    """
    wedge = ConnectorWedgeElement(length=320)

    boolean_geometries = wedge.boolean_geometries

    assert len(boolean_geometries) == 1
    assert boolean_geometries[0].is_closed()
