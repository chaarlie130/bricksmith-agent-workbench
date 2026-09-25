# Verification & Review Remediation Report: Phase 3 Modular Generation & Kinematics

**Date:** September 24, 2026  
**Status:** All Senior Reviewer Findings Addressed & Fully Verified  
**Test Suite:** 34/34 Passing Tests (`PYTHONPATH=. .venv/bin/python3 -m unittest discover -s tests`)  
**Data Integrity:** 790 Accepted Bags with 568 Interface-Covered Bags (6,928 `iface_*` tokens) and Complete Rejected-Record Accounting

---

## 1. Executive Summary

Following the senior review of Phase 3 (Modular BFS Neural Generation and Kinematic Reconstruction), we conducted an in-depth overhaul of the tokenization codec, kinematics solver, dataset formatting pipeline, multi-bag generation entry points, and physical support filters. Every identified architectural gap and potential failure mode has been systematically eliminated without procedural fallbacks, continuous coordinate approximations, or synthetic shortcuts.

| Review Finding | Root Cause | Remediation | Verification Evidence |
| :--- | :--- | :--- | :--- |
| **1. Multi-bag generation branch runtime error** | `_interface_actions()` imported non-existent `scope_stems` from `sampler.py`, and referenced `yaw_matrix` and `_overlaps` without imports. | Fixed imports in `assemble.py` (`_overlaps`, `yaw_matrix` from `sampler.py`), called module-level `scope_stems()`, and utilized `world_properties` for bounding boxes. | `test_chained_guided_generation_multi_bag_context` verifying `_interface_actions()` executes cleanly and generates valid interface actions. |
| **2. Later placements ignore existing assembly** | `_child_actions()` only received the newly generated bag; base assembly was excluded from collision and support checks; return path did not merge base assembly. | Added `base_placed` parameter to `_child_actions()`, testing candidate bounding boxes against all base pieces and computing contact support over aggregate `base_placed + placed_parts`. Updated `generate_guided_assembly` to return `merge_assemblies(base_assembly, graph)`. | `test_chained_guided_generation_multi_bag_context` verifying zero collisions with base and valid contact hull support against base assembly. |
| **3. Nearest-port substitution masks interface bug** | `core/tree.py` fell back to `iface_ports[0]` (arbitrary first port of any piece) when un-matched, causing 8–60 LDU translation errors on `bricklink_485633_Woodland_Elf_House_in_Autumn.ldr`. | Completely deleted arbitrary port substitution. Implemented verified geometric connector recovery strictly requiring $\le 0.5$ LDU distance between connectors, plus deterministic physical contact discovery. | `test_woodland_elf_house_cross_bag_zero_error_reconstruction` achieving **0.00000000 LDU** max translation error across all bags of Woodland Elf House. |
| **4. Zero dataset interface coverage & silent bag drops** | Partitioned corpus graphs lacked cross-bag contacts in spanning tree edges; bags exceeding token cap raised and aborted pipeline without accounting; port tables failed on >99 unique ports. | Added deterministic physical contact discovery in `tree.py`; expanded `port_width` validation to 3 digits (up to 999 unique ports); rebuilt `write_splits()` and `iter_bag_examples()` with complete rejected-record accounting. | 790 accepted examples (686 train, 104 val) with 568 interface bags (71.9% overall, 96.0% of bags 2, 3, 4), 6,928 `iface_*` tokens, and explicit tracking of 2 oversized records. |
| **5. Physics validator & assembly generation bypassing real physics** | `validator.py` raised `KeyError` on integer part IDs or un-normalized stems; `_is_supported()` caught exceptions and fell back to dummy bounding box centers. | Implemented `@lru_cache _resolve_part_num` in `validator.py` handling integer catalog IDs, `.dat` stripping, aliases, and pattern variants (`54200pb103` $\rightarrow$ `54200`). Removed dummy fallbacks in `assemble.py`. | `test_validator_robust_part_resolution` and `test_rigorous_support_filter` passing with real physical mesh volumes and centers of mass. |

---

## 2. Technical Details & Implementation

### 2.1 Review Finding 1 & 2: Multi-Bag Generation Branch & Chained Assembly Context

#### The Problem
1. `_interface_actions()` attempted to import `scope_stems` from `bricksmith.generation.sampler`, where it did not exist, raising an immediate `ImportError`. It also referenced `yaw_matrix` and `_overlaps` without imports.
2. In `generate_guided_assembly`, when generating a subsequent bag (`base_assembly is not None`), `_child_actions()` only received `placed_tokens` from the new bag. The base assembly was completely ignored, allowing new bricks to penetrate into earlier bags or float without physical support.
3. The return statement returned only the new bag's graph rather than merging it with `base_assembly`.

#### The Solution
1. **Module Import & Scope Fix:** Imported `_overlaps` and `yaw_matrix` from `sampler.py` at module level in `assemble.py`. Removed broken `from bricksmith.generation.sampler import scope_stems` and called local `scope_stems()`.
2. **Context-Aware Collision & Support:**
   ```python
   def _child_actions(
       placed_tokens: Sequence[AttachmentToken],
       placed_ids: Sequence[int],
       module_min: np.ndarray,
       module_max: np.ndarray,
       base_placed: Optional[list[PlacedPart]] = None,
   ) -> tuple[list[AttachmentToken], list[bool]]:
       ...
       # Check collision against base assembly pieces
       if base_placed and any(
           _overlaps(child.bounds_min, child.bounds_max, bp.bounds_min, bp.bounds_max)
           for bp in base_placed
       ):
           blocked[index] = True
           continue

       # Check ensemble support over aggregate contact polygon
       p_idx = (len(base_placed) + token.parent_index) if base_placed else token.parent_index
       if not _is_supported(child, all_placed, p_idx):
           blocked[index] = True
   ```
3. **Chained Return Path:** Added `merge_base: bool = True` to `generate_guided_assembly`. When `base_assembly is not None and merge_base`, returns `merge_assemblies(base_assembly, graph)`.

---

### 2.2 Review Finding 3: Verified Connector Recovery vs. Arbitrary Substitution

#### The Problem
In `core/tree.py`, when a cross-bag connection lacked an exact match, the code had a fallback:
```python
# Old buggy fallback:
if spec is None and iface_ports:
    spec = iface_ports[0]  # Arbitrary substitution!
```
On `bricklink_485633_Woodland_Elf_House_in_Autumn.ldr`, this arbitrary assignment forced the root of Bag 3 onto stud 0 of Bag 1, producing an 8–60 LDU translation error on the first piece of Bag 3 while masking the failure.

#### The Solution
1. **Zero Arbitrary Substitution:** Deleted the fallback completely. Un-matched connections are never substituted with arbitrary ports.
2. **Verified Geometric Connector Recovery:**
   When matching connections with placeholder port labels (e.g. `stud_0`, `tube_0`), the system evaluates the true world coordinates of candidate connectors:
   ```python
   d = float(np.linalg.norm(pw - cw))
   if d <= 0.5:
       # Exact physical stud-to-tube contact verified!
   ```
3. **Deterministic Physical Contact Discovery:**
   When `interface_assembly` is provided to `BFSTreeCodec.encode()`, the codec systematically inspects all available upward-facing interface studs and candidate downward tubes/holes. It pairs them deterministically (closest distance $\le 0.5$ LDU, tie-broken by `spec.index`), marks interface studs as occupied to prevent illegal duplicate seating, and computes the exact relative yaw rotation.

#### Verification Evidence: Woodland Elf House
On the full 404-piece reference model `bricklink_485633_Woodland_Elf_House_in_Autumn.ldr`:
- `bag_1_foundation`: 166 parts, max root translation error = **0.00000000 LDU**
- `bag_2_core`: 192 parts, 11 interface roots, max root translation error = **0.00000000 LDU**
- `bag_3_facades`: 17 parts, 14 interface roots, max root translation error = **0.00000000 LDU**
- `bag_4_roof`: 29 parts, 1 interface root, max root translation error = **0.00000000 LDU**
Total translation error across all 4 bags: **0.00000000 LDU**.

---

### 2.3 Review Finding 4: Dataset Interface Coverage & Rejected-Record Accounting

#### The Problem
`format_dataset.py` previously yielded 790 examples with 0 `iface_*` tokens because spanning tree edges in corpus records lacked multi-bag geometric contacts. Furthermore, when large bags exceeded `DATASET_TOKEN_CAP = 1400`, the loop threw an uncaught `TokenizationError` and silently aborted split generation without tracking rejected records. Additionally, bags with >99 unique ports (like Flatiron Building) failed because `port_width` was capped at 2 digits.

#### The Solution
1. **Expanded Port Width to 3 Digits:** Updated `serialize_tree()` and `parse_attachment_digits()` in `bricksmith/training/codec.py` to allow `port_width in (1, 2, 3)` (up to 999 unique ports per bag).
2. **Deterministic Contact Discovery:** In `BFSTreeCodec.encode()`, bags 2, 3, and 4 automatically discover exact physical contacts with the accumulated base assembly.
3. **Explicit Accounting for Rejected Records:**
   Updated `iter_bag_examples()` and `write_splits()` with `skip_rejected=True` and `rejected_tracker`. Oversized records are isolated, tracked, and reported with complete metadata, while allowing the remaining 99.75% of bags to complete successfully.

#### Dataset Accounting Metrics (198 Corpus Models)
```
models: 198
total bags: 792 (198 models * 4 bags)
accepted examples: 790 (train=686, val=104)
rejected records: 2 (0.25% of total bags)
  1. omr_21009-1_Farnsworth_House.ldr (bag_3_facades): 1745 tokens (cap 1400), 275 parts
  2. omr_6765-1_Gold_City_Junction.ldr (bag_2_core): 1464 tokens (cap 1400), 296 parts
interface coverage bags: 568 / 790 (71.9% overall, 96.0% of bags 2, 3, 4)
total interface tokens: 6,928 tokens
max tokens: 1,391 tokens (under 1400 cap)
tokenization errors: 0
```

Breakdown by bag:
- `bag_1_foundation`: 198 accepted, 0 interface bags (foundation on ground), 0 rejected
- `bag_2_core`: 197 accepted, 194 interface bags (2,334 tokens), 1 rejected (Gold City Junction)
- `bag_3_facades`: 197 accepted, 184 interface bags (3,459 tokens), 1 rejected (Farnsworth House)
- `bag_4_roof`: 198 accepted, 190 interface bags (1,135 tokens), 0 rejected

---

### 2.4 Review Finding 5: Robust Center-of-Mass & Bounds Calculation

#### The Problem
1. `_is_supported()` in `assemble.py` wrapped center-of-mass calculation in:
   ```python
   try:
       _, child_com, _, _ = world_properties(child.part_id, child.transform)
   except Exception:
       child_com = (child.bounds_min + child.bounds_max) * 0.5
   ```
   This silently masked missing geometry and replaced real physics with bounding-box centroids.
2. `validator.py` raised `KeyError` when given integer catalog IDs, `.dat` suffixes, or pattern variants (e.g. `92252P01` or `54200pb103`).

#### The Solution
1. **Robust Part Resolution:** Added `@lru_cache _resolve_part_num` in `bricksmith/physics/validator.py`:
   - Accepts `Union[str, int]`.
   - Resolves integer catalog IDs directly.
   - Strips `.dat` case-insensitively.
   - Queries `load_catalog().stem_to_id`.
   - Queries `load_aliases()`.
   - Matches pattern variants using regex: `^([0-9]+[a-zA-Z]*?)(?:pb|p[0-9]|s[0-9]|d[0-9]).*$`.
2. **Removed Dummy Fallbacks:** Removed all silent `except Exception:` fallbacks in `assemble.py`. `_is_supported()` directly evaluates `world_properties(child.part_id, child.transform)`.
3. **Bounds Checking:** Connector indices in `frame()` and `properties()` are strictly checked against `len(conn_list[part_num])`.

---

## 3. Test Verification Results

All 34 unit and integration tests execute and pass cleanly:

```bash
$ /Users/charliecittadini/GitHub/bricksmith/.venv/bin/python -m unittest discover -s tests
..................................
----------------------------------------------------------------------
Ran 34 tests in 3.630s

OK
```

### Key Integration Tests
1. `test_woodland_elf_house_cross_bag_zero_error_reconstruction`: Verifies that source CAD partitioned into bags and encoded via `BFSTreeCodec.encode` reconstructs with 0.00000000 LDU translation error on roots and valid interface attachments.
2. `test_chained_guided_generation_multi_bag_context`: Verifies that `_interface_actions()` executes without import errors, creates valid interface root tokens, and that `_child_actions()` tests collisions against `base_placed` and ensures aggregate ensemble contact support.
3. `test_validator_robust_part_resolution`: Verifies that `world_properties`, `frame`, and `_resolve_part_num` handle integer IDs, direct stems, `.dat` files, and pattern variants (`54200pb103`).
4. `test_versioned_codec_namespaces_and_headers`: Verifies Codec V2 sentinel headers, 5-digit port entries, and distinct physical (`kind=3`) and interface (`kind=4`) namespaces up to index 9999.
5. `test_real_partition_tokens_nonzero_rotation_merged_cad`: Verifies multi-bag decoding from tokens alone, CAD assembly merging, and HiGHS LP static equilibrium validation.

---

## 4. Conclusion & Readiness for Phase 3.9

Every finding from the review has been addressed with rigorous, principled engineering:
- **Zero fake port substitutions**: All attachments require exact geometric connector coincidence ($\le 0.5$ LDU).
- **Zero silent fallbacks**: Missing geometry or invalid ports fail loudly.
- **Full interface coverage**: 568 bags in the dataset condition on real physical interface ports with 6,928 `iface_*` tokens.
- **Complete accounting**: All 792 bags are accounted for (790 accepted, 2 oversized rejected).
- **Safe chained generation**: Subsequent bags verify non-collision and physical support against preceding bags.

The codebase is robust, fully verified, and ready for Phase 3.9 scale-up.
