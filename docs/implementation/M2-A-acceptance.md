# M2-A reviewer acceptance

Decision: **M2-A accepted. M2-B is the next assigned checkpoint.**
The full M2 review gate remains open until M2.6 integration is implemented and
reviewed. This acceptance resolves R1–R7, R3a/R5a, and R5b.

## Accepted snapshot

Artifact: [m2-a-offline-provenance-v4.json](evidence/m2-a-offline-provenance-v4.json).

- Manifest identity:
  `2d5c726fc5a662d5dd3fef9dcc5911b2911d42c65daf8799d3114a03bb3079ef`.
- Artifact SHA-256:
  `eb1acea26dbc6f2685e9a8fa48af3acaa509a306788b23947f2914c9a2fa0bb9`.
- Reviewer validated the manifest, recomputed its identity, confirmed complete
  provenance-only capture, and compared the source manifest to the checkout.
- Accepted M0/M1 and submitted M2-A v1/v2/v3 artifact hashes remain unchanged.
  This identifies working-tree contents, not a new implementation commit.

## Independent verification

- Required dependency imports passed.
- Configured full discovery passed **189 tests in 138.647 seconds**, including
  real transaction CLI integration and subprocess interruption tests:
  `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`.
- Configured preflight exited zero, passed all five real construction checks,
  and performed an actual render.
- Reviewed the R5b failure-record/receipt reconciliation and its subprocess
  regressions, including interruption during recovery, original error-byte
  preservation, stable terminal outcomes, and rejection of mismatched evidence.
- Reviewed ID allocation history against both validated revision ancestry and
  committed receipt-bound allocation reports, including transient and nested IDs.
- Earlier review cases for lock deletion, sequential clone values, provisional
  issue references, strict request validation, and evaluation identity remain
  covered by the passing suite.
- `git diff --check` passed. Reviewer changes are documentation only. No model
  calls, dependency downloads, library edits, commits, or pushes were made.

## Accepted scope and limits

M2-A supplies an offline transaction core with private candidates, stable IDs,
construction-policy decisions, atomic revision publication, idempotent outcomes,
and recovery for the reviewed local process-crash boundaries. Candidate,
failed, aborted, discarded, and committed outcomes have distinct semantics.
Recovering an interrupted proposal does not automatically publish it.

This does not assert protection against arbitrary filesystem/hardware failure,
general real-world LEGO stability, final visual acceptance, or improved model
design quality. Synthetic policy reports are transaction tests; only the tiny
real fixtures establish checker/renderer integration. Clean installation remains
unverified; the configured local environment is the tested environment.

Legacy v1 tools still have their previous implementation. No transaction-backed
model execution is enabled. M2-B will connect those tool names to this service
for explicitly selected transaction workspaces, with versioned invocation
context and offline end-to-end tests. Runner execution and later acceptance/
visual/context work remain outside this checkpoint.
