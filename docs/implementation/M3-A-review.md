# M3-A v1 review — corrections R1–R4

Date: 2026-10-16. Decision: **corrections required; M3-A remains open**.
Implement only these corrections and the original assignment's verification.
M0–M2 remain accepted. M3-B and later milestones are not assigned.

## Reviewed evidence

The reviewer verified the complete v1 manifest and exact current source match:
identity `9266395996ca27452f404e71392c57ecf92b2538e34ac18a9adac2eeff56fd77`,
artifact SHA-256 `3f68229be29262163374ece5787d0ad5629a57271d85aefb9223d2f019d0311c`.
The saved catalog matches runtime serialization, SHA-256
`aa0eedcee28a69c81fde8bb74f32d52cd06aa9b166fe9927b623bfc098a41d56`.
Accepted M0/M1/M2-A/M2-B and earlier M2-B evidence hashes remain unchanged.

Independent checks: required imports, **6 ledger unit tests in 4.706 seconds**,
configured preflight with all five real construction checks and renderer, and
`git diff --check` passed. The worker reports 225 full-suite tests in 467.358s;
the reviewer has not repeated that full run for this blocked submission.
Reviewer output is in `/tmp/bricksmith-m3a-review-unit-v1.log` and
`/tmp/bricksmith-m3a-review-preflight-v1.json` (temporary local files).

The following reproductions use temporary workspaces and the unit suite's
explicitly synthetic all-green validator. They test persistence/contracts, not
construction quality. One integrity probe deliberately corrupts a local receipt;
it is not a claim of an OS security boundary against arbitrary filesystem access.

## R1 — repair outcomes must derive from authoritative, source-bound evidence (P1)

Locations: `transactions._verify_attempted_operation`,
`intent_ledger._attempt_outcome`, repair record creation/read paths.

Reproduction: create an upgraded workspace and an issue, propose an ordinary
geometry edit without committing it, then change only its operation-local
`receipt.json` to `disposition: committed` and `revision_id: candidate_id`.
Record that operation as a repair through ordinary operator intake and read it.
The recording commits and returns `verified: true, disposition: committed` even
though the attempted operation is absent from `state.json.receipts` and its
candidate was never published. Report/candidate hashes were not altered.

A second probe changes a real committed attempt's `observed_revision_id` to its
parent (which contains the same issue); verification accepts it. Currently any
sealed revision containing the issue suffices, with no stated relationship to the
attempt's actual source/result. This makes observation provenance ambiguous.

- [ ] Treat the authoritative state receipt as the sole evidence of commitment.
  An operation-local committed claim without that receipt is corruption or
  recovery-required evidence; reject it rather than label it verified. Retain
  proper handling of genuine staged, blocked, failed, aborted, and discarded work.
- [ ] Use one verified outcome resolver for recording and reading; do not validate
  once and then independently reread weaker evidence in `_attempt_outcome`.
  Bind intent, candidate/report, terminal failure evidence where applicable, and
  receipt identity/hash/disposition. Missing/corrupt/symlinked required evidence
  must not turn into a verified outcome. Reuse existing M2 verification helpers
  where appropriate; do not build a weaker parallel receipt interpreter.
- [ ] Define exact observation semantics. Keep issue-observation/recording revision
  distinct from the attempted operation's base and candidate/result revisions.
  A recorded observation revision must have a validated documented relationship
  to that attempt; arbitrary same-issue revisions are insufficient. If a separate
  field is necessary, version the affected new schema before acceptance. A blocked
  candidate need not be a published revision, so verify its private candidate via
  its operation evidence instead of requiring publication to record a failure.
- [ ] Distinguish outcome at recording from outcome at read time if an initially
  staged attempt later commits/discards. Preserve immutable historical observation
  and label any current reconciled outcome separately. Do not silently rewrite
  the meaning of an old revision's repair observation.
- [ ] Add regression coverage for the forged local committed receipt, missing/
  corrupt terminal evidence, unrelated observation revision, genuine committed
  and failed outcomes, and a staged attempt changing disposition after recording.

## R2 — enforce v2 ledger invariants through every ingress (P2)

Locations: `operator_intake`, operation/record validation, and
`_validate_ledger_authority`.

Reproductions:

- A v3 `ledger_update_issue` with 20,000-byte `kind` and `next_proposed_action`
  becomes commit-eligible despite the assigned 16 KiB per-new-text limit.
- `ledger_update_issue.status: []` raises `TypeError`, not the documented
  validation error. `operator_intake(fill_brief="false")` is accepted and fills
  an empty brief because the string is truthy; a wrong JSON type changes intent.
- On an upgraded design, an operation-v2 `upsert_issue` can create a brand-new
  `resolved` issue and obtain a commit-eligible candidate, bypassing the v3 rule
  that new issues cannot begin resolved. The guard keys off request version
  instead of the target design's invariant.

- [ ] Validate exact types before enum membership, truthiness, string methods,
  or application. In particular require boolean `fill_brief`, typed source/text/
  timestamp, and safe list/object enum rejection. Malformed inputs must produce
  consistent `ValueError`/`TransactionError` diagnostics without publication.
- [ ] Enforce the assigned text/aggregate/count bounds across all new ledger
  fields, including issue fields, with exact-boundary and UTF-8 multi-byte cases.
  Do not change accepted untouched v1 records to make them fit new limits.
- [ ] Enforce upgraded-design ledger invariants regardless of the request envelope.
  Reject legacy issue mutations against design-v2 or deliberately lower them
  through the strict ledger path. Preserve legacy behavior on actual design-v1
  workspaces and old geometry-operation compatibility on upgraded workspaces.
- [ ] Test otherwise-valid requests for each failure so rejection cannot be caused
  by an unrelated malformed UUID/record. Verify unchanged current state and proper
  retained failure evidence where the transaction boundary has already been entered.

## R3 — bounded ledger reads must preserve attribution and evidence meaning (P2)

Location: `intent_ledger.ledger_read` and derived collection projections.

Reproductions: after a trusted requirement intake, `requirements.items[0]` has
`authority_verification: verified`, but the same record in `active_requirements`
has no authority annotation, because the projection is copied before annotation.
With `limit=1`, the read also returns the entire three-entry `revision_chain`;
that field grows without any paging limit as edits accumulate.

- [ ] Decorate/verify records before deriving active views. The same record must
  expose consistent source/authority/evidence qualification in active and full
  collections, including unverified historical source claims after upgrade.
- [ ] Page revision history as well as ledger collections, with explicit total/
  continuation semantics. No field may silently return unlimited revision history
  despite a bounded read request. Keep complete history retrievable.
- [ ] Label model-authored issue/requirement/decision observations as claims with
  originating revision/operation and evidence provenance. A checker being available
  does not prove an unrelated visual issue has been observed or resolved. Preserve
  the distinction between actual construction results and asserted design progress.
- [ ] Test multiple pages over more than ten revisions, consistent full/active
  authority annotations, historical reads after later edits, and readable pending
  visual requirements after successful construction checks. Reads must remain
  free of physics/model calls and must not mutate sealed records.

## R4 — complete the assigned behavioral verification (P2)

The ten-event JSON fixture is a description, not execution evidence. Its current
sequence even describes repair events before creating their issue; adapt it into
valid explicit transactions rather than merely asserting its labels. The worker
correctly disclosed this gap, but it remains an acceptance requirement.

- [ ] Execute an original ten-edit lifecycle with real ledger operations and
  reopening between edits. Preserve early user requirement, evidenced decision,
  genuinely failed repair, later checked progress, pending round-window requirement,
  and explicit operator interruption/render-only handoff. Verify persisted state,
  history, identities, and attribution. The entire sequence need not use ten CLI
  subprocesses; keep representative real CLI integration plus fresh-load assertions.
  Context-window truncation itself remains M3-B work.
- [ ] Add M3-specific before-publication process-death recovery and competing-writer
  coverage, plus conflicting retries, stale base, and trusted-evidence reuse for
  a different edit. Retain the existing after-publication test. Generic M2 tests
  do not establish the new authority/provenance behavior by themselves.
- [ ] Correct the existing protected-user supersession regression: its forged
  record currently uses `originating_operation_id: None`, so it can fail UUID
  validation before reaching the intended authority check. Use a fully valid
  agent record and assert the specific authority refusal and unchanged state.
- [ ] Cover supersession self/cycle/branch cases, actual malformed inputs, boundary
  sizes/counts, and unsafe/corrupt evidence with meaningful expected outcomes.
  Test the new promises; a checked assignment box is not substitute evidence.
- [ ] Run focused tests, final full discovery after all source/test edits, required
  imports, configured real preflight, and `git diff --check`. Update completion and
  assignment checkboxes to match demonstrated behavior and disclose remaining limits.
- [ ] Preserve v1 and all accepted evidence. Create a fresh numbered M3-A v2
  provenance artifact after final runtime changes and validate source/catalog
  identity. Send REVIEWER the evidence and stop. M3-A/full M3 gates stay open;
  no M3-B, later milestones, live calls, benchmark, download, commit, or push.
