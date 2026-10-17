# M2-B review — bounded corrections B1–B5

Resolved at v3: the original reproduction cases below and
[follow-up B1a/B2a](M2-B-review-followup.md) are resolved. This document retains
the historical v1 findings; [the full M2 gate is accepted](M2-acceptance.md).

Date: 2026-10-16. Decision: **corrections required; M2 review stays open**.
M2-A acceptance is unchanged. Implement only these corrections and the original
M2-B assignment's outstanding verification; do not start M3 or enable model runs.

The implementation uses the actual dispatcher and core transaction service and
preserves the legacy/v2 execution distinction. The submitted provenance validates
as complete and matches current source; its generated catalog matches runtime.
Manifest identity: `49b6544e75c84950c2de7408c0d20c2c74c174e899a00d9bc2ea987d1a3c6124`.
Artifact SHA-256: `c960cfe753db121e15e01308f7f130041dc22890b3a8096ad8c98156afcee53a`.
Accepted M0/M1/M2-A artifact hashes remain unchanged.

Independent verification of the final submitted checkout: dependency imports
passed; **202 tests passed in 275.537 seconds**; configured preflight passed all
five real checks and rendering; `git diff --check` passed. The findings below
identify behavior not established by that passing suite.

The reviewer reproduced the findings below in temporary workspaces. Mutation
probes used explicitly synthetic checker reports; renderer-path/interruption
probes used a fake renderer writing temporary bytes. These are control-flow
and filesystem tests, not construction/render-quality claims.

## B1 — replay the durable invocation outcome without regenerating it (P1)

Locations: `transaction_tools.dispatch`, `_propose_commit`, `_result`.

Observed: commit `save_support_column`, then replace its generator with a function
that raises. An identical retry raises that generator exception instead of
returning the committed outcome. Dispatch re-lowers every invocation before the
core sees its operation ID. A normal retry also returns `affected_ids: []` and
`policy_status: null` where the first result contains affected IDs and
`construction_passed`, because the committed receipt is treated as a report.
Even the first successful commit reports `stale_base: true` simply because its
own commit advanced the pointer.

- [ ] Before running generators/parsers/lowering for an existing mutation ID,
  validate the submitted invocation against its durable original invocation and
  reconcile the existing operation. Use authenticated report/receipt evidence,
  not a newly generated request, to return the existing outcome. Reject changed
  arguments/tool/base/export identity without running their generator.
- [ ] For committed outcomes, use the authoritative state receipt and its
  hash-verified report to reconstruct stable operation results. Preserve affected
  IDs, policy status/reasons, candidate identity, generator/clone details, and
  invocation identity across retry. Current workspace status/export may advance
  separately, but must be clearly separated from the original operation outcome.
- [ ] Keep receipts and candidate reports distinct in result assembly. A successful
  commit is not a stale-base failure. Terminal failed/aborted/discarded operations
  must not report `commit_eligible: true` from an older staged report. A stale
  uncommitted candidate is ineligible pending a new proposal; preserve its original
  report as historical evidence rather than presenting it as current eligibility.
- [ ] Keep the accepted rule that a retry of an already staged candidate does
  not auto-publish it. Recovery-required incomplete staging must remain explicit.
- [ ] Test committed retry with generator/parser mocked to fail if called, retry
  after a later unrelated commit, conflicting invocation reuse, provisional and
  repair-incomplete committed replay, and each noncommitted terminal outcome.
  Compare meaningful result fields, not only revision IDs or the committed flag.

## B2 — contain and durably publish offline render artifacts (P1)

Location: `_dispatch_read`, render branch.

Observed: replace the workspace's empty `evidence/` directory with a symlink to
a sibling temporary directory. `render` reports success and writes PNG/JSON files
outside the workspace. Only `evidence/renders` is checked for being a symlink;
its parent is not. A renderer that writes an image and then raises also leaves
an image-only artifact which makes every identical retry fail with
`Existing render artifact is unsafe`.

- [ ] Validate all workspace-internal path components before artifact directory
  creation or writes. Reject symlink escapes through `evidence`, `renders`,
  staging directories, images, or metadata, including dangling symlinks. Do not
  remove/overwrite external targets. Retain the existing canonical-root handling
  for ordinary macOS parent paths outside the workspace.
- [ ] Publish each render's image and metadata as one sealed artifact unit, e.g.
  a private directory atomically renamed into an operation-ID destination after
  files/directories are flushed. Use the workspace writer lock (or equivalent
  tested exclusion) so two callers cannot race to overwrite the same evidence.
  Incomplete staging is retained or safely reconciled on retry, never mistaken
  for a completed render and never made a permanent normal retry dead end.
- [ ] Bind the final artifact to the complete invocation. Reusing one render
  operation ID with a different view/source/arguments must conflict, rather than
  creating another artifact because the filename contains the view. Identical
  retries verify/reuse the completed image and metadata without rerendering.
- [ ] Add temporary-directory escape tests and actual subprocess interruption
  before/after render publication, plus a competing-writer test. Validate source
  and artifact hashes and show retry/recovery does not overwrite accepted output.
  This is artifact persistence only; do not add M4/M5 delivery or visual-review
  machinery.

## B3 — support decimal array inputs through the real JSON path (P2)

Location: `_args_to_ldr('save_array')` and its legacy expansion helper.

Observed: an otherwise valid invocation with `step_x: [Decimal('0.5'), 0, 0]`
fails with `Each step must contain three LDU coordinates within ±2000`. The CLI
intentionally decodes JSON fractions as Decimal, the new schema accepts numbers,
but the reused legacy helper accepts only int/float. That helper also converts
source positions to float and formats six decimal places.

- [ ] Make the transaction array adapter accept finite Decimal/int inputs from
  the JSON decoder and preserve exact coordinate arithmetic using the M1 helpers.
  Do not solve this by converting everything to float or rounding stored geometry.
  Keep legacy v1 expansion behavior isolated if necessary.
- [ ] Preserve bounds, counts, template-part limits, part multiplicity, and
  nonfinite/bool rejection. Validate the source through the supported flat-LDraw
  path; caller comments remain data and raw invocation provenance remains saved.
- [ ] Exercise fractional steps through the actual CLI decoder, tiny nonzero
  source coordinates, zero offsets, and low ambient Decimal precision. Assert
  exact generated positions, persisted evidence, and deterministic retries.

## B4 — enforce the assigned module boundary and optional core metadata (P2)

Locations: clone lowering and operation-v2 normalization.

Observed: a 251-part imported leaf is cloned into a new 251-part module without
the compatibility module cap being applied; the total can still be below 1,500.
The new core operation-v2 also requires `adapter_invocation`, contrary to the
assignment's optional adapter metadata: direct bulk transactions must currently
invent a tool invocation to use the core extension.

- [ ] Enforce the 250-part compatibility module ceiling before clone construction,
  as already done for saved/generated modules. Keep the separate 1,500-part total
  core ceiling. Do not lower or commit an over-limit clone just because its source
  came from a larger imported design. Test exact-limit and over-limit cases.
- [ ] Make adapter metadata optional for direct operation-v2 requests. When it is
  present, validate its complete shape/identity strictly; adapter dispatch must
  still require it and bind it to the original invocation. Do not fabricate source
  tool identity for a direct core call. Retain the v1 reader unchanged.
- [ ] Add a direct core bulk-replacement test without adapter metadata, a strict
  malformed-metadata rejection test, and the required adapter cap tests.

## B5 — complete the required end-to-end failure coverage (P2)

The report correctly discloses that adapter process-kill and provisional/
repair-incomplete tests were omitted. They were explicit M2-B acceptance items;
the M2-A tests do not establish correctness of the new wrapper's replay and result
translation. B1 demonstrates why those boundaries matter.

- [ ] Add real subprocess termination through the actual adapter dispatcher after
  candidate sealing and after pointer publication. Reopen in a fresh process,
  retry/recover, and verify one complete original/new revision with no duplicate
  module, moved group, or generator allocation. Cover an 80-part save and a
  multi-module movement. Exception-only simulation is supplementary.
- [ ] Through dispatch, exercise synthetic provisional, improving repair-incomplete,
  blocked hard regression, and unavailable-check results; verify statuses, issues,
  policy reasons, eligibility, and authoritative state before and after replay.
- [ ] Add any still-missing required forged-map, limit, and source-preserving
  migration regressions. Keep real CLI construction/render tests separate from
  synthetic transaction-policy cases and document their exact coverage.
- [ ] Run full discovery after the final code AND test changes, plus configured
  preflight, imports, and `git diff --check`. Do not report an earlier full run as
  validation of a later source snapshot without qualification.
- [ ] Update the M2-B completion report and supported checklist boxes. Preserve
  v1 provenance; create a fresh numbered v2 artifact after final runtime edits,
  including the final catalog identity. Preserve accepted M0/M1/M2-A artifacts.
- [ ] Leave M2.6/final M2 review pending reviewer acceptance. Send REVIEWER the
  correction evidence under the existing human authorization and stop. No M3,
  live inference, benchmark, dependency download, commit/push, or unrelated work.
