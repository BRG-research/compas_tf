from compas_viewer.config import Config
from compas_viewer.viewer import Viewer

from compas_tf.joint_screw import ScrewElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element

config = Config()
config.unit = "mm"
viewer = Viewer(config)
viewer.renderer.rendermode = "lighted"  # "lighted", "wireframe", "shaded", "ghosted"

b = ScrewElement()
c = SherpaXL120Element()

viewer.scene.add(b.elementgeometry)
viewer.scene.add(c.elementgeometry)

viewer.show()
