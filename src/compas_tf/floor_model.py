import math

from compas.geometry import Frame
from compas.geometry import Point
from compas.geometry import Rotation
from compas.geometry import Transformation
from compas.geometry import Vector
from compas.geometry import Plane
from compas.geometry import Polyline
from compas.geometry import Polygon
from compas.geometry import Line
from compas.geometry import Translation
from compas.geometry import intersection_plane_plane
from compas.geometry import intersection_line_plane
from compas.geometry import intersection_line_line
from compas_model.elements.group import Group
from compas_model.models import Model
from compas_model.models.interactiongraph import InteractionGraph
from compas_model.models.elementtree import ElementNode
from compas_model.elements import ColumnElement
from compas_tf.joint_sherpaxl120 import SherpaXL120Element
from compas_tf.plate import PlateElement

from compas_tf.floor_builder import FloorBuilder
from compas_tf.support import SupportElement
from compas_tf.solid_difference_modifier import SolidDifferenceModifier


class FloorModel(Model):
    """A timber floor model combining a Model tree with a FloorBuilder.

    Uses composition: holds a ``Model`` for the element tree
    and a ``FloorBuilder`` for the parametric geometry.

    Parameters
    ----------
    builder : :class:`FloorBuilder`
        Parametric floor geometry.
    name : str
        Name passed to the inner ``Model``.
    """ 


    @property
    def __data__(self) -> dict:
        data = {
            "transformation": self.transformation,
            "elements": self._elements,
            "materials": self._materials,
            "tree": self._tree.__data__,
            "graph": self._graph.__data__,
            "builder": self.builder.__data__,
            "story_height": self.story_height
        }
        return data

    @classmethod
    def __from_data__(cls, data: dict) -> "Model":
        model = cls(FloorBuilder.__from_data__(data["builder"]), story_height=data["story_height"])

        model._transformation = data["transformation"]
        model._elements = data["elements"]
        model._materials = data["materials"]

        for guid, element in model._elements.items():
            element.model = model

        model._graph = InteractionGraph.__from_data__(data["graph"])
        model._graph.model = model

        graphnode: int
        for graphnode in model._graph.nodes():  # type: ignore
            element = model._graph.node_element(graphnode)
            element.graphnode = graphnode

        def add(nodedata: dict, node: ElementNode) -> None:
            if "children" in nodedata:
                for childdata in nodedata["children"]:
                    name = childdata["name"]
                    guid = childdata["element"]
                    attr = childdata.get("attributes") or {}

                    element = model._elements[guid]
                    childnode = ElementNode(element=element, name=name, **attr)
                    element.treenode = childnode

                    node.add(childnode)
                    add(childdata, childnode)

        nodedata = data["tree"]["root"]
        node = model._tree.root

        add(nodedata, node)
        return model

    def __init__(self, builder, name="session", story_height=3500):
        super(FloorModel, self).__init__(name=name)
        self.builder = builder
        self.story_height = story_height

    # ------------------------------------------------------------------ #
    #  floor block
    # ------------------------------------------------------------------ #
    @staticmethod
    def _intersect_consecutive_planes(planes, reference_plane=None):
        """Find intersection points of consecutive plane pairs with a reference plane.

        Parameters
        ----------
        planes : list[:class:`compas.geometry.Plane`]
            List of planes to intersect pairwise.
        reference_plane : :class:`compas.geometry.Plane`, optional
            Plane to intersect the resulting lines with. Defaults to world XY.

        Returns
        -------
        list[:class:`compas.geometry.Point`]
            Intersection points.
        """
        if reference_plane is None:
            reference_plane = Plane.worldXY()

        intersection_points = []
        for i in range(len(planes) - 1):
            result = intersection_plane_plane(planes[i], planes[i + 1])
            if result:
                line = Line(result[0], result[1])
                pt = intersection_line_plane(line, reference_plane)
                if pt:
                    intersection_points.append(pt)
        return intersection_points
    
    def add_floor_block(self):
        """Add column blocks. """
        
        offset_planes = self.builder.compute_cut_planes(scale=self.builder.head_o, inclination=0)[3:6]
        for i in range(len(offset_planes)):
            offset_planes[i] = offset_planes[i].offset(-SherpaXL120Element.WIDTH*2)

        corner_end_plane0 = Plane(self.builder.end_planes[3].point, Vector.Zaxis().cross(self.builder.end_planes[3].normal)).offset(self.builder.thick*-1.5)
        corner_end_plane1 = Plane(self.builder.end_planes[0].point, Vector.Zaxis().cross(self.builder.end_planes[0].normal)).offset(self.builder.thick*1.5)
        cut_planes = [corner_end_plane1] + offset_planes + [corner_end_plane0] + self.builder.compute_cut_planes()[3:6][::-1] + [corner_end_plane1]

        top = Polygon(FloorModel._intersect_consecutive_planes(cut_planes, Plane.worldXY())).translated(Vector(0, 0, -self.builder.head_h))
        bottom = top.translated(Vector(0, 0, -self.builder.head_b ))

        plate = PlateElement(top=top, bottom=bottom, name="add_floor_block")
        plate.transformation = Translation.from_vector(Vector(0, 0, self.story_height))
        

        # Rotate 4 times, 90 degress
        quarters = self.find_element_with_name("quarters")
        
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            copy = plate.copy()
            copy.transformation = rot * plate.transformation
            copy.name = f"floor_block{i}"
            self.add_element(copy, parent=quarters)

    # ------------------------------------------------------------------ #
    #  column heads cuts
    # ------------------------------------------------------------------ #

    def add_column_cutter(self):
        """Add column 3 cutter per column. """


        # Columns are ordered 0..3 like the quarters (both rotated j * pi/2).
        columns = self.find_all_elements_of_type(ColumnElement)
        columns_by_index = {int(c.name.split("_")[-1]): c for c in columns}

        # Cutters
        offset_planes = self.builder.compute_cut_planes(scale=self.builder.head_o, inclination=0)[3:6]
        for i in range(len(offset_planes)):
            offset_planes[i] = offset_planes[i].offset(-SherpaXL120Element.WIDTH*2)
        
        corner_end_plane0 = Plane(self.builder.end_planes[3].point, Vector.Zaxis().cross(self.builder.end_planes[3].normal)).offset(self.builder.thick*-1.5)
        corner_end_plane1 = Plane(self.builder.end_planes[0].point, Vector.Zaxis().cross(self.builder.end_planes[0].normal)).offset(self.builder.thick*1.5)
        cut_planes = [corner_end_plane1] + offset_planes + [corner_end_plane0] + self.builder.compute_cut_planes()[3:6][::-1] + [corner_end_plane1]
        top = Polygon(FloorModel._intersect_consecutive_planes(cut_planes, Plane.worldXY())).translated(Vector(0, 0, 0))
            

        for i in range(3):
            p00 = top[i]
            p01 = top[i+1]
            p10 = top[i+1] + Vector(0, 0, -self.builder.head_b-self.builder.head_h)
            p11 = top[i] + Vector(0, 0, -self.builder.head_b-self.builder.head_h)
            v0 = (p01 - p00).unitized()
            p00 = p00 - v0 * self.builder.thick + Vector(0, 0, 10)
            p01 = p01 + v0 * self.builder.thick + Vector(0, 0, 10)
            p10 = p10 + v0 * self.builder.thick 
            p11 = p11 - v0 * self.builder.thick 

            poly0 = Polygon([p11, p10, p01, p00])
            poly1 = poly0.translated(poly0.normal * SherpaXL120Element.WIDTH * 6)
            bot_pl = Polyline(list(poly0.points) + [poly0.points[0]])
            top_pl = Polyline(list(poly1.points) + [poly1.points[0]])
            plate = PlateElement(bottom_polyline=bot_pl, top_polyline=top_pl, name="column_cutter")
            plate.transformation = Translation.from_vector(Vector(0, 0, self.story_height))
            quarters = self.find_element_with_name("quarters")

            for j in range(4):
                rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), j * math.pi / 2, Point(0, 0, 0))
                copy = plate.copy()
                copy.transformation = rot * plate.transformation
                copy.name = f"column_cutter_{i}_{j}"
                self.add_element(copy, parent=quarters)

                column = columns_by_index.get(j)
                if column is not None:
                    self.add_modifier(copy, column, SolidDifferenceModifier())


    # ------------------------------------------------------------------ #
    #  sherpa joints
    # ------------------------------------------------------------------ #

    def add_sherpa_joints(self):
        """Add 3 SherpaXL120 joints per column with solid difference cuts on the column."""
        columns = self.find_all_elements_of_type(ColumnElement)
        columns_by_index = {int(c.name.split("_")[-1]): c for c in columns}

        connection_width = SherpaXL120Element.WIDTH

        offset_planes = self.builder.compute_cut_planes(scale=self.builder.head_o, inclination=0)[3:6]
        for k in range(len(offset_planes)):
            offset_planes[k] = offset_planes[k].offset(-connection_width * 2)

        corner_end_plane0 = Plane(self.builder.end_planes[3].point, Vector.Zaxis().cross(self.builder.end_planes[3].normal)).offset(self.builder.thick * -1.5)
        corner_end_plane1 = Plane(self.builder.end_planes[0].point, Vector.Zaxis().cross(self.builder.end_planes[0].normal)).offset(self.builder.thick * 1.5)
        cut_planes = [corner_end_plane1] + offset_planes + [corner_end_plane0, corner_end_plane1]
        top = Polyline(FloorModel._intersect_consecutive_planes(cut_planes, Plane.worldXY()))

        sherpa_frames = []
        for i in range(3):
            p1 = top[i + 1]
            p0 = top[i]
            midpoint = (p0 + p1) * 0.5
            if i == 0 or i == 2:
                direction = (p1 - p0).unitized()
                length = (p1 - p0).length * 0.5 - 80 * 0.5
                direction = direction * length if i == 2 else direction * -length
                midpoint = direction + midpoint
            frame = Frame(midpoint, p0 - p1, -Vector.Zaxis().cross(p1 - p0))
            sherpa_frames.append(frame)

        quarters = self.find_element_with_name("quarters")
        lift = Translation.from_vector(Vector(0, 0, self.story_height))

        for i, frame in enumerate(sherpa_frames):
            for j in range(4):
                rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), j * math.pi / 2, Point(0, 0, 0))
                sherpa = SherpaXL120Element(
                    depth=80,
                    height=370,
                    transformation=rot * lift * Transformation.from_frame(frame),
                    name=f"sherpaxl120_{i}_{j}",
                )
                self.add_element(sherpa, parent=quarters)

                column = columns_by_index.get(j)
                if column is not None:
                    self.add_modifier(sherpa, column, SolidDifferenceModifier())

    # ------------------------------------------------------------------ #
    #  Ribs
    # ------------------------------------------------------------------ #

    def add_ribs(self, boundary_thick=None, inner_thick=None, inner_outward_signs=None):
        """Add rib PlateElements (axes 0, 1, 2, 6) per quarter.

        Boundary ribs (axes 0 and 6) keep their column-side face fixed at
        +/-1.5*thick from the axis and grow inward until total width =
        ``boundary_thick``.

        Inner ribs (axes 1 and 2) keep their *outer* face fixed at
        +/-0.5*thick from the axis (matching the original geometry on the
        side facing the boundary) and grow inward until total width =
        ``inner_thick``. Which side counts as outward depends on the target
        plane's normal direction — pass ``inner_outward_signs`` as
        ``{1: +1 or -1, 2: +1 or -1}`` to flip a rib that went the wrong
        way. Default ``{1: -1, 2: +1}``.

        Each plate is lifted by ``self.story_height`` and rotated 4x around
        Z, nested under the ``quarters`` group.
        """
        if inner_outward_signs is None:
            inner_outward_signs = {1: -1, 2: +1}
        from compas.geometry import Projection
        from compas_tf.geometry import PolylineCut
        from compas_tf.geometry import PolylineLoft

        builder = self.builder
        if boundary_thick is None:
            boundary_thick = builder.outer_thick
        if inner_thick is None:
            inner_thick = builder.inner_thick
        rib_parabolas = builder.rib_parabolas
        target_planes = builder.target_planes
        cut_planes = builder.cut_planes
        thick = builder.thick
        head_h = builder.head_h
        end_planes = builder.compute_cut_planes(scale=builder.head_o, inclination=0)[3:6]
        sherpa_width = SherpaXL120Element.WIDTH

        # Retrieve the sherpa frames previously added by add_sherpa_joints.
        # Each sherpa was placed with transformation = rot * lift * Transformation.from_frame(frame).
        # Take j=0 (rot is identity at j=0), strip the lift, recover the local frame.
        inv_lift = Translation.from_vector(Vector(0, 0, -self.story_height))
        sherpa_frames = []
        for i in range(3):
            sherpa = self.find_element_with_name(f"sherpaxl120_{i}_0")
            if sherpa is None:
                raise RuntimeError(
                    "add_sherpa_joints must be called before add_ribs so the rib "
                    "ends can be cut at the sherpa frames."
                )
            local_xform = inv_lift * sherpa.transformation
            sherpa_frames.append(Frame.from_transformation(local_xform))

        # (axis_idx, parabola_idx, target_idx, boundary_cut_idx, rib_cut_idx, end_plane_idx)
        rib_configs = [
            (0, 0, 0, 0, 0, 0),
            (1, 1, 1, 0, 1, 1),
            (2, 2, 2, 2, 1, 1),
            (6, 3, 3, 2, 2, 2),
        ]

        quarters = self.find_element_with_name("quarters")
        lift = Translation.from_vector(Vector(0, 0, self.story_height))

        for axis_idx, parabola_idx, target_idx, boundary_cut_idx, rib_cut_idx, end_plane_idx in rib_configs:
            # Per-axis offsets along target_plane normal, expressed as multiples of `thick`
            # so the existing `* thick * offset` math below stays unchanged.
            #
            # Boundary ribs (0, 6): keep the OUTER face (column-side, at +/-1.5*thick from axis
            # in the original geometry) fixed and grow the rib INWARD until total width = boundary_thick.
            # Inner ribs (1, 2): centred on the axis with total width = inner_thick.
            if axis_idx == 0:
                # Outward = -normal. Column-side face stays at -1.5*thick; inner face moves toward +normal.
                offset1 = -1.5
                offset0 = offset1 + boundary_thick / thick
            elif axis_idx == 6:
                # Outward = +normal. Column-side face stays at +1.5*thick; inner face moves toward -normal.
                offset0 = 1.5
                offset1 = offset0 - boundary_thick / thick
            else:
                # Inner ribs: anchor the outer face at +/-0.5*thick (whichever side faces
                # the boundary, per inner_outward_signs) and grow inward.
                sign = inner_outward_signs.get(axis_idx, +1)
                if sign > 0:
                    offset0 = 0.5
                    offset1 = 0.5 - inner_thick / thick
                else:
                    offset0 = -0.5 + inner_thick / thick
                    offset1 = -0.5

            # Rib end_plane = sherpa frame offset by sherpa width along its yaxis.
            # Plane normal flipped so cut_by_plane(..., flip=True) keeps the rib
            # body next to the column head (matches the original sign convention).
            sherpa_frame = sherpa_frames[end_plane_idx]
            end_plane = Plane(sherpa_frame.point + sherpa_frame.yaxis * sherpa_width, -sherpa_frame.yaxis)
            cut_boundary = cut_planes[boundary_cut_idx]
            cut_rib = cut_planes[rib_cut_idx + 3]

            if axis_idx in (0, 6):
                cut_boundary = cut_boundary.offset(-thick)

            proj0 = rib_parabolas[parabola_idx].translated(target_planes[target_idx].normal * thick * offset0)
            proj1 = rib_parabolas[parabola_idx].translated(target_planes[target_idx].normal * thick * offset1)

            cut0 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj0, cut_rib), cut_boundary)
            cut1 = PolylineCut.cut_by_plane(PolylineCut.cut_by_plane(proj1, cut_rib), cut_boundary)

            extension = 600
            line0 = PolylineCut.cut_by_plane(Polyline([cut0[0], cut0[-1]]).extended([extension, 0]), end_plane, flip=True)
            line1 = PolylineCut.cut_by_plane(Polyline([cut1[0], cut1[-1]]).extended([extension, 0]), end_plane, flip=True)

            xy_proj = Projection.from_plane_and_direction(Plane.worldXY(), Vector.Zaxis())
            mid_proj = Projection.from_plane_and_direction(Plane([0, 0, -head_h], [0, 0, 1]), Vector.Zaxis())

            top0, top1 = line0.transformed(xy_proj), line1.transformed(xy_proj)
            mid0 = PolylineCut.cut_by_plane(line0.transformed(mid_proj), cut_rib, flip=True)
            mid1 = PolylineCut.cut_by_plane(line1.transformed(mid_proj), cut_rib, flip=True)

            joined0 = Polyline(list(reversed(top0.points)) + mid0.points + cut0.points)
            joined1 = Polyline(list(reversed(top1.points)) + mid1.points + cut1.points)
            joined0.append(joined0.points[0])
            joined1.append(joined1.points[0])

            mesh = PolylineLoft.to_mesh(joined0, joined1)

            for j in range(4):
                rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), j * math.pi / 2, Point(0, 0, 0))
                plate = PlateElement(
                    top_polyline=joined0,
                    bottom_polyline=joined1,
                    mesh=mesh,
                    name=f"rib_{axis_idx}_{j}",
                )
                plate.transformation = rot * lift
                self.add_element(plate, parent=quarters)

    # ------------------------------------------------------------------ #
    #  Boundaries
    # ------------------------------------------------------------------ #

    def add_boundaries(self, boundary_thick=None):
        """Add boundary PlateElements along the oculus perimeter (axes 3, 4, 5).

        Boundaries are vertical wall plates running along the oculus-side edges
        of the quarter polygon (q1[1] -> q1[2] -> q1[3] -> q1[4]). The 3 plates
        meet at the two oculus points. Default thickness comes from
        ``builder.inner_thick`` so it matches the inner ribs.
        """
        from compas_tf.geometry import PolylineLoft
        from compas_tf.geometry import PolylineOffset
        from compas.geometry import Polygon as _Polygon

        builder = self.builder
        if boundary_thick is None:
            boundary_thick = builder.inner_thick
        # Contract the boundary plate at the side that meets the boundary rib
        # by the boundary rib's "inward extent" past the wall = outer_thick -
        # column_head_offset. This puts the plate's start at the rib's inner
        # face so they meet flush instead of overlapping.
        contraction = builder.outer_thick - builder.column_head_offset
        dist = builder.height - builder.rise

        q1 = builder.quarter_polygon
        # poly0: edge -> oculus_south -> oculus_west -> edge
        poly0 = _Polygon([q1[1], q1[2], q1[3], q1[4]])
        plates = PolylineOffset.offset_quarter_reciprocally(poly0, boundary_thick)

        quarters = self.find_element_with_name("quarters")
        lift = Translation.from_vector(Vector(0, 0, self.story_height))

        for j, plate_poly in enumerate(plates):
            axis_idx = j + 3  # axes 3, 4, 5
            inner_pts = list(plate_poly.points)

            # Contract the side meeting a boundary rib so the plate's start lies
            # at the rib's inner face (parametric on outer_thick).
            if j == 0:
                dir03 = Vector.from_start_end(inner_pts[0], inner_pts[1]).unitized() * contraction
                inner_pts[0] = inner_pts[0] + dir03
                dir30 = Vector.from_start_end(inner_pts[3], inner_pts[2]).unitized() * contraction
                inner_pts[3] = inner_pts[3] + dir30
            elif j == 2:
                dir01 = Vector.from_start_end(inner_pts[0], inner_pts[1]).unitized() * contraction
                inner_pts[0] = inner_pts[0] + dir01
                dir32 = Vector.from_start_end(inner_pts[3], inner_pts[2]).unitized() * contraction
                inner_pts[3] = inner_pts[3] + dir32

            # Build the two vertical face polylines of the boundary wall.
            if j < 2:
                s0 = Polyline([inner_pts[0], inner_pts[0] + Vector(0, 0, -dist), inner_pts[1] + Vector(0, 0, -dist), inner_pts[1], inner_pts[0]])
                s1 = Polyline([inner_pts[3], inner_pts[3] + Vector(0, 0, -dist), inner_pts[2] + Vector(0, 0, -dist), inner_pts[2], inner_pts[3]])
            else:
                s0 = Polyline([inner_pts[0], inner_pts[1], inner_pts[1] + Vector(0, 0, -dist), inner_pts[0] + Vector(0, 0, -dist), inner_pts[0]])
                s1 = Polyline([inner_pts[3], inner_pts[2], inner_pts[2] + Vector(0, 0, -dist), inner_pts[3] + Vector(0, 0, -dist), inner_pts[3]])

            mesh = PolylineLoft.to_mesh(s1, s0)

            for k in range(4):
                rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), k * math.pi / 2, Point(0, 0, 0))
                plate = PlateElement(
                    top_polyline=s1,
                    bottom_polyline=s0,
                    mesh=mesh,
                    name=f"boundary_{axis_idx}_{k}",
                )
                plate.transformation = rot * lift
                self.add_element(plate, parent=quarters)

    # ------------------------------------------------------------------ #
    #  Wedges (small plates between ribs near the column head)
    # ------------------------------------------------------------------ #

    def add_wedges(self):
        """Add 3 wedge PlateElements per quarter, between adjacent ribs at the
        column head.

        For each wedge k, the polygon is built by consecutive plane intersection
        of 4 planes:
          - left rib's wedge-facing vertical face plane (from rib polyline)
          - outer column-head plane = ``compute_cut_planes()[3+k]``
          - right rib's wedge-facing vertical face plane (from rib polyline)
          - inner column-head plane = ``compute_cut_planes(scale=head_o)[3+k].offset(-WIDTH*2)``
        These are the same plane pairs used by ``add_floor_block`` /
        ``add_column_cutter``. Top polygon at z=0, bottom at z=-head_h.
        """
        from compas_tf.geometry import PolylineLoft

        builder = self.builder
        head_h = builder.head_h
        sherpa_width = SherpaXL120Element.WIDTH

        # Plane construction inspired by add_floor_block / add_column_cutter,
        # but with one less sherpa thickness on the inner pair so it lines up
        # with the rib end (rib end = sherpa_frame + yaxis * WIDTH, which is
        # one sherpa thickness back from the cutter position at -2*WIDTH).
        inner_planes = [p.offset(-sherpa_width) for p in builder.compute_cut_planes(scale=builder.head_o, inclination=0)[3:6]]
        outer_planes = builder.compute_cut_planes()[3:6]

        # (left_axis, left_polyline_attr, right_axis, right_polyline_attr).
        # 'top'/'bottom' picks which rib polyline (joined0/joined1) is on the
        # wedge side. axis 6 in add_ribs uses target_planes[3] (+n direction is
        # n3, not n6), so its wedge-side polyline for wedge k=2 is 'bottom'.
        wedge_configs = [
            (0, 'top', 1, 'bottom'),
            (1, 'top', 2, 'bottom'),
            (2, 'top', 6, 'bottom'),
        ]

        quarters = self.find_element_with_name("quarters")
        lift = Translation.from_vector(Vector(0, 0, self.story_height))

        def _top_edge_pts(polyline, tol=1.0):
            pts = polyline.points
            max_z = max(p.z for p in pts)
            top = [p for p in pts if abs(p.z - max_z) < tol]
            seen = []
            for p in top:
                if not any(abs(p.x - q.x) < 1e-3 and abs(p.y - q.y) < 1e-3 for q in seen):
                    seen.append(p)
            return seen

        def _vertical_plane_through_edge(p0, p1):
            d = Vector.from_start_end(p0, p1).unitized()
            return Plane(p0, Vector.Zaxis().cross(d))

        for k, (left_axis, left_attr, right_axis, right_attr) in enumerate(wedge_configs):
            rib_left = self.find_element_with_name(f"rib_{left_axis}_0")
            rib_right = self.find_element_with_name(f"rib_{right_axis}_0")
            if rib_left is None or rib_right is None:
                raise RuntimeError("add_ribs must be called before add_wedges.")

            left_poly = rib_left.top_polyline if left_attr == 'top' else rib_left.bottom_polyline
            right_poly = rib_right.top_polyline if right_attr == 'top' else rib_right.bottom_polyline

            l_pts = _top_edge_pts(left_poly)
            r_pts = _top_edge_pts(right_poly)
            if len(l_pts) < 2 or len(r_pts) < 2:
                raise RuntimeError(
                    f"wedge {k}: rib top-edge has {len(l_pts)} (left) and "
                    f"{len(r_pts)} (right) unique points; expected >=2"
                )

            left_face = _vertical_plane_through_edge(l_pts[0], l_pts[1])
            right_face = _vertical_plane_through_edge(r_pts[0], r_pts[1])

            outer = outer_planes[k]
            inner = inner_planes[k]

            # Consecutive plane intersection: 4 planes -> 4 corners (closing back to first).
            polygon_planes = [left_face, outer, right_face, inner, left_face]
            pts = FloorModel._intersect_consecutive_planes(polygon_planes, Plane.worldXY())
            if not pts or len(pts) < 4:
                continue

            top = Polyline([Point(p[0], p[1], 0) for p in pts] + [Point(pts[0][0], pts[0][1], 0)])
            bottom = Polyline([Point(p[0], p[1], -head_h) for p in pts] + [Point(pts[0][0], pts[0][1], -head_h)])
            # Skip earclip triangulation (it fails on self-intersecting/degenerate
            # quads). Build a quad prism mesh directly: top quad + bottom quad +
            # 4 side quads. The polylines themselves are stored on the plate.
            from compas.datastructures import Mesh as _Mesh
            n = len(pts)
            mesh = _Mesh()
            for p in pts:
                mesh.add_vertex(x=p[0], y=p[1], z=0.0)
            for p in pts:
                mesh.add_vertex(x=p[0], y=p[1], z=-head_h)
            mesh.add_face(list(range(n)))                       # top
            mesh.add_face([n + i for i in range(n - 1, -1, -1)])  # bottom (reversed)
            for i in range(n):
                ni = (i + 1) % n
                mesh.add_face([i, ni, n + ni, n + i])           # side

            for j in range(4):
                rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), j * math.pi / 2, Point(0, 0, 0))
                plate = PlateElement(
                    top_polyline=top,
                    bottom_polyline=bottom,
                    mesh=mesh,
                    name=f"wedge_{k}_{j}",
                )
                plate.transformation = rot * lift
                self.add_element(plate, parent=quarters)

    # ------------------------------------------------------------------ #
    #  TSections
    # ------------------------------------------------------------------ #

    # ------------------------------------------------------------------ #
    #  Surfaces
    # ------------------------------------------------------------------ #



    # ------------------------------------------------------------------ #
    #  quarters
    # ------------------------------------------------------------------ #

    def add_quarter_floor(self, angles=None):
        """Add quarter floor elements for all quarters.

        Parameters
        ----------
        angles : list[float], optional
            Rotation angles in degrees. Default is [0, 90, 180, 270].

        Returns
        -------
        list[QuarterResult]
            Results for each quarter.
        """
        from compas_tf.quarter_floor import QuarterFloorElement

        if angles is None:
            angles = [0, 90, 180, 270]

        quarters_group = self.model.add_group("quarters")
        results = []

        for angle in angles:
            result = QuarterFloorElement.build(self.builder, angle=angle)
            quarter_group = Group(name=f"quarter_{angle}")
            self.model.add_element(quarter_group, parent=quarters_group)

            # Ribs (axes 0, 1, 2, 6)
            ribs_group = Group(name="ribs")
            self.model.add_element(ribs_group, parent=quarter_group)
            for axis_idx in [0, 1, 2, 6]:
                if axis_idx in result.axis_elements:
                    self.model.add_element(result.axis_elements[axis_idx], parent=ribs_group)

            # Boundaries (axes 3, 4, 5)
            boundaries_group = Group(name="boundaries")
            self.model.add_element(boundaries_group, parent=quarter_group)
            for axis_idx in [3, 4, 5]:
                if axis_idx in result.axis_elements:
                    self.model.add_element(result.axis_elements[axis_idx], parent=boundaries_group)

            # T-sections
            tsections_group = Group(name="tsections")
            self.model.add_element(tsections_group, parent=quarter_group)
            for element in result.tsection_elements:
                self.model.add_element(element, parent=tsections_group)

            # Surfaces
            surfaces_group = Group(name="surfaces")
            self.model.add_element(surfaces_group, parent=quarter_group)
            for element in result.surface_elements:
                self.model.add_element(element, parent=surfaces_group)

            # Corner blocks
            corners_group = Group(name="corner_blocks")
            self.model.add_element(corners_group, parent=quarter_group)
            for element in result.corner_block_elements:
                self.model.add_element(element, parent=corners_group)

            # Connectors
            connectors_group = Group(name="connectors")
            self.model.add_element(connectors_group, parent=quarter_group)
            for screw in result.screws:
                self.model.add_element(screw, parent=connectors_group)
            for dowel in result.dowels:
                self.model.add_element(dowel, parent=connectors_group)
            for strip in result.strips:
                self.model.add_element(strip, parent=connectors_group)
            for hilti in result.hilti_joints:
                self.model.add_element(hilti, parent=connectors_group)

            # Interactions
            for connector, element in result.interactions:
                self.model.add_interaction(connector, element)

            # Modifiers
            for source, target, modifier in result.modifiers:
                self.model.add_modifier(source, target, modifier)

            results.append(result)

        return results

    # ------------------------------------------------------------------ #
    #  oculus
    # ------------------------------------------------------------------ #

    def add_oculus(self):
        """Add oculus beam elements using OculusElement.build().

        Returns
        -------
        list
            The oculus elements.
        """
        from compas_tf.oculus import OculusElement

        result = OculusElement.build(self.builder)

        oculus_group = self.add_group("oculus")
        for element in result.oculus_elements:
            self.add_element(element, parent=oculus_group)

        connectors_group = Group(name="oculus_connectors")
        self.add_element(connectors_group, parent=oculus_group)
        for screw in result.screws:
            self.add_element(screw, parent=connectors_group)
        for dowel in result.dowels:
            self.add_element(dowel, parent=connectors_group)
        for strip in result.strips:
            self.add_element(strip, parent=connectors_group)

        for connector, element in result.interactions:
            self.add_interaction(connector, element)

        return result.oculus_elements

    # ------------------------------------------------------------------ #
    #  supports
    # ------------------------------------------------------------------ #

    def add_support(self, column_size=200):
        """Add 4 support elements rotated 90° around centre.

        Parameters
        ----------
        column_size : float
            Column cross-section side length in mm.
        story_height : float
            Story height in mm.
        """
        column_plan = self.builder.corner_point_column(column_size)
        base_frame = Frame([column_plan.x, column_plan.y, 0], [1, 0, 0], [0, 1, 0])
        supports_group = self.add_group("supports")
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            support = SupportElement(rot * Transformation.from_frame(base_frame))
            support.name = f"support_{i}"
            self.add_element(support, parent=supports_group)

    # ------------------------------------------------------------------ #
    #  columns
    # ------------------------------------------------------------------ #

    def add_column(self, column_size=200):
        """Add 4 column elements rotated 90° around centre.

        Parameters
        ----------
        column_size : float
            Column cross-section side length in mm.
        story_height : float
            Story height in mm.
        """
        column_plan = self.builder.corner_point_column(column_size)
        column_height = self.story_height - SupportElement.HEIGHT
        base_frame = Frame([column_plan.x, column_plan.y, SupportElement.HEIGHT], [1, 0, 0], [0, 1, 0])
        columns_group = self.add_group("columns")
        for i in range(4):
            rot = Rotation.from_axis_and_angle(Vector(0, 0, 1), i * math.pi / 2, Point(0, 0, 0))
            column = ColumnElement(column_size, column_size, column_height, rot * Transformation.from_frame(base_frame), name=f"column_{i}")
            self.add_element(column, parent=columns_group)



