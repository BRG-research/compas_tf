# Decoupling Column Head Geometry from FloorSkeleton

## Problem Statement

The `column_heads` property in `floor_skeleton.py` (lines 813-936) is tightly coupled to the `FloorSkeleton` class. The goal is to create a standalone `ColumnHead` geometry class that can generate column head meshes without needing access to `FloorSkeleton` internals.

---

## Current Architecture Analysis

### Column Head Geometry Components

The column head consists of **3 mesh types** per corner (4 corners total):

1. **Main column head mesh** (`_column_heads`) - A tapered solid from top to bottom
2. **Top block mesh** (`_column_head_top_blocks`) - Tension block at top
3. **Gap block meshes** (`_column_head_gap_blocks`) - 3 diagonal filler blocks per corner

### Dependency Graph

```
column_heads property
├── _compute_corner_geometry(q)
│   ├── axes[q]          → requires boundary_parabolas → requires ms, t
│   └── t (thickness)
├── bm (column head height) → derived from boundary_parabolas
├── bb (boundary beam width)
├── z (total height)
├── pt (top points)
├── fs (face indices)
├── end_planes[q]
│   ├── rib_parabolas[q]
│   └── axis_boundary_planes
├── ribs_polylines[q-1]  → ⚠️ CRITICAL: computed by rib_meshes property
└── utility methods:
    ├── loft_polylines()
    ├── loft_multiple_polylines()
    ├── cut_polyline_plane()
    └── intersect_consecutive_planes_with_xy()
```

### Key Observations

1. **Circular dependency**: `column_heads` needs `ribs_polylines`, which is populated by `rib_meshes` property
2. **Deep coupling**: Many geometric parameters flow from top-level dimensions through several transformations
3. **Utility methods**: Reusable lofting/cutting methods should be extracted

---

## Proposed Solution

### Option A: Pure Geometry Input (Recommended)

Create `ColumnHeadGeometry` class that takes pre-computed geometric primitives:

```python
class ColumnHeadGeometry:
    def __init__(
        self,
        corner_point: Point,           # self.pt[self.fs[q][0]]
        axis_directions: list[Vector], # 4 vectors from axes[q]
        axis_start_points: list[Point],# 4 points from axes[q]
        end_planes: list[Plane],       # 4 end planes
        rib_polylines: list[Polyline], # 8 rib polylines for gap blocks
        stop_planes: tuple[Plane, Plane], # boundary planes
        # Dimensions
        thickness: float,              # self.t
        boundary_beam_width: float,    # self.bb
        total_height: float,           # self.z
        column_head_height: float,     # self.bm
    ):
        ...
```

**Pros:**
- Complete decoupling from FloorSkeleton
- Testable in isolation
- Can be used with any geometric input

**Cons:**
- Requires FloorSkeleton to prepare many parameters

### Option B: Configuration + Frame-based Input

Create `ColumnHeadGeometry` that takes a Frame (position/orientation) and configuration:

```python
@dataclass
class ColumnHeadConfig:
    thickness: float = 40
    boundary_beam_width: float = 250
    total_height: float = 650
    taper_ratio: float = 0.99
    angle_inclination: float = 180
    scale: float = 460

class ColumnHeadGeometry:
    def __init__(
        self,
        frame: Frame,                  # Position and orientation
        config: ColumnHeadConfig,
        # Minimal geometric context
        axis_lines: list[Line],        # 4 axis lines at corner
        end_planes: list[Plane],       # 4 end planes
        rib_outlines: list[Polyline],  # For gap block cutting
    ):
        ...
```

**Pros:**
- Cleaner API
- Configuration reusable across corners

**Cons:**
- Still needs some FloorSkeleton geometry

### Option C: Factory Pattern with Minimal Interface

```python
class ColumnHeadFactory:
    """Creates column head geometry from minimal interface."""

    @staticmethod
    def from_corner_axes(
        corner: Point,
        axis_lines: list[Line],  # 4 lines radiating from corner
        height_params: HeightParams,
        rib_cutting_planes: list[Plane],
    ) -> ColumnHeadMeshes:
        ...
```

---

## Recommended Implementation Plan

### Phase 1: Extract Utility Methods

Move reusable geometry utilities to a separate module:

```
src/compas_tf/
├── geometry_utils.py   # NEW
│   ├── loft_polylines()
│   ├── loft_multiple_polylines()
│   ├── cut_polyline_plane()
│   ├── offset_polyline()
│   └── intersect_consecutive_planes_with_xy()
```

### Phase 2: Create ColumnHeadGeometry Class

```
src/compas_tf/
├── column_head_geometry.py   # NEW
│   └── class ColumnHeadGeometry
│       ├── __init__(frame, config, axis_context)
│       ├── compute_main_mesh() -> Mesh
│       ├── compute_top_block() -> Mesh
│       ├── compute_gap_blocks() -> list[Mesh]
│       └── property: all_meshes -> list[Mesh]
```

### Phase 3: Define Minimal Input Interface

```python
@dataclass
class ColumnHeadContext:
    """All geometric context needed for one column head."""
    corner_point: Point
    axis_lines: list[Line]           # 4 lines from corner
    end_planes: list[Plane]          # 4 cutting planes
    rib_cut_polylines: list[Polyline] # 8 polylines for gap blocks
    stop_plane_0: Plane              # Boundary plane 1
    stop_plane_1: Plane              # Boundary plane 2
```

### Phase 4: Update FloorSkeleton

```python
class FloorSkeleton:
    def _build_column_head_context(self, q: int) -> ColumnHeadContext:
        """Prepare context for column head geometry."""
        ...

    @property
    def column_heads(self):
        contexts = [self._build_column_head_context(q) for q in range(1, 5)]
        config = ColumnHeadConfig(t=self.t, bb=self.bb, z=self.z, bm=self.bm)

        for ctx in contexts:
            geom = ColumnHeadGeometry(ctx, config)
            self._column_heads.append(geom.main_mesh)
            self._column_head_top_blocks.append(geom.top_block)
            self._column_head_gap_blocks.append(geom.gap_blocks)
```

---

## Detailed Dependencies to Extract

### 1. Core Dimensions (Simple)
| Parameter | Source | Description |
|-----------|--------|-------------|
| `t` | FloorSkeleton.t | Beam thickness (40) |
| `bb` | FloorSkeleton.bb | Boundary beam width (250) |
| `z` | FloorSkeleton.z | Total floor height (650) |
| `bm` | FloorSkeleton.bm | Column head mid-height (derived) |

### 2. Corner Geometry (Moderate)
| Parameter | Source | How to Extract |
|-----------|--------|----------------|
| `corner_point` | `pt[fs[q][0]]` | Direct point access |
| `axis_lines` | `axes[q][0:4]` | 4 Line objects |
| `intersection` | `intersection_line_line(axes[0], axes[-1])` | Compute in context builder |

### 3. Planes (Complex)
| Parameter | Source | Dependencies |
|-----------|--------|--------------|
| `end_planes[q]` | end_planes property | rib_parabolas, axis_boundary_planes |
| `stop_plane_0` | Derived from `fs` points | pt, fs |
| `stop_plane_1` | Derived from `fs` points | pt, fs |

### 4. Rib Polylines (Critical Coupling)
| Parameter | Source | Issue |
|-----------|--------|-------|
| `ribs_polylines[q-1]` | Computed by `rib_meshes` | Must be computed first |

**Solution**: Pass polylines as input, or compute rib outline bounds separately.

---

## Files to Create/Modify

### New Files
1. `src/compas_tf/geometry_utils.py` - Utility functions
2. `src/compas_tf/column_head_geometry.py` - ColumnHeadGeometry class

### Modified Files
1. `src/compas_tf/floor_skeleton.py` - Use new classes, remove embedded logic

---

## Testing Strategy

1. **Unit tests for geometry_utils.py**
   - Test lofting with known polylines
   - Test plane cutting edge cases

2. **Unit tests for ColumnHeadGeometry**
   - Create mock context with known geometry
   - Verify mesh vertex/face counts
   - Verify mesh is watertight

3. **Integration test**
   - Compare output with current FloorSkeleton.column_heads
   - Ensure visual equivalence

---

## Open Questions

1. Should `bm` (column head height) be computed from parabola or passed as config?
2. Should gap blocks be optional? They depend heavily on rib geometry.
3. Consider splitting into `ColumnHeadMain` and `ColumnHeadBlocks` classes?

---

## Next Steps

1. [ ] Create `geometry_utils.py` with extracted methods
2. [ ] Create `ColumnHeadContext` dataclass
3. [ ] Create `ColumnHeadConfig` dataclass
4. [ ] Implement `ColumnHeadGeometry` class
5. [ ] Add `_build_column_head_context()` to FloorSkeleton
6. [ ] Update `column_heads` property to use new class
7. [ ] Write tests
8. [ ] Remove dead code from FloorSkeleton
