"""example_model_9_element_with_features.py

Open the cantilever_model written by example_model_8 and isolate two elements:

- one ``inner_beams`` plate, carved by its wedge + cylinder connectors, and
- one column, carved by its head/connector cutters.

For each we show BOTH the carved element geometry AND the feature solids that
performed the boolean cuts (still stored on the element, in its local frame).
The features are recovered in model space so they can be reused for other
operations (further booleans, fabrication toolpaths, ...).
"""

import pathlib

import compas
from compas.datastructures import Mesh
from compas_model.models import Model

from compas_tf.column import ColumnCutFeature
from compas_tf.column import ColumnElement
from compas_tf.plate import PlateElement
from compas_tf.solid_difference_modifier import MeshCutFeature
from compas_tf.viewer import make_viewer
from compas_tf.viewer import triangulated

data_dir = pathlib.Path(__file__).parent.parent / "data"

# Boolean-DIFFERENCE feature types (the cuts). Union features (e.g. the column
# capitel, a ColumnFeature) are NOT in here, so they stay part of the element.
CUT_FEATURES = (MeshCutFeature, ColumnCutFeature)

# ------------------------------------------------------------------ #
# Deserialize the cantilever model written by example_model_8
# ------------------------------------------------------------------ #

model: Model = compas.json_load(data_dir / "cantilever_model.json")

# ------------------------------------------------------------------ #
# Recover the feature solids (the cutters / capitel) of an element in MODEL
# space. Features are stored in the element's LOCAL frame, so push them through
# modeltransformation - the same transform the element geometry gets.
# ------------------------------------------------------------------ #


def feature_solids(element):
    """Feature solids of ``element`` (cut meshes + capitel boxes) in model space."""
    xform = element.modeltransformation
    solids = []
    for feature in element._features:
        for mesh in getattr(feature, "meshes", None) or []:
            solids.append(mesh.transformed(xform))
        for box in getattr(feature, "boxes", None) or []:
            solids.append(box.to_mesh().transformed(xform))
    return solids


def original_geometry(element):
    """Element geometry in its ORIGINAL form, in model space — the boolean
    difference (cut) features are NOT applied, so the wedge/cylinder/connector
    pockets are absent. Union features (the column capitel) are kept.
    """
    mesh = element.compute_elementgeometry(include_features=False)
    for feature in element._features:
        if isinstance(feature, CUT_FEATURES):
            continue
        mesh = feature.apply(mesh)
    return mesh.transformed(element.modeltransformation)


# ------------------------------------------------------------------ #
# Pick the two elements to isolate: an inner_beams plate carved by wedge +
# cylinders, and a column carved by its features.
# ------------------------------------------------------------------ #

plate = next(
    e for e in model.elements()
    if isinstance(e, PlateElement) and e._features and (e.name or "").startswith("inner_beams_")
)
column = next(e for e in model.elements() if isinstance(e, ColumnElement))

print(f"plate  : {plate.name}  features={len(plate._features)}  cutter solids={len(feature_solids(plate))}")
print(f"column : {column.name}  features={len(column._features)}  cutter solids={len(feature_solids(column))}")

# ------------------------------------------------------------------ #
#  View - each element in its own group: carved body (grey, opaque) plus the
#  feature solids (red, semi-transparent) that cut it.
# ------------------------------------------------------------------ #

GREY = (0.6, 0.6, 0.6)
RED = (0.9, 0.2, 0.2)

viewer = make_viewer(data_dir)

for element in (plate, column):
    group = viewer.scene.add_group(f"{element.name}__with_features")

    body = group.add_group("original_element")
    geometry = original_geometry(element)  # uncut, original form (no boolean difference)
    if isinstance(geometry, Mesh):
        body.add(triangulated(geometry), name=element.name, hide_coplanaredges=True, color=GREY)

    cutters = group.add_group("feature_solids")
    for j, solid in enumerate(feature_solids(element)):
        cutters.add(triangulated(solid), name=f"feature_{j}", color=RED, opacity=0.5)

viewer.show()
