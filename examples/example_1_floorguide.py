"""example_1_floorguide.py

Visualize the FloorGuide plate geometry for one quarter of the floor:
beds, t-sections, outer/inner ribs, wedge blocks, wedge columns,
inner beams, and sherpa connections.

FloorGuide owns all parametric plate geometry for one quarter.
It is independent of FloorBuilder and uses its own parameter set.
"""

import pathlib

import compas
from compas.colors import Color
from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

from compas_tf.floor_guide import FloorGuide
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.plate import PlateElement

data_dir = pathlib.Path(__file__).parent.parent / "data"

# ------------------------------------------------------------------ #
#  FloorGuide
# ------------------------------------------------------------------ #

guide = FloorGuide(
    size_grid_x=3000,
    size_grid_y=3000,
    size_column_head=250,
    size_column_head_chamfer=120,
    size_outer_ribs=100,
    size_inner_ribs=60,
    size_inner_beams=60,
    height=650,
    rise=453,
    size_oculus=1000,
)

compas.json_dump(guide, data_dir / "floorguide.json")

# ------------------------------------------------------------------ #
#  Viewer
# ------------------------------------------------------------------ #

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"


def add_plates(viewer, group_name, plates, facecolor):
    g = viewer.scene.add_group(group_name)
    for i, plate in enumerate(plates):
        if not isinstance(plate, PlateElement):
            continue
        pg = viewer.scene.add_group(f"{group_name}_{i}", parent=g)
        pg.add(plate.elementgeometry, facecolor=facecolor, show_lines=False)
        if plate.top_polyline:
            pg.add(plate.top_polyline, linecolor=Color.black())
        if plate.bottom_polyline:
            pg.add(plate.bottom_polyline, linecolor=Color.black())


add_plates(viewer, "beds", guide.beds, Color.green())
add_plates(viewer, "tsections", guide.tsections, Color.orange())
add_plates(viewer, "outer_ribs", guide.outer_ribs, Color.yellow())
add_plates(viewer, "inner_ribs", guide.inner_ribs, Color.yellow())
add_plates(viewer, "wedge_block", guide.wedge_block, Color.yellow())
add_plates(viewer, "wedges_column", guide.wedges_column, Color.cyan())
add_plates(viewer, "inner_beams", guide.inner_beams, Color.yellow())

g = viewer.scene.add_group("sherpas")
for i, sherpa in enumerate(guide.sherpas):
    if isinstance(sherpa, SherpaXL120Element):
        viewer.scene.add(sherpa.elementgeometry, facecolor=Color.red(), show_lines=False, parent=g)
    elif isinstance(sherpa, PlateElement):
        viewer.scene.add(sherpa.elementgeometry, facecolor=Color(0.8, 0.2, 0.8), show_lines=False, parent=g)

g = viewer.scene.add_group("debug")
for o in guide.debug:
    viewer.scene.add(o, parent=g)

viewer.show()
