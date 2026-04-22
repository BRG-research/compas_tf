from session_py.element_schoring import ElementSchoring, Dataset
from session_py.session import Session
from session_py.plane import Plane
from session_py.point import Point
from session_py.vector import Vector
from session_py.xform import Xform
from session_compas.session import view


# =============================================================================
# Base parameters
# =============================================================================
p0 = Point(0, 0, 2.5)
v0 = Vector(0, 0, 1)

p1 = Point(2.5, 0, 0)
v1 = Vector(1, 0, 0)

dir_01 = p1 - p0

# =============================================================================
# Feet / head elements
# =============================================================================
foot0_plane = Plane(origin=p0, x_axis=v0, y_axis=v0.cross(-dir_01))
head0_plane = Plane(origin=p1, x_axis=v1, y_axis=v1.cross(dir_01))

GEOMETRY_AS_BREP = False

foot0 = ElementSchoring(Dataset.schoring_foot_0, transformation=Xform.to_frame(foot0_plane), geometry_as_brep=GEOMETRY_AS_BREP)
head0 = ElementSchoring(Dataset.schoring_head_0, transformation=Xform.to_frame(head0_plane), geometry_as_brep=GEOMETRY_AS_BREP)

# =============================================================================
# World-space frames at the foot / head local mate points
# =============================================================================
foot0.frames[0].xform = foot0.session_transformation
frame0 = foot0.frames[0].transformed()
head0.frames[0].xform = head0.session_transformation
frame1 = head0.frames[0].transformed()
direction = frame1.origin - frame0.origin

# =============================================================================
# Body elements
# =============================================================================
body0 = ElementSchoring(Dataset.schoring_body_start_0, geometry_as_brep=GEOMETRY_AS_BREP)
body1 = ElementSchoring(Dataset.schoring_body_end_0, geometry_as_brep=GEOMETRY_AS_BREP)

body0_plane = Plane(origin=frame0.origin, x_axis=frame0.y_axis, y_axis=direction.cross(frame0.y_axis))

body1_origin = frame1.origin + body0_plane.z_axis * (-body1.frames[0].origin.z)
body1_plane = Plane(origin=body1_origin, x_axis=frame0.y_axis, y_axis=direction.cross(frame0.y_axis))

body0.session_transformation = Xform.to_frame(body0_plane)
body1.session_transformation = Xform.to_frame(body1_plane)

# =============================================================================
# Session + viewer (via session_compas)
# =============================================================================
sess = Session("scaffolding")
grp = sess.add_group("scaffolding")
sess.add_element(foot0, parent=grp)
sess.add_element(head0, parent=grp)
sess.add_element(body0, parent=grp)
sess.add_element(body1, parent=grp)

view(sess)
