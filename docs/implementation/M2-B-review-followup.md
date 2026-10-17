# M2-B v2 re-review — bounded corrections B1a and B2a

Resolved at v3: [M2 reviewer acceptance](M2-acceptance.md). The findings and
v2 decision below are historical; all follow-up items are now verified.

Date: 2026-10-16. Decision: **two corrections required; M2 remains open**.
M2-A remains accepted. The original B1–B5 reproduction cases are corrected;
these two remaining cases concern the same result-authority and render-retry
contracts. Implement only this follow-up, then stop for reviewer acceptance.

## Independent evidence

- Required dependency import passed. Full discovery passed **216 tests in
  335.164 seconds** on the submitted v2 runtime snapshot.
- Configured preflight passed all five real construction checks and actual
  rendering. Reviewer output: `/tmp/bricksmith-m2b-review-preflight-v2.json`.
- The v2 provenance validates as complete and its source manifest matches the
  checkout. Runtime catalog bytes match the saved catalog.
- Manifest identity: `d842deb5d29ba203170244d5390a2b0e7f61c51e1213a1b3ad57a59d76472544`.
  Artifact SHA-256: `8a0d16f0a4e697b5d52f2a470852f141b5e97091692522bf65256c3fce5442b7`.
- Accepted M0/M1/M2-A artifacts and M2-B v1 are byte-identical. `git diff --check`
  passed. The reviewer probes below use temporary workspaces, synthetic checker
  reports, and fake renderer bytes; they establish control-flow defects, not
  construction or visual-quality results.

## B1a — keep adapter metadata separate from authoritative outcomes (P1)

Locations: `transaction_tools._result`, operation-v2 adapter evidence validation,
and report construction in `transactions.py`.

Observed through supported core proposal plus adapter replay: lower a normal
`save_module` invocation with `_mutation_request`, supply
`adapter_evidence.result_metadata` containing `committed: true`,
`disposition: "committed"`, `status: "accepted"`, and `commit_eligible: true`,
and propose it with a synthetic unavailable checker. The real proposal reports
`commit_eligible: false` and `status: "blocked"`. An identical adapter dispatch
then returns the supplied success fields, although the state pointer is unchanged
and no authoritative receipt exists. No on-disk hash forgery is required.

The cause is unrestricted `result.update(saved_extra)` after authoritative result
assembly. Hashing caller-supplied metadata preserves its identity; it does not
make that metadata an authoritative transaction result.

- [x] Keep tool-specific details in a separate explicit namespace or use a strict
  allowlist of non-authoritative detail keys. Decide the smallest compatible
  representation and document it. Never allow saved or immediate extras to
  override schema, tool/invocation identity, operation/revision IDs, disposition,
  commit/status/eligibility fields, policy fields, affected IDs, evidence
  references, receipt, or export identity.
- [x] Validate the permitted metadata shape at the core boundary and defensively
  assemble results so stored metadata cannot fabricate success. Retain legitimate
  generator/clone details and deterministic replay. Reject unsupported metadata
  before publication, or preserve it solely as explicitly non-authoritative data.
- [x] Add the direct-core-to-adapter regression above. Verify blocked and staged
  results cannot claim commitment; exercise committed, provisional, and terminal
  replay with colliding metadata and assert outcome fields agree with actual
  state/receipt/policy evidence. Test both saved metadata and immediate extras.

## B2a — reserve render invocation identity before rendering (P2)

Location: `transaction_tools._render_revision`.

Observed: render `front_left`, interrupt at `render_before_publish`, then dispatch
the same operation ID/base/export with view changed to `top`. The adapter deletes
the original private stage and publishes the changed invocation successfully.
The original stage already contained image and invocation-hash metadata. A crash
earlier than metadata creation likewise leaves no durable invocation binding.
The existing changed-view test covers only an already published render.

- [x] Persist a durable render invocation reservation under the writer lock before
  calling the renderer or creating its output. Bind the complete validated
  invocation and source identity; flush the reservation and its parent using
  existing durability helpers. Validate existing reservations before reconciling
  stages. Keep this within offline artifact persistence, not future visual review.
- [x] Reusing a reserved operation ID with different view/source/arguments must
  conflict before deleting existing staging evidence or invoking a renderer.
  Matching retries may safely reconcile an interrupted stage and publish exactly
  one artifact. A reservation or image-only stage is never a completed render.
- [x] Preserve all path-containment/symlink and writer-exclusion guarantees.
  Validate reservation contents and reject malformed or conflicting evidence.
  Do not overwrite a completed artifact or silently discard an invocation binding.
- [x] Add actual subprocess-termination cases after reservation/before metadata
  and immediately before publication. In a fresh process, conflicting retries
  must fail without renderer calls or evidence loss; matching retries must recover.
  Retain the existing after-publication/no-rerender coverage.

## Completion and boundaries

- [x] Run targeted regressions and final full discovery after all runtime/test
  edits, required imports, configured real preflight, and `git diff --check`.
- [x] Update completion evidence and checklist claims, distinguishing synthetic
  policy/persistence tests from real checker/render results. Reconcile any stale
  test-count prose rather than mixing earlier and final suite counts.
- [x] Preserve all prior provenance artifacts. Capture a fresh numbered M2-B v3
  manifest after final runtime changes and verify it and the catalog identity.
- [x] Leave M2.6 and the final M2 acceptance box open. Send REVIEWER the completion
  report and evidence under the human's existing authorization, then stop.
  No M3+, model calls, benchmark execution, downloads, library changes, commit,
  push, or unrelated cleanup is authorized by this assignment.
