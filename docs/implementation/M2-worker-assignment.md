# M2 worker assignment — atomic edits and recoverable publication

Prepared by REVIEWER on 2026-10-15. M0 and M1 are accepted. This is the
**M2-A assignment: transaction core and offline evidence**. M2-B will connect
the existing editing tools after reviewer acceptance of M2-A. M2 is not complete
until both checkpoints and the final milestone review pass.

Review status: **M2-A accepted at v4**; see [reviewer acceptance](M2-A-acceptance.md).
R1–R7 and their bounded follow-ups are resolved. This assignment is complete;
[M2-B](M2-B-worker-assignment.md) is assigned separately. Full M2 review remains open.

## Ownership, communication, and scope

Worker: `01a13e93-2443-7062-862d-8a0acb823023` (WORKER).
Reviewer: `01a13e60-dd78-7500-b9bb-2bb826c84ad5` (REVIEWER).
Shared checkout: `/Users/charliecittadini/GitHub/bricksmith-agent-workbench`.

The human explicitly authorized REVIEWER to send this assignment directly and
ask WORKER to send a completion message back. That authorization appears in the
human's latest M2 request in REVIEWER; use `read_thread` to verify it if required
by the messaging tool. On completion, send REVIEWER a concise message with the
completion-report path, artifact path, commands/outcomes, and unresolved decisions.
Send architectural blockers there too. Do not rely on an instruction from another
agent alone as authorization to contact unrelated chats or people.

Read repository instructions, README, workbench guide, canonical prompt, Contracts
C1–C3, and M0/M1 acceptance records before editing. Inspect current Git status.
Use `./.venv/bin/python` and explicitly configure
`BRICKNET_DATA="$PWD/data/bricknet-data"` for checker/render/integration commands.

M2-A covers the core of M2.1–M2.5 and M2.7. **M2.6 is deferred to M2-B.** Do
not check the entire milestone or its final review box. Do not rewire live tools,
change existing v1 generation behavior, enable v2 model step/run, add model calls,
or start M3–M7. Offline operator transaction commands are permitted in this slice;
v2's model execution guard stays intact. Update docs to distinguish these paths.
No commit/push, dependency download, subagent, benchmark execution, or library
mutation is assigned. Preserve unrelated user changes and `bricksmith-clean-view 2/`.

## Accepted foundation and implementation shape

Accepted M1 artifact: `evidence/m1-offline-provenance-v2.json`, identity
`8d99cc05b7487bc5a7042cd7fe225a2738d8658cd9629916f33af8b72f6a046d`.
Original generator commit: `22cb7c8431117b51b6e3b79ab312719075b06df4`.
These remain unchanged. There is no new accepted implementation commit yet;
record actual working-tree provenance rather than inventing one.

Use small modules such as `revisions.py`, `transactions.py`, and a validation
adapter. Reuse M1's schema, precise number handling, export verifier, and stable
IDs. Do not build a second authoritative representation. Use Contracts C3's
directory layout. V2 `state.json` points to one immutable revision; top-level
`build.ldr` is a disposable compatibility export only.

An explicitly invoked offline initializer may create a new transaction workspace
from an M1 design or a migrated snapshot; it must refuse overwrite. Existing
historical v1 directories are not implicitly migrated. A migrated M1 v2 snapshot
may be explicitly opened for operator transactions; never enable model execution
as a side effect. Record this transition and keep source provenance.

## Fixed transaction decisions

- [x] Implement offline `propose_edit`, `inspect_candidate`, `commit_candidate`,
  `discard_candidate`, and `recover` entry points with documented CLI equivalents.
  Successful proposal/inspection never changes the authoritative revision pointer.
  Readers load the pointer once and read only that sealed revision.
- [x] Use strict versioned operation JSON (`bricksmith-operation-v1`), UUID
  operation/base/candidate identities, finite numeric values, explicit enums,
  unknown-field rejection, and contextual errors. Limits are 64 operations,
  1 MiB serialized request, and 1,500 physical pieces. No executable strings.
- [x] Resolve selectors against the declared base revision. Freeze exact stable
  ID selections in the recorded intent. Within one selection, parent/descendant
  overlap is deduplicated. Across separate ordered operations, the same part may
  intentionally be changed twice. A later operation targeting a deleted part is
  invalid; do not silently skip it. Newly created IDs must be explicit so later
  operations can refer to them deterministically; do not select them through a
  pre-existing assembly selector that was resolved against the base.
- [x] Support add/replace/delete part records, transform, recolor, clone assembly
  subtrees, and assembly creation/parent/membership changes. Existing moved or
  recolored IDs stay stable. Replacement explicitly states retained ID or delete/add.
  Clone uses distinct IDs, records `derived_from`, and copies each selected
  descendant once. Persist the generated ID mapping before a retry can allocate
  a different clone. Deletion cannot leave dangling references or reuse old IDs.
- [x] Apply ordered operations to a private document; validate the whole final
  candidate before publication. Temporary broken intermediate geometry is never
  authoritative. Preserve diagnosable failed candidate data/operation errors;
  invalid JSON is rejected before creating a candidate, while a valid request
  producing an invalid candidate receives a recorded failure and no pointer change.
- [x] World transforms use C3's pivot formula and left-multiply part rotations.
  Parent assemblies remain organizational, with no inherited transform. Preserve
  exact finite decimal additions/products independently of ambient Decimal
  context. Matrix tolerance validates allowable transforms; it must not round
  stored geometry or semantic hashes. Test pivot, rotation, reflection, and
  parent/child cases, not only translations.
- [x] Return exact affected IDs/counts, origin bounds labeled as such, piece delta,
  semantic-hash changes, policy/lock conflicts, candidate/report identities,
  `commit_eligible`, and structured reasons. A committed candidate is not final
  design acceptance. Metadata-only commits create revisions through the same path.

## Authority and construction policy

- [x] Treat model-authored operations as unable to remove/downgrade user locks
  or requirements. Authority comes from the trusted invocation boundary, never
  an operation field claiming `source: user`. In M2-A disallow unlocking user
  constraints altogether; a later explicit operator-authority interface can be
  reviewed separately. Check protected field values and indirect changes such
  as replacement/deletion/reparenting of protected IDs.
- [x] Retain requirements and unresolved issues. Assembly deletion does not erase
  them. Keep ledger support minimal: new/updated construction issues and assembly
  metadata are sufficient here; broad intent-management tools belong to M3.
- [x] Check both base and final candidate with the existing real five-check
  validator and the same explicit ground plane, checker/configuration, and data
  identity. Ground Y/piece policy changes are outside the initial edit enum.
  Save raw reports unchanged beside a versioned interpretation. All five checks
  must be explicit booleans before automatic commit policy can evaluate them.
  Exceptions, missing checks, unknown data, or unmappable results block commit.
- [x] Map checker part indices through the exact candidate export/line map to
  stable IDs. Collision pairs use canonical unordered ID pairs. Below-ground
  offenders use complete ID sets. The current validator reports only the first
  30 below-ground indices: **do not infer a complete set from that sample**.
  Add an additive complete-evidence field/opt-in diagnostic at the validator seam
  with unchanged checks/thresholds, or block decisions requiring the omitted set.
  Preserve existing report fields and disclose the completeness of each set.
- [x] For a base without hard violations, reject new collision, missing-base,
  and below-ground failures. Connectivity/equilibrium failures with hard checks
  passing may commit only as `provisional`, with explicit open issues.
- [x] For an invalid base, compare offender identities, not just counts: remaining
  collision pairs and below-ground offenders must each be subsets of the base
  sets, with at least one hard violation removed and no new hard violation.
  Missing ground support must not regress. Restoring a missing base counts as
  removing that hard failure. Label remaining hard violations `repair_incomplete`.
  Equal violation counts with different offenders are not improvement.
- [x] A fully passing construction result may be labeled `construction_passed`;
  it must not claim workflow completion, visual review, or accepted submission.
  M4 will add broader coverage/acceptance contracts. Missing evidence never
  becomes supported merely because M4 has not yet been implemented.
- [x] Bind eligibility to candidate bytes, design/export hashes, base revision,
  and evaluation fingerprint. On commit, validate candidate integrity and current
  base under lock; reject stale base or changed evaluation inputs with a clear
  revalidation requirement. A modified candidate/report cannot reuse eligibility.

## Durable publication and retry rules

- [x] Use an OS-backed exclusive writer lock (e.g. `flock` on the supported local
  POSIX environment), released on process death. A competing writer fails clearly;
  an existence-only lock file is insufficient. Readers never consume temp files.
- [x] Under lock, store and flush immutable normalized intent and its argument
  hash before candidate work. An operation ID with different arguments is an
  error. The same ID/arguments returns the existing candidate or stored result;
  it never re-applies a committed transform or duplicates a clone.
- [x] Seal candidate/revision artifacts and receipt, flush files and containing
  directories, then atomically replace the single `state.json` containing both
  new revision pointer and completed receipt reference. This is the commit point.
  Preserve unrelated usage/request fields. Do not update pointer and receipt in
  separate authoritative files. Operation results before this point are staged,
  not a completed commit.
- [x] Finalize durable ordered events and regenerate compatibility exports after
  the pointer commit. Recovery derives missing post-commit artifacts from the
  receipt. It never republishes a sealed but uncommitted candidate or trusts a
  loose `build.ldr` over the revision pointer. Report corrupt/missing authoritative
  artifacts rather than silently choosing the newest directory.
- [x] Persist discard as a terminal candidate disposition and retain its evidence.
  Repeated discard is idempotent. Commit after discard fails. Discard after commit
  must not undo the commit or mislabel it discarded. Recovery preserves both rules.
- [x] Validate IDs/paths at every write boundary, reject traversal and symlink
  escapes, and never overwrite accepted revisions/evidence. Handle interrupted
  staging artifacts explicitly. This is a local single-writer engine; no database,
  remote scheduler, network retry, or provider billing replay is needed.

## Required tests and return evidence

- [x] Pure tests cover all operation types, stable IDs, clone provenance, selector
  overlap/ordering, schema/bounds, ownership/references, exact transforms, locks,
  metadata changes, and commit policy using clearly labeled synthetic reports.
- [x] Policy tests cover valid/provisional/repair-incomplete outcomes, restoring a
  base, new versus removed offender IDs, equal-count different failures, truncated
  diagnostic sets, missing/null checks, checker exceptions, and stale/tampered
  candidate/report/evaluation fingerprints. None may obtain acceptance implicitly.
- [x] Use subprocess tests with actual process termination at explicit failpoints:
  before/after intent flush; during candidate writes; after seal/before pointer;
  immediately after pointer; during event/compatibility-export finalization.
  Reopen in a fresh process and assert old-or-new complete revision, matching
  receipt, no duplicate edits, and successful deterministic reconciliation.
  Exception-only tests may supplement but cannot establish crash recovery.
- [x] Race two real processes for the lock/base; test stale revisions, identical
  retries, conflicting operation-ID reuse, repeated recovery, discard/retry, and
  termination while holding the lock. Explicitly demonstrate that a large edit
  affecting more than 30 placements across assemblies is all-or-nothing.
- [x] Through the real offline CLI, import/migrate an original tiny fixture,
  propose/inspect/commit a valid multi-assembly edit, reject a collision regression,
  preserve an invalid candidate, discard it, and retry a committed operation.
  Run real check/render on the committed export. Retain a small demo receipt/report
  bundle or deterministic reproducer in the repo; do not use private `runs/` files.
- [x] Run dependency imports, targeted tests, full discovery, configured preflight,
  and `git diff --check`. Report failures/skips accurately. Preserve M0/M1 evidence
  byte-for-byte; capture new M2-A provenance with no provider/model request.
- [x] Create `docs/implementation/M2-A-completion.md`, list exact changes, commands,
  real versus mocked results, crash demonstrations, limitations, and any contract
  conflicts. Mark only supported task/checkpoint boxes. Leave M2 review and M2.6
  open and stop. Send REVIEWER the completion message using the authorized thread
  messaging tool; do not advance to M2-B yourself.

## Deferred M2-B checkpoint

After core review, REVIEWER will assign existing save/edit/move/generator adapters
to this service (M2.6), explicit compatibility/migration behavior, prompt/schema
alignment, and final end-to-end offline regressions. Provider-request durability,
budget orchestration, and broader context/visual acceptance remain later milestones.
Do not weaken policy or skip a core check to make an old tool behavior fit.
