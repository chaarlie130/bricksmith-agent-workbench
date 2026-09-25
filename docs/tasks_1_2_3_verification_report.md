# Verification & Review Remediation Report: Phase 3 Modular Generation & Kinematics

**Date:** September 24, 2026  
**Status:** All Senior Reviewer Findings Addressed & Fully Verified  
**Test Suite:** 31/31 Passing Tests (`PYTHONPATH=. .venv/bin/python3 -m unittest discover -s tests`)  
**Data Integrity:** 792/792 Training & Validation Examples Migrated to Codec V2 (100% Roundtrip Verified)

---

## 1. Executive Summary

Following the comprehensive review of Phase 3 (Modular BFS Neural Generation and Kinematic Reconstruction), we conducted an in-depth overhaul of the tokenization codec, kinematics solver, dataset formatting pipeline, and physical support filters. Every identified architectural gap and potential failure mode has been systematically eliminated without procedural fallbacks, continuous coordinate approximations, or synthetic shortcuts.

| Review Finding | Root Cause | Remediation | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **1. Port Namespace Collision & Dataset Breakage** | Allocating codes `500–999` to `iface_*` in v1 broke physical ports $\ge 500$ (e.g. `port_528` in baseplates) and silently reinterpreted existing examples. | Created **Codec V2** with unambiguous `00002` sentinel header and 5-digit port table entries (`kind:1`, `index:04d`). Physical ports (`kind=3`) and interface ports (`kind=4`) are completely orthogonal up to index 9999. Migrated 792 dataset records. Maintained full backward compatibility for v1 payloads. | `test_versioned_codec_namespaces_and_headers`, `test_legacy_v1_compatibility`, and `scripts/migrate_dataset_v2.py` (792/792 migrated with 0 errors). |
| **2. Interface Rotation Disappearance** | Serializer forced `quarters = 0` on every node with `parent_step_index is None`, wiping out yaw rotation for interface roots. | Serialized exact `rotation_quarters` (`0, 1, 2, 3`) for all root nodes and interface connections: `quarters = int(getattr(node, "rotation_quarters", 0)) % 4`. | `test_interface_rotations_preserved_across_all_quarters` verifying roundtrip persistence of quarters 0, 1, 2, and 3. |
| **3. Silent Kinematic Failures (`except: pass`)** | Kinematics decoder silently caught all exceptions (`except Exception: pass`) and defaulted to identity transforms at $(0,0,0)$. | Removed all `except: pass` blocks. Implemented fail-loudly semantics: raises `IndexError` on out-of-range port indices, `ValueError` on missing interface assemblies/ports, and `KeyError` on unknown stems. Added canonical stem alias resolution and pattern variant stripping. | `test_kinematics_fail_loudly` confirming explicit exceptions on bad port indices, missing interface assemblies, and unresolvable stems. |
| **4. Incomplete Cross-Bag Pipeline Integration** | Manifests were not wired into `format_dataset.py`, `assemble.py` lacked base assembly conditioning, and multi-bag integration lacked realistic nonzero-rotation tests. | Connected `CrossBagConnection` manifests into `format_dataset.py` with multi-bag assembly accumulation; updated `assemble.py` to condition on `base_assembly`; added comprehensive multi-bag partitioned test with multiple roots and nonzero rotations. | `test_real_partition_tokens_nonzero_rotation_merged_cad` decoding Bag 2 from tokens alone, merging into full CAD, and verifying HiGHS LP static equilibrium and zero collisions. |
| **5. Permissive Support Filter Adjacency Fallback** | `_is_supported` allowed mid-air floating cantilevers if their bounding box touched a parent bounding box. | Eliminated unconditional bounding box adjacency fallback. Evaluated true center of mass from `world_properties` and verified support strictly against the 2D convex hull of lower contact patches via Delaunay triangulation. | `test_rigorous_support_filter` confirming that side-adjacent floating overhangs return `False` while running bonds and stacked columns return `True`. |

---

## 2. Technical Details & Implementation

### 2.1 Review Finding 1: Versioned Codec V2 & Distinct Port Namespaces

#### The Problem
In the initial interface implementation, `port_code` allocated codes `0..499` to `port_{idx}` and `500..999` to `iface_{idx}`. This introduced two critical bugs:
1. Physical parts with $\ge 500$ ports (such as 32x32 baseplate `3811` with `port_528`) raised `TokenizationError: port index does not fit in allocated range: port_528`.
2. Existing training examples that referenced physical ports $\ge 500$ were silently reinterpreted as interface ports during parsing.

#### The Architecture of Codec V2
To resolve this cleanly and provide permanent scalability:
1. **Sentinel V2 Header:** In V1, the token stream starts with `n_parts` (a 3-digit number $\ge 1$). Thus, any string starting with `000` is impossible in V1. We defined `00002` (`000` sentinel + `02` version) as the V2 file header.
2. **Orthogonal 5-Digit Port Table:** In V2, each entry in the header port table is encoded as 5 digits: `f"{kind:01d}{index:04d}"`:
   - `kind = 3`: Physical port (`port_0` .. `port_9999`).
   - `kind = 4`: Interface port (`iface_0` .. `iface_9999`).
   - `kind = 0`: Root / None port (`00000`).
3. **Dataset Migration:** Created `scripts/migrate_dataset_v2.py`. Migrated all 688 records in `data/training/train.jsonl` and 104 records in `data/training/val.jsonl` to V2. Every record was re-parsed and roundtripped against its original assembly graph to guarantee 100% data integrity.
4. **V1 Backward Compatibility:** Kept `port_name_v1` and `port_code_v1` active in `parse_attachment_digits` for legacy streams not starting with `00002`.

```python
# Codec V2 Port Table Entry Serialization
def port_to_v2_entry(port_name: Optional[str]) -> str:
    if port_name is None:
        return "00000"
    if port_name.startswith("port_"):
        idx = int(port_name[5:])
        return f"3{idx:04d}"
    if port_name.startswith("iface_"):
        idx = int(port_name[6:])
        return f"4{idx:04d}"
    raise TokenizationError(f"unsupported port name format: {port_name}")
```

---

### 2.2 Review Finding 2: Root & Interface Rotations in Serialization

#### The Problem
In `serialize_tree()`, the tail token packed connection type and rotation quarters:
```python
# Previous buggy line:
quarters = 0 if node.parent_step_index is None else (node.rotation_quarters % 4)
```
This forced `quarters = 0` on every root node. When a modular bag connected to an interface stud with a 90°, 180°, or 270° orientation relative to the parent bag, the rotation was zeroed out during serialization.

#### The Solution
Updated `serialize_tree()` to preserve `rotation_quarters` for root and interface nodes:
```python
quarters = int(getattr(node, "rotation_quarters", 0)) % 4
tail = _pack_tail(conn, quarters)
```
In `parse_attachment_digits()`, the unpacked `quarters` is assigned directly to the `TreeNode`. This ensures full angular fidelity across both intra-bag and cross-bag attachments.

---

### 2.3 Review Finding 3: Fail-Loudly Kinematic Reconstruction

#### The Problem
In `BFSTreeCodec.decode()`, kinematic reconstruction wrapped port frame evaluations in:
```python
except Exception:
    pass
```
If a port index was invalid, an interface port was missing, or a stem was unrecognized, the exception was silently swallowed. The child piece was left with `transform = np.eye(4)`, placing it at the world origin $(0,0,0)$ and causing invisible corruptions during inference and evaluation.

#### The Solution
1. **Removed all `except: pass`**: Every kinematic attachment step must succeed or fail loudly with a descriptive exception.
2. **Explicit Error Types**:
   - `IndexError`: Raised when a port index exceeds catalog bounds or interface spec list lengths (`port_99999` or out-of-range interface index).
   - `ValueError`: Raised when a node specifies an interface attachment (`iface_K`) but `interface_assembly` / `interface_ports` is `None`, or when parent steps are un-decoded.
   - `KeyError`: Raised when a stem cannot be resolved in the brick catalog.
3. **Canonical Stem Resolution**: Implemented `_stem_numeric()` to automatically resolve LDraw alias variants (e.g. `3023` $\rightarrow$ `3023b`) via `load_aliases()` and strip printed pattern suffixes (e.g. `bl_54200pb103` $\rightarrow$ `54200`), preventing false `KeyError`s on legitimate parts while strictly failing on unknown geometry.

---

### 2.4 Review Finding 4: Cross-Bag Pipeline Metadata Integration

#### The Problem
1. `format_dataset.py` lacked support for accumulating assemblies across multi-bag models, preventing proper interface port indexing during dataset preparation.
2. `assemble.py` (`generate_guided_assembly`) did not accept an existing `base_assembly`, making it impossible to sequentially generate Bag $N$ conditioned on Bag $N-1$.
3. Prior tests only verified identity-rotation single-root reconstructions.

#### The Solution
1. **Dataset Pipeline Integration**: Updated `example_text()` in `format_dataset.py` to accept `interface_assembly` and `interface_ports`. Updated `iter_bag_examples()` to maintain an accumulated base assembly using `merge_assemblies()` as it steps through bags.
2. **Inference Pipeline Integration**: Updated `generate_guided_assembly()` in `assemble.py` to accept an optional `base_assembly: Optional[AssemblyGraph]`. When provided:
   - Available interface ports are derived via `get_available_interface_ports(base_assembly)`.
   - Interface connection candidate actions are populated via `_interface_actions()`.
   - The decoded bag is merged onto the base assembly via `merge_assemblies()`.
3. **Multi-Bag Integration Test**: Built `test_real_partition_tokens_nonzero_rotation_merged_cad` in `tests/test_codec_v2.py`:
   - **Bag 1 (Foundation)**: 4x4 baseplate (`3031`) grounded at $Y=8$ with a 1x2 brick (`3004`).
   - **Bag 2 (Structure)**: Two separate 1x1 bricks (`3005`), forming **multiple roots**:
     - Root 1 attached to Brick 2 stud 4 with **90° yaw rotation** (`quarters = 1`).
     - Root 2 attached to Baseplate 1 stud 26 with **180° yaw rotation** (`quarters = 2`).
   - **Verification**: Bag 2 was serialized to pure V2 digit tokens (`00002...`), parsed back, and decoded from tokens alone using Bag 1.
   - **Physics & CAD Validation**: Decoded poses matched ground truth with $< 10^{-6}$ error. Merged assembly passed all CAD checks: `actual_connectivity = True`, `mesh_collision_free = True`, `included_base = True`, and `approximate_gravity_equilibrium = True` (HiGHS LP compressive static equilibrium).

---

### 2.5 Review Finding 5: Rigorous Physical Support Filter

#### The Problem
In `bricksmith/generation/assemble.py`, `_is_supported()` contained a dangerous fallback:
```python
# Buggy fallback:
if np.all(child.bounds_min < parent.bounds_max + 1.0) and np.all(child.bounds_max > parent.bounds_min - 1.0):
    return True
```
This check returned `True` as long as the child's bounding box intersected a parent's bounding box in 3D. A brick placed side-by-side with a parent in mid-air (with zero vertical overlap or support underneath) was approved as "supported", leading to floating overhangs.

#### The Solution
1. **Eliminated Bounding Box Fallback**: Removed the unconditional adjacency check.
2. **Physical Center of Mass**: Calculated the exact center of mass for the child part using `world_properties(child.part_id, child.transform)`.
3. **Contact Polygon & Convex Hull**:
   - Identified all placed parts directly beneath the child whose top surface aligns with the child's bottom surface ($\Delta Y \le 0.5$ LDU).
   - Computed the horizontal $(X, Z)$ contact patch for each supporting part.
   - Used `scipy.spatial.Delaunay` on the aggregate lower contact polygon corners to test if the child's 2D $(X, Z)$ center of mass lies strictly inside the convex hull.
4. **Behavioral Verification**:
   - Multi-column running bonds: **Approved** (`True`).
   - Stacked columns: **Approved** (`True`).
   - Side-adjacent mid-air overhangs: **Strictly Rejected** (`False`).
   - Cantilever with unsupported center of mass: **Strictly Rejected** (`False`).

---

### 2.6 Documentation Alignment

In `docs/ARCHITECTURE.md` and `docs/ROADMAP.md`, references to vertical insertion clearance and monotonic assembly trajectories were clarified:
- Vertical insertion clearance and collision-free monotonic assembly sequence checks are reserved for **Phase 4** (Production Pipeline / Step-by-Step Assembly Instructions).
- The current Phase 3 validator focuses on static CAD correctness: syntax, scope, non-penetration mesh collisions, graph connectivity, and HiGHS LP static gravity equilibrium.

---

## 3. Test Suite Verification Summary

Running the complete test suite verifies 31 passing unit tests across all modules:

```bash
PYTHONPATH=. .venv/bin/python3 -m unittest discover -s tests
```

```text
Ran 31 tests in 2.896s
OK
```

### Detailed Breakdown of Key Test Cases
- `tests/test_codec_v2.py`:
  - `test_versioned_codec_namespaces_and_headers`: Confirms V2 prefix `00002` and 5-digit orthogonal table encoding (`kind=3` for physical, `kind=4` for interface).
  - `test_legacy_v1_compatibility`: Confirms that V1 legacy payloads without `00002` decode physical ports $0..996$ without reinterpretation.
  - `test_interface_rotations_preserved_across_all_quarters`: Confirms persistence of rotation quarters 0, 1, 2, and 3 across token serialization and parsing.
  - `test_kinematics_fail_loudly`: Confirms fail-loudly exceptions (`IndexError`, `ValueError`, `KeyError`) when encountering invalid ports, missing interfaces, or unresolvable stems.
  - `test_real_partition_tokens_nonzero_rotation_merged_cad`: Complete multi-bag pipeline test with multiple roots, nonzero rotations, token decoding, and full CAD physics validation.
  - `test_rigorous_support_filter`: Confirms strict rejection of floating side-adjacent bricks and acceptance of structurally sound running bonds.
- `tests/test_modularizer.py`: Tests modular partition graph splitting and cross-bag connection manifests.
- `tests/test_training_format.py`: Verifies shared conditioning prompt format between training and inference.
- `tests/test_physics.py`: Verifies mesh collisions, connectivity, and HiGHS LP static equilibrium solver.

---

## 4. Conclusion & Readiness

All 5 review findings have been resolved, verified, and committed. The BrickSmith generation, tokenization, and kinematic reconstruction engine is now mathematically sound, fully backwards-compatible, robust against floating artifacts, and ready for model training and Phase 3 Gate validation.
