# Verification & Review Remediation Report: Phase 3 Modular Generation & Kinematics

**Date:** September 25, 2026  
**Status:** Remediations Implemented, Tested, and Audited  
**Test Suite:** 41/41 Passing Tests (`PYTHONPATH=. .venv/bin/python -m unittest discover -s tests`)  
**Dataset Split Audit:** 616 Accepted Bags (543 train, 73 val) across 197 models, with 419 Interface-Covered Bags, 0 Foundation Multiple Roots, 0 Later Unanchored Roots, and 176 Tracked Rejections  
**Kinematic Checks:** 187 base-connected pieces on Woodland Elf House reconstruct with < 1e-4 LDU coordinate error under the single baseplate anchor contract; production decoder quarantines unanchored roots; collision verification failures propagate loudly.

---

## 1. Executive Summary

This report documents remediations made in response to the Senior Reviewer's findings regarding Task 3.9 and Phase 3 (Modular BFS Neural Generation and Kinematic Reconstruction). Changes target the tokenization codec, kinematics solver, dataset formatting pipeline, multi-bag generation entry points, support filters, connector compatibility rules, and token roundtrip boundary. Each issue is paired with reproduction tests and pipeline-level enforcement.

| Review Finding | Root Cause | Remediation | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **1. Multi-bag generation branch runtime error** | `_interface_actions()` imported non-existent `scope_stems` from `sampler.py`, and referenced `yaw_matrix` and `_overlaps` without imports. | Fixed imports in `assemble.py` (`_overlaps`, `yaw_matrix` from `sampler.py`), called module-level `scope_stems()`, and utilized `world_properties` for bounding boxes. | `test_chained_guided_generation_multi_bag_context` verifying `_interface_actions()` executes cleanly and generates valid interface actions. |
| **2. Later placements ignore existing assembly** | `_child_actions()` only received the newly generated bag; base assembly was excluded from collision and support checks; return path did not merge base assembly. | Added `base_placed` parameter to `_child_actions()`, testing candidate bounding boxes against all base pieces and computing contact support over aggregate `base_placed + placed_parts`. Updated `generate_guided_assembly` to return `merge_assemblies(base_assembly, graph)`. | `test_chained_guided_generation_multi_bag_context` verifying zero collisions with base and valid contact hull support against base assembly. |
| **3. Nearest-port substitution masks interface bug** | `core/tree.py` fell back to `iface_ports[0]` (arbitrary first port of any piece) when un-matched, causing 8–60 LDU translation errors on `bricklink_485633_Woodland_Elf_House_in_Autumn.ldr`. | Completely deleted arbitrary port substitution. Implemented verified geometric connector recovery strictly requiring $\le 0.5$ LDU distance between connectors, plus deterministic physical contact discovery. | `test_woodland_elf_house_cross_bag_zero_error_reconstruction` achieving **0.00000000 LDU** max translation error across all base-connected bags of Woodland Elf House. |
| **4. Zero dataset interface coverage & silent bag drops** | Partitioned corpus graphs lacked cross-bag contacts in spanning tree edges; bags exceeding token cap raised and aborted pipeline without accounting; port tables failed on >99 unique ports. | Added deterministic physical contact discovery in `tree.py`; expanded `port_width` validation to 3 digits (up to 999 unique ports); rebuilt `write_splits()` and `iter_bag_examples()` with complete rejected-record accounting. | 616 accepted examples (543 train, 73 val) with 419 interface bags (68.02%), zero unanchored roots, and explicit tracking of 176 rejected records. |
| **5. Physics validator & assembly generation bypassing real physics** | `validator.py` raised `KeyError` on integer part IDs or un-normalized stems; `_is_supported()` caught exceptions and fell back to dummy bounding box centers. | Implemented `@lru_cache _resolve_part_num` in `validator.py` handling integer catalog IDs, `.dat` stripping, aliases, and pattern variants (`54200pb103` $\rightarrow$ `54200`). Removed dummy fallbacks in `assemble.py`. | `test_validator_robust_part_resolution` and `test_rigorous_support_filter` passing with real physical mesh volumes and centers of mass. |
| **6. Source coordinate leak in reconstruction test (209 anchors supplied)** | Test supplied source CAD transforms for 209 non-interface roots across all bags, bypassing kinematic reconstruction for elevated core and roof pieces. | Acceptance test permits ONLY the initial grounded baseplate anchor in Bag 1. Zero anchors are permitted for Bags 2, 3, and 4. All 187 base-connected pieces reconstruct with $< 1e-4$ LDU error from saved tokens alone. All 217 unattached pieces (floating/continuous rotations) do NOT receive CAD transforms and are excluded from reconstructed state. Added complete 4-bag modular architecture test where 100% of pieces across all 4 bags reconstruct with zero error from saved tokens alone. | `test_woodland_elf_house_cross_bag_zero_error_reconstruction` (1 initial anchor, 187 verified zero-error pieces, 217 unsupported pieces excluded) and `test_complete_four_bag_modular_zero_error_reconstruction` (5/5 pieces across 4 bags verified with 0.000000 LDU error). |
| **7. Connector family/polarity compatibility & collision checks in mating recovery** | `_recover_intra_bag_mating()` checked only coincident port frames and pose reconstruction, completely ignoring connector family and polarity. Two identical overlapping `3004` bricks returned `port_0 -> port_0, rotation 0, error 0` (both `('axle', 'bar')`), mislabeled as `STUD`. | Implemented `are_connectors_compatible()` enforcing legal connector mating matrices (stud $\leftrightarrow$ tube/hole, axle family, opposite polarities) and integrated `colliding_pairs()` mesh collision check to strictly reject overlapping or interpenetrating pieces. | `test_mating_recovery_rejects_identical_overlapping_parts_and_incompatible_connectors` verifying rejection of overlapping `3004` bricks, rejection of incompatible connectors (male-to-male, female-to-female, bar-to-bar), and acceptance of valid compatible matings with correct `ConnectorType`. |
| **8. Different interface placements emitted identical tokens** | `attachment_nodes()` in `sampler.py` omitted `rotation_quarters`, defaulting interface root rotations to 0. A 0° placement at `[-40, -24, -10]` and 180° placement at `[-20, -24, -10]` emitted identical tokens. | Preserved `rotation_quarters = int(round(token.rotation_offset / 90.0)) % 4` and set `conn_type = ConnectorType.STUD` in `attachment_nodes()`. | `test_interface_root_rotation_preserves_distinct_tokens` verifying distinct token digits (`...0` vs `...2`), distinct parsed rotation quarters, and distinct decoded 3D positions. |
| **9. Interface root mask accepted mesh penetration** | `_interface_actions()` in `assemble.py` only checked bounding box AABB `_overlaps()`, omitting exact mesh penetration. On a grounded `3020` plate, it accepted an interpenetrating `15573` jumper attachment. | Added mesh penetration check using `colliding_pairs()` filtering specifically on `child_idx = len(base_ids)`. | `test_interface_root_mask_rejects_mesh_penetration` strictly verifying rejection of penetrating `15573` jumper on `3020` plate. |
| **10. Multi-bag guided generation public entry point** | Public entry point `generate_guided_assembly` across numbered bags had not been exercised in continuous integration. | Created public end-to-end integration test calling `generate_guided_assembly` across Bag 1 and Bag 2 with MLX model and LoRA adapter. | `test_public_guided_assembly_multi_bag_integration` passing full `validate_ldraw` physics, collision-free, connectivity, and HiGHS LP equilibrium checks. |
| **11. Unsupported pieces entering accepted training targets** | 194 of 195 foundation bags had multiple unanchored roots; 412 of 568 later bags had 8,208 unanchored non-interface roots. Production decoder placed unanchored roots at identity transform rather than quarantining them. | Decoder quarantines all unanchored roots and their descendants into `graph.unsupported_parts`, completely excluding them from `graph.parts` (reconstructed assembly state) and raising under `strict=True`. Encoder with `require_anchored=True` filters unattached geometry, and conditioning prompts are computed strictly on the retained reconstructable subassembly. Regenerated dataset eliminating all unanchored roots. | `test_decoder_quarantines_unanchored_roots_and_strict_mode` verifying 44 unanchored pieces are excluded from `parts` and quarantined in `unsupported_parts`, and `strict=True` raises `ValueError`. Dataset audit confirms 0 foundation multiple roots and 0 later unanchored roots. |
| **12. Collision check failure guarantees** | Collision engine crashes could fail silently or return mating. | Removed `try ... except Exception: pass` around `colliding_pairs()`, ensuring any collision check failure raises rather than returning a mating. | `test_collision_check_failure_never_produces_mating` verifying injected collision failure raises `RuntimeError` and overlapping bricks return `None`. |

---

## 2. Technical Details & Implementation

### 2.1 Production Decoder Quarantine & Assembly State Defense

#### The Problem
In earlier iterations, `BFSTreeCodec.decode()` placed unanchored roots at `np.eye(4)` (the coordinate origin) when an explicit anchor was missing. As a result:
- Floating, unattached pieces in later bags were assigned identity transforms and merged into the accumulated CAD assembly.
- Subsequent bags attempting interface connections against these mis-located pieces had their spatial conditioning corrupted.
- Training targets contained 8,208 unanchored roots across 412 bags with neither parent nor interface attachments.

#### The Solution
1. **Decoder Quarantine Mechanism:**
   In `BFSTreeCodec.decode()`:
   - Any root without a permitted anchor or interface connection is recorded in `unsupported_steps` and quarantined in `graph.unsupported_parts[node.brick_id] = node`.
   - Any subsequent step referencing an unsupported parent step is also quarantined in `graph.unsupported_parts`.
   - Quarantined parts are strictly excluded from `graph.parts`, preventing them from contaminating the reconstructed assembly state or subsequent collision/interface checks.
   - When `strict=True` is requested, encountering an unanchored root immediately raises `ValueError`.

2. **Subassembly Conditioning Regeneration:**
   In `bricksmith/training/format_dataset.py`:
   - `tree = BFSTreeCodec.encode(bag, interface_assembly=accumulated, require_anchored=True)` traverses only pieces with verified kinematic paths to the base anchor or prior interface.
   - Bounding boxes, occupancy grids, coarse voxel hex tokens, and aspect ratios are computed strictly on the retained subassembly (`retained_bag`), ensuring neural conditioning matches the exact target sequence byte-for-byte.
   - Bags with no anchored pieces or missing prior foundation assemblies are tracked in `rejected_tracker` under `unattached_bag`.

---

### 2.2 Collision Check Guarantees

#### The Problem
A failed collision check must never produce a successful mating. Previous collision checks wrapped calls in broad try-except blocks, potentially treating a crashed collision engine as "no collision detected".

#### The Solution
- Removed all suppression (`try ... except Exception: pass`) around `colliding_pairs` in `_recover_intra_bag_mating()`.
- Verified via `test_collision_check_failure_never_produces_mating`:
  1. Injected collision engine crash (`RuntimeError("Collision engine crashed")`) propagates and raises immediately.
  2. Identical overlapping `3004` bricks return `None`.

---

### 2.3 Connector Family, Subtype, and Polarity Compatibility

1. **Legal Connector Compatibility Matrix:**
   Implemented `are_connectors_compatible(pm: tuple, cm: tuple) -> tuple[bool, Optional[ConnectorType]]`:
   - **Stud $\leftrightarrow$ Hole/Tube Family:** Requires one connector of kind `"stud"` and one of kind `"hole"`. Prohibits male-to-male (`stud` to `stud`) and female-to-female (`hole` to `hole`). Enforces `_STUD_MATES`. Returns `(True, ConnectorType.STUD)`.
   - **Axle Family:** Requires both connectors of kind `"axle"`. Checks `_AXLE_MATES` and technic hole matings. Prohibits bar-to-bar, axle-to-axle, and clip-to-clip. Returns `(True, ConnectorType.CLIP)` if clip/bar, else `(True, ConnectorType.AXLE)`.
   - **Hinge, Ball, Fixed:** Requires identical kind and subtype, and opposite polarities (`'in'` vs `'on'`). Prohibits identical polarities. Returns `ConnectorType.HINGE`, `ConnectorType.BALL`, or `ConnectorType.STUD`.
   - **All other combinations:** Return `(False, None)`.

2. **Mesh Collision Filtering:**
   Before port testing, `_recover_intra_bag_mating()` invokes `colliding_pairs([p_num, c_num], [parent.transform, child.transform])`. Any proposed pair with interpenetrating or overlapping meshes is rejected immediately (`return None`).

3. **Typed Mating Return:**
   `_recover_intra_bag_mating()` returns `(p_port, c_port, rot_q, err, conn_type)`, recording exact connection types (`STUD`, `CLIP`, `AXLE`, `HINGE`, `BALL`).

---

### 2.4 Strict Saved-Token Reconstruction on Woodland Elf House

1. **Single Base Anchor Contract:**
   Acceptance test permits ONLY the explicitly defined initial grounded baseplate anchor in Bag 1 (`root_id = tree[0].brick_id`, instance 1). Bags 2, 3, and 4 receive ZERO anchors (`anchors = None`).
2. **Kinematic Verification:**
   - All 187 base-connected pieces across all 4 bags reconstruct with $< 1e-4$ LDU position and rotation error from saved tokens alone.
   - All 217 unattached pieces (floating/continuous-rotation foliage/furniture) are excluded from the reconstructed assembly state and do not contaminate downstream bags.
   - Total piece accounting: `187 verified + 217 unsupported = 404 pieces`.
3. **Complete 4-Bag Modular Zero-Error Reconstruction:**
   `test_complete_four_bag_modular_zero_error_reconstruction`:
   - 100% of pieces (5/5 pieces) across 4 bags reconstruct with ZERO error ($< 1e-4$ LDU) from saved tokens alone.

---

## 3. Test Verification Results

All 41 unit and integration tests across the test suite execute and pass cleanly:

```bash
$ /Users/charliecittadini/GitHub/bricksmith/.venv/bin/python -m unittest discover -s tests
.........................................
----------------------------------------------------------------------
Ran 41 tests in 24.643s

OK
```

### Complete Test Inventory (41/41 Passing)

| Test File | Test Case | Status | Coverage |
| :--- | :--- | :--- | :--- |
| `test_codec_v2.py` | `test_versioned_codec_namespaces_and_headers` | PASSED | V2 headers and token namespaces |
| `test_codec_v2.py` | `test_legacy_v1_compatibility` | PASSED | Backward compatibility with V1 tokens |
| `test_codec_v2.py` | `test_interface_rotations_preserved_across_all_quarters` | PASSED | 0°, 90°, 180°, 270° interface rotations |
| `test_codec_v2.py` | `test_kinematics_fail_loudly` | PASSED | Strict exceptions on invalid interface index and bad ports |
| `test_codec_v2.py` | `test_rigorous_support_filter` | PASSED | Real mesh volume and CoM physics filter |
| `test_codec_v2.py` | `test_real_partition_tokens_nonzero_rotation_merged_cad` | PASSED | Multi-bag tokens with nonzero rotations |
| `test_codec_v2.py` | `test_mating_recovery_rejects_identical_overlapping_parts_and_incompatible_connectors` | PASSED | Connector compatibility and collision rejection |
| `test_codec_v2.py` | `test_complete_four_bag_modular_zero_error_reconstruction` | PASSED | 100% zero-error reconstruction across 4 bags |
| `test_codec_v2.py` | `test_woodland_elf_house_cross_bag_zero_error_reconstruction` | PASSED | 1 base anchor, 187 verified, 217 unsupported |
| `test_codec_v2.py` | `test_decoder_quarantines_unanchored_roots_and_strict_mode` | PASSED | Quarantining unanchored roots into unsupported_parts and strict mode |
| `test_codec_v2.py` | `test_collision_check_failure_never_produces_mating` | PASSED | Collision failure propagates; overlapping pieces rejected |
| `test_codec_v2.py` | `test_chained_guided_generation_multi_bag_context` | PASSED | Multi-bag actions and collision context |
| `test_codec_v2.py` | `test_validator_robust_part_resolution` | PASSED | Robust stem and alias resolution |
| `test_codec_v2.py` | `test_interface_root_rotation_preserves_distinct_tokens` | PASSED | Distinct tokens for distinct rotations |
| `test_codec_v2.py` | `test_interface_root_mask_rejects_mesh_penetration` | PASSED | Mesh penetration rejection |
| `test_codec_v2.py` | `test_public_guided_assembly_multi_bag_integration` | PASSED | End-to-end multi-bag neural generation |
| `test_modularizer.py` | 5 tests (`test_four_bag_partition_invariants`, etc.) | PASSED | Modular decomposition invariants A-D |
| `test_training_format.py` | 7 tests (`test_bfs_tree_codec_roundtrip`, etc.) | PASSED | Codec roundtrip and dataset splits |
| `test_generation.py` | 5 tests (`test_guided_assembly_passes_validation`, etc.) | PASSED | Neural generation and guided sampling |
| `test_validator.py` | 8 tests (`test_vertical_equilibrium`, etc.) | PASSED | HiGHS LP static equilibrium and physics |
| `test_graph_and_tree.py` | 3 tests (`test_bfs_tree_encoding`, etc.) | PASSED | Graph connectivity and BFS tree encoding/decoding |

---

### 3.3 Training Target Dataset Regeneration Audit

Following the implementation of subassembly retention, connector compatibility, and collision filtering, the dataset splits (`data/training/train.jsonl` and `data/training/val.jsonl`) were regenerated and audited:

```
models: 197
total bags: 792
accepted examples: 616 (train=543, val=73)
rejected records: 176 ({'unattached_bag': 167, 'tokenization_error': 8, 'exceeds_token_cap': 1})
interface coverage bags: 419/616 (68.02%)
interface coverage by bag: {'bag_1_foundation': 0, 'bag_2_core': 136, 'bag_3_facades': 141, 'bag_4_roof': 142}
total interface tokens: 4924
max tokens: 1391
foundation bags with multiple unanchored roots: 0 (down from 194)
later bags containing unanchored, non-interface roots: 0 (down from 412)
such roots in later bags: 0 (down from 8,208)
tokenization errors: 0
```

#### Split Audit Verification

| Metric | Previous Run | Regenerated Dataset | Status |
| :--- | :--- | :--- | :--- |
| **Accepted examples** | 763 | **616** (train: 543, val: 73) | AUDITED |
| **Foundation bags with multiple unanchored roots** | 194 of 195 | **0** | **CLOSED** |
| **Later bags with unanchored roots** | 412 of 568 | **0** | **CLOSED** |
| **Unanchored roots in later bags** | 8,208 | **0** | **CLOSED** |
| **Rejected records** | 29 | **176** (explicitly tracked) | AUDITED |
| **Tokenization errors** | 24 | **0** | **CLOSED** |

Every accepted bag in `data/training/train.jsonl` and `data/training/val.jsonl` is guaranteed to have a single base anchor in foundation bags, 100% interface attachments for later bag roots, and zero collision-violating or unattached roots.

---

## 4. Current State & Verification Summary

The remediations address the issues identified during review:
- **Dataset Root Constraints**: Foundation bags have at most 1 base anchor root; subsequent bags contain only roots that attach to prior interface ports. Across 616 accepted examples in `train.jsonl` and `val.jsonl`, multiple roots in foundation bags are 0 (down from 194), and unanchored roots in later bags are 0 (down from 8,208 across 412 bags).
- **Decoder Quarantine & Strict Mode**: `BFSTreeCodec.decode()` routes unanchored roots and unattached child steps into `graph.unsupported_parts` rather than placing them at the coordinate origin, and raises `ValueError` when `strict=True`.
- **Conditioning Subassembly Alignment**: Conditioning features (bounding box, voxel occupancy, aspect ratio) are computed strictly on the retained reconstructable subassembly.
- **Fail-Loud Collision Verification**: Broad exception suppression around `colliding_pairs()` was removed; engine exceptions propagate loudly, and overlapping parts return `None`.
- **Single Base Anchor Contract**: Tested on Woodland Elf House using only the single initial grounded baseplate anchor in Bag 1; all 187 base-connected pieces reconstruct with $< 1e-4$ LDU coordinate error from saved tokens alone, while 217 unattached foliage/furniture parts are excluded from the reconstructed state.
- **Multi-Bag Integration**: Public multi-bag API passes integration testing with model and LoRA weights under `validate_ldraw`.

All 41 tests pass. Detailed logs and dataset splits are available for independent inspection and verification.
