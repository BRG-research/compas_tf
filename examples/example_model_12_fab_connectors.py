import pathlib

import compas
from compas.colors import Color
from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Transformation
from compas.geometry import Vector
from compas_viewer import Viewer

from compas_tf.model import TFModel
from compas_tf.writer import write_parts

data_dir = pathlib.Path(__file__).parent.parent / "data"
fab_dir = data_dir / "fabrication"
fab_dir.mkdir(parents=True, exist_ok=True)

GREY = Color(0.85, 0.85, 0.85)
RED = Color(0.9, 0.2, 0.2)
GAP = 400.0  # spacing between the laid-flat connectors along +Y

# One of each connector kind, laid flat and exported to its OWN fabrication
# set (the other instances are copies of the same part):
#
# - connector_0: the column <-> rib box connector PLATE, drilled through by its
#   four dowel holes (a boolean feature - modelgeometry is the drilled plate);
# - connector_wedge_0: the contact wedge between a quarter and its neighbour,
#   with its dowel cylinders as separate solids;
# - outer_rib_connector_0: the steel connector joining two quarters' outer ribs
#   (a fixed template shape - no cutters of its own).

model: TFModel = compas.json_load(data_dir / "cantilevers_model.json")
by_name = {element.name: element for element in model.elements()}


def orient_to_xy(mesh, oy=0.0):
    """Transformation that lays a world-space mesh flat on worldXY, resting on
    its broadest face at ``(0, oy)`` - same layout as example_model_16."""
    obb = mesh.obb
    obb = obb() if callable(obb) else obb
    axes = sorted(
        [
            (obb.xsize, Vector(*obb.frame.xaxis)),
            (obb.ysize, Vector(*obb.frame.yaxis)),
            (obb.zsize, Vector(*obb.frame.zaxis)),
        ],
        key=lambda item: item[0],
    )
    up_size, up = axes[0]
    long_axis = axes[2][1]
    source = Frame(Point(*obb.frame.point), long_axis, up.cross(long_axis))  # z-axis = up
    target = Frame(Point(0, oy, 0.5 * up_size), Vector(1, 0, 0), Vector(0, 1, 0))
    return Transformation.from_frame_to_frame(source, target)


def export(name, solids, preview):
    """Lay the part's solids flat together and write its fabrication set."""
    flat = orient_to_xy(preview)
    solids = [mesh.transformed(flat) for mesh in solids]
    preview = preview.transformed(flat)
    obb = preview.obb
    obb = obb() if callable(obb) else obb
    print(name, *sorted([obb.xsize, obb.ysize, obb.zsize], reverse=True))
    write_parts(solids, fab_dir, name, preview=preview)
    return solids


# Column <-> rib box connector: stock plate, drilled plate, drill cutters.
box = by_name["connector_0"]
box_cut = box.modelgeometry
box_uncut = box.compute_elementgeometry(include_features=False).transformed(box.modeltransformation)
box_cutters = [mesh.transformed(box.modeltransformation) for feature in box._features for mesh in getattr(feature, "meshes", None) or []]
box_uncut.name = f"{box.name}_uncut"
box_cut.name = box.name
for index, solid in enumerate(box_cutters):
    solid.name = f"{box.name}_cutter_{index}"
box_parts = export(box.name, [box_uncut, box_cut] + box_cutters, box_cut)

# Contact wedge: the wedge body plus its dowel cylinders as separate solids.
wedge = by_name["connector_wedge_0"]
wedge_cut = wedge.modelgeometry
wedge_dowels = [cylinder.boolean_geometry for cylinder in wedge.create_cylinders()]
wedge_cut.name = wedge.name
for index, solid in enumerate(wedge_dowels):
    solid.name = f"{wedge.name}_dowel_{index}"
wedge_parts = export(wedge.name, [wedge_cut] + wedge_dowels, wedge_cut)

# Outer rib connector: the template body on its own.
outer = by_name["outer_rib_connector_0"]
outer_cut = outer.modelgeometry
outer_cut.name = outer.name
outer_parts = export(outer.name, [outer_cut], outer_cut)

# The turned hardware, straight from the elements the booleans were cut with:
# a column-side dowel (DowelCylinderElement, 100 x O49 hardwood) and a wedge
# bolt (ConnectorCylinderElement, 160 x O18 steel).
dowel = by_name["cylinder_column_0"]
dowel_cut = dowel.modelgeometry
dowel_cut.name = "dowel_0"
dowel_parts = export("dowel_0", [dowel_cut], dowel_cut)

bolt = by_name["connector_wedge_0_cylinder_0"]
bolt_cut = bolt.modelgeometry
bolt_cut.name = "bolt_0"
bolt_parts = export("bolt_0", [bolt_cut], bolt_cut)

viewer = Viewer()
cursor = 0.0
for name, parts in [(box.name, box_parts), (wedge.name, wedge_parts), (outer.name, outer_parts), ("dowel_0", dowel_parts), ("bolt_0", bolt_parts)]:
    group = viewer.scene.add_group(name)
    for part in parts:
        aabb = part.aabb()
        color = RED if "_cutter_" in part.name or "_dowel_" in part.name else GREY if part.name.endswith("_uncut") else None
        moved = part.translated([0, cursor - min(0.0, aabb.ymin), 0])
        moved.name = part.name
        viewer.scene.add(moved, name=part.name, parent=group, facecolor=color)
    cursor += GAP + max(part.aabb().ymax for part in parts)

viewer.show()
