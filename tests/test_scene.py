import pytest

pytest.importorskip("compas_viewer", reason="scene objects only register when compas_viewer is installed")

from compas.datastructures import Mesh  # noqa: E402
from compas.geometry import Polygon  # noqa: E402
from compas.geometry import area_polygon  # noqa: E402
from compas.scene import SceneObject  # noqa: E402

from compas_tf.connectors import ConnectorWedgeElement  # noqa: E402
from compas_tf.model import TFModel  # noqa: E402


def _sceneobject(item):
    return SceneObject(item=item, context="Viewer")


def test_element_draws_itself():
    """A compas_tf element resolves to a compas_tf scene object.

    Registered against the TFElement base, so this covers every element type
    through compas' MRO dispatch. The element has to be IN a model:
    ``modelgeometry`` walks up the tree for the accumulated placement, and a
    loose element has no tree node to walk.
    """
    model = TFModel(name="test")
    element = ConnectorWedgeElement(length=320)
    model.add_element(element)

    obj = _sceneobject(element)

    assert type(obj).__name__ == "TFElementObject"
    positions, triangles = obj.viewmesh
    assert positions and triangles
    assert all(len(t) == 3 for t in triangles)


def test_mesh_registration_wins_over_compas_viewer():
    """compas_tf's Mesh scene object must override compas_viewer's.

    It only does so because compas scans installed compas* packages in pkgutil
    order and compas_tf sorts after compas_viewer, so its registration runs
    last. If that ever flips, meshes silently fall back to compas_viewer's
    centroid fan and concave faces render wrong - wrong pixels, not an
    exception, which is exactly the kind of regression nothing else catches.
    """
    obj = _sceneobject(Mesh.from_polyhedron(6))

    assert type(obj).__name__ == "TFMeshObject", "compas_viewer's MeshObject won the registration race"


def test_triangulation_of_a_concave_face_is_area_exact():
    """Ear-clipping must not overlap, which a centroid fan does on a concave face.

    An L-shaped face is the minimal case of the plate and column sides the
    capitel/cutter booleans produce.
    """
    L = [(0, 0, 0), (3, 0, 0), (3, 1, 0), (1, 1, 0), (1, 3, 0), (0, 3, 0)]
    mesh = Mesh()
    for x, y, z in L:
        mesh.add_vertex(x=x, y=y, z=z)
    mesh.add_face(list(range(len(L))))

    positions, triangles = _sceneobject(mesh).viewmesh

    true_area = area_polygon(Polygon(L))
    assert true_area == pytest.approx(5.0)

    tri_area = sum(area_polygon([positions[i] for i in t]) for t in triangles)
    assert tri_area == pytest.approx(true_area, rel=1e-9)


def test_coplanar_seams_are_not_drawn_as_edges():
    """A face split into coplanar triangles must not show the split.

    This is what the old ``hide_coplanaredges`` flag was for; the scene object
    filters on face-normal angle instead.
    """
    flat = Mesh()
    for x, y in [(0, 0), (1, 0), (1, 1), (0, 1)]:
        flat.add_vertex(x=x, y=y, z=0)
    flat.add_face([0, 1, 2])
    flat.add_face([0, 2, 3])  # the 0-2 diagonal is coplanar -> not a real edge

    lines = _sceneobject(flat).lines

    assert len(lines) == 4, "the coplanar diagonal was drawn"
