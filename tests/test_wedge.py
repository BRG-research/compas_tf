from compas_tf.wedge import WedgeElement


def test_wedge_boolean_geometry_excludes_debug_dowels():
    wedge = WedgeElement(target_length=320)

    dowel_lines = wedge.dowel_lines(step=80)
    dowels = wedge.create_dowels(step=80)
    boolean_geometries = wedge.boolean_geometries

    assert len(dowel_lines) == 4
    assert len(dowels) == len(dowel_lines)
    assert len(boolean_geometries) == 1
    assert boolean_geometries[0].is_closed()
