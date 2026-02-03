"""Test script for QuarterFloorElement.build()"""

from compas_tf.floor_builder import FloorBuilder
from compas_tf.quarter_floor import QuarterFloorElement

# Create builder
builder = FloorBuilder()

# Build quarter floor
result = QuarterFloorElement.build(builder)

# Print summary
print(f"Axis elements: {len(result.axis_elements)}")
print(f"Axis polylines: {len(result.axis_polys)}")
print(f"T-section elements: {len(result.tsection_elements)}")
print(f"Surface elements: {len(result.surface_elements)}")
print(f"Surface edge polys: {len(result.surface_edge_polys)}")
print(f"Screws: {len(result.screws)}")
print(f"Dowels: {len(result.dowels)}")
print(f"Strips: {len(result.strips)}")
print(f"Interactions: {len(result.interactions)}")

# Verify elements
print("\nVerifying axis elements...")
for axis_idx, element in result.axis_elements.items():
    mesh = element.compute_elementgeometry()
    print(f"  Axis {axis_idx} ({element.name}): {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces")

print("\nVerifying T-section elements...")
for i, element in enumerate(result.tsection_elements):
    mesh = element.compute_elementgeometry()
    print(f"  T-section {i} ({element.name}): {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces")

print("\nVerifying surface elements...")
for i, element in enumerate(result.surface_elements):
    mesh = element.compute_elementgeometry()
    print(f"  Surface {i} ({element.name}): {mesh.number_of_vertices()} vertices, {mesh.number_of_faces()} faces")

print("\nTest completed successfully!")
