# M2-A v3 re-review — R5b failed-proposal receipt recovery

Final status: **resolved in v4; M2-A accepted**. See
[reviewer acceptance](M2-A-acceptance.md). The text below records the historical
correction and reproduction.
R3a and R5a are addressed by v3. This assignment covers only the adjacent
failed-proposal publication boundary below. Do not start M2-B.

Reviewed v3 manifest validates as complete and its source manifest matches the
checkout. Manifest identity:
`7803a9a995a6501ae27b19800e33612196f4986407b08fa0eec26ef588733657`.
File SHA-256:
`da160df74b9be1473040b7c848d1128b571d0c525187eb443d0cdb1420ca0f84`.
M0/M1 and M2-A v1/v2 evidence hashes remain unchanged.

Independent verification of v3: **187 tests passed in 120.961 seconds**;
dependency imports, configured preflight (all five real checks and rendering),
and `git diff --check` passed. The remaining reproduction is outside that
currently passing suite.

## R5b — recover a durable proposal failure whose terminal receipt is missing (P2)

Implementation complete; awaiting reviewer acceptance.

Location: the exception path in `transactions.py::propose_edit` and existing
`failure.json` handling in `recover`.

Independent reproduction in a temporary workspace:

1. Use a valid operation request that deletes a part then transforms the same
   base-selected part. Candidate application correctly fails.
2. In a subprocess, terminate with `os._exit(88)` immediately after the durable
   `failure.json` write, before the `disposition: failed` receipt is written.
3. Reopen and call recovery twice. Both attempts raise
   `TransactionError: aborted failure evidence is invalid`.

The existing error record has `status: failure`, which is correct for an observed
candidate error. Recovery incorrectly requires it to have `status: aborted`.
This is distinct from interrupted proposal staging and the newly repaired
interruption during abort recovery. It uses no model calls or real library edits.

- [x] When a valid durable proposal failure exists without its terminal receipt,
  reconcile it into the same `failed` terminal disposition used by the normal
  proposal exception path. Preserve the original failure record byte-for-byte,
  including exception category, error text, and candidate-artifact reference.
  Do not relabel this observed error as an interruption or overwrite it.
- [x] Validate the failure's schema, operation ID, base revision against the
  durable intent, and required error fields before trusting it. Malformed or
  mismatched evidence fails clearly without overwriting it. Existing aborted
  evidence and complete candidate receipts retain their current handling.
- [x] Make receipt reconstruction idempotent and safe if recovery is interrupted
  again. Inspection, identical retry, discard, and repeated recovery return the
  same terminal failed outcome; commit is rejected and the current revision
  remains unchanged.
- [x] Add a real subprocess regression at the failed-proposal report/receipt
  boundary. Assert original failure bytes are preserved and a fresh process
  completes recovery. Test malformed/mismatched failure evidence separately.
- [x] Review the local terminal-outcome write boundaries for the three distinct
  outcomes (`candidate`, `failed`, `aborted`) so recovery handles each durable
  prefix; keep this confined to receipt reconciliation, not a new workflow.

## Return evidence

- [x] Run focused transaction/review tests, full discovery (including real CLI
  integration), configured preflight, dependency imports, and `git diff --check`.
- [x] Preserve v1/v2/v3 evidence. Capture v4 after final runtime changes, update
  the completion record, and report exact validation outcomes and hashes.
- [x] Leave review gates open and send REVIEWER the completion message under
  the existing human authorization. No M2-B, later milestones, model calls,
  benchmarks, downloads, commits/pushes, or unrelated cleanup.
