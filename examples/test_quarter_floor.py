"""Test script for QuarterFloorElement.build()"""

from compas_tf.floor_builder import FloorBuilder
from compas_tf.quarter_floor import QuarterFloorElement


# Create builder
builder = FloorBuilder()

# Build quarter floor
result = QuarterFloorElement.build(builder)

# Print summary
print(f"Rib elements: {len(result.rib_elements)}")
print(f"Rib polylines: {len(result.rib_polys)}")
print(f"T-section elements: {len(result.tsection_elements)}")
print(f"Surface elements: {len(result.surface_elements)}")
print(f"Surface edge polys: {len(result.surface_edge_polys)}")
print(f"Boundary beam elements: {len(result.boundary_beam_elements)}")

# Verify elements
print("\nVerifying elements...")
for i, element in enumerate(result.rib_elements):
    mesh = element.mesh
    print(f"  Rib element {i} ({element.name}): {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces")

for i, element in enumerate(result.tsection_elements):
    mesh = element.mesh
    print(f"  T-section element {i} ({element.name}): {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces")

for i, element in enumerate(result.surface_elements):
    mesh = element.mesh
    print(f"  Surface element {i} ({element.name}): {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces")

for i, element in enumerate(result.boundary_beam_elements):
    mesh = element.mesh
    print(f"  Boundary element {i} ({element.name}): {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces")

print("\nTest completed successfully!")
