# M0 third review — R1a/R1b accepted; R4a remains open

Reviewed: 2026-10-15. Decision: **M0 not yet accepted; M1 remains unstarted.**

## Accepted evidence

- R1a: arbitrary untracked runtime modules under the bounded source roots now
  affect full manifest identity. The regression changes real file bytes while
  Git status remains unchanged.
- R1b: the imported BrickNet runtime's actual package-data tree is fingerprinted
  separately from external meshes. Real JSON byte changes affect identity;
  relocation does not. Missing data is represented as incomplete.
- The submitted `/tmp/bricksmith-m0-review-final-v6.json` validates and recomputes
  to `b3fcbe6b9f122ca2a0681c0da76e9f688f00cd29221166dda9965b5805504a84`.
  Its 112 source records match this checkout, and its five package-data records
  hash to the current imported package-data tree. The submitted artifact itself
  does contain the evidence described here.
- The previous bad prompt digest, bad BrickNet digest, missing source-record
  list, and altered source/catalog record digests are rejected before publication.
- Reviewer dependency imports passed. Full discovery passed **125 tests in
  73.618 seconds**. No model calls, dependency downloads, library changes, or
  production-code edits were made during review.

## Remaining R4a — P2: enforce evidence presence, not just digest consistency

Locations in the reviewed `bricksmith/workbench/provenance.py`:
`validate_manifest` lines 425–438 and `_capture_evidence_present` lines 519–521.

The validator accepts an empty BrickNet source-file list if its digest is the
correct hash of `[]`. It also accepts a package-data tree containing only its
root directory if that digest is recomputed. Both records still pass completeness
and can be published with `capture_status: complete`. The collector already
requires a physical file before declaring package data available; validation must
enforce that same condition for imported records.

These are structural consistency checks, not a demand to prove that arbitrary
submitted hashes describe real disk contents or to add cryptographic attestation.
Do not expand this task into a new provenance system.

Independent reviewer reproduction, starting with a deep copy of v6 for each case:

```python
b = value["environment"]["bricknet_source"]
# Case 1:
b.update(source_files=[], source_content_sha256=_records_sha256([]))
# Case 2, on a fresh copy:
files = [{"path": ".", "type": "directory", "size": 0}]
b["catalog_data"].update(files=files, content_sha256=_records_sha256(files))
```

For each case the reviewer recomputed manifest identity and published to a new
temporary path. Both returned `published: True; complete: True`.

There is also a remaining error-contract case at `_validate_tree_records`, line
70: setting a nested tree record's `type` to `[]` raises an unhandled `TypeError`
from set membership. R4a explicitly requires malformed types to raise useful
`ValueError`s.

## Exact bounded worker assignment

- [ ] When BrickNet source is declared available, require a nonempty validated
  source-file list. Missing source evidence must be represented as unavailable or
  incomplete; it cannot support a complete capture. Ensure the collector does not
  create an available record with no readable Python source files.
- [ ] When package data is declared available, require at least one validated
  `file` or `symlink_file` record. Reject the available directory-only record.
  Preserve the existing unavailable representation (`available: false`, null
  digest, empty files) as valid incomplete evidence.
- [ ] Validate the tree record's `type` as a string before enum membership so
  list/object values raise a field-specific `ValueError`. Apply the same small
  type guard to other enum membership checks in `validate_manifest` that can
  receive JSON lists/objects (notably `capture_status`).
- [ ] Add regressions starting from a valid complete manifest for empty source
  records, directory-only package data, list/object record types, and list/object
  capture status. Recompute aggregate hashes in the first two tests so they
  exercise evidence presence rather than an unrelated digest mismatch. Require
  validation/publication to raise `ValueError` and create no output. Keep positive
  coverage for valid complete and explicitly unavailable/incomplete records.
- [ ] Run the unit suite and full discovery with `./.venv/bin/python`, run
  `git diff --check`, update the completion record, and export to a new path.

Only the remaining R4a checks are assigned. Preserve the accepted R1a/R1b changes
and prior fixes. No M1, live inference, benchmark execution, library mutation,
dependency downloads, or unrelated refactoring. Leave the review gate open.

The previously disclosed clean-install limitation remains accepted for M0 and
must be resolved before claiming portable benchmark reproduction.
