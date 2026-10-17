# M2-B worker assignment — transaction-backed tool adapters

M0, M1, and [M2-A](M2-A-acceptance.md) are accepted. Implement **M2.6 and the
offline integration needed for final M2 review**. REVIEWER owns acceptance.

Review status: the first M2-B submission required
[bounded corrections B1–B5](M2-B-review.md). Their implementation and evidence are
recorded in [M2-B-completion.md](M2-B-completion.md). The
[bounded follow-up B1a/B2a](M2-B-review-followup.md) is resolved at v3.
[M2.6 and final M2 are accepted](M2-acceptance.md). Historical handback
instructions below are retained; no next milestone is assigned.

Worker: `01a13e93-2443-7062-862d-8a0acb823023` (WORKER).
Reviewer: `01a13e60-dd78-7500-b9bb-2bb826c84ad5` (REVIEWER).
The human authorized direct assignment and your completion message back. Preserve
that workflow. Read AGENTS.md, README, the workbench guide, canonical prompt,
Contracts C1–C3, and the accepted M2-A record before implementation.

Use `./.venv/bin/python` from the repository root and explicitly configure
`BRICKNET_DATA="$PWD/data/bricknet-data"` for real checks. Preserve the accepted
M0/M1/M2-A artifacts and unrelated checkout changes, including
`bricksmith-clean-view 2/`. No model/provider request, benchmark, download,
library mutation, commit/push, subagent, or M3–M7 work is assigned.

## Fixed compatibility and execution boundary

- [x] Implement the existing mutation tool names against explicitly initialized
  `bricksmith-transaction-state-v1` workspaces. The transaction service remains
  the sole publisher of their authoritative geometry/metadata. Add a small
  adapter module rather than another persistence engine.
- [x] Wire schema-aware dispatch through the existing tool entry point in
  `agent_session.py`, with explicit invocation context for transaction workspaces,
  and expose an offline CLI for the same dispatch. Do not implement a parallel
  demonstration function disconnected from the real dispatcher.
- [x] Preserve legacy v1 execution semantics as the historical baseline. A v1
  session is never silently upgraded, and its tools must never be described as
  transaction-backed. The new guarantees apply to explicit transaction workspaces.
  Keep M1 migration and `transaction-init-v2` as explicit, source-preserving paths.
- [x] Keep model `step`/`run` disabled for both inert M1 v2 snapshots and transaction
  workspaces. Error messages should explain that offline tool adapters are available
  but runner integration is pending M7. No provider call may occur before rejection.
- [x] Preserve the transaction workspace's authoritative state schema. Do not use
  legacy `_save`/`_assemble` to overwrite it, copy a second mutable module tree into
  authority, or synthesize legacy `module_order` as another source of truth.

This is the planned offline integration checkpoint. Live v1 behavior remains
isolated until the runner milestone; closing M2 will not claim live v2 generation.

## Invocation, replay, and publication

- [x] Define a strict versioned offline invocation envelope with tool name,
  unchanged tool-specific argument object, caller-supplied UUID operation ID,
  expected base revision ID, and expected assembled-export SHA-256. Include an
  explicit schema identifier, e.g. `bricksmith-tool-invocation-v1`.
  Mutation calls without this context must fail; never substitute the newest
  revision or infer which old line listing the caller meant.
- [x] Persist/bind the original tool invocation and its canonical argument hash
  to the normalized transaction intent before candidate application. Identical
  operation retries return the same candidate/terminal/committed result. Changed
  tool name, arguments, base, or export identity under the same operation ID fail,
  even if they happen to lower to equivalent geometry.
- [x] Allocate new entity IDs deterministically from operation ID plus a stable
  per-entity label/ordinal, or durably record allocations once before retries.
  Do not regenerate mappings from the latest state on retry. Resolve the declared
  immutable base once, then lower into one bounded transaction.
- [x] For compatibility mutation calls, propose and automatically commit only
  when M2-A says eligible, revalidating through its commit path. A blocked/failed
  proposal returns its evidence and leaves the current revision untouched.
  Provisional/repair-incomplete commits retain their exact labels and open issues.
  Do not discard rejected evidence or reproduce old collision-count rollback rules.
- [x] If another writer commits between proposal and commit, return the stale-base
  result and retained candidate; do not silently rebase/retry against new geometry.
  An interruption after proposal leaves an explicit uncommitted candidate; an
  identical retry returns its existing outcome without publishing it implicitly.
  The caller can use the explicit commit command to finish a staged candidate.
- [x] Results expose operation/candidate/base/current revision IDs, disposition,
  committed boolean, policy status/reasons, exact affected stable IDs, report
  references, and export identity. Preserve old response fields only where their
  meaning remains true. A saved candidate is not a saved current module.

## Tool mapping and identity decisions

Implement these names: `save_module`, `clone_module`, `discard_module`,
`recolor_module_lines`, `edit_lines`, `move_lines`, `move_groups`, `save_array`,
`save_floor`, `save_wall_runs`, `save_gable`, `save_stepped_roof_beams`,
`save_roof_tile_caps`, `save_support_column`, and `save_roof_seam_column`.

- [x] Module names resolve to exactly one assembly in the declared revision.
  Retain the existing safe-name rule for newly named modules. Reject ambiguous
  existing names; never choose the first match. IDs and verified map entries,
  not mutable filenames, determine ownership. Module views contain direct parts;
  selecting a whole assembly subtree remains the stable-ID transaction interface.
- [x] `save_module` replaces only the named assembly's direct part contents;
  preserve its identity, parents, children, constraints, relationships, and other
  ledger entries. Create an assembly if the name is new. With the existing
  name/LDraw arguments, replacement is explicit delete/add with fresh part IDs;
  do not guess identity from line positions, coordinates, or nearest matches.
  Explain this in the result and prompt, and reject replacements violating locks.
- [x] Parse through the supported M1 flat-LDraw rules. Preserve submitted type-0
  comments and exact input/source provenance as data, with M1 injection checks.
  Keep historical source evidence; update the target module's current comment
  view without deleting unrelated comments. Do not import caller text as user
  requirements or grant it user-owned locks.
- [x] `edit_lines` uses the exact base assembled export. A replacement preserves
  the selected stable part ID and ownership; deletion removes that ID. Reject
  duplicate/conflicting edits within one call and non-placement lines. Each
  replacement must contain exactly one valid placement, with no extra records.
- [x] `move_lines` and `move_groups` lower to exact world-space translation
  operations. Deduplicate lines within a selection. For overlapping groups, apply
  them in listed order and document that offsets accumulate; there is no silent
  double selection within a group. Keep existing argument bounds; the stable-ID
  core remains available for larger selections.
- [x] `recolor_module_lines` resolves module-local placement lines through that
  module's verified export map, preserving stable IDs, positions, and rotations.
  Verify both the assembled base identity and the module export/map integrity.
- [x] `clone_module` creates a distinct assembly and fresh part IDs, preserving
  physical catalog part types, colors, and orientations plus translated positions.
  Record `derived_from`. The old wording "preserves part IDs" means catalog IDs,
  not stable instance IDs; correct it. Reject destination-name collisions. Limit
  this compatibility tool to leaf modules; nested assembly cloning uses the core
  explicit maps, avoiding ambiguous descendant naming.
- [x] `discard_module` is an ordinary checked deletion transaction. Restrict it
  to leaf modules, retain historical evidence/requirements/issues, and honor locks
  and ground/collision policy. Reject dangling references; do not silently erase
  issues. It has no special bypass because the caller labels a module failed.
- [x] Every generator produces candidate content using its existing allowlisted
  pure geometry function, then uses the same module-replacement adapter. It must
  never invoke a legacy filesystem mutation path. Preserve generator arguments
  and generated content in invocation/operation evidence. Validate bounds before
  expansion and enforce limits after expansion; no executable generator names.

## Bounded bulk replacement — needed for existing module limits

Existing modules can contain 250 pieces, but the core allows only 64 operations.
Do not split a single save into multiple committed transactions or increase that
operation limit to hide this mismatch.

- [x] Add a versioned operation extension (`bricksmith-operation-v2`) supporting
  a logical `replace_assembly_contents` operation, while retaining the v1 reader
  and all existing v1 behavior. V2 includes the existing operations and a strict
  optional adapter-invocation record; reject unknown fields/types as before.
- [x] Bulk replacement names an existing assembly and supplies explicit final
  direct part records and validated current comment records for it. It may retain
  existing part IDs only through explicit supplied records belonging to that same
  assembly. Otherwise IDs must be fresh. Preserve all other design records.
  Replacement of the entire design document is not part of this operation.
- [x] Support assembly creation followed by its bulk replacement in one request.
  Apply bulk edits in sequence, include every created/deleted/affected identity
  in reports and lifetime allocation history, and use the unchanged core lock,
  issue-reference, validation, commit, and recovery checks. No special eligibility.
- [x] Retain 64 logical operations, 1 MiB serialized request (including invocation
  evidence), 250 physical parts per compatibility module, and 1,500 total physical
  parts. No unbounded nested operations or hidden batches. Repeated identical
  physical placements remain distinct parts and are checked normally.

## Reads, line-map safety, and documentation

- [x] Provide transaction-backed `read_module`, `inspect_build_region`,
  `inspect_alignment`, and `check` through the same dispatch. Read one sealed
  revision, verify its artifacts/maps, and return revision/export identities with
  line-based results. Never read the top-level compatibility export as authority.
- [x] Provide an offline `render` adapter for a current sealed revision using
  the existing renderer, retaining a distinct artifact and its source revision/
  export hash. This records render creation only; no delivery/review/acceptance
  claim or model image queue is introduced before M4/M5.
- [x] Unsupported transaction-session tools (including `set_plan`,
  `review_renders`, and `submit_design`) fail explicitly without falling through
  to legacy state mutation. General lookup and runner orchestration are not
  required for this bounded dispatch. Do not widen scope into M3/M4/M5/M7.
- [x] Add an offline schema/catalog command exposing only supported adapters,
  their required invocation context, and strict tool argument shapes. Keep the
  legacy tool schema available for legacy execution; version the new catalog.
  Record the new catalog hash in the M2-B provenance/settings as well as source
  identity, without rewriting historical manifests.
- [x] Update the canonical prompt, loader-alignment tests, README, workbench guide,
  and contracts for the new offline/legacy distinction, bulk operation extension,
  stale-line protection, replacement identity behavior, and construction statuses.
  Do not imply that live v2 model execution or final acceptance is implemented.

## Required verification and handback

- [x] Table-driven adapter tests exercise every mutation name through the actual
  dispatcher, proving it delegates to one transaction and cannot write current
  geometry directly. Synthetic reports must be clearly labeled; tests asserting
  just that a helper was called are insufficient for transaction behavior.
- [x] Cover ID-preserving move/recolor/line replace; delete/add module replacement;
  clone provenance/retry; ambiguous/unsafe names; comments; stale/forged maps;
  ordered overlapping groups; user-lock rejection; unavailable checks; and retained
  failed/provisional candidates. Validate safe paths for all new artifacts.
- [x] Save a >64-part module (e.g. 80 parts) and generate another through an
  existing generator, each as one commit. Test over-limit refusal and a multi-module
  move, demonstrating all-or-nothing state under actual process termination.
- [x] Exercise identical and conflicting invocation retries, stale base between
  propose/commit, crash after candidate seal and after pointer publication, and
  fresh-process recovery. Verify caller invocation hashes and mappings survive.
- [x] Through real CLI dispatch, migrate/import a small fixture, save a module,
  move/recolor/clone it, reject a collision regression without publishing, recover
  a retry, and check/render the committed revision. Keep fixtures original and
  portable; no dependency on private ignored runs.
- [x] Keep existing v1 tests passing, verify migration inputs byte-for-byte, and
  prove v2/transaction `step`/`run` reject before a mocked provider could be called.
  No live inference is needed to test any part of this assignment.
- [x] Run required imports, focused adapter/core tests, full discovery, configured
  preflight, and `git diff --check`. Preserve M0/M1/M2-A accepted artifacts and
  capture fresh numbered `m2-b-offline-provenance-v2.json` after final runtime changes.
- [x] Write `M2-B-completion.md` with exact changed entry points, schema/compatibility
  decisions, real versus synthetic tests, outputs/hashes, and limitations. Check
  M2.6 only when its evidence exists. Leave the final M2 review box open. Send
  REVIEWER the report and artifact paths under the existing authorization, then
  stop; do not start M3 or the official benchmark.
