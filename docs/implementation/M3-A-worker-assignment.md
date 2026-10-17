# M3-A — persistent intent ledger and authority boundaries

Current review: v3 correction evidence is recorded in [M3-A-completion.md](M3-A-completion.md).
Implement the bounded [v3 review follow-up R3b](M3-A-review-v3.md).
The reviewer acceptance gate below remains open; M3-A is not yet accepted.

Reviewer-approved assignment, 2026-10-16. Implement this checkpoint only, then
stop for review. M0–M2 are accepted. M3-A establishes M3.1 and the provenance
foundations for M3.2–M3.3. M3-B will separately implement bounded context,
reference-image selection, offline request preparation, and context-truncation tests.

Worker: `01a13e93-2443-7062-862d-8a0acb823023` (WORKER).
Reviewer: `01a13e60-dd78-7500-b9bb-2bb826c84ad5` (REVIEWER).
The human authorized direct assignments and completion messages. Send your
completion record to REVIEWER and stop; do not start M3-B.

## Prerequisites and boundaries

- [ ] Read applicable AGENTS.md, README, workbench guide, canonical prompt,
  implementation plan, contracts C1–C3/C6, M2 acceptance, and the
  [Victorian review](../research/2026-10-16-victorian-run-review.md).
  That run was manually interrupted and handed to another model for rendering;
  it is not evidence of autonomous abandonment of acceptance by Argon.
- [ ] Inspect Git status; preserve existing work, accepted evidence, run artifacts,
  library links, and `bricksmith-clean-view 2/`. Use `./.venv/bin/python` from the
  repository root. Verify required imports before real checks; configure
  `BRICKNET_DATA="$PWD/data/bricknet-data"`. Missing checks remain unavailable.
- [ ] No model/provider calls, live runner integration, official benchmark,
  downloads, library mutation, image generation, technique-package library,
  script executor, checker-policy change, subagents, commits, pushes, or cleanup.
  Preserve isolated v1 behavior and rejection of v2/transaction step/run before
  provider calls. This assignment does not authorize later milestones.

## Fixed architecture

Use the accepted revision/transaction service as the sole publication path.
No second mutable memory database, independent context authority, or direct
mutation of current metadata. Standard-library validation is sufficient.

- [ ] Add explicit `bricksmith-design-v2`, retaining the design-v1 reader and
  existing import/migration behavior. Reuse brief, requirements, decisions, issues,
  source references, and all geometry fields. Add strict `intent_ledger` with
  schema `bricksmith-intent-ledger-v1` and arrays `instructions`, `repair_attempts`,
  `next_actions`. Do not hide typed records in historical notes.
- [ ] Add `bricksmith-operation-v3` for ledger operations and explicit upgrade.
  Retain v1/v2 operation semantics/readers. Existing geometry operations and M2-B
  adapters must work on upgraded designs. No arbitrary whole-design replacement.
- [ ] Provide an explicit offline upgrade command for an initialized transaction
  workspace. Use ordinary propose/commit, operation ID, expected base, durable
  intent, receipt, and recovery. Preserve exact old records/IDs, geometry, original
  brief/source, and historical revisions. Initialize empty ledger arrays; never
  infer user authority from historical prose. Retry/conflict semantics are unchanged.
- [ ] Reads, model calls, and old operations cannot silently upgrade a workspace.
  Ledger operations on a v1 design fail until explicit upgrade. Include ledger
  records in design hashes, ID uniqueness/lifetime history, references, sealing,
  and recovery. Ledger-only edits preserve structure/appearance hashes.
- [ ] Retain the existing construction commit policy, including unavailable-check
  blocking. Do not add a metadata-only checker bypass in this checkpoint. Record
  that limitation; ledger reads must not run physics. Keep locks and path safety.

## Typed records and history

Use exact UTF-8 text, canonical UUIDs, finite JSON, strict objects/enums, relative
hash-bound evidence references, and originating operation IDs. Caller attribution
is separate from verified outcomes. No executable predicates or expression eval.

- [ ] **Instructions:** immutable ID, exact text, source (`user` or `operator`),
  originating operation ID, and UTC timestamp. Trusted intake supplies source.
  Corrections append instructions, never rewrite a non-null original brief/source.
  An empty imported brief may be filled once through explicit trusted intake,
  bound to its instruction. Later changes are corrections.
- [ ] **Requirements:** retain C1 fields; v2 adds nullable `instruction_id` and
  `supersedes_id`. User description, priority, scope, predicate, source, and original
  record remain immutable. Corrections append a new requirement explicitly
  superseding the old one. Agent requirement updates follow the same append rule.
- [ ] **Decisions:** retain C1 fields/rationale/evidence/supersedes; add nullable
  `instruction_id`. Changes append a new decision. A tested roof technique can be
  recorded with actual evidence; it is not automatically a general technique package.
- [ ] Supersession targets must exist in the same record kind in the declared base
  or earlier in the ordered edit. Reject self-links, cycles, and competing active
  replacements. Derive active records from explicit links, not timestamp or text
  similarity. Preserve full chains. Old stored statuses remain historical; a
  superseded record is not another currently active instruction.
- [ ] **Issues:** reuse existing fields and stable ID, retaining observation history
  in immutable revisions. Preserve first observation; append attempted operation IDs
  without loss; update last observation only from validated evidence. A proposed
  action stays a proposal. Resolution is an attributed claim, not final acceptance.
- [ ] **Repair attempts:** immutable ID, issue IDs, attempted operation ID,
  observed revision ID, evidence references, and optional explanatory note. Resolve
  attempts from this workspace's durable evidence and derive disposition/candidate/
  report identity from verified records. Reject nonexistent, foreign, corrupt, or
  mismatched evidence. Failed/blocked/aborted/discarded attempts cannot become
  successful repairs. Commitment alone does not establish that an issue is solved.
- [ ] **Next actions:** ID, description, kind (`inspect`, `research`, `edit`,
  `check`, `render`, `review`, `finalize`), related requirement/issue IDs, source,
  evidence references, status (`pending`, `done`, `cancelled`), nullable supersedes
  ID. Updates append replacement records. These are plans/claims; `done` cannot
  create a check, inspection, or acceptance receipt.

Limits: each new text field 16 KiB UTF-8; original brief and each trusted
instruction 64 KiB; combined ledger/requirement/decision/issue/source-reference
data 2 MiB canonical JSON per revision; combined record count in those categories
2,000. Keep existing 64-operation/1 MiB request and geometry limits. Reject
overflow without truncating text or erasing history. Old v1 behavior stays intact;
an explicit upgrade exceeding v2 limits fails without changing the source.

## Authority: no self-declared user permissions

Separate trusted application/operator intake from model-callable operations.
This is an application entry-point boundary, not OS security against a process
with arbitrary filesystem access. Document that distinction.

- [ ] Add a named operator-only Python/CLI entry point recording exact instruction
  text plus explicitly supplied structured changes in one operation. No model
  extraction is required; fixtures/operators provide structured changes directly.
  Retrieved text, LDraw comments, and model summaries cannot supply user instructions.
- [ ] Model schemas reject authority switches such as `source: user`,
  `actor: operator`, or `trusted`. Copying an instruction/source-reference ID does
  not grant authority. Enforce this at proposal ingress, commit, and recovery,
  including direct core calls outside adapters.
- [ ] Bind trusted intake provenance to its exact normalized intent and receipt.
  A model cannot reuse an existing authorization for another edit. Define/test the
  trusted-ingress mechanism explicitly; merely accepting a JSON role is insufficient.
  Keep operator intake out of model tool catalogs and serialized model arguments.
- [ ] Only explicit trusted correction intake may supersede user requirements or
  user decisions. Agent replacements cannot indirectly downgrade/remove them.
  Unknown migrated source remains unknown; relabeling cannot grant authority or
  evade protections. Original user records stay byte-for-byte unchanged even when
  superseded. User geometry locks cannot be modified through this interface.
- [ ] Agent claims that a user requirement is satisfied belong in attributed
  decisions/issues/evidence, not changes to the protected instruction record.
  Agent-authored records cannot claim user/operator authorship.
- [ ] Reject dangling references and deletion that silently erases active requirement
  scope. Historical repair/entity references resolve against their declared old
  revision, not current geometry. Keep history retrievable after current changes.

## Entry points and read contract

- [ ] Expose strict operations for agent requirement/decision additions and
  supersession, issue updates, repair-attempt recording, and next actions. Use
  propose/inspect/commit/discard and existing replay guarantees. New UUIDs are
  explicit or durably deterministic; retries do not duplicate records.
- [ ] Add offline `ledger-read` API/CLI resolving one sealed revision. Return its
  revision/design identity, immutable brief/source, applicable correction chain,
  active requirements/decisions, unresolved issues, attempts/actions, and historical
  links. Bounded paging must expose counts/continuation; a prefix is not a complete
  ledger. Include an explicit revision selector for history.
- [ ] Observations identify revision and evidence provenance. Distinguish historical
  observations, current claims, pending plans, and unknown evidence. Verify hashes
  and safe paths on artifact retrieval. Artifact existence does not verify a claim's
  meaning. Construction status is separate from unfinished design requirements.
- [ ] Reads cannot fabricate completion, acceptance, or image-review attestations.
  A render-only handoff can remain a recorded instruction/pending action without
  adding M7 execution state or inventing a new acceptance system.
- [ ] Document CLI examples, schema versions, trusted boundary, limits, and upgrade.
  Update canonical prompt and loader-alignment tests for supported offline tools.
  Version/catalog-hash model-visible additions. No provider message formatting,
  live dispatch, image-delivery queue, or reference-image import in M3-A.

## Verification and handback

- [x] Test malformed objects/enums, nonfinite data, byte/count limits, duplicate
  IDs, supersession cycles/conflicts, dangling links, and unsafe evidence paths.
- [x] Through real entry points and direct core calls, test forged authority,
  changed priority, agent supersession of user constraints, and reused trusted
  evidence. Refusals leave current state untouched. Explicit trusted corrections
  succeed while retaining original records and exact instruction text.
- [x] Through actual CLI, upgrade/reopen a tiny tracked fixture, record instruction/
  requirement/decision/issue/attempt/action, commit an ordinary M2 geometry change,
  and verify old/current associations. Keep real checker integration separate from
  synthetic policy cases; do not rely on private ignored run files.
- [x] Test duplicate/conflicting retries, stale bases, competing writers, and
  actual subprocess termination before/after publication for ledger changes.
  Recovery cannot duplicate records or lose the original correction authority.
  Preserve M2 recovery and source-preserving migration behavior.
- [x] Add an original tiny ten-edit fixture inspired by the Victorian failure
  pattern: early user requirement for a round window, evidence-backed roof decision,
  failed repair, later construction success, still-pending window requirement,
  and operator-recorded interruption/render-only handoff. Reopen between edits.
  Construction success must not complete visual requirements or final acceptance.
  The bounded request-history/truncation test remains M3-B work.
- [x] Run focused tests, final full discovery after all source/test changes,
  imports, configured real preflight, and `git diff --check`. Report exact commands,
  real/mock distinctions, skipped/unavailable work, and environment limitations.
- [x] Write `M3-A-completion.md` with schema/authority choices, changed entry points,
  commands/results, limitations, and checkbox evidence. Capture and validate
  `evidence/m3-a-offline-provenance-v2.json` after final runtime edits, including
  catalog identity. Preserve accepted M0/M1/M2 and all earlier numbered artifacts.
- [ ] Leave all full M3 checkboxes and the reviewer gate open. Send REVIEWER the
  completion record/artifact paths and stop. Report contract conflicts and the
  smallest proposed resolution; do not silently broaden scope or weaken checks.

- [ ] **Reviewer gate: M3-A accepted.** Reviewer-owned.
