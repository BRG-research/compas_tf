import pathlib

import compas
from compas_viewer import Viewer

from compas_tf.model import TFModel

data_dir = pathlib.Path(__file__).parent.parent / "data"
MODEL_FILE = data_dir / "cantilevers_baked_model.json"
BAY_FILE = data_dir / "bay_model.json"
BAY_STEP_FILE = data_dir / "bay_model.stp"

model: TFModel = compas.json_load(MODEL_FILE)

# Both groups at once: the contacts between them survive only if they come out
# together. neighbors= adds the fasteners, which live in their own groups.
bay = model.find_groups_with_names(["column_model_0", "quarter_model_0"], name="bay_0", neighbors=True)

elements = list(bay.geometry_elements())
print(f"{len(elements)} of {len(list(model.geometry_elements()))} elements, {len(list(bay.contacts()))} contacts")

compas.json_dump(bay, BAY_FILE)
bay.to_step(BAY_STEP_FILE)

viewer = Viewer()
for element in elements:
    viewer.scene.add(element, name=element.name)
viewer.show()
