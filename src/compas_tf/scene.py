"""Viewer scene objects for compas_tf elements.

Registered through the standard compas plugin mechanism, exactly like
``compas_occt/scene.py``: compas scans every installed top-level package whose
name starts with ``compas``, imports the modules listed in its
``__all_plugins__``, and collects the ``register_scene_objects`` plugins it
finds. So this module is what makes ``viewer.scene.add(element)`` work - the
element draws itself, and the example does not have to know how.

What this replaces
------------------
Without it an example has to hand the viewer a mesh AND pre-process it::

    parent.add(triangulated(element.modelgeometry), hide_coplanaredges=True, color=GREY)

``triangulated()`` exists because ``compas_viewer``'s ``MeshObject`` fans an
n-gon from its centroid, which is only correct for a CONVEX face - the L-shaped
column and plate sides that come out of the capitel/cutter booleans fan into
overlapping triangles and render wrong. So every element was copied into a whole
new ear-clipped Mesh just to be drawn, and ``hide_coplanaredges`` was then needed
to hide the diagonals that copy introduced.

A scene object does the ear-clipping while it fills the shader buffer, so there
is no copy and no diagonal to hide: ``viewmesh`` emits correct triangles, and
``lines`` emits the real feature edges only.
"""

from compas.plugins import plugin


@plugin(category="factories", requires=["compas_viewer"])
def register_scene_objects():
    from compas.datastructures import Mesh
    from compas.geometry import Polygon
    from compas.geometry import earclip_polygon
    from compas.scene import GeometryObject
    from compas.scene import register
    from compas_viewer.scene.geometryobject import GeometryObject as ViewerGeometryObject

    from compas_tf.element import TFElement
    from compas_tf.viewer import _patch_group_nesting

    # compas_viewer's Group has no add_group: only the scene can nest, via
    # scene.add_group(name, parent=group). Every example mirrors a model tree
    # with `parent.add_group(child_name)`, which is the natural way to write it,
    # so give Group that method. Idempotent, and the only patch left.
    _patch_group_nesting()

    # Two face normals are treated as the same plane below this angle, so the
    # edge between them is a boolean artefact rather than a real edge. Compared
    # as a normal dot product rather than with compas' is_coplanar(), which
    # takes a DISTANCE tolerance and false-positives at building scale (a 6 m
    # face tilted by a degree still sits within 1e-5 of a plane through three
    # of its corners).
    COPLANAR_DOT = 0.999999  # ~0.08 degrees

    class TFElementObject(ViewerGeometryObject, GeometryObject):
        """Draw a compas_tf element from its model-space mesh.

        ``self.geometry`` is the ELEMENT (compas.scene names the item it wraps
        ``geometry``); :attr:`mesh` is the mesh that element resolves to.
        """

        @property
        def element(self):
            return self.geometry

        @property
        def mesh(self) -> Mesh:
            return self.element.modelgeometry

        @property
        def points(self):
            # Plates have hundreds of boolean vertices; drawing a dot on each
            # one is noise, and the viewer skips the buffer entirely for None.
            return None

        @property
        def lines(self):
            """Only the real edges: naked ones, and creases between faces that
            actually meet at an angle. This is what ``hide_coplanaredges`` was
            being used for, done once and correctly.
            """
            mesh = self.mesh
            normals = {face: mesh.face_normal(face, unitized=True) for face in mesh.faces()}
            lines = []
            for u, v in mesh.edges():
                faces = [f for f in mesh.edge_faces((u, v)) if f is not None]
                if len(faces) == 2:
                    a, b = (normals[f] for f in faces)
                    if a[0] * b[0] + a[1] * b[1] + a[2] * b[2] >= COPLANAR_DOT:
                        continue  # same plane -> a boolean seam, not an edge
                lines.append([mesh.vertex_coordinates(u), mesh.vertex_coordinates(v)])
            return lines

        @property
        def viewmesh(self):
            """Positions + triangles, ear-clipped so concave faces are right."""
            mesh = self.mesh
            index = {}
            positions = []
            for vertex in mesh.vertices():
                index[vertex] = len(positions)
                positions.append(mesh.vertex_coordinates(vertex))

            triangles = []
            for face in mesh.faces():
                vertices = mesh.face_vertices(face)
                if len(vertices) == 3:
                    triangles.append([index[v] for v in vertices])
                    continue
                try:
                    ears = earclip_polygon(Polygon([mesh.vertex_coordinates(v) for v in vertices]))
                except Exception:
                    ears = None
                if not ears:
                    # Degenerate face - fan it, which is what the viewer would
                    # have done anyway, rather than dropping the face.
                    for i in range(1, len(vertices) - 1):
                        triangles.append([index[vertices[0]], index[vertices[i]], index[vertices[i + 1]]])
                    continue
                for ear in ears:
                    triangles.append([index[vertices[i]] for i in ear])
            return positions, triangles

    class TFMeshObject(TFElementObject):
        """Same drawing, for a bare :class:`compas.datastructures.Mesh`.

        Not everything an example draws is an element: cut-feature solids,
        dowel cylinders, wedge boolean geometry and uncut column stock are all
        loose meshes. They come out of the same booleans, so they have the same
        concave n-gons, and they deserve the same exact triangulation.
        """

        @property
        def mesh(self) -> Mesh:
            return self.geometry

    # Registered against the BASE class: compas' dispatch walks the MRO
    # (inspect.getmro) looking for a registered type, so one entry covers
    # PlateElement, ColumnElement, SupportElement, SchoringElement,
    # TowerElement and every connector - all of which are TFElement subclasses.
    # Register a subclass here too if it ever needs different drawing.
    register(TFElement, TFElementObject, context="Viewer")

    # This one DELIBERATELY overrides compas_viewer's own Mesh -> MeshObject.
    # It wins because compas scans installed compas* packages in pkgutil order
    # and compas_tf sorts after compas_viewer, so this registration runs last.
    # That ordering is the one fragile thing here: if it ever flipped, meshes
    # would silently fall back to the centroid fan and concave faces would
    # render wrong again - wrong pixels, not an exception. compas_tf.scene has
    # a test for exactly that (tests/test_scene.py).
    register(Mesh, TFMeshObject, context="Viewer")
