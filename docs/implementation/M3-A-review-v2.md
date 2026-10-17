# M3-A v2 review — bounded R3a follow-up

Date: 2026-10-16. Decision: **one correction remains; M3-A stays open**.
The R1, R2, and R4 implementation corrections are satisfactory for this review.
R3's paging and active-projection corrections are satisfactory; its issue
observation attribution needs the bounded correction below. Preserve those fixes.
M3-B and later milestones remain unassigned.

## Evidence reviewed

- Validated complete v2 provenance, identity
  `9be7b6b049c816d2dc80b454aa8604be5b35354ab17073dae758682770fc9631`;
  artifact SHA-256
  `bae59e0c9649df4a804b0e41be6725af21eb7c4ab0a708aef079c72a2b1b0a8b`.
  Its source fingerprint equals the current runtime source fingerprint.
- Runtime catalog SHA-256 remains
  `aa0eedcee28a69c81fde8bb74f32d52cd06aa9b166fe9927b623bfc098a41d56`.
  Accepted M0/M1/M2-A/M2-B evidence and M3-A v1 bytes remain unchanged.
- Independently passed required imports and configured real preflight, including
  all five construction checks and rendering. Output:
  `/tmp/bricksmith-m3a-review-preflight-v2.json`.
- Reviewed the new regressions and executed both focused reproductions below
  using temporary workspaces and the unit suite's synthetic validator.
  These probes establish ledger behavior, not physical construction quality.
- Worker reports 235 full-suite tests passed in 617.829 seconds. Reviewer started
  independent full discovery, then deliberately terminated it after reproducing
  R3a, before further source changes. That partial run is **not a pass**;
  log `/tmp/bricksmith-m3a-review-tests-v2.log`. Repeat full validation after R3a.

The disclosed staged-attempt limitation is accepted for M3-A: recording a repair
publishes a new revision, so a previously staged edit has a stale base. Retain
stale-base rejection and candidate-to-discard reconciliation. No special staged
commit flow or transaction-contract change is requested.

## R3a — reconstruct each issue observation from its own evidence (P2)

Location: `bricksmith/workbench/intent_ledger.py`, `ledger_read.claim_view`,
especially the issue `observations` projection.

Reproduction A, through ordinary successful operator intake:

1. Upgrade a tiny workspace. Create an open issue with no evidence references.
2. Update that issue to resolved and link the existing source reference.
3. Read the ledger. Both observation entries now list the later source reference,
   including the first observation, whose committed issue had an empty list.
   The top-level claim also combines the creation operation with current evidence.

Reproduction B: run the existing
`test_issue_decision_attempt_and_next_action_follow_validated_geometry_revision`
setup and inspect its issue observation entries and operation intents. The
geometry-only `transform` is labeled an `asserted_claim` observation because its
candidate contains the unchanged issue. A repair attempt is not itself a new
issue-status observation. This distinction matters for M3-B's historical context.

- [ ] Read each verified observation's issue fields and source references from
  that operation's own verified candidate, never from the current issue. Include
  the observed status and evidence IDs/hashes, with its operation/revision identity,
  so an earlier open observation cannot inherit a later resolved claim or evidence.
- [ ] Separate issue creation provenance from the provenance of its latest status
  assertion. Keep creation identity intact, but explicitly identify the operation
  and revision responsible for current status/evidence. Do not label a combination
  of old origin and new contents as one historical observation.
- [ ] Distinguish actual issue updates from attempted repairs. Check the verified
  operation's semantics when deriving observations; mere presence of a copied issue
  in a candidate is insufficient. Geometry-only attempts stay in repair history
  with their validated outcomes and must not become status observations. Preserve
  explicit treatment of checker-created policy issues; legacy entries without
  demonstrable observation provenance remain clearly historical/unverified.
- [ ] Add regressions for open/no-evidence -> resolved/with-evidence and a later
  reopen/change of evidence. Verify each historical snapshot and current read;
  verify a geometry-only repair does not create an issue observation. Check
  source hashes and latest-versus-creation attribution. Reads must not run physics
  or mutate sealed records. Retain bounded paging and active/full consistency.
- [ ] Run focused tests, then full discovery after final edits, imports, configured
  real preflight, and `git diff --check`. Update completion and any affected read
  contract documentation. Preserve v1/v2 and accepted evidence; export a fresh
  numbered M3-A v3 provenance artifact and verify source/catalog identities.
- [ ] Send REVIEWER the completion evidence and stop. Leave M3-A/full M3 gates open.
  No M3-B, live provider calls, benchmark, downloads, library mutation, commits,
  pushes, cleanup, or unrelated refactoring.

This follow-up concerns the derived read projection. Prefer reconstructing it
from existing immutable evidence; do not rewrite sealed historical revisions or
introduce a second mutable history store.
