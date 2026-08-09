__author__ = ["Petras Vestartas"]
__copyright__ = "Petras Vestartas, Tom van Mele"
__license__ = "MIT License"
__email__ = "petrasvestartas@gmail.com"
__version__ = "0.1.2"

from compas_tf.geometry import (
    PolylineOffset,
    PolylineCut,
    PolylineLoft,
)

# Shared bases: baked-geometry serialization (TFElement/TFFeature/TFModel) and
# the mesh -> solid Brep conversion (BrepMixin.get_brep) every class exposes.
from compas_tf.brep import BrepMixin, mesh_to_brep, meshes_to_brep
from compas_tf.element import TFElement, TFFeature, baked, bakekey
from compas_tf.model import TFModel

from compas_tf.floor_guide import FloorGuide
from compas_tf.column import ColumnElement, ColumnAddFeature, ColumnCutFeature, ColumnFeature

# Additional element types for JSON serialization
from compas_tf.plate import PlateElement
from compas_tf.support import SupportElement
from compas_tf.schoring_element import SchoringElement
from compas_tf.tower_element import TowerElement, TowerElementFeature
from compas_tf.connectors import (
    ConnectorBoxElement,
    ConnectorBoxFeature,
    ConnectorCylinderElement,
    ConnectorCylinderFeature,
    ConnectorWedgeElement,
    ConnectorWedgeFeature,
    ConnectorElement,
    ConnectorFeature,
    DowelCylinderElement,
)

__all__ = [
    "PolylineOffset",
    "PolylineCut",
    "PolylineLoft",
    "BrepMixin",
    "mesh_to_brep",
    "meshes_to_brep",
    "TFElement",
    "TFFeature",
    "TFModel",
    "baked",
    "bakekey",
    "FloorGuide",
    "ColumnElement",
    "ColumnAddFeature",
    "ColumnCutFeature",
    "ColumnFeature",
    "PlateElement",
    "SupportElement",
    "SchoringElement",
    "TowerElement",
    "TowerElementFeature",
    "ConnectorBoxElement",
    "ConnectorBoxFeature",
    "ConnectorCylinderElement",
    "ConnectorCylinderFeature",
    "ConnectorWedgeElement",
    "ConnectorWedgeFeature",
    "ConnectorElement",
    "ConnectorFeature",
    "DowelCylinderElement",
]
