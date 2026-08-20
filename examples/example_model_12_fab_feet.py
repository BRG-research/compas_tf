import pathlib

import compas
from compas.colors import Color
from compas.geometry import Frame
from compas.geometry import Transformation
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.support import SupportElement
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

STEEL = Color(0.45, 0.45, 0.5)

model: TFModel = compas.json_load(data_dir / "cantilevers_model.json")
support: SupportElement = model.find_element_with_name("support_0")

# Base plate center on the origin, standing up.
xform = Transformation.from_frame_to_frame(support.base_frame, Frame.worldXY())
foot = support.elementgeometry.transformed(xform)
print(foot.aabb().xsize, foot.aabb().ysize, foot.aabb().zsize)

foot.name = support.name
write_parts([foot], fab_dir, support.name, preview=foot)

viewer = Viewer()
viewer.scene.add(foot, name=support.name, facecolor=STEEL)
viewer.show()
