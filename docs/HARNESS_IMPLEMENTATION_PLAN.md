# BrickSmith harness implementation plan

Status: M0, M1, and M2 accepted. M3-A v3 requires bounded R3b correction; M3-B and M4–M7 have not started.
Prepared: 2026-10-15.
Inspected starting commit: `22cb7c8431117b51b6e3b79ab312719075b06df4`.

## Purpose and ownership

Build a harness that reliably turns a brief into a complete, editable,
construction-checked LEGO design. Improve the model's ability to maintain
intent, make coordinated revisions, learn construction techniques, and recover
from failure. Preserve the existing construction engine and canonical prompt.

The planning/review agent owns architecture, acceptance policy, benchmark
protocol, and changes to scope. A worker implements **one assigned milestone**,
including its tests and documentation, and returns evidence for review.
Local implementation details that do not change these contracts belong to the
worker. This is not an instruction to launch other agents or model requests.

Read these companion documents before starting:

- [Contracts](HARNESS_CONTRACTS.md): authoritative behavior and data boundaries.
- [Worker handoff](WORKER_HANDOFF.md): ready-to-use assignment and completion format.
- [Benchmark draft](BENCHMARK_PROTOCOL_DRAFT.md): evaluation design; not an active benchmark.

`AGENTS.md`, `README.md`, `docs/AGENT_WORKBENCH.md`, and
`bricksmith/workbench/system_prompt.md` remain required reading. When this plan
proposes a future behavior, existing runtime behavior does not change until the
implementation, prompt, tests, and documentation are updated together.

## Decisions fixed for this implementation

1. Keep Python, the repository `.venv`, LDraw, the existing physics/rendering
   infrastructure, and local reference provenance. Do not restart the project.
2. Add a versioned design document with stable part and assembly identities.
   LDraw is the physical interchange/export format; the document stores editable
   placements and design intent. Derived exports must not become competing state.
3. Use a single-writer, file-backed revision store with immutable snapshots and
   atomic publication. No database, distributed scheduler, or web service is needed.
4. Use one design agent. Planning, construction, and review are work phases,
   not a requirement for multiple model agents.
5. Retain raw placement authoring and existing generators. Add general assembly
   operations before adding more subject-specific tools. Arbitrary model-written
   Python execution is deferred pending a separately reviewed execution boundary.
6. Separate construction evidence, workflow evidence, brief satisfaction, and
   visual judgment. No metric is allowed to stand in for the others.
7. Preserve all five existing construction checks. Add explicit coverage and
   provenance; never reinterpret missing support as a pass.
8. Establish the baseline and evaluator before relying on post-change results.
   The exact benchmark briefs, model configuration, and live spending limits
   will be selected in the benchmark setup phase, not guessed by a worker.
9. Implementation and regression testing default to offline operation. Fake
   provider responses may test orchestration; they cannot establish design quality.
10. Preserve existing entry points with documented compatibility adapters.
    Do not silently rewrite old runs or relabel their historical acceptance.

## Current evidence and constraints

The current runner already has persistent modules, revisions, checks, render
digests, provisional stages, and a useful tool interface. Its context includes
the brief, a prose plan, geometry summary, and approximately two tool turns.
Its editing paths have different rollback rules and line-based moves are bounded
to 30 placements. Direct acceptance and `submit_design` implement different
workflow requirements. Visual review uses supplied text and a changed placement
digest; that is iteration evidence, not an independent quality measurement.

Existing `tests/test_acceptance.py` reads models from ignored `runs/` directories.
The LDraw/BrickNet data directories are machine-specific symlinks, dependency
versions are not fully pinned, and image/run patterns are ignored by Git. These
are concrete obstacles to a reproducible benchmark and fresh-checkout testing.

The untracked `bricksmith-clean-view 2/` directory is unrelated user state. Do not
modify, stage, delete, or use it as the implementation source.

## Milestone order and review rules

| Milestone | Outcome | Prerequisite |
| --- | --- | --- |
| M0 | Reproducible tests and baseline provenance | None |
| M1 | Stable design state and explicit migration | M0 |
| M2 | Atomic, recoverable edits across assemblies | M1 |
| M3 | Persistent design intent and bounded context | M2 |
| M4 | Common acceptance, checker coverage, spatial diagnosis | M2; integrate M3 requirements |
| M5 | Comparable visual alternatives and revisions | M3, M4 |
| M6 | Tested construction-technique library | M4, M5 |
| M7 | Durable bounded runner and end-to-end demonstration | M2–M6 |
| B0–B3 | Official benchmark setup and first comparison | See benchmark draft |

The first functional slice is M0–M5. M6 and M7 extend it; do not defer all
integration until the end. Each milestone needs a coherent testable result.
Prepare the benchmark baseline after M0, before changing generation behavior.
Benchmark tooling can evolve separately from the frozen generation checkout.

A checkbox means its implementation and specified evidence exist. The milestone
review checkbox is completed by the reviewing agent after checking that evidence.
Do not mark a milestone complete because files were created or tests were skipped.

## M0 — Reproducible test foundation and provenance

Accepted on 2026-10-15 after independent validation and 128 passing tests.
See [M0 acceptance](implementation/M0-acceptance.md) for the retained manifest,
resolved findings, and explicitly unverified clean-install limitation.

Primary files: `tests/test_acceptance.py`, other tests with machine-local inputs,
new `tests/fixtures/`, new `bricksmith/workbench/provenance.py`, and a small
`scripts/workbench.py` environment-report command. Update dependency/setup docs.

- [x] M0.1 Record the starting commit, tracked working-tree changes, runtime
  versions, platform, renderer/checker source hashes, prompt/tool schema hashes,
  library versions/content hashes, and corpus manifest in a versioned run manifest.
  Do not call a source hash or manifest a captured baseline *result*.
- [x] M0.2 Add an offline environment preflight. Validate the prescribed imports,
  library targets, catalog/mesh/connector availability, and a tiny real
  check/render. Report unavailable components explicitly; do not fabricate a pass.
- [x] M0.3 Replace ignored `runs/` dependencies in tests with small original,
  tracked fixtures or deterministic fixture builders. Include known supported,
  colliding, floating, and below-ground cases. Preserve the behaviors each test
  originally covered; do not change expected failures merely to make tests green.
- [x] M0.4 Separate offline contract tests from real geometry/render integration
  tests. Document commands for both. The integration job fails its preflight when
  required libraries are absent; a lightweight unit job cannot report integration
  success on its behalf.
- [x] M0.5 Document a reproducible dependency/data installation or snapshot recipe,
  including how BrickNet is installed. Capture actual versions, not just the
  existing lower bounds. Check data redistribution rights before checking in assets.
- [x] M0.6 Add manifest validation and deterministic hashing tests. Moving a run to
  another directory must not change its content identity; changing its prompt,
  catalog, connector data, or renderer must be detected.
- [x] M0.7 Add an offline baseline-export command that captures configuration and
  source provenance without invoking a model or editing old runs. Existing hybrid
  or operator-assisted artifacts remain labeled historical, not official baselines.
- [x] M0 review: documented commands work without the user's private `runs/`
  fixtures; mocked, skipped, unavailable, and real checks are distinguishable.

Do not add new construction tools or alter checker thresholds in M0. A CI workflow
is optional at this point; a green workflow with only mocked physics is insufficient.

## M1 — Design document and stable identities

Ready-to-use scope and evidence checklist:
[M1 worker assignment](implementation/M1-worker-assignment.md). Accepted on
2026-10-15 after independent correction checks, 149 passing tests, and configured
real preflight. See [M1 acceptance](implementation/M1-acceptance.md).
V2 live generation remains disabled pending M7; M2 offline integration is now accepted.

Primary files: `bricksmith/workbench/design.py`, strict LDraw import/export and
migration CLI adapters, `tests/unit/test_design.py`, integration coverage, and
a narrow compatibility boundary in `agent_session.py`.

M1 introduces offline import/export/inspection and explicit migration. Keep live
v2 mutation/step execution disabled until M2 provides atomic persistence; do not
temporarily maintain two authoritative editable representations.

- [x] M1.1 Implement the design schema, IDs, hashes, units, ownership, and graph
  invariants specified in Contracts C1–C2. Reject invalid input before file mutation.
- [x] M1.2 Provide deterministic import/export of the supported flat type-0/type-1
  LDraw subset. Preserve part identities, colors, transforms, placement multiplicity,
  and meaningful source comments. Fail explicitly on unsupported MPD/nested input;
  do not silently omit parts or claim a generic parser fallback validated them.
- [x] M1.3 Add `inspect_design` and assembly/part selectors. Report source lines
  as a convenience, with revision ID and stable IDs as the durable edit addresses.
- [x] M1.4 Support grouping existing modules into assemblies, assembly parent
  links, requirements, decisions, issues, and relationships. Architecture-specific
  roles are labels; the core must not assume every subject has floors or a roof.
- [x] M1.5 Add an explicit v1-session-to-v2 migration command that writes a new
  destination. Preserve the original byte-for-byte. Unknown historical intent and
  review evidence stay unknown. Map old modules to assemblies; never invent a plan.
- [x] M1.6 Test import/export multiplicity, stable IDs after moves/recolors,
  duplicate ownership, cyclic hierarchy, dangling references, malformed/nonfinite
  transforms, migration repeatability, and unsupported-format rejection.
- [x] M1 review: an imported build exports equivalent physical placements;
  reorder/reformat operations do not look like construction progress.

## M2 — Atomic edits, candidate revisions, and recovery

Execution checkpoints approved by REVIEWER on 2026-10-15:
[M2-A worker assignment](implementation/M2-worker-assignment.md) covers the offline
transaction core and recovery (M2.1–M2.5/M2.7). Review it before assigning M2-B,
which connects existing editing tools (M2.6) and closes the full milestone. This
sequencing does not remove any M2 requirement or authorize live inference.

M2-A is [accepted](implementation/M2-A-acceptance.md) at the v4 source snapshot.
[M2-B](implementation/M2-B-worker-assignment.md) and the full milestone are
[accepted at v3](implementation/M2-acceptance.md), with 218 independently passing
tests and configured real preflight. The original
[B1–B5 corrections](implementation/M2-B-review.md) and
[follow-up B1a/B2a](implementation/M2-B-review-followup.md) are resolved.
Transaction guarantees apply to explicitly initialized transaction workspaces;
legacy v1 execution remains the preserved historical baseline. Live v2 runner
integration remains M7 work, not an implicit consequence of M2 acceptance.

Primary files: `bricksmith/workbench/revisions.py`,
`bricksmith/workbench/transactions.py`, `scripts/workbench.py`,
`tests/unit/test_transactions.py`, and
`tests/integration/test_transactions_cli.py`. Existing mutation tools remain
unchanged and deferred to M2-B.

- [x] M2.1 Implement immutable candidate snapshots, a single-writer lock, base
  revision checks, atomic publication, operation receipts, and recovery under C3.
  A process crash must never leave half the roof moved in the authoritative state.
- [x] M2.2 Implement `propose_edit`, `inspect_candidate`, `commit_candidate`, and
  `discard_candidate`. Support add/replace/delete placements, transforms, recolor,
  clone, and assembly membership changes as one bounded transaction.
- [x] M2.3 Select by stable IDs or assembly descendants. Transform a large
  assembly in one operation without enumerating 30 line numbers. Preview the exact
  selection and change summary; selections refer to the declared base revision.
- [x] M2.4 Apply operations sequentially inside the candidate, then validate the
  resulting candidate as a whole. Intermediate steps are not published. Retain
  failed candidate geometry and diagnostics for inspection.
- [x] M2.5 Enforce commit policy and design locks from C3. Connectivity/equilibrium
  failures may be provisional; collision/ground regressions and evidence gaps
  cannot silently become accepted construction.
- [x] M2.6 Route old save/edit/move/generator calls through the same transaction
  service in explicit transaction workspaces. Preserve tool-specific arguments
  where possible; add versioned invocation context for safe replay and line maps.
  Document intentional behavior changes and update the canonical prompt and tests
  in the same change. Keep the legacy v1 baseline isolated and clearly labeled.
- [x] M2.7 Test duplicate operation retries, conflicting reuse of an operation ID,
  stale revisions, two writers, overlapping selections, failed validation, and
  crashes before/after snapshot creation and before/after publication.
- [x] M2 review: replaying a completed operation does not clone or move parts
  twice, and a multi-assembly edit is either wholly published or wholly absent.

## M3 — Persistent intent and useful context

Execution checkpoints approved by REVIEWER on 2026-10-16:
[M3-A](implementation/M3-A-worker-assignment.md) implements the typed persistent
ledger, trusted correction intake, and revision-bound evidence. Review it before
assigning M3-B for deterministic bounded context, reference-image persistence/
selection, offline request preparation, and the full ten-turn truncation test.
Both checkpoints are offline; live v2 runner integration remains M7. The full M3
gate stays open until both checkpoints are implemented and independently reviewed.
M3-A v3 requires [bounded correction R3b](implementation/M3-A-review-v3.md) before acceptance.

Primary files: new `bricksmith/workbench/context.py`, design-ledger operations,
`tests/test_context.py`, runner request construction, canonical prompt.

- [ ] M3.1 Add typed update/read operations for requirements, design decisions,
  unresolved issues, attempted repairs, and next actions. Preserve provenance,
  superseded entries, and who supplied a constraint. User constraints cannot be
  removed or downgraded by a model-authored summary.
- [ ] M3.2 Build requests from the immutable brief, applicable user corrections,
  current design summary, outstanding constraints/issues, relevant failed attempts,
  recent tool results, and explicit links to retrievable older evidence.
- [ ] M3.3 Give every included observation a revision/provenance identity. Replace
  stale geometry summaries; retain earlier failures as historical observations.
  Never present a planned feature as an observed one.
- [ ] M3.4 Persist reference images with hashes. Reattach the user reference at
  initial design and visual review phases; supply bounded relevant views during
  repair. Restore it on demand instead of relying on a first-turn-only image.
- [ ] M3.5 Add deterministic prioritization and size accounting. If mandatory user
  constraints exceed the budget, stop with an explicit context error; do not
  silently truncate them. Report estimated versus provider-measured token counts.
- [ ] M3.6 Test at least ten scripted turns: an early user constraint, settled
  design decision, and failed roof repair survive recent-history truncation.
  Confirm that current geometry and references are correctly identified.
- [ ] M3 review: context remains bounded and useful without making a second model
  call for summarization. No new live model request is required for these tests.

Keep the canonical design prompt focused on the active tool/quality contract.
These engineering plans are worker documentation; do not paste them wholesale
into every design-model request. Load detailed technique guidance only when useful.

## M4 — Common acceptance and trustworthy diagnostics

Primary files: `acceptance.py`, `feedback.py`, `physics/validator.py`,
`scripts/accept_build.py`, API submission adapter, new calibration fixtures/tests.

- [ ] M4.1 Implement C4's shared acceptance service and versioned report. Both
  direct and API paths supply the same evidence types. Keep each historical
  policy version identifiable; do not rewrite old reports.
- [ ] M4.2 Separate rendered, delivered, explicitly reviewed, and independently
  evaluated images. Bind every review to current artifact hashes and camera
  settings. A view flag is an attestation, not visual-quality measurement.
- [ ] M4.3 Save explicit stage checkpoints. Enforce the existing default piece
  range and three distinct checked major construction stages for the architecture
  profile. Failed intermediate attempts remain in history; repaired stage snapshots
  provide the required stage evidence. Schematic alternatives cannot count as stages.
- [ ] M4.4 Add checker coverage fields without altering existing five-check
  outcomes. Distinguish a known violation, unsupported mechanics, and unavailable
  infrastructure. Unsupported coverage blocks certification; it does not repair
  or erase the raw failed check.
- [ ] M4.5 Create a calibration matrix with small conventional stud connections,
  deliberate illegal overlaps/floating parts, and documented special-connection
  probes. Record independently established legality or `unverified`; do not use
  this checker as the source of its own ground truth.
- [ ] M4.6 Map errors to stable parts/assemblies and save localized diagnostics:
  highlighted parts, useful camera/crop, matching-connector evidence, and the exact
  original error. Gravity suspects remain hints, not guaranteed root causes.
- [ ] M4.7 Test direct/API parity, stale review rejection, missing-check rejection,
  color-only versus structural stage changes, unsupported coverage, and local
  diagnostic mapping after reordered export lines.
- [ ] M4 review: no passing result is inferred from command success, a render,
  visual self-description, unsupported mechanics, or missing evidence.

Changing the solver or adding clip/hinge mechanics is a separate reviewed task,
not an implicit part of adding coverage labels.

## M5 — Visual alternatives and meaningful revision

Primary files: new `bricksmith/workbench/visual_review.py`, renderer camera framing
support, review tools, a small local HTML comparison artifact, integration tests.

- [ ] M5.1 Support two or three named concept candidates off one base revision,
  independent from the committed construction state. Mark schematic geometry
  visibly and structurally as non-certified. Preserve unchosen alternatives.
- [ ] M5.2 Add shared framing for comparison views: fixed camera, scale, target,
  backdrop, resolution, and palette version, computed from the compared candidates'
  union bounds. Do not independently auto-fit each image and hide size differences.
- [ ] M5.3 Record a review finding with affected assemblies, requirement IDs,
  evidence image IDs, the intended change, and unresolved uncertainty. Inspect the
  current model and the user's reference when one was supplied.
- [ ] M5.4 Produce before/after placement and geometry summaries. Reject a
  color-only or source-order change as evidence of a requested structural revision.
  Keep the distinction between a measurable change and subjective improvement.
- [ ] M5.5 Permit compare/select/revert through immutable revisions. Selecting a
  schematic concept guides construction but cannot bypass construction checks.
- [ ] M5.6 Generate a local comparison page with images, actual check results,
  requirement status, and revision identities. No frontend framework, hosted site,
  or new server is needed for this milestone.
- [ ] M5.7 Demonstrate an offline multi-assembly balcony-depth revision on an
  original development fixture: slab, railing, glazing/supports change together;
  unrelated placements remain identical; both states and diagnostics are retained.
  Include real checks and inspect both views. This is a tool demonstration, not an
  autonomous generation benchmark or a 500–1000-piece display-set claim.
- [ ] M5 review: a reviewer can determine exactly what changed and whether the
  model addressed its stated concern, without reconstructing a long transcript.

## M6 — Reusable construction techniques

Primary files: new `bricksmith/workbench/techniques.py`, `data/techniques/`,
technique fixtures/tests and search/apply tools.

- [ ] M6.1 Implement C5's technique schema: parameter ranges, ports, required
  surrounding support, exact provenance, tested configurations, failures, and
  checker/library versions. Separate design inspiration from validated construction.
- [ ] M6.2 Start with three original or rights-cleared techniques grounded in the
  existing tested primitives: bonded slab/support, framed opening, and compact
  stepped roof. Each needs nominal, boundary, and invalid-parameter tests.
- [ ] M6.3 Add deterministic tagged/lexical retrieval with dimensions and connector
  needs. Return evidence and suitability limits. Embeddings are not required.
- [ ] M6.4 Instantiation creates a candidate transaction with exact parts and
  provenance, then checks the full assembly at the chosen location. A validated
  isolated technique never implies a validated installation.
- [ ] M6.5 Add a proposal-only path for lessons from runs. Promotion into the
  reviewed library requires fixtures and review. Benchmark runs cannot silently
  update a shared library for later scored cases.
- [ ] M6 review: an unusable technique is rejected with a specific reason;
  historical reference metadata is never treated as current validation.

## M7 — Bounded runtime and integrated capability

Primary files: runner extraction into small orchestration/transport modules,
`scripts/agent_session.py`, event/provenance reports, integration tests.

- [ ] M7.1 Define a provider adapter around the existing transport. Preserve its
  model, usage, errors, and required opaque continuation items without pretending
  all providers support the same options. Add a fake adapter for deterministic tests.
- [ ] M7.2 Persist request intent before dispatch and the completed response before
  executing its tools. Recover completed tools through receipts. An interrupted
  remote request with unknown billing/completion becomes `request_outcome_unknown`;
  do not blindly resend it as a free retry.
- [ ] M7.3 Add explicit run states and stop reasons, progress events, cancellation
  at safe boundaries, and resume. A text-only model response with no accepted
  submission is `incomplete`, not success. Keep existing bounded step/run commands.
- [ ] M7.4 Enforce request limits and configured wall-time/tool-time limits. Record
  soft token limits honestly. If a transport cannot enforce the selected hard
  budget profile, reject that profile before starting; do not claim a guarantee.
- [ ] M7.5 Persist all usage categories available from the provider and calculate
  cost only from an identified price schedule. Unknown billing is `null`, never
  zero. Record local checker/render time separately from model latency.
- [ ] M7.6 Detect repeated repair/search stalls using unchanged state plus issue
  recurrence, not tool names alone. Preserve current default behavior until a
  documented controller change is tested; no hidden retries or budget extensions.
- [ ] M7.7 Run an offline scripted end-to-end scenario through planning, candidate
  edit, provisional repair, stage checkpoints, review, acceptance, interrupt, and
  resume. Include a failure path and usage accounting. Then prepare a bounded live
  smoke-test configuration for the planning agent; do not execute it implicitly.
- [ ] M7 review: the same revision/evidence contracts are used throughout. The
  worker reports tool correctness separately from unmeasured autonomous quality.

## Explicitly deferred work

Multi-agent orchestration, unrestricted code execution, training/fine-tuning,
full CAD constraint solving, physically certified clutch/strength simulation,
assembly instructions, price/availability optimization, hosted accounts/billing,
photorealistic rendering, and a large web UI are outside this sequence.
Each may become valuable, but none should expand a worker's current assignment.

## Completion evidence required per milestone

- [ ] Changed files and public behavior are listed; canonical prompt matches tools.
- [ ] Focused tests and appropriate existing regression tests have recorded commands
  and outcomes. Required integration failures are repaired or reported explicitly.
- [ ] Fixtures are tracked, original/rights-cleared, and independent of private runs.
- [ ] Migration/backward compatibility is demonstrated where applicable.
- [ ] One concrete artifact or CLI example demonstrates the intended behavior.
- [ ] No unrequested live inference, reference downloads, or benchmark scoring ran.
- [ ] Remaining limitations and planning decisions are reported, with affected task IDs.
- [ ] Reviewer accepts the milestone before the next implementation assignment.

Success for the complete program is measured by the official benchmark, including
failed attempts and cost per accepted build. Completing these checkboxes establishes
the implementation; it does not by itself establish improved design quality.
