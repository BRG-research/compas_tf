from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

from compas_tf.floor_builder import FloorBuilder
from compas_tf.geometry import PolylineOffset

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"

builder = FloorBuilder(
    size=3000,
    height=650,
    rise=453,
    oculus=1000,
    thick=40,
    beam_w=200,
)

for line in builder.quarter_polygon.lines:
    viewer.scene.add(line)

for p in builder.boundary_points:
    viewer.scene.add(p)



for line in builder.axes:
    viewer.scene.add(line)

viewer.show()
