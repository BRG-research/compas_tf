from compas_tf.floor_guide import FloorGuide

guide = FloorGuide()

print(f"size_grid_x: {guide.size_grid_x}")
print(f"size_grid_y: {guide.size_grid_y}")
print(f"size_column_head: {guide.size_column_head}")
print(f"size_outer_ribs: {guide.size_outer_ribs}")
print(f"size_inner_ribs: {guide.size_inner_ribs}")
print(f"size_inner_beams: {guide.size_inner_beams}")
print(f"height: {guide.height}")
print(f"rise: {guide.rise}")
print(f"static_h: {guide.static_h}")
print(f"size_oculus: {guide.size_oculus}")
print(f"size_oculus_x: {guide.size_oculus_x}")
print(f"size_oculus_y: {guide.size_oculus_y}")

print(f"oculus_points: {guide.oculus_points}")
print(f"quarter_polygon: {guide.quarter_polygon}")
print(f"quarter_column_polygon: {guide.quarter_column_polygon}")

data = guide.__data__
print(f"__data__: {data}")

restored = FloorGuide.__from_data__(data)
print(f"round-trip size_grid_x: {restored.size_grid_x}")
print(f"round-trip size_oculus: {restored.size_oculus}")
