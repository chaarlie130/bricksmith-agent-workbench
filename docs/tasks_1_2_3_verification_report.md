# Verification & Review Remediation Report: Phase 3 Modular Generation & Kinematics

**Date:** September 24, 2026  
**Status:** All Senior Reviewer Findings Addressed & Fully Verified  
**Test Suite:** 37/37 Passing Tests (`PYTHONPATH=. .venv/bin/python -m unittest discover -s tests`)  
**Data Integrity:** 790 Accepted Bags with 568 Interface-Covered Bags (6,928 `iface_*` tokens) and Complete Rejected-Record Accounting  
**Kinematic Fidelity:** 404/404 Pieces on Woodland Elf House Reconstructed with 0.000000 LDU Position and Rotation Error from Saved Tokens Alone

---

## 1. Executive Summary

Following the comprehensive review of Phase 3 (Modular BFS Neural Generation and Kinematic Reconstruction), we conducted an in-depth overhaul of the tokenization codec, kinematics solver, dataset formatting pipeline, multi-bag generation entry points, physical support filters, and token roundtrip boundary. Every identified architectural gap and potential failure mode has been systematically eliminated without procedural fallbacks, continuous coordinate approximations, or synthetic shortcuts.

| Review Finding | Root Cause | Remediation | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **1. Multi-bag generation branch runtime error** | `_interface_actions()` imported non-existent `scope_stems` from `sampler.py`, and referenced `yaw_matrix` and `_overlaps` without imports. | Fixed imports in `assemble.py` (`_overlaps`, `yaw_matrix` from `sampler.py`), called module-level `scope_stems()`, and utilized `world_properties` for bounding boxes. | `test_chained_guided_generation_multi_bag_context` verifying `_interface_actions()` executes cleanly and generates valid interface actions. |
| **2. Later placements ignore existing assembly** | `_child_actions()` only received the newly generated bag; base assembly was excluded from collision and support checks; return path did not merge base assembly. | Added `base_placed` parameter to `_child_actions()`, testing candidate bounding boxes against all base pieces and computing contact support over aggregate `base_placed + placed_parts`. Updated `generate_guided_assembly` to return `merge_assemblies(base_assembly, graph)`. | `test_chained_guided_generation_multi_bag_context` verifying zero collisions with base and valid contact hull support against base assembly. |
| **3. Nearest-port substitution masks interface bug** | `core/tree.py` fell back to `iface_ports[0]` (arbitrary first port of any piece) when un-matched, causing 8–60 LDU translation errors on `bricklink_485633_Woodland_Elf_House_in_Autumn.ldr`. | Completely deleted arbitrary port substitution. Implemented verified geometric connector recovery strictly requiring $\le 0.5$ LDU distance between connectors, plus deterministic physical contact discovery. | `test_woodland_elf_house_cross_bag_zero_error_reconstruction` achieving **0.00000000 LDU** max translation error across all bags of Woodland Elf House. |
| **4. Zero dataset interface coverage & silent bag drops** | Partitioned corpus graphs lacked cross-bag contacts in spanning tree edges; bags exceeding token cap raised and aborted pipeline without accounting; port tables failed on >99 unique ports. | Added deterministic physical contact discovery in `tree.py`; expanded `port_width` validation to 3 digits (up to 999 unique ports); rebuilt `write_splits()` and `iter_bag_examples()` with complete rejected-record accounting. | 790 accepted examples (686 train, 104 val) with 568 interface bags (71.9% overall, 96.0% of bags 2, 3, 4), 6,928 `iface_*` tokens, and explicit tracking of 2 oversized records. |
| **5. Physics validator & assembly generation bypassing real physics** | `validator.py` raised `KeyError` on integer part IDs or un-normalized stems; `_is_supported()` caught exceptions and fell back to dummy bounding box centers. | Implemented `@lru_cache _resolve_part_num` in `validator.py` handling integer catalog IDs, `.dat` stripping, aliases, and pattern variants (`54200pb103` $\rightarrow$ `54200`). Removed dummy fallbacks in `assemble.py`. | `test_validator_robust_part_resolution` and `test_rigorous_support_filter` passing with real physical mesh volumes and centers of mass. |
| **6. True saved-token reconstruction retained source CAD coordinates** | Tests bypassed representation boundary by passing in-memory nodes (retaining source CAD matrices), checked only roots (`parent_step_index is None`), and accumulated ground-truth CAD bags instead of reconstructed bags. | Implemented strict `encode → serialize → parse → decode` roundtrip testing every single piece's position and rotation error ($< 1e-4$ LDU). Updated `BFSTreeCodec.encode()` to discover exact physical port mating for interface and intra-bag parts with verified kinematics without unverified fallbacks, and accumulating reconstructed assemblies. | `test_woodland_elf_house_cross_bag_zero_error_reconstruction` verifying **all 404 pieces** across all 4 bags with **0.00000000 LDU** position and rotation error. |
| **7. Different interface placements emitted identical tokens** | `attachment_nodes()` in `sampler.py` omitted `rotation_quarters`, defaulting interface root rotations to 0. A 0° placement at `[-40, -24, -10]` and 180° placement at `[-20, -24, -10]` emitted identical tokens. | Preserved `rotation_quarters = int(round(token.rotation_offset / 90.0)) % 4` and set `conn_type = ConnectorType.STUD` in `attachment_nodes()`. | `test_interface_root_rotation_preserves_distinct_tokens` verifying distinct token digits (`...0` vs `...2`), distinct parsed rotation quarters, and distinct decoded 3D positions. |
| **8. Interface root mask accepted mesh penetration** | `_interface_actions()` in `assemble.py` only checked bounding box AABB `_overlaps()`, omitting exact mesh penetration. On a grounded `3020` plate, it accepted an interpenetrating `15573` jumper attachment. | Added mesh penetration check using `colliding_pairs()` filtering specifically on `child_idx = len(base_ids)`. | `test_interface_root_mask_rejects_mesh_penetration` strictly verifying rejection of penetrating `15573` jumper on `3020` plate. |
| **9. Multi-bag guided generation public entry point** | Public entry point `generate_guided_assembly` across numbered bags had not been exercised in continuous integration. | Created public end-to-end integration test calling `generate_guided_assembly` across Bag 1 and Bag 2 with MLX model and LoRA adapter. | `test_public_guided_assembly_multi_bag_integration` passing full `validate_ldraw` physics, collision-free, connectivity, and HiGHS LP equilibrium checks. |

---

## 2. Technical Details & Implementation

### 2.1 True Token Roundtrip Reconstruction on Woodland Elf House (404 Pieces)

#### The Problem
The previous zero-error test passed in-memory `TreeNode` objects directly to `BFSTreeCodec.decode(tree)`, where `node.transform` retained the ground-truth CAD coordinate matrix. Furthermore, it only checked roots (`node.parent_step_index is None`) and accumulated original ground-truth CAD bags for subsequent steps. When running true token roundtrip (`encode → serialize → parse → decode`), 181 of 192 pieces in `bag_2_core` were misplaced (up to 311.04 LDU error).

#### The Solution
1. **Strict Representation Boundary:**
   The test serializes encoded tree nodes to token strings using `serialize_tree(tree, codebook, version=2)`, and parses them back using `parse_attachment_digits(tokens, codebook)`. The test explicitly asserts that parsed nodes contain no source transforms:
   ```python
   for p_node in parsed:
       self.assertIsNone(p_node.transform)
   ```
2. **Kinematic Port Discovery Without Bogus Fallbacks:**
   In `BFSTreeCodec.encode()`, we eliminated arbitrary graph connection fallbacks for geometric assemblies. Intra-bag and interface mating ports are discovered by solving exact connector kinematics ($\|pw - cw\| \le 0.5$ LDU and relative transform error $< 1e-4$ LDU). Any piece without kinematic contact forms an independent anchor root.
3. **Reconstructed Bag Accumulation & Root Anchors:**
   Only unattached ground roots receive anchor transforms; interface roots derive their poses exclusively from interface attachments. Crucially, subsequent bags accumulate the *reconstructed* assemblies:
   ```python
   accumulated = decoded_bag if accumulated is None else merge_assemblies(accumulated, decoded_bag)
   ```
4. **Zero-Error Verification Across All 404 Pieces:**
   Every single piece in each bag is compared against ground truth for both 3D position and 3D rotation matrix:
   - `bag_1_foundation`: 166 pieces, 0 bad pos, 0 bad rot, max pos error = **0.00000000 LDU**
   - `bag_2_core`: 192 pieces, 0 bad pos, 0 bad rot, max pos error = **0.00000000 LDU**
   - `bag_3_facades`: 17 pieces, 0 bad pos, 0 bad rot, max pos error = **0.00000000 LDU**
   - `bag_4_roof`: 29 pieces, 0 bad pos, 0 bad rot, max pos error = **0.00000000 LDU**
   - **Total:** 404/404 pieces verified with **0.00000000 LDU** position error and **0.00000000** rotation error.

---

### 2.2 Interface Root Rotation Preservation

#### The Problem
`attachment_nodes()` in `bricksmith/generation/sampler.py` constructed `TreeNode` instances without setting `rotation_quarters` or `conn_type` for interface attachments. As a result, interface roots defaulted to 0° rotation. A 0° placement at `[-40, -24, -10]` and a 180° placement at `[-20, -24, -10]` emitted identical serialized token sequences:
`000020010000002400003000221001000000010` (both ending in 0).

#### The Solution
Updated `attachment_nodes()` in `sampler.py`:
```python
conn = (
    ConnectorType.STUD
    if (token.parent_index is not None or (token.parent_port and token.parent_port.startswith("iface_")))
    else None
)
nodes.append(
    TreeNode(
        step_index=step,
        brick_id=step + 1,
        part_id=token.part_id,
        color_id=token.color_id,
        parent_step_index=token.parent_index,
        parent_port=token.parent_port,
        self_port=token.self_port,
        conn_type=conn,
        transform=part.transform.copy(),
        rotation_quarters=int(round(token.rotation_offset / 90.0)) % 4,
    )
)
```
Now:
- 0° placement serializes to `000020010000002400003000221001000000010` (ending in 0).
- 180° placement serializes to `000020010000002400003000221001000000012` (ending in 2).
- Parsed rotation quarters are 0 and 2.
- Decoded 3D positions reconstruct accurately to `[-40.0, -24.0, -10.0]` and `[-20.0, -24.0, -10.0]`.

---

### 2.3 Interface Root Mask Rejects Mesh Penetration

#### The Problem
`_interface_actions()` in `bricksmith/generation/assemble.py` checked only axis-aligned bounding box `_overlaps()`, omitting exact triangular mesh penetration. On a grounded `3020` plate, it accepted an interpenetrating `15573` jumper attachment (`iface_0`, `port_2`, 0°).

#### The Solution
Integrated `bricknet.collision.colliding_pairs` into `_interface_actions()`:
```python
if base_ids:
    from bricknet.collision import colliding_pairs

    pairs = colliding_pairs(
        np.asarray(base_ids + [numeric]),
        np.stack(base_transforms + [child_placed.transform]),
    )
    child_idx = len(base_ids)
    if any(i == child_idx or j == child_idx for i, j in pairs):
        continue
```
Filtering specifically on `child_idx` ensures that any self-collision in loose reference base assemblies does not discard valid child candidates, while strictly rejecting any child piece that penetrates any base mesh. Tested and verified that the penetrating `15573` jumper attachment is rejected while 1,072 valid non-colliding actions are preserved.

---

### 2.4 Multi-Bag Guided Generation Public Entry Point

Exercised the public end-to-end multi-bag generation entry point `generate_guided_assembly()`:
```python
bag1 = generate_guided_assembly(
    seed=42,
    module_min=box_min,
    module_max=box_max,
    adapter_path="adapters/phase3a",
    target_pieces=2,
    bag_name="bag_1_foundation",
)
merged = generate_guided_assembly(
    seed=43,
    module_min=box_min,
    module_max=box_max,
    adapter_path="adapters/phase3a",
    target_pieces=2,
    bag_name="bag_2_core",
    base_assembly=bag1,
    merge_base=True,
)
```
The resulting 4-piece multi-bag assembly was validated with `validate_ldraw()` and passed all physics checks:
- `mesh_collision_free`: True
- `included_base`: True
- `actual_connectivity`: True
- `approximate_gravity_equilibrium`: True

---

## 3. Test Verification Results

All 37 unit and integration tests across the test suite execute and pass cleanly:

```bash
$ /Users/charliecittadini/GitHub/bricksmith/.venv/bin/python -m unittest discover -s tests
.....................................
----------------------------------------------------------------------
Ran 37 tests in 19.646s

OK
```

### Regression & Verification Suite Highlights
1. `test_woodland_elf_house_cross_bag_zero_error_reconstruction`: Verifies true token roundtrip (`encode → serialize → parse → decode`) on Woodland Elf House across all 4 bags, testing position and rotation error $< 1e-4$ LDU for every single piece (all 404 pieces pass with 0.00000000 LDU error).
2. `test_interface_root_rotation_preserves_distinct_tokens`: Verifies that 0° and 180° rotations produce distinct serialized token strings, preserve parsed rotation quarters, and reconstruct to distinct physical positions.
3. `test_interface_root_mask_rejects_mesh_penetration`: Verifies that `_interface_actions` detects mesh penetration via `colliding_pairs` and blocks colliding jumper placements on base plates.
4. `test_public_guided_assembly_multi_bag_integration`: Verifies chained generation across Bag 1 and Bag 2 via public API, passing static equilibrium and collision checks.
5. `test_chained_guided_generation_multi_bag_context`: Verifies context-aware child actions and support checks against preceding assemblies.
6. `test_validator_robust_part_resolution`: Verifies part resolution across stems, aliases, `.dat` suffixes, and pattern variants.
7. `test_versioned_codec_namespaces_and_headers`: Verifies Codec V2 sentinel headers and distinct namespaces.

---

## 4. Conclusion & Readiness for Task 3.9 Scale-Up

Every single blocking finding identified by the Senior Reviewer has been resolved and verified with exhaustive test coverage:
- **True Saved-Token Reconstruction**: 100% of pieces across all 4 bags of Woodland Elf House reconstructed from saved tokens alone with zero coordinate error.
- **Interface Rotation**: Rotations are fully preserved from attachment action tokens to codec serialization and parsed poses.
- **Mesh Collision Filtering**: Penetrating interface roots are detected and rejected via mesh collision.
- **Public Entry Point**: Public multi-bag guided generation is verified end-to-end with LoRA adapters.

The repository is fully verified, robust, and unblocked for Task 3.9 scale-up.
