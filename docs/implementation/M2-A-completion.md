# M2-A completion report — offline transactions and recovery

Date: 2026-10-16. Scope: **M2-A only**, covering the offline transaction
core/recovery work in M2.1–M2.5 and M2.7. Corrections R1–R7 and follow-ups
R3a/R5a/R5b are submitted for re-review; M2 remains open. M2.6 and M2-B were
not implemented.

## Correction pass R1–R7

- **R1:** User-owned lock IDs, holders, owners, targets, fields, and full lock
  semantics are compared against the candidate. Removing a lock holder through
  direct or subtree assembly deletion blocks the proposal; removing a protected
  target through deletion or replacement records a failed candidate. Tests also
  confirm an unrelated edit remains eligible and failed proposals leave the
  authoritative revision and original constraints unchanged.
- **R2:** Clone operations retain their frozen base selection but clone each
  assembly and part from the sequential candidate state. Transform, recolor,
  retained-ID replacement, and assembly metadata edits are visible to the clone.
  Deleted sources or owners moved outside the frozen map fail clearly; retries
  reuse the original candidate and explicit ID mappings.
- **R3:** Lifetime entity-ID use is derived from validated committed revision
  ancestry. R3a adds report-bound allocation evidence in each authoritative state
  receipt so committed transient allocations, nested relationship/field-lock IDs,
  and top-level identities remain reserved. New nested relationship and lock
  identities are checked for freshness across ordered operations; retained nested
  IDs may be edited. Failed/uncommitted operation directories do not contribute
  history. Tests cover assembly and part create-delete-commit-reuse, nested lock
  and relationship ID reuse, cross-category collisions, fresh-process reopen,
  and publication-crash recovery.
- **R4:** Operation evidence keeps all affected/deleted IDs, while generated
  live issues reference only entities still present. Provisional and
  repair-incomplete deletion candidates commit with open, valid issues and the
  corresponding construction status. Existing issues that would dangle require
  an explicit valid `upsert_issue`; M1 validation remains strict.
- **R5:** Recovery terminally aborts an intent whose candidate receipt is absent
  or unverifiable, retaining interrupted files and prior candidate receipt
  evidence. Fully verified candidate receipts remain available for commit or
  discard. Stored candidate failures are terminal; retry, inspection, discard,
  and repeated recovery return stable outcomes. A local committed receipt absent
  from authoritative `state.json` is reported as corruption.
- **R5a:** Recovery verifies and reuses an already preserved original candidate
  receipt, keeps the first durable failure explanation, and writes a terminal
  aborted receipt that binds the preserved receipt hash. A new recovery process
  resumes after either preservation or failure-record writes; subsequent recovery
  is inert. Mismatched preservation/failure evidence fails closed. Subprocess
  regressions verify inspection, retry, and discard retain the same aborted
  result and do not move the authoritative revision pointer.
- **R5b:** Recovery validates durable proposal failures against their intent and
  reconstructs the normal `failed` terminal receipt when the process dies after
  `failure.json` is durable. It preserves the original failure bytes and error
  fields, rejects malformed or mismatched evidence without overwriting it, and
  verifies failed terminal receipts against both intent and failure evidence.
  Subprocess regressions kill proposal at the failure/receipt boundary and
  recovery after its failed receipt write; a fresh process completes recovery
  idempotently. Inspection, identical retry, discard, commit rejection, and the
  unchanged revision pointer all confirm the same outcome. Malformed and
  mismatched failure evidence is rejected without overwriting it.
- **R6:** Required operation fields and types are checked before operation
  directories or intents are created, including selector fields, matrices,
  finite values, enum containers, and integer-vs-boolean fields across every
  operation type. Invalid requests raise contextual `TransactionError`; valid
  requests that fail final candidate validation retain diagnostic evidence.
- **R7:** Eligibility binds a path-independent checker environment identity over
  local checker/interpreter/config source, imported BrickNet source, actual
  BrickNet package data, configured mesh data, Python, and checker dependency
  versions. Proposal and commit recapture it; incomplete or changed inputs block
  eligibility even when the checker booleans are identical.

Latest correction verification:

- `./.venv/bin/python -m unittest tests.unit.test_transactions tests.unit.test_m2a_review_regressions -v`
  — passed, **38 tests in 39.993 seconds** after R5b; the final receipt-write
  crash extension also passed its focused regressions (**2 tests in 5.292
  seconds**).
- `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest tests.integration.test_transactions_cli -v`
  — passed, **2 real CLI tests in 21.566 seconds**.
- `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  — passed, **189 tests in 122.990 seconds**.
- Configured preflight passed; all five real construction checks and rendering
  passed. Required imports, `py_compile`, provenance validation, and
  `git diff --check` passed.

R1–R7 and R3a/R5a/R5b are submitted for re-review. M2-A/M2 review gates remain
open; M2.6 and M2-B are unassigned.

## Initial implementation changes

- Added `bricksmith/workbench/revisions.py`: immutable, hashed revision trees;
  single-read authoritative state; POSIX `flock` writer exclusion; durable atomic
  state publication; receipts, ordered events, compatibility export recovery,
  and explicit reporting of interrupted staging and orphan revisions.
- Added `bricksmith/workbench/transactions.py`: strict bounded
  `bricksmith-operation-v1` parsing; stable-ID selection and edits; exact
  context-independent decimal transforms; assembly cloning and membership;
  protected user locks/requirements; candidate evidence; identity-based
  five-check policy; idempotent commit/discard/recovery behavior.
- Added offline-only `transaction-*` CLI commands in `scripts/workbench.py`.
  They can explicitly initialize from an M1 design or an inert v2 snapshot and
  do not enable model execution or reroute existing live editing tools.
- Added a complete below-ground identity diagnostic at the validator seam while
  preserving the prior fields and thresholds. The M2 policy uses only complete,
  identity-mappable evidence.
- Documented the offline path and M2-B boundary in README and the workbench
  guide. Updated the plan and assignment checklists for implemented M2-A scope;
  M2.6 and reviewer gates remain open.
- Added 23 transaction unit tests and 2 real CLI integration tests. These tests
  are deterministic reproducer/evidence bundles; no private `runs/` artifacts
  were used.

## Initial submission verification (v1)

All commands ran from the repository root using `./.venv/bin/python`.

- `./.venv/bin/python -c 'import bricknet, meshlib, matplotlib'` — passed.
- `./.venv/bin/python -m unittest tests.unit.test_transactions -v` — passed,
  **23 tests**. Policy/operation tests use explicitly synthetic reports; crash
  and writer tests use actual subprocesses and process termination.
- `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest tests.integration.test_transactions_cli -v`
  — passed, **2 tests**. Real CLI import, multi-assembly proposal/inspection/
  commit/retry used all five real checks and rendered the committed export. A
  collision regression was retained as an invalid candidate, rejected at commit,
  and then explicitly discarded.
- `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
  — passed, **174 tests in 123.399 seconds**.
- `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python scripts/workbench.py preflight`
  — passed. The actual 3024 fixture check reported
  `mesh_collision_free`, `included_base`, `no_parts_below_ground`,
  `actual_connectivity`, and `approximate_gravity_equilibrium` true; real render
  passed. The configured BrickNet data identity was
  `abdcc7bf8176b439ff70a1dbc93f8cd8bcdb8df312b99552b088e8cf9692b021`.
- `./.venv/bin/python -m py_compile bricksmith/workbench/revisions.py bricksmith/workbench/transactions.py scripts/workbench.py bricksmith/physics/validator.py`
  and `git diff --check` — passed.
- Subprocess crash coverage terminates before/after intent flush, during candidate
  writes, after seal/before pointer, immediately after pointer, during event
  finalization, and during compatibility-export finalization. Fresh recovery
  verifies either the old revision with an uncommitted/orphan candidate or the
  new revision with its matching receipt and repaired artifacts. Additional
  tests terminate a lock holder, race actual writers, and show an edit across
  more than 30 placements is all-or-nothing.

## Initial submission provenance (v1)

The offline provenance record is
[`m2-a-offline-provenance-v1.json`](evidence/m2-a-offline-provenance-v1.json).
Its capture is complete, its classification is
`provenance_only_no_design_result`, and provider/model are null. Manifest
identity: `fa43aeea82d2f7873dd6db5abdd633d055fc99d7417fc73ca979a54657eeabcb`.
Artifact SHA-256: `dcaf955afcb3eb92a140d94ce6d339a14b80ba29c49f3661ef5eb50eb2afa9fc`.

The corrected snapshot is recorded separately as
[`m2-a-offline-provenance-v2.json`](evidence/m2-a-offline-provenance-v2.json).
The v2 capture is complete and remains provenance-only with null provider/model.
Manifest identity: `6c64d9f4fcdc4e5b8019402a478c27bf4286553bd08a0e9eb7c011cc3961e947`.
Artifact SHA-256: `01b74facb5fa961d8e4cce5f816a5a1c6f8534c1cd5f4e4bae1034c66682d4e2`.
An earlier pre-final v2 capture was retained as
[`m2-a-offline-provenance-v2-pre-final.json`](evidence/m2-a-offline-provenance-v2-pre-final.json);
the v2 artifact above records the final correction source snapshot.
The R3a/R5a final runtime snapshot is recorded as
[`m2-a-offline-provenance-v3.json`](evidence/m2-a-offline-provenance-v3.json).
It validates as complete, provenance-only, with null provider/model;
manifest identity `7803a9a995a6501ae27b19800e33612196f4986407b08fa0eec26ef588733657`;
artifact SHA-256 `da160df74b9be1473040b7c848d1128b571d0c525187eb443d0cdb1420ca0f84`.
The v1 and v2 artifact hashes above were rechecked and remain unchanged.
The R5b final runtime snapshot is recorded as
[`m2-a-offline-provenance-v4.json`](evidence/m2-a-offline-provenance-v4.json).
It validates as complete and provenance-only, with null provider/model;
manifest identity `2d5c726fc5a662d5dd3fef9dcc5911b2911d42c65daf8799d3114a03bb3079ef`;
artifact SHA-256 `eb1acea26dbc6f2685e9a8fa48af3acaa509a306788b23947f2914c9a2fa0bb9`.
The v1, v2, and v3 artifacts were preserved byte-for-byte.
The accepted M0 and M1 provenance artifacts remain byte-for-byte unchanged at
their accepted SHA-256 values recorded in [M1 acceptance](M1-acceptance.md).

No model/provider calls, downloads, benchmarks, commits, pushes, or library
mutations were performed. There are no model-quality, visual-review, or final
workflow-acceptance claims. The test environment is the configured local
checkout; a clean installation was not verified. This assignment intentionally
does not connect old editing/generation adapters, alter v2 model execution, or
close the M2 review gate. M2-A is ready for independent review; M2-B must be
assigned separately after that review.
