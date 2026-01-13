# Plan: Decouple EdgeBeam and ColumnHead from FloorSkeleton

## Goal

Create independent `EdgeBeam` and `ColumnHead` classes that can generate geometry without knowledge of `FloorSkeleton`. The slab class becomes an orchestrator that prepares inputs.

---

## Phase 1: EdgeBeam (Simple - Start Here)

### 1.1 Create `edge_beam.py`

```
src/compas_tf/
├── edge_beam.py   # NEW
```

**Input requirements:**
| Parameter | Type | Source in FloorSkeleton |
|-----------|------|-------------------------|
| `polyline_a` | `Polyline` | `ribs_polylines[q][1]` |
| `polyline_b` | `Polyline` | `ribs_polylines[q][6]` |
| `depth` | `float` | `bb` |

**Class structure:**
```python
class EdgeBeam:
    def __init__(self, polyline_a, polyline_b, depth):
        ...

    @property
    def mesh(self) -> Mesh:
        ...
```

### 1.2 Update FloorSkeleton

Replace `edge_beam_meshes` property:
```python
@property
def edge_beam_meshes(self):
    from compas_tf.edge_beam import EdgeBeam

    connections = [(0, 1), (1, 2), (2, 3), (3, 0)]
    beams = []
    for a, b in connections:
        beam = EdgeBeam(
            self.ribs_polylines[a][1],
            self.ribs_polylines[b][6],
            self.bb
        )
        beams.append(beam.mesh)
    return beams
```

### 1.3 Test EdgeBeam

- Create unit test with two simple polylines
- Verify mesh is watertight
- Compare output with current implementation

---

## Phase 2: ColumnHead (Complex)

### 2.1 Analyze Dependencies

Current `column_heads` method uses:

| Dependency | Type | How Used |
|------------|------|----------|
| `_compute_corner_geometry(q)` | method | Returns points, offset points, planes |
| `pt[fs[q][0]]` | Point | Corner point |
| `fs[q]` | list | Face indices for stop planes |
| `end_planes[q]` | list[Plane] | 4 end planes |
| `ribs_polylines[q-1]` | list[Polyline] | For gap block cutting |
| `bm` | float | Column head height |
| `bb` | float | Boundary beam width |
| `z` | float | Total height |
| `t` | float | Thickness |

### 2.2 Define Input Dataclass

```python
@dataclass
class ColumnHeadInput:
    """Geometry context for one column head."""

    # Corner geometry
    corner_point: Point
    corner_planes: list[Plane]           # 4 planes from _compute_corner_geometry
    corner_points: list[Point]           # 4 points for loft lines
    corner_points_offset: list[Point]    # 4 offset points (inclined)

    # Cutting geometry
    end_planes: list[Plane]              # 4 end planes
    stop_plane_0: Plane                  # Boundary plane 1
    stop_plane_1: Plane                  # Boundary plane 2

    # Gap block cutting (optional - can be None if no gap blocks)
    rib_polylines: list[Polyline] | None  # 8 polylines for gap blocks
```

### 2.3 Define Config Dataclass

```python
@dataclass
class ColumnHeadConfig:
    """Dimensions for column head generation."""
    thickness: float = 40       # t
    boundary_width: float = 250 # bb
    total_height: float = 650   # z
    head_height: float = 50     # bm (derived from parabola)
```

### 2.4 Create `column_head.py`

```
src/compas_tf/
├── column_head.py   # NEW
```

**Class structure:**
```python
class ColumnHead:
    def __init__(self, input: ColumnHeadInput, config: ColumnHeadConfig):
        self.input = input
        self.config = config
        self._main_mesh = None
        self._top_block = None
        self._gap_blocks = None

    @property
    def main_mesh(self) -> Mesh:
        """Main tapered column head solid."""
        if self._main_mesh is None:
            self._main_mesh = self._compute_main_mesh()
        return self._main_mesh

    @property
    def top_block(self) -> Mesh:
        """Top tension block."""
        if self._top_block is None:
            self._top_block = self._compute_top_block()
        return self._top_block

    @property
    def gap_blocks(self) -> list[Mesh]:
        """3 diagonal gap filler blocks."""
        if self._gap_blocks is None:
            self._gap_blocks = self._compute_gap_blocks()
        return self._gap_blocks

    @property
    def all_meshes(self) -> list[Mesh]:
        """All meshes combined."""
        return [self.main_mesh, self.top_block] + self.gap_blocks
```

### 2.5 Extract Methods from FloorSkeleton

Move these code blocks to ColumnHead:

| FloorSkeleton lines | ColumnHead method |
|---------------------|-------------------|
| 552-597 | `_compute_main_mesh()` |
| 600-623 | `_compute_top_block()` |
| 625-654 | `_compute_gap_blocks()` |

### 2.6 Add Builder Method to FloorSkeleton

```python
def _build_column_head_input(self, q: int) -> ColumnHeadInput:
    """Prepare all inputs for column head at quarter q."""
    pts, pts_offset, planes = self._compute_corner_geometry(q)

    return ColumnHeadInput(
        corner_point=self.pt[self.fs[q][0]],
        corner_planes=planes,
        corner_points=pts,
        corner_points_offset=pts_offset,
        end_planes=self.end_planes[q],
        stop_plane_0=Plane(self.pt[self.fs[q][0]],
                          Vector.Zaxis().cross(self.pt[self.fs[q][1]] - self.pt[self.fs[q][0]])),
        stop_plane_1=Plane(self.pt[self.fs[q][0]],
                          Vector.Zaxis().cross(self.pt[self.fs[q][-1]] - self.pt[self.fs[q][0]])),
        rib_polylines=self.ribs_polylines[q-1] if self.ribs_polylines else None,
    )
```

### 2.7 Update FloorSkeleton.column_heads

```python
@property
def column_heads(self):
    from compas_tf.column_head import ColumnHead, ColumnHeadInput, ColumnHeadConfig

    if self._column_heads is None:
        config = ColumnHeadConfig(
            thickness=self.t,
            boundary_width=self.bb,
            total_height=self.z,
            head_height=self.bm,
        )

        self._column_heads = []
        self._column_head_top_blocks = []
        self._column_head_gap_blocks = []
        self._column_centers = []

        for q in range(1, 5):
            input = self._build_column_head_input(q)
            head = ColumnHead(input, config)

            self._column_heads.append(head.main_mesh)
            self._column_head_top_blocks.append(head.top_block)
            self._column_head_gap_blocks.append(head.gap_blocks)
            self._column_centers.append(head.center_point)

    return self._column_heads
```

---

## Phase 3: Testing

### 3.1 Unit Tests for EdgeBeam

```python
def test_edge_beam_simple():
    p0 = Polyline([Point(0,0,0), Point(1,0,0), Point(2,0,0)])
    p1 = Polyline([Point(0,1,0), Point(1,1,0), Point(2,1,0)])
    beam = EdgeBeam(p0, p1, depth=0.5)

    assert beam.mesh is not None
    assert beam.mesh.is_valid()

def test_edge_beam_matches_original():
    # Compare with FloorSkeleton output
    ...
```

### 3.2 Unit Tests for ColumnHead

```python
def test_column_head_main_mesh():
    input = ColumnHeadInput(...)  # Mock data
    config = ColumnHeadConfig()
    head = ColumnHead(input, config)

    assert head.main_mesh is not None
    assert head.main_mesh.is_valid()

def test_column_head_without_gap_blocks():
    input = ColumnHeadInput(..., rib_polylines=None)
    config = ColumnHeadConfig()
    head = ColumnHead(input, config)

    assert head.gap_blocks == []  # Should handle gracefully
```

### 3.3 Integration Test

```python
def test_floor_skeleton_uses_new_classes():
    floor = FloorSkeleton()
    _ = floor.rib_meshes  # Compute ribs first

    # These should now use EdgeBeam and ColumnHead internally
    assert len(floor.edge_beam_meshes) == 4
    assert len(floor.column_heads) == 4
```

---

## Implementation Order

| Step | Task | File | Estimated Complexity |
|------|------|------|---------------------|
| 1 | Create `EdgeBeam` class | `edge_beam.py` | Low |
| 2 | Update `edge_beam_meshes` to use `EdgeBeam` | `slab.py` | Low |
| 3 | Test EdgeBeam | `test_edge_beam.py` | Low |
| 4 | Create `ColumnHeadInput` dataclass | `column_head.py` | Low |
| 5 | Create `ColumnHeadConfig` dataclass | `column_head.py` | Low |
| 6 | Move main mesh logic to `ColumnHead` | `column_head.py` | Medium |
| 7 | Move top block logic to `ColumnHead` | `column_head.py` | Medium |
| 8 | Move gap blocks logic to `ColumnHead` | `column_head.py` | Medium |
| 9 | Add `_build_column_head_input()` | `slab.py` | Medium |
| 10 | Update `column_heads` property | `slab.py` | Low |
| 11 | Test ColumnHead | `test_column_head.py` | Medium |
| 12 | Remove old code from FloorSkeleton | `slab.py` | Low |

---

## File Structure After Refactoring

```
src/compas_tf/
├── __init__.py
├── edge_beam.py        # NEW - EdgeBeam class
├── column_head.py      # NEW - ColumnHead, ColumnHeadInput, ColumnHeadConfig
├── geometry.py         # Existing - PolylineLoft, etc.
├── slab.py             # Simplified - orchestrates EdgeBeam and ColumnHead
├── beam.py
├── plate.py
├── slicer.py
├── slicemodifier.py
├── solid.py
└── solid_difference_modifier.py
```

---

## Success Criteria

1. `EdgeBeam` can create mesh with just two polylines and depth
2. `ColumnHead` can create all meshes with just `ColumnHeadInput` and `ColumnHeadConfig`
3. Both classes have zero imports from `slab.py`
4. `FloorSkeleton` output is identical before/after refactoring
5. All tests pass
6. Lint checks pass
