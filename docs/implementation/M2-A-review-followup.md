# M2-A re-review — bounded R3a and R5a follow-up

Final status: **resolved; M2-A accepted at v4**. See
[reviewer acceptance](M2-A-acceptance.md). The following records the historical
R3a/R5a assignment.

V3 re-review: R3a/R5a are addressed. One adjacent failed-proposal receipt crash
case is assigned separately as [R5b](M2-A-review-final-followup.md); acceptance
remains pending that correction.

The v2 correction pass addresses the original R1, R2, R4, R6, and R7 findings.
The original R3 and R5 examples also now work. Two independently reproduced
boundary cases remain in those same guarantees. Implement only the follow-up
below, preserving the original M2-A scope and accepted evidence.

Reviewed v2 provenance validates as complete, with manifest identity
`6c64d9f4fcdc4e5b8019402a478c27bf4286553bd08a0e9eb7c011cc3961e947`
and file SHA-256
`01b74facb5fa961d8e4cce5f816a5a1c6f8534c1cd5f4e4bae1034c66682d4e2`.
Accepted M0/M1 and submitted M2-A v1 artifact hashes remain unchanged.

Independent validation of v2: dependency imports passed; configured full discovery
passed **184 tests in 164.701 seconds**; configured preflight passed all five
real construction checks and actual rendering; `git diff --check` passed.
These results establish the current covered behavior, but the reproductions below
are not covered by that passing suite.

## R3a — reserve all committed identities, including transient and nested ones (P2)

Location: `transactions.py::_historical_entity_ids`, `_apply`, committed evidence.

Independent temporary-workspace probes with synthetic construction reports:

1. Create an assembly with ID A and delete A in the same request. Commit that
   valid metadata transaction. Propose creating A again against the new revision.
   Observed: `commit_eligible: true`, `status: construction_passed`.
2. Initialize a design containing an agent relationship with ID R. Commit an
   update removing that relationship, then propose adding a part with ID R.
   Observed: `commit_eligible: true`, `status: construction_passed`.

Scanning only top-level records in saved design snapshots loses the first ID
entirely and omits nested relationship/field-lock IDs in the second case. M1
already treats those nested IDs as part of the same global uniqueness domain.

- [x] Reserve every newly allocated entity ID in a committed operation, even
  when the entity is absent from that operation's final candidate. Include all
  M1 ID-bearing categories and nested relationships/field locks.
- [x] Extend the durable history mechanism: derive allocated IDs from verified
  committed operation evidence as well as validated revision ancestry, or seal
  a cumulative registry with revision publication. Never trust an unverified
  loose report as authoritative history. Do not reserve failed/uncommitted
  operations merely because their directories exist.
- [x] Apply freshness enforcement to nested entity introduction through assembly
  creation, relationship updates, and clones, as well as part/assembly/issue
  creation. Updating a surviving relationship with the same identity remains an
  update; deleting it and later recreating an object with that ID is reuse.
- [x] Track introduction/removal during sequential operations, so a nested ID
  cannot be recycled later in the same request. Do not relax M1 global uniqueness.
- [x] Add regressions for both reproductions, part create→delete→commit→reuse,
  deleted nested lock ID reuse, and reuse in the reverse category direction.
  Include a fresh-process reopen and publication-crash recovery case. Keep normal
  retained-ID edits and identical committed retries passing.

## R5a — recovery must be restartable after preserving an interrupted receipt (P2)

Location: `transactions.py::recover`, preservation of
`interrupted-candidate-receipt.json` before writing a terminal abort receipt.

Independent reproduction: create a sealed candidate, append whitespace to its
design artifact so its receipt verification fails, then run recovery in a
subprocess. Terminate the process immediately after the durable write of
`interrupted-candidate-receipt.json` and before the terminal receipt is written.
The child exited 83. Each subsequent recovery failed with
`TransactionError: interrupted candidate receipt evidence already exists`.

The test used a temporary workspace; no installed library or accepted artifact
was changed. The byte change deliberately exercises the implementation's
unverifiable-candidate recovery branch, not physical validation.

- [x] Make evidence preservation idempotent: when the preservation file already
  exists, verify it is safe and matches the original receipt being preserved,
  then continue terminal reconciliation. Never overwrite mismatching evidence;
  report actual corruption when identities or contents differ.
- [x] Ensure repeated attempts cannot overwrite the first interruption/failure
  explanation or produce different terminal outcomes simply because an earlier
  recovery wrote some of its artifacts. Preserve all diagnostic evidence.
- [x] Add real subprocess termination during recovery after evidence preservation
  and after the failure record but before the terminal receipt. In a new process,
  recovery must finish, then another recovery must be inert. Inspection/retry/
  discard must return the same terminal outcome and the authoritative revision
  must remain unchanged.
- [x] Keep complete sealed candidates available for explicit commit/discard,
  committed state authoritative, and mismatched evidence fail-closed. No automatic
  operation replay or publication is introduced by this fix.

## Evidence and handback

- [x] Run focused transaction/review tests, real CLI tests, full discovery,
  configured preflight, and `git diff --check`; distinguish synthetic and real
  checks. Update completion evidence with exact outcomes.
- [x] Preserve v1 and v2 artifacts. Capture a fresh numbered v3 provenance after
  final runtime edits; report its identity and file SHA-256.
- [x] Leave M2-A/M2 review gates open and M2-B untouched. All original scope
  boundaries remain: no live calls, benchmark, downloads, commits/pushes, or
  unrelated cleanup. Send REVIEWER the completion message under the human's
  existing authorization, then stop for re-review.
