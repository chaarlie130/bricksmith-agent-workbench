# M1 worker assignment — stable design state and explicit migration

Scope: **M1.1–M1.6 only**, from the implementation plan. **Accepted on 2026-10-15**;
see [M1 acceptance](M1-acceptance.md). This assignment and its correction pass
are complete. The checklist below is retained as the accepted scope; it does
not authorize M2 implementation or live model calls.

Read `AGENTS.md`, `README.md`, `docs/AGENT_WORKBENCH.md`, the canonical system
prompt, and Contracts C1–C2 before implementation. Consult C3 for the future
storage layout, but do not implement its transaction engine in this milestone.
Use `./.venv/bin/python` for every Python command.

## Prerequisite and baseline boundary

M0 acceptance is recorded in `M0-acceptance.md`. The accepted implementation is
currently a working-tree snapshot, not a new commit. Its accepted provenance
artifact is `evidence/m0-accepted-v7.json`, content identity
`a23a44205e6cd81857e8215bfb60ab5d4812b9546dc39876675b2edb71858b20`.
The original generator commit remains
`22cb7c8431117b51b6e3b79ab312719075b06df4`.

Inspect Git status first and record your actual starting state. Preserve the M0
artifact unchanged. Do not relabel it as an M1 manifest or a generated benchmark
result. Generate new provenance for M1 evidence. The clean-install limitation
remains disclosed. No official benchmark or model call is authorized here.

## Fixed implementation boundaries

- Add the design representation and offline import/export/inspection/migration.
  Existing v1 sessions continue operating as before. V2 sessions must refuse
  `step`, `run`, and mutation until M2 supplies atomic persistence. Refusal must
  happen before a model request or write. Do not maintain two writable authorities.
- Use standard-library records/validation and the existing catalog interfaces.
  New `design.py` and small serialization/migration helpers are appropriate;
  avoid a framework, service, database, or rewrite of the engine.
- Keep the runtime tool schema and canonical agent prompt unchanged unless an
  actual agent-visible behavior changes. `inspect_design` in M1 is an offline
  function/CLI capability, not a new live model tool.
- Require new destinations and refuse overwrite. Validate inputs before final
  publication, use a temporary output directory, and clean up failed temporary
  outputs. Do not implement M2's candidate, operation, lock, or recovery services.
- Preserve the unrelated `bricksmith-clean-view 2/`, libraries, historical runs,
  and existing user changes. Do not launch subagents, download dependencies,
  change authentication, commit/push, or run inference under this assignment.

## Implementation checklist

- [x] **M1.1 — schema and validation.** Implement `bricksmith-design-v1` and
  the inert `bricksmith-agent-session-v2` envelope using C1's minimum fields.
  Validate UUIDs, finite coordinates, matrix dimensions, ownership, ID references,
  acyclic assembly parents, and status enums. Reject malformed JSON types with
  useful field-specific errors. Keep unknown historical facts null/unverified.
  Ground Y and piece constraints come from explicit input/session fields; do not
  infer a different ground plane or budget from bounding boxes.
- [x] **Numeric policy.** Preserve serialized decimal values for lossless physical
  hashing. Do not route them through binary float before canonicalization or round
  to a geometry tolerance. Treat `1`, `1.0`, and negative zero consistently.
  Validate orthonormal rotations/reflections with maximum absolute residual
  `1e-6` for `R^T R - I` and `abs(abs(det(R)) - 1)`; reject scaling/shear without
  repairing the matrix. That tolerance is validation-only, not hash rounding.
- [x] **M1.2 — flat LDraw import/export.** Support type-0 comments and physical
  type-1 `.dat` placements. Reject MPD directives, submodel references, type-2–5
  geometry, malformed placements, and unresolved part/color identifiers with
  source-file/line diagnostics. Do not pass unknown geometry through a parser
  that silently drops it. Catalog unavailability is an explicit failure, not an
  empty catalog or successful validation. Preserve comments as source data,
  placement multiplicity, part IDs, colors, and transforms.
- [x] **IDs and hashes.** Allocate UUIDs once and persist them. Migration uses
  a documented fixed UUID namespace and input-content identity, module identity,
  and placement ordinal; absolute paths and time must not affect migrated IDs.
  Independent reimports need not preserve IDs across changed source bytes.
  Implement versioned file, appearance, structure, and design hashes per C2.
  Appearance/structure hashes ignore UUIDs and order but retain duplicate parts.
  No render cache or acceptance-evidence reuse is implemented yet.
- [x] **Exports and line map.** Produce deterministic `build.ldr` and assembly
  module views, with a line map tied to each exact export hash. Map every physical
  placement to its stable part/assembly IDs. Never derive stable IDs from the
  current exported line numbers. Regenerating an export cannot rewrite design IDs.
- [x] **M1.3 — inspection and selection.** Provide `inspect_design`, stable-part
  selection, and assembly selection including descendants. Return revision ID,
  selected stable IDs, piece count, and bounds; report line numbers only with
  their export identity. Parent-plus-child selection yields each part once.
  Unknown selectors fail explicitly. Selection does not mutate the document.
- [x] **M1.4 — generic design intent.** Represent assembly grouping, parent links,
  relationships, requirements, decisions, issues, source references, and locks
  under C1. Validate references. Roles such as roof are optional labels. Preserve
  supplied source/authority and unknown evidence; do not infer physical support
  from relationship records or turn prose into proven requirements. Defer model
  ledger-update tools and context composition to M3.
- [x] **M1.5 — explicit migration.** Read a v1 session without calling helpers
  that assemble, render, or rewrite it. Use `module_order` and module files as the
  source of placements; `build.ldr` is a derived artifact. Detect missing/duplicate
  module entries and reject source-path escapes. If a saved build disagrees with
  module geometry, report it and refuse migration instead of choosing silently.
  Map modules to assemblies, preserve the brief and explicit configuration, and
  retain old plan text as attributed historical prose. Historical checks/reviews
  remain historical; migration establishes no fresh acceptance or inspected view.
- [x] **Migration publication.** Write a new inert v2 destination using C3's
  initial revision/pointer layout. Preserve input byte-for-byte, including on
  failure. Resolve all written artifact paths inside the destination; refuse an
  existing destination and destinations inside the source. Record source file
  hashes and migration schema/version. Repeating against unchanged input in two
  destinations yields identical design IDs and semantic hashes; timestamps and
  diagnostic destination paths may differ. Unknown legacy fields must be reported
  as retained historical metadata or explicitly unmigrated, never silently invented.
- [x] **CLI and documentation.** Expose offline import, export, inspection, and
  explicit migration through documented CLI commands. Supply exact runnable
  examples using tracked tiny fixtures. A user should be able to inspect the
  resulting stable IDs and line map without running a model. Keep existing CLI
  behavior compatible. Explain that M1 adds representation, not better generation.

## Required evidence and tests

- [x] **M1.6 — identity tests:** duplicate identical placements remain two parts;
  reordered/comment-only/reformatted source has equal physical hashes; recolor
  changes appearance only; movement changes structure and appearance while the
  affected persisted part ID remains stable. Exercise moves/recolors on copied
  in-memory documents, without adding a live mutation tool ahead of M2.
- [x] Reject duplicate IDs/ownership, parent cycles, dangling references,
  malformed/nonfinite transforms, scaling/shear, missing parts, and unsupported
  input formats. Accept legal fractional offsets and orthonormal reflections.
  Include a small decimal change that must survive import, serialization, export,
  and hashing. Separately test behavior around the stated matrix tolerance.
- [x] Exercise the actual CLI for import → inspect → export, checking physical
  equivalence and every line-map entry. Test migration to two new destinations,
  source-tree hashes before/after, existing-destination refusal, malformed input,
  and failure without a published partial destination. Test v2 execution refusal
  before any provider dispatch or session mutation.
- [x] Keep pure schema/hash tests independent of installed geometry data. Use
  explicit catalog fixtures there; include real catalog resolution in integration.
  Run the prescribed dependency imports and full existing test discovery. A real
  tiny supported fixture must still check/render through the existing engine.
  No physics thresholds or expected fixture failures may change to accommodate M1.
- [x] Add `docs/implementation/M1-completion.md` with task IDs, files, exact test
  commands/outcomes, runnable demonstration, new provenance, and limitations.
  Mark only implemented task boxes; stop for review before M2.

The worker may choose helper names and internal organization. Changes to these
scope, identity, authority, publication, or compatibility decisions require a
recorded proposal for the planning agent rather than a silent deviation.
