# M2-A review — corrections required

Reviewer: REVIEWER. Review date: 2026-10-15 (user timezone).
Final status: **resolved; M2-A accepted at v4**. See
[reviewer acceptance](M2-A-acceptance.md). The following is the historical bounded
correction assignment, not a new authorization to repeat work.

Re-review update: the v2 submission fixes the original examples; remaining R3/R5
boundary cases are assigned in [the R3a/R5a follow-up](M2-A-review-followup.md).
Completion of the boxes below does not close that follow-up or the review gate.

The implementation has a useful core: immutable revisions, OS writer locks,
atomic pointer/receipt publication, real checker integration, and actual
subprocess crash tests. The existing tests pass, but the cases below violate
the assigned transaction contract. Passing the current suite is insufficient
to close the checkpoint.

## Independent verification

- Dependency imports passed using `./.venv/bin/python`.
- Configured full discovery passed: **174 tests in 143.678 seconds**.
- Configured `scripts/workbench.py preflight` passed: all five real construction
  checks and an actual render. `git diff --check` passed.
- Accepted M0 artifact SHA-256 remains
  `4f4c2722e4d492730aff84d8375000bc3edf8368c65ed7e1f70cb357b213f873`.
- Accepted M1 v2 artifact SHA-256 remains
  `6dbce8aec941c0e61267c9acb02651ac3c4d87d640bae013a56092717ce9a9fd`.
- Submitted M2-A v1 artifact SHA-256 matches the report:
  `dcaf955afcb3eb92a140d94ce6d339a14b80ba29c49f3661ef5eb50eb2afa9fc`.
- R1–R6 below include independent temporary-workspace or request-parser probes.
  Operation/policy probes deliberately used synthetic construction reports;
  they establish transaction behavior, not physical construction success.
  R7 is a source-inspection finding.

## R1 — preserve the user lock itself, including indirect deletion (P1)

Location: `transactions.py::_check_lock_change` and assembly deletion.

Reproduction: put a user-owned translation lock on an otherwise empty assembly,
targeting a part owned by another assembly. Delete the empty lock-holder
assembly. Proposal reports eligible with no conflicts, and commit succeeds.
A subsequent translation of the still-existing target also reports eligible.
The code compares the protected values but never checks that the lock survives.

- [x] Compare user-owned lock identities and their complete protective semantics
  between base and candidate, as well as protected target values. A model edit
  cannot remove a lock, change its owner/target, or reduce its fields.
- [x] For M2-A, reject deletion of an assembly containing a user lock; do not
  silently relocate or recreate it. Keep the existing prohibition on claiming
  user authority. Indirect assembly/subtree deletion and replacement must obey
  the same rule.
- [x] Add proposal and commit-path regressions for the two-step bypass above,
  direct protected-target deletion, and an allowed unrelated edit. The blocked
  proposal must leave the current revision and user constraints unchanged.

## R2 — clones must observe earlier operations in the same transaction (P1)

Location: `transactions.py::_apply`, `clone_assemblies` branch.

Reproduction: translate a source part by +20, then clone its assembly with a
+100 translation in the same request. The source ends at 20 but the clone ends
at 100 instead of 120. Clone reads `base`/`before_parts`, ignoring the sequential
candidate. It can also resurrect a source deleted by an earlier operation.

- [x] Preserve frozen selection membership from the declared base, but obtain
  each selected source record's values from the private candidate at the moment
  the clone operation executes. Missing/deleted selected sources are errors.
- [x] Preserve explicit ID maps, deduplication, and `derived_from`. Do not
  reselect new descendants based on an earlier membership change. If a selected
  source's current owner cannot be represented by the frozen assembly map,
  reject the operation clearly rather than reverting to base ownership.
- [x] Test transform→clone, recolor→clone, retained-ID replacement→clone,
  assembly metadata update→clone, and delete→clone. Verify exact candidate
  values and retry behavior, not only piece counts.

## R3 — deleted stable identities must not be reused (P1)

Location: freshness checks in `_apply` and revision history/state.

Reproduction: commit deletion of a part, then propose adding the old part record
with its old ID against the new revision. It is eligible. Freshness only checks
the immediate base/current request, so historical observations can accidentally
refer to an unrelated new object. Assembly creation has analogous gaps.

- [x] Enforce lifetime non-reuse for part and assembly IDs across committed
  workspace history, including IDs from the imported starting revision. Choose
  a durable used-ID registry sealed with revision/state publication, or derive
  it from validated revision ancestry; it must not depend on process memory.
- [x] Apply the rule to add, delete/add replacement, create assembly, and clone
  destination maps. Within a request, create→delete→create must also fail.
  Retained-ID replacement and edits of an existing object remain valid.
- [x] Keep global ID uniqueness across record categories. Do not let a fresh
  assembly/part use an ID belonging to another existing or historical entity.
- [x] Test separate committed operations, fresh-process reopening, and recovery
  after the publication failpoint. Identical operation retries must still return
  their original outcome without falsely treating their own IDs as new reuse.

## R4 — provisional repairs must not create dangling issue references (P2)

Location: `propose_edit`, automatic provisional/repair-incomplete issue creation.

Reproduction: delete one part of a two-part design with a synthetic report that
passes hard checks but fails connectivity. The policy permits provisional work,
but the generated issue copies deleted IDs from `summary.affected_ids`.
`validate_design` raises `DesignError` for an unknown affected ID, so a legitimate
deletion repair cannot produce the intended candidate. Repair-incomplete follows
the same path.

- [x] Keep operation summaries/evidence inclusive of deleted IDs. In the live
  design issue, reference only existing valid targets; retain the operation ID
  and saved base/candidate reports as the historical evidence for deleted objects.
  Do not weaken M1's reference validation or erase an existing issue.
- [x] Existing issues that would become dangling require an explicit valid
  `upsert_issue` in the same transaction; otherwise return a clear recorded
  candidate failure. Do not silently resolve them because their target vanished.
- [x] Exercise propose→inspect→commit→reload for both provisional deletion and
  an improving hard-violation deletion that remains repair-incomplete. Assert
  open issues, valid live references, retained historical evidence, and the
  appropriate non-final construction status.

## R5 — interrupted proposal staging needs a durable terminal outcome (P2)

Location: `propose_edit`, `inspect_candidate`, `discard_candidate`, `recover`.

Reproduction: a subprocess exits at `after_intent_flush`. Recovery reports the
operation as uncommitted, but a same-request retry forever returns
`status: staging, candidate_available: false`. Discard fails with
`operation has no candidate receipt`. Reporting the directory alone does not
provide usable reconciliation.

Reviewer decision for this bounded slice: **abort incomplete proposals on
recovery; do not automatically replay their operations**. Fully sealed candidate
receipts remain available for explicit commit/discard. Recovery never publishes
an uncommitted candidate.

- [x] For a durable intent without a complete, verified candidate receipt or
  recorded terminal failure, recovery writes a durable terminal `aborted` outcome
  with an interruption reason and retained evidence. Repeated recovery is inert.
- [x] Inspection and identical retries return that terminal outcome. Commit
  rejects it. Discard may return the same terminal outcome without changing its
  meaning. A deliberate retry uses a new operation ID against the current base.
- [x] Treat stored candidate failures as terminal diagnosable outcomes too;
  do not leave them undiscardable or report them as endless staging. Preserve
  argument-conflict detection for every durable intent.
- [x] Extend real subprocess tests at intent flush, partial candidate writes,
  report/receipt boundaries, and post-publication. Reopen and actually retry,
  inspect, discard, and recover; checking only that the pointer stayed old is
  insufficient. Preserve the valid candidate and post-commit recovery cases.
- [x] Keep `state.json` authoritative for committed outcomes. Remove the fallback
  that trusts an operation-local `disposition: committed` when no matching receipt
  exists in authoritative state; report that inconsistency rather than claiming
  a commit. Test this corruption case separately from process interruption.

## R6 — validate complete operation shapes before recording intent (P2)

Location: `_validate_operation` and request normalization.

Reproduction: transform with only a selector, and recolor without `color_id`,
both pass `normalize_request`. Their validation branches are unreachable because
the earlier selector branch consumes those types. `upsert_issue.status: []`
raises an uncontextualized `TypeError` instead of the documented input error.

- [x] Validate shared selector fields and each operation's own required fields
  independently. Remove unreachable duplicate branches. Missing fields, wrong
  types, nonfinite numbers, malformed matrices, and malformed enum containers
  must raise contextual `TransactionError` before intent/candidate creation.
- [x] Add a compact table of required-field/type regression cases for all
  supported operation types, including list/object enum values and integer
  fields receiving booleans. Verify the operation directory was not created.
- [x] Preserve the distinction between an invalid request and a valid request
  whose final candidate violates design/construction rules; the latter still
  retains its diagnosable evidence.

## R7 — bind eligibility to the actual checker environment (P2)

Location: `_data_identity` and `_evaluation_fingerprint`.

Source inspection: the fingerprint covers the mesh directory, three local files,
and interpreted reports. It omits the imported BrickNet source and its actual
package-data catalog/connector tree, which M0 already fingerprints separately,
and relevant dependency versions. Changing these inputs can leave the stored
eligibility fingerprint unchanged whenever the coarse report is the same.

- [x] Reuse the existing provenance primitives to capture a versioned,
  path-independent evaluation environment identity: relevant local checker/
  interpretation code and config, imported BrickNet source, actual package data,
  configured mesh data, and checker runtime/dependency versions. Missing or
  incomplete required identity blocks eligibility.
- [x] Save that identity with proposal evidence and recapture it under the
  commit lock. Any changed evaluation input requires a new proposal/revalidation,
  even when all five reported booleans happen to match. Do not hash the entire
  mutable workspace or unrelated documents into this identity.
- [x] Test source-only, package-data-only, mesh-only, and dependency-version-only
  changes with temporary fixture trees or explicit test seams. Keep checker
  reports constant to prove the environment identity causes rejection. Do not
  edit the real installed libraries. Retain location-independent equivalence.

## Return evidence and stop condition

- [x] Add regressions for R1–R7; run targeted units, real transaction CLI tests,
  full discovery, configured preflight, and `git diff --check`.
- [x] Update the M2-A completion record with exact outcomes and remaining limits.
  Preserve the submitted v1 provenance artifact; capture a fresh numbered v2
  artifact and identify both its manifest identity and file SHA-256.
- [x] Preserve accepted M0/M1 evidence and all original scope restrictions.
  Leave review gates open; no M2-B, later milestones, live calls, benchmark,
  downloads, commit/push, or unrelated cleanup.
- [x] Send REVIEWER the completed correction report under the human's existing
  authorization, then stop for re-review. Mark these correction boxes only after
  implementation and evidence exist; REVIEWER owns acceptance.
