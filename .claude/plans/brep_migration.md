# Migrating compas_tf solids to Breps (compas_occt)

## Verdict

Go Brep for **solids**, and make `compas_occt` the one geometry kernel — booleans
included. A mesh becomes an **export format**, produced by tessellation at the
moment a file is written and never stored, cached or reasoned about.

Two scope rules, both deliberate:

- **Only solids migrate.** `compas.geometry`'s simple types stay exactly as they
  are: `Polygon`, `Polyline`, `Line`, `Point`, `Plane`, `Frame`, `Box`. Contact
  polygons stay `Polygon`. `floor_guide.py`'s 1380 lines of polyline and plane
  geometry stay untouched. This migration is about the thing an element *is
  made of*, nothing else.
- **Speed is a hard constraint.** The earlier draft of this plan said "speed is
  not a constraint; exactness is the point". That is withdrawn. The model must
  stay fast, and the measurements below show it can — but only after two
  `compas_occt` fixes. Without them the Brep path is 45x slower than mesh and
  the migration should not start.

## The measurements that decide this

All on `data/cantilevers_model.json` (145 plates, 4 columns, 233 elements).
"ruled" is `compas_occt` 0.1.18 as shipped; "planar" is with the `make_face_polygon`
fix below.

| operation | mesh (today) | Brep, ruled | Brep, **planar** |
|---|---|---|---|
| one planar face | — | 2.95 ms | **0.105 ms** (28x) |
| plate loft ×145 | 0.53 s | 4.43 s | **0.62 s** |
| plate loft + cutters ×145 | 0.78 s | 34.90 s | **3.21 s** |
| column (union + 12 cutters) | 0.07 s | 3.80 s | **0.47 s** |
| column face count | 626 | 266 | **229** |
| outer rib face count | 246 | — | **100** |

The "planar" column is measured against a **real built wheel** of
`fix/planar-faces-and-boolean-solids`, through the public `OCCBrep.from_polygons`
API — not a simulation. All 1190 plate faces come back planar and solid; the
carved column is 229/229 planar faces and reproduces the mesh volume to 1.4e-13.

Exactness, against the current mesh volumes:

| part | rel. volume difference |
|---|---|
| inner rib | 2.0e-12 |
| outer rib (4 cutters) | 1.0e-13 |
| t-section | 1.2e-12 |
| column (union + 12 cutters, largest piece) | **1.4e-13** |

So the finished state is **~4x slower than mesh for a one-time bake**, in
exchange for exact geometry and 2.7x fewer faces — not 45x slower. That is a
trade worth making. The 45x version is not.

---

## Two compas_occt bugs block this. Fix them upstream first.

Repo: `petrasvestartas/compas_occt` (currently v0.1.18, C++/nanobind, with a
working `release.yml` that builds wheels on tag push). Bug 1 is in the C++
sources; Bug 2 turned out to be pure Python. Both are fixed on the branch
`fix/planar-faces-and-boolean-solids` (PR #2), which needs a wheel build and a
release before compas_tf can depend on them.

### Bug 1 — `quad_to_face` / `ngon_to_face` build curved surfaces for flat input

`quad_to_face` builds a **ruled (bilinear) surface**; `ngon_to_face` builds a
**best-fit surface**. Every flat quad in this project therefore becomes a
BSpline. This single root cause is behind three separate problems:

1. **Speed.** Face construction is 2.95 ms/face and 76% of all loft time.
   `_occt.make_face_polygon` — a planar face builder already in the bindings —
   does the same job in 0.105 ms, **28x faster**, with zero volume difference
   across all 145 plates.
2. **Booleans.** Cutting BSpline surfaces instead of planes is what makes the
   full plate pipeline 34.9 s. On planar faces it is 3.45 s.
3. **Contact detection.** `contacts.py`'s docstring records the symptom without
   the cause: *"these Breps are built from mesh polygons, so a flat quad comes
   back as a bilinear surface and the planar test drops 529 of the 585 pairs"*.
   With planar faces, `face.is_plane` is true for **229/229** column faces and
   **6/6** plate faces, so that prefilter becomes usable instead of forbidden.

**Fix**: in `meshing.cpp`, test the input points for coplanarity and emit a
planar face (`BRepBuilderAPI_MakeFace` on a `gp_Pln`) when they are coplanar,
falling back to the ruled / best-fit surface only when genuinely twisted. The
fallback will essentially never fire here: measured max deviation of any side
quad from its own plane, across all 145 plates, is **8.5e-11 mm**.

### Bug 2 — boolean results come back as a compound of shells, with no solids

**This one is pure Python — the C++ is correct.** The raw binding output is
right and the Python wrapper then destroys it. Measured on `column_0`:

```
raw _occt.boolean_difference(...)  ->  COMPOUND, 6 SOLID, 6 SHELL   .solids == 6
after the wrapper's sew()+fix()    ->  COMPOUND, 0 SOLID, 6 SHELL   .solids == []
```

`OCCBrep.from_boolean_difference` runs `sew()` + `fix()` + `make_solid()` on a
shape that needs none of them. `sew()` flattens the compound into loose shells,
and `make_solid()` only acts `if self.type == SHELL`, so the compound is
skipped entirely.

That breaks the operation this project cannot do without: the column cut
fragments into 6 pieces, and `largest_piece` has to select the real body from
them. With `.solids` empty there is nothing to select, `.volume` silently
reports 152 358 623 (all fragments) instead of 148 138 552, and `.is_solid` is
False on a shape that is fine.

**Fix**: do not sew or heal an OCCT boolean result — it is already valid — and
unwrap a compound holding exactly one solid to that solid, so `.is_solid` and
`.volume` answer correctly in the common case too. Applies to all six entry
points (`from_boolean_*` and the `boolean_*` methods).

**Verified**: with the fix, the column cut returns all 6 solids and the largest
matches the mesh volume to 1.6e-13. The existing 38-test suite passes unchanged.

### Release plan for compas_occt

Both fixes are on `fix/planar-faces-and-boolean-solids` (PR #2), one commit
each, with regression tests that are confirmed to fail on 0.1.18:

- `tests/test_booleans.py` — a fragmenting cut keeps its pieces as solids
  (fails on 0.1.18 with `assert 0 == 2`), a single-piece result is a solid, a
  union of touching boxes is a solid.
- `tests/test_faces.py` — flat quads / n-gons / triangles are planes, warped
  ones are not, and a box built from its own polygons is an exact planar solid.
  (4 of these fail on 0.1.18.)

CI builds wheels and runs the suite on manylinux, mac-intel, mac-arm and
windows via cibuildwheel. Once green: merge, tag **v0.1.19** to fire
`release.yml`, then pin `compas_occt >= 0.1.19` in compas_tf's
`requirements.txt`. Nothing in compas_tf's migration starts before that release
exists.

**The release also had to un-rot the build.** Nothing had run in CI since
2026-06-28, and three things had broken underneath it in the meantime. None are
related to the two geometry bugs; all three blocked shipping:

1. `cibuildwheel`'s `before-build` installed cmake/ninja into the surrounding
   venv, while scikit-build-core probes cmake from inside pip's *isolated* build
   env. The console script was on PATH but its module was not importable there:
   `Could not determine CMake version via --version ... ModuleNotFoundError: No
   module named 'cmake'`. Moved both into `[build-system].requires`.
2. nanobind now requires Python 3.10+, and cibuildwheel was still building cp39:
   `nanobind requires Python 3.10 or newer (found Python 3.9.21)`.
3. The same loop rebuilt OCCT once per CPython version, five times per platform,
   every run producing the same `cp312-abi3` wheel and overwriting the last. The
   project ships a single stable-ABI wheel (`wheel.py-api = "cp312"`), so the
   build is now restricted to `cp312-*` — which fixes (2) and cuts CI ~5x.

Note for local development: building compas_occt from source on this machine
fails in OCCT's Visualization module with `fatal error: X11/Xlib.h: No such file
or directory`. Install `libx11-dev` to build locally; CI images already have it.
Until then the C++ half of Bug 1 can only be verified in CI — the algorithm
itself was validated by porting it to Python and running it over all 1190 faces
of the real model.

---

## One live bug in compas_tf, independent of any of this

`plate.py:750` and `support.py:227` read `self.modelgeometry.obb` **without
calling it**. `Mesh.obb` is a method, so `compute_obb` stores a bound method in
`self._obb` and returns it; with `inflate != 1.0` it raises
`AttributeError: 'function' object has no attribute 'xsize'`. Every other
override in the codebase calls `.obb()`.

This matters for sequencing, because the migration **flips which form is
correct**: `OCCBrep.aabb` / `.obb` / `.volume` / `.centroid` are *properties*,
while `Mesh.aabb()` / `.obb()` / `.volume()` / `.centroid()` are *methods*. Every
one of the ~20 call sites changes call form. Fix the two broken ones first, in
isolation, so the audit starts from a consistent baseline.

Call sites to convert: `plate.py:741,750`, `plate.py:875` (`centroid()`),
`support.py:218,227`, `connectors.py:162,171,290,299,687,696,753,762,1238,1247`,
`tower_element.py:87,95`, `schoring_element.py:256,305,325`.

---

## What the framework already gives us

- **`compas_model` accepts Breps.** `compute_elementgeometry` is typed
  `Union[Brep, Mesh]`. No framework to fight.
- **The BVH is geometry-agnostic.** `ElementAABBNode`/`ElementOBBNode` read
  `element.aabb` / `element.obb`, which route to each element's own
  `compute_aabb`/`compute_obb`. `contacts.py`'s claim that *"Breps cannot simply
  be put on the elements — `compute_aabb` and the BVH are Mesh-only"* is
  **stale**; only the call form needs fixing (above).
- **`base_model._aabb` already branches on Mesh vs Brep** (`base_model.py:59-71`).
- **compas_occt ships its own viewer scene object** (`OCCBrepObject`), so
  `viewer.scene.add(occbrep)` works today. Blocker "compas_viewer" from the
  earlier draft mostly dissolves: `scene.py`'s `viewmesh` ear-clipping and
  seam-suppression exist only to clean up mesh-boolean debris, which Breps do
  not produce. Watch one thing: `OCCBrepObject` tessellates at
  `TOL.lineardeflection` (0.001 mm), which `contacts.py` measured at 200 s for
  the whole model. Viewer tessellation deflection must be loosened.
- **`schoring_element.py` is the transition template** — `geometry_as_brep` flag,
  separate caches, `Union[Mesh, Brep]` return. Copy it per element, then delete
  the mesh half. It is scaffolding, not the end state.

---

## Contact detection

Already Brep-based and already **faster than mesh**: `contacts.py` records one
column/rib joint at 1 contact / full area in ~0.2 s, against 8 fragmented
contacts / 50 344 mm² instead of 62 632 mm² in ~13 s for the mesh path. So this
part of the migration *removes* work rather than adding it.

What changes:

1. `BrepContacts.brep()` (`contacts.py:330`) stops converting and returns
   `element.modelgeometry` directly. The `id(element)` Brep cache and the
   ~55 ms/element conversion both disappear.
2. `prepare_faces` keeps its boundary-AABB + opposite-normal prefilter, and
   **gains** the `face.is_plane` filter that Bug 1 currently forbids. The
   module docstring's standing warning —

   > *Do not narrow the prefilter to `face.is_plane`: these Breps are built from
   > mesh polygons, so a flat quad comes back as a bilinear surface and the
   > planar test drops 529 of the 585 pairs.*

   — is **obsolete as of the fix, and verified so**. Running
   `compute_contacts_brep` on `cantilever_model.json` against a real built wheel
   of the fix: **354/354 faces planar**, 128 contacts, 0 face-pair errors, 1.24 s.

   Be precise about what this buys, though. The filter was *unsafe* before — it
   discarded 529 of 585 real pairs because flat quads were bilinear surfaces —
   and it is now *safe*. That is a correctness unlock, not automatically a
   speedup: on a model whose faces are all planar it skips nothing and costs one
   check per face. It pays off only where genuinely curved faces exist to skip —
   the dowels, drillings and connector cylinders — which is exactly the geometry
   `involving(DowelCylinderElement, ConnectorCylinderElement)` currently has to
   exclude by hand. Measure it there before claiming a win.
3. `model.element_breps()` (`model.py:90-142`) becomes identity — this is where
   the 7.9 s whole-model conversion on every export goes away.
4. `PlateElement.compute_contacts:845` — `isinstance(other.modelgeometry, Mesh)`
   else `NotImplementedError`. A Brep neighbour **raises today**. Must be fixed
   before any element a plate touches becomes Brep-backed.
5. Keep `contact.polygon` a `compas.geometry.Polygon`. Contacts are not solids.

---

## Booleans: what replaces compas_manifold

`compas_manifold` is 9 call sites in 2 modules — narrow, and two of them are
funnels everything else flows through:

- `column.py:61,67` — capitel union → `OCCBrep.from_boolean_union`
- `column.py:123,129,132` — cutter union + difference → `from_boolean_difference`
- `solid_difference_modifier.py:128,141,144` — `MeshCutFeature.apply`
- `solid_difference_modifier.py:274,295` — `_difference_backend` / `_chain_backend`

`compas_cgal` appears in zero code, only stale docstrings — delete on sight.

Two behaviours must survive the swap:

- **`largest_piece`.** Both kernels fragment the column cut (mesh: 4 solids,
  1 kept, 4.29e6 mm³ discarded; Brep: 6 solids, same body kept). This is what
  Bug 2 breaks, and it is not optional.
- **Origin-shifting.** `MeshCutFeature.apply:134` translates operands to the
  origin because Manifold's merge tolerance scales with bounding-box magnitude.
  OCCT uses an absolute tolerance instead, so re-measure whether this is still
  needed rather than porting it blindly.

---

## What gets deleted

Roughly **600 lines** that exist only because booleans produce triangle soup:

| location | lines | what |
|---|---|---|
| `solid_difference_modifier.py:301-560` | ~260 | triangulate → boolean → re-merge-into-ngons |
| `solid_difference_modifier.py:27-97` | ~70 | `heal_mesh`, `_halfedge_defects` |
| `plate.py:479-563` | ~85 | `_earclip_polygon`, `loft` |
| `geometry.py:202-282` | ~80 | `_orient_closed`, `PolylineLoft` |
| `brep.py:25-164` | ~140 | `_from_mesh`, `mesh_to_brep`, `meshes_to_brep` |
| `scene.py:90-117` | ~28 | `viewmesh` ear-clipping |
| `writer.py:43-64` | ~22 | `triangulated` |
| `plate.py:624`, `column.py:426` | — | `merge_coplanar_faces` calls |

Plus the `compas_manifold` dependency and the `id(element)` cache in
`model.py:100-141`.

Note `brep.py`'s `VOLUME_TOLERANCE` guard goes with it. It was written to stop
`simplify()` flattening "twisted quads" — geometry this project does not have
(max twist 8.5e-11 mm). Once faces are planar by construction there is nothing
to guard.

---

## Order of work

Each phase leaves the model working and the examples running. No flag day.

### Phase 0 — compas_occt v0.1.19

Both bugs above, with regression tests, built and released. Pin it. Nothing else
starts first.

### Phase 1 — safety net

The test suite is 227 lines across 3 files and will not catch a geometry
regression. Add a characterization harness over `cantilevers_baked_model.json`:
per element **volume, aabb, obb, centroid**; per model **contact count and total
contact area**; and **wall-clock per phase**, since speed is now a constraint
and a regression in it is a failure like any other. Assert after every phase.

### Phase 2 — normalize the seams (no behaviour change)

- Fix the two `.obb` bugs; make aabb/obb/volume/centroid call form consistent.
- Turn the silent `isinstance` skips at `solid_difference_modifier.py:782,785`
  into raises — they currently *skip the cut and print a warning* for a Brep,
  which during a partial migration means quietly not carving.
- Fix `PlateElement.compute_contacts:845` to accept Brep operands.
- Delete the dead `compas_cgal` docstring references.

### Phase 3 — Brep backend behind the existing funnels

Swap `_difference_backend` / `_chain_backend` to OCCT, mesh-in/mesh-out at the
boundary at first. Slower than the end state and that is fine — the point is to
prove boolean results match before any signature changes. Verify with Phase 1.

### Phase 4 — element by element, easiest first

Each gets `geometry_as_brep` per the `schoring_element` template:

1. `DowelCylinderElement` — `Cylinder.to_mesh()` → `Brep.from_cylinder`.
   32 elements, 1536 faces → 32 exact solids with real cylindrical holes.
2. `ConnectorBoxElement`, `ConnectorWedgeElement` → `from_box` / `from_polygons`.
3. `ConnectorCylinderElement` — n-gon loft → exact cylinder.
4. `SupportElement` — delete the OBJ path and the vertex-iteration
   `_hole_points:288` in favour of querying cylindrical faces.
5. `ColumnElement` — union + difference. Measured: 0.48 s, 626 → 229 faces,
   volume exact to 1.4e-13.
6. `PlateElement` — the bulk. Loft from two polylines as planar side quads plus
   two planar caps. Measured across all 145: exact, zero failures, 3.45 s.
   **It also repairs 24 broken parts**: the t-sections' mesh loft is an open,
   non-manifold 38-face shape whose 14-gon caps ear-clipping never closes. The
   Brep is a clean 16-face solid.
7. `OuterRibConnectorElement` — rebuild from dimensions, or re-author once as
   STEP. Do not keep `mesh_to_brep` alive for one part.

### Phase 5 — the examples and the part list

**Only 3 of 35 examples touch Breps today** — `_18` (write STEP), `_20` (read
STEP), `_22` (contact adjacency). Everything that *builds* the model (`_1`..`_11`)
and **all 14 `example_model_12_fab_*` part-list scripts** are pure mesh. They are
the tutorials, and `docs/fabrication.md` is generated from what they write.

Each fab script has one shape — pull an element, pull its cutters,
`write_parts([uncut, cut] + cutters, ...)` — so it is the same edit 14 times:

- `compute_elementgeometry(types=[...])` and `.elementgeometry` return Breps, so
  `uncut` / `cut` need no conversion.
- `feature.meshes` becomes `feature.solids`; `.transformed(xform)` is unchanged.
- `write_parts` takes Breps; `write_step` stops converting and passes them
  straight through. This is where exactness finally reaches the shop files.
- `preview=` still tessellates, via `writer._as_mesh`.

Start with `example_model_12_fab_column.py` — smallest, and the column is
Phase 4 step 5. Then regenerate `docs/fabrication.md` via
`tools/print_part_table.py`; expect small dimension changes where a faceted
cylinder was measured before.

### Phase 6 — collapse the boundaries

- `contacts.py:344-347` — conversion becomes a pass-through.
- `model.py:90-142` — `element_breps()` becomes identity; the 7.9 s export
  conversion and the `id(element)` cache disappear.
- Delete `brep.py:25-164`, every `geometry_as_brep` flag and `_mesh_cache`, and
  the `compas_manifold` dependency.
- Loosen the viewer's tessellation deflection off `TOL.lineardeflection`.

### Phase 7 — Brep serialization

`bake()` bakes Breps. `element.py:157-162` and `MeshCutFeature.__data__:117`
store Breps. Add a compat read path so existing mesh JSON on disk keeps loading
(this is a read-side branch, not a migration script), then regenerate the
committed models.

A Brep serializes to roughly 12x the JSON of the equivalent mesh (170 KB vs
14 KB for the Sherpa connector), so the baked model grows from ~4 MB to tens of
MB. **Measure load time against the Phase 1 harness before accepting this.**
Given the speed constraint, the mitigation is to store parameters rather than
geometry wherever possible: `CylinderCutFeature` and `PrismCutFeature` already
keep line/radius/sides and two polylines and derive their cutter on demand. Push
`MeshCutFeature` the same way — parametric is smaller *and* exact.

---

## Open questions

1. **Does `compas_rhino` register a Brep scene object?** `rhino.py` replays a
   bundle documented as Mesh/Polyline/Polygon/Line. If not, `dump_scene`
   tessellates on the way out.
2. **How far does the column's face count actually fall?** Measured 229, against
   626 for mesh. The remaining count comes from cutters built from *meshes*;
   building them parametrically as Breps should reduce it further, but that is
   unmeasured.
3. **Is the origin-shift in `MeshCutFeature.apply` still needed** under OCCT's
   absolute tolerance? Measure, do not port blindly.
4. ~~**Is `PlateElement`'s twisted-quad loft a ruled surface?**~~ **Answered: no.**
   Max twist 8.5e-11 mm across all 145 plates. Planar faces reproduce every one.
5. ~~**Do Brep booleans reproduce the current cut results?**~~ **Answered: yes.**
   Column exact to 1.4e-13, outer rib to 1.0e-13, zero failures across 145
   plates — *given* Bug 2 is fixed so `largest_piece` can select the body.
