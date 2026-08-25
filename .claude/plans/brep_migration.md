# Migrating compas_tf from meshes to Breps (compas_occt)

## Verdict

Go fully Brep. The Brep is the geometry; a mesh is only ever an **export
format**, produced by tessellation at the moment a file is written and never
stored, cached or reasoned about. Speed and file size are not constraints on
this decision — exactness is the point.

Concretely that means:

- Every `compute_elementgeometry` returns a Brep.
- Every boolean is `compas_occt`. `compas_manifold` is removed.
- `bake()` bakes **Breps**, not meshes.
- Meshes are created in exactly three places, all of them writers:
  `write_ifc` (compas_ifc needs one), `write_mesh`/`write_colored_obj` (OBJ,
  STL, and the docs viewer), and whatever the Rhino bundle needs.

What this buys, measured on this repo:

| | mesh today | Brep |
|---|---|---|
| 6 pockets + 8 drillings on a rib-sized plate | triangle soup | **36 exact faces** |
| a carved column in the model | **622 faces** of boolean debris | ~30 exact faces |
| the Sherpa connector | 220 triangles, Ø15 holes faceted | **32 faces, real cylindrical holes** |
| whole-model mesh→Brep conversion on every export | **7.9 s** | gone — already Brep |

Costs, accepted deliberately: a Brep serializes to roughly **12× the JSON** of
the equivalent mesh (170 KB vs 14 KB for the connector), so the baked model
grows from ~4 MB to tens of MB and loads more slowly. That is the correct
trade. A baked mesh is a lossy cache of a shape the project no longer has to
approximate.

Two facts make the rest cheap:

- **`compas_model` already accepts Breps.** `Element.elementgeometry`,
  `compute_elementgeometry` and `apply_features` are typed `Union[Brep, Mesh]`.
  There is no framework to fight.
- **`compas_occt` is already a hard dependency** (`requirements.txt`), already
  the STEP kernel, and already ships the Brep scene object compas_viewer needs.

---

## What is actually being replaced

`compas_manifold.booleans` is the entire mesh-boolean surface, and it is
narrow — **9 call sites in 2 modules**:

- `column.py:61,67` — capitel union
- `column.py:123,129,132` — cutter union, then difference
- `solid_difference_modifier.py:128,141,144` — `MeshCutFeature.apply`
- `solid_difference_modifier.py:274,295` — `_difference_backend` /
  `_chain_backend`, the two funnels everything else goes through

Those two funnels are the leverage point. `compas_cgal` appears in three
docstrings and **zero code** — stale references to delete on sight.

---

## The template already in the repo

`schoring_element.py` has done this already. It carries a `geometry_as_brep`
flag (`:147`), separate `_brep_cache` / `_mesh_cache` (`:168-169`), loads
`Brep.from_step` (`:207`) or falls back to `data["meshes"][0]` (`:212`), and
returns `Union[Mesh, Brep]` from `compute_elementgeometry` (`:263`). Its
`compute_aabb`/`compute_obb` call `.aabb()`/`.obb()` on whichever it holds.

**Copy this pattern for the transition, then delete the mesh half.** The flag
is scaffolding: it lets the migration land element by element with the model
working at every commit, instead of as one flag day. It is not the end state —
when the last element is Brep-backed, the flag and every `_mesh_cache` go.

`base_model.py:59-71` is the other precedent — `_aabb(element)` already
branches on `hasattr(geometry, "vertices_attributes")` to handle both.

---

## Blockers, ranked by how much they cost

### 1. compas_viewer — `scene.py:146` (hardest)

`register(Mesh, TFMeshObject, context="Viewer")` deliberately overrides
compas_viewer's own mesh object, and `viewmesh` (`:90-117`) and `lines`
(`:77-87`) do vertex/face/half-edge reasoning to suppress boolean seams and
ear-clip concave n-gons.

*Both of those problems are artefacts of mesh booleans.* A Brep has no seams to
suppress and no n-gons to ear-clip — `compas_occt`'s scene object draws the
exact edges. So this blocker mostly **dissolves** rather than needing a port.
What remains is a `TFBrepObject` for the project's own colouring, or accepting
the compas_occt default.

Already proven: both assembly examples render `OCCBrep` elements in
compas_viewer today, with `opacity` and `linecolor` working.

### 2. `Element.compute_aabb` and the BVH

`contacts.py:16-18` states the constraint outright — Breps cannot go on the
elements because `compute_aabb` and the BVH are Mesh-only. This is the sentence
the whole migration turns on, and it is **half stale**: `OCCBrep` provides both
`.aabb` and `.obb`. The real work is an inconsistency the codebase already
carries — `plate.py:750` uses `.obb` (Mesh property form) while
`connectors.py:171` uses `.obb()` (method form). Normalize that first, in
isolation, before anything else moves.

`column.py:466,488` needs nothing: it computes aabb/obb from `self.box`, not
from geometry.

### 3. `PlateElement.compute_contacts:845`

`isinstance(other.modelgeometry, Mesh)` → else `NotImplementedError`. A
Brep-geometry neighbour raises **today**. Must be fixed before any element that
plates touch becomes Brep-backed.

### 4. `SolidDifferenceModifier.apply:782,785`

`isinstance(x, Mesh)` gates that *silently skip* the operation and print a
warning for a Brep. Worse than raising — a partial migration would quietly stop
carving. Fix these to raise before starting.

### 5. `write_ifc:167`

`compas_ifc.create_element(geometry=mesh)` needs a Mesh. Tessellate on the way
out; `writer._as_mesh` already does exactly this.

### 6. Serialized baked meshes

`element.py:157-162`, `MeshCutFeature.__data__:117`, `tower_element.py:77`,
`schoring_element.py:212` all persist Meshes into JSON, and existing models on
disk carry them. Baking moves to Breps, but **a compatibility read path is
required** — old files must keep loading. This is a read-side branch, not a
migration script.

### 7. OBJ template parts

`connectors.py:1148` (`OuterRibConnectorElement`) and `support.py:196` read
`Mesh.from_obj`. `SupportElement` already shows the right answer: rebuild the
part from its dimensions and delete the OBJ dependency entirely. Do the same
for the outer rib connector — or, if its shape is not reducible to dimensions,
re-author it once as STEP. Keeping `mesh_to_brep` alive for one part would keep
the whole conversion layer alive; don't.

---

## What gets deleted

Roughly **600 lines**, all of it machinery that exists only because booleans
produce triangle soup:

| location | lines | what |
|---|---|---|
| `solid_difference_modifier.py:301-560` | ~260 | triangulate → boolean → re-merge-into-ngons |
| `solid_difference_modifier.py:27-97` | ~70 | `heal_mesh`, `_halfedge_defects` |
| `plate.py:479-563` | ~85 | `_earclip_polygon`, `loft` |
| `geometry.py:202-282` | ~80 | `_orient_closed`, `PolylineLoft` |
| `brep.py:25-164` | ~140 | `_from_mesh`, `mesh_to_brep`, `meshes_to_brep` |
| `scene.py:90-117` | ~28 | `viewmesh` ear-clipping |
| `writer.py:43-64` | ~22 | `triangulated` |
| calls at `plate.py:624`, `column.py:426` | — | `merge_coplanar_faces` |

Plus the `compas_manifold` dependency and the `id(element)` Brep cache in
`model.py:100-141`.

---

## Order of work

Each phase leaves the model working and the examples running. No flag day.

### Phase 0 — safety net (do not skip)

The test suite is **227 lines across 3 files**. That will not catch a geometry
regression. Before touching anything, add a characterization harness: for
`cantilevers_baked_model.json`, record per element the **volume, aabb, obb and
centroid**, plus the **contact count and total contact area** for the model.
Assert against it after every phase.

Since speed is not a constraint, make this harness as strict as it can be:
compare volumes at tight tolerance and fail loudly. It is the only thing that
will tell you a boolean silently changed a part.

### Phase 1 — normalize the seams (no behaviour change)

- Make `.aabb`/`.obb` consistent across all 20 overrides.
- Turn the silent `isinstance` skips at `solid_difference_modifier.py:782,785`
  into raises.
- Fix `PlateElement.compute_contacts:845` to handle Brep operands.
- Delete the dead `compas_cgal` docstring references.

### Phase 2 — Brep backend behind the existing funnels

Add Brep implementations of `_difference_backend` (`:274`) and `_chain_backend`
(`:295`) and switch them over. Mesh in, mesh out at the boundary at first —
convert, boolean in Brep, tessellate back. This is *slower* than today and
that is irrelevant; the point is to prove the boolean results match before any
signature changes. Verify with the Phase 0 harness, then continue.

### Phase 3 — element by element, easiest first

Each gets `geometry_as_brep` per the `schoring_element` template:

1. **`DowelCylinderElement`** (`connectors.py:746`) — one `Cylinder.to_mesh()`
   becomes `Brep.from_cylinder`. 32 elements, 1536 faces → 32 exact solids.
2. **`ConnectorBoxElement`, `ConnectorWedgeElement`** — box and hand-built
   meshes → `Brep.from_box` / `from_polygons`.
3. **`ConnectorCylinderElement`** — n-gon loft → exact cylinder.
4. **`SupportElement`** — already done; delete the OBJ path and the vertex-
   iteration hole detection (`_hole_points:288`) in favour of querying
   cylindrical faces.
5. **`ColumnElement`** — the union/difference at `:61-133`. Highest payoff:
   622 faces → ~30.
6. **`PlateElement`** — the big one. `loft` → `OCCBrep.from_loft`, ear-clipped
   caps → planar faces, cutters → Brep difference. 145 elements.
7. **`OuterRibConnectorElement`** — rebuild from dimensions, or re-author as
   STEP.

`floor_guide.py` needs **no work at all** — 1380 lines of pure polyline and
plane geometry that never touches a Mesh. It inherits whatever `PlateElement`
produces. Only `brep_meshes:135` changes.

### Phase 4 — collapse the boundaries

- `contacts.py:344-347` — `mesh_to_brep` fallback becomes a pass-through.
- `model.py:90-142` — `element_breps()` becomes identity; the 7.9 s and the
  `id(element)` cache both disappear.
- `writer.write_step` takes Breps directly instead of converting.
- Delete `brep.py:25-164`, the `geometry_as_brep` flags, every `_mesh_cache`,
  and the `compas_manifold` dependency.

### Phase 5 — Brep serialization

`bake()` bakes Breps. `element.py:157-162` and `MeshCutFeature.__data__:117`
store Breps. Add the compat read path for legacy mesh JSON and regenerate the
committed models. Expect the baked model to grow by an order of magnitude and
load more slowly; that is the accepted cost of the model carrying exact
geometry rather than an approximation of it.

Cutter features should stop storing geometry at all where they can:
`CylinderCutFeature` (`:165-210`) and `PrismCutFeature` (`:212-`) already keep
parameters (line/radius/sides, two polylines) and derive the cutter on demand.
Push `MeshCutFeature` the same way — a parametric cutter is smaller *and*
exact, which is the one place this migration gets both.

---

## Open questions

1. **Does `compas_rhino` have a Brep scene object registered?** `rhino.py`
   replays a bundle documented as Mesh/Polyline/Polygon/Line. If not,
   `dump_scene` must tessellate on the way out.
2. **Do Brep booleans reproduce the current results** on the awkward cases —
   the lofted twisted-quad ribs and t-sections, where `brep.py`'s volume guard
   exists precisely because near-coplanar merging distorts them? Phase 2
   answers this before any commitment.
3. **Is `PlateElement`'s twisted-quad loft a ruled surface** that
   `OCCBrep.from_loft` produces identically, or does it need `from_sweep`?
   Prototype one rib before Phase 3 step 6.
