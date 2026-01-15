from compas_tf.joint_screw import ScrewElement
screw = ScrewElement()
print(f"Is closed: {screw.mesh.is_closed()}")
print(f"Is valid: {screw.mesh.is_valid()}")
print(f"Vertices: {screw.mesh.number_of_vertices()}")
print(f"Faces: {screw.mesh.number_of_faces()}")
