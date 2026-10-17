# BrickSmith harness contracts

Status: proposed implementation contracts, 2026-10-15. These describe the target
behavior for [the implementation plan](HARNESS_IMPLEMENTATION_PLAN.md), not
capabilities already available. The reviewing agent owns changes to these
contracts. Version schemas when their meaning changes.

## C1 — State, identity, and units

Use JSON documents with explicit schema identifiers and strict validation at
the boundary. Python dataclasses and standard-library validation are sufficient;
do not add a framework solely to serialize these records.

Use `bricksmith-run-manifest-v1`, `bricksmith-agent-session-v2`,
`bricksmith-design-v1`, `bricksmith-operation-v1`, and
`bricksmith-build-acceptance-v2` for the respective new records. Store machine
fields in snake_case, timestamps in UTC ISO 8601, unknown values as JSON null,
and collection fields as explicit arrays or ID-keyed objects. Reject unknown
schema versions. Version-independent readers must not silently guess their meaning.

M3-A reviewed extension: `bricksmith-design-v2` adds a strict versioned intent
ledger while retaining design-v1 readers and geometry semantics;
`bricksmith-operation-v3` adds ledger mutations and explicit upgrade through the
existing transaction service. See the [bounded assignment](implementation/M3-A-worker-assignment.md)
for record and authority rules. User corrections append immutable instruction
and replacement records; active requirement/decision projections follow explicit
supersession links while preserving originals. A model cannot self-declare
user/operator authority. These are assigned capabilities, not an implemented claim.

### Authoritative records

| Record | Minimum fields and meaning |
| --- | --- |
| Run manifest | Schema, run ID, creation time, original brief hash, generation source commit/patch hash, prompt/tools/config hashes, provider/model/settings, environment/data versions, input provenance, budgets, execution track |
| Session state | Schema, session ID, current revision ID, operation receipt index, run state/stop reason, request/event references, pending image IDs, cumulative usage |
| Design revision | Schema, revision ID, parent revision ID, brief reference, ground Y, piece range, assemblies, parts, requirements, decisions, issues, source references |
| Part | Stable ID, owning assembly ID, catalog part ID, color, translation XYZ in LDU, 3×3 LDraw rotation matrix, provenance |
| Assembly | Stable ID, name, optional role, optional parent assembly ID, design properties, relationship records, optional field locks |
| Requirement | Stable ID, exact description, source (`user` or `agent`), priority, affected assembly IDs, measurable predicate when available, evidence references, status |
| Decision | Stable ID, statement, rationale, source, related assemblies/requirements, evidence references, supersedes ID, status |
| Issue | Stable ID, kind, affected IDs, first/last observation revision, evidence, attempted operation IDs, current status, next proposed action |
| Source reference | Stable ID, original source identity, content hash, role, local artifact reference, license/rights status, missing-data notes |

Requirements use `pending`, `satisfied`, `failed`, or `unverified`. Agent-written
"satisfied" without supporting evidence is a claim, not an acceptance result.
Decisions may be active or superseded; issues may be open or resolved. Keep the
history when either changes. Saved files use relative artifact paths and content
hashes; resolved absolute paths are runtime convenience only.

All stored coordinates are **world-space LDU**, with negative Y upward. One stud
is 20 LDU and one plate is 8 LDU. Conversion helpers may expose studs/plates to
users but must name units explicitly. Assembly parents are organizational; there
is no hidden transform inheritance in v1. A transform operation updates selected
part world transforms once. This avoids double application to descendants.

IDs are opaque UUID strings allocated once on creation; names and export line
numbers are not identities. Clone creates new IDs and records `derived_from`.
An unchanged/moved/recolored part keeps its ID. Deleted IDs are not reused.
Whole-module replacement preserves IDs only when the caller supplies an explicit
mapping; otherwise it is a documented delete/add operation. Migration allocates
deterministic UUIDs from the immutable input identity, module, and placement ordinal.

Every physical part has exactly one owning assembly. An assembly may contain zero
direct parts and group children. Parent links are acyclic; references must resolve.
Support/adjacency relationships are design assertions, may form cycles, and do not
prove physical connection. A selection including a parent and its child addresses
each descendant part only once; conflicting operations are resolved by explicit
sequence, never accidental duplicate selection.

Validate finite numeric values, valid part/color identifiers, and the supported
LDraw transform rules. Do not globally quantize coordinates to full studs or forbid
legal offsets. Reject unsupported scaling/shear explicitly rather than changing
it silently. Preserve supported orthonormal reflections and rotations; document
the numerical validation tolerance separately from hash normalization.

### Locks and authority

Locks enumerate exact protected fields/IDs, e.g. a facade's existing placement
geometry or a fixed entrance region. Advisory prose such as "keep it airy" is a
requirement for review, not a fabricated geometric lock. User-owned locks and
requirements can be changed only through a recorded user/operator instruction.
Tools invoked by the model cannot impersonate that source or unlock a user field.
Agent-authored decisions may be revised with rationale. Removing an assembly does
not implicitly delete its requirements or locks.

## C2 — Exports, hashes, and evidence

For v1 authoring, support flat physical type-1 `.dat` placements plus type-0
comments. Unsupported records, unresolved submodels, missing parts, and parser
fallbacks are explicit diagnostics. Preserve source comments/provenance without
treating any retrieved text as instructions. A future MPD expansion needs its own
piece-count and source-mapping contract.

Export deterministic `build.ldr` and module views plus `line_map.json` mapping
each physical source line to a stable part/assembly ID. The mapping belongs to
one exact exported file hash. Do not apply an old line mapping to a new export.
Existing core graphs remain useful computational structures; their transient
instance IDs must not silently replace persisted part IDs.

Store separate hashes, each with an algorithm/schema version:

- **File hash:** SHA-256 of exact bytes. Binds a report to a saved artifact.
- **Appearance hash:** a sorted multiset of normalized physical part IDs, colors,
  and transforms. Ignores source order, comments, UUIDs, and numeric formatting.
- **Structure hash:** the same multiset excluding color. Detects physical changes
  without treating recoloring as construction progress.
- **Design hash:** canonical full design state, excluding its own hash and runtime
  timestamps. Detects changes to requirements, ownership, decisions, and locks.
- **Render identity:** appearance hash plus renderer/version, library/palette hash,
  camera/framing settings, resolution, and rendering configuration.

Multiplicity matters: two identical placements are two parts and must not be
deduplicated during hashing. Normalize numeric values losslessly from their
serialized decimal values (`1`, `1.0`, and negative zero normalize consistently).
Do not round away small geometry changes to manufacture identical hashes. Keep
numerical comparison tolerances out of the hash algorithm.

A render record stores artifact hash, render identity, source revision/file hash,
view name/settings, creation outcome, and omitted/unsupported parts. A delivered
image event references the exact model request that included it. A review event
references the images actually reviewed and the author/source of that attestation.
Image delivery is evidence of opportunity to inspect, not proof of comprehension.

Pure comments/reordering do not invalidate physical evidence if matching semantic
hashes and configuration permit explicit reuse. Record such reuse. Geometry or
color changes invalidate relevant visual evidence. Context-only changes can retain
the same render, but requirement satisfaction must be reconsidered where affected.

## C3 — Revisions, transactions, and durable execution

### Local storage

```text
session/
  manifest.json
  state.json                    # authoritative current pointer and execution state
  revisions/<revision-id>/      # immutable once sealed
    design.json
    build.ldr
    modules/*.ldr
    line_map.json
    revision.json               # parent, hashes, operation, validation references
  operations/<operation-id>/    # intent, candidate, checks, result/receipt
  requests/<request-id>/        # sanitized request, response, outcome/usage
  evidence/                    # checks, renders, reviews, stage checkpoints
  events/                      # ordered durable event records
  build.ldr                    # optional compatibility export, not authoritative
```

Validate all generated names and resolve paths inside the session root. Disallow
absolute/path-traversal tool arguments and symlink escapes for tool writes.
Use relative immutable artifact references. Keep credentials outside this tree.

Acquire an OS-backed exclusive session lock for a mutation or request step.
Concurrent writers fail clearly; do not interleave them. The lock must release on
process death. A reader resolves one `state.json` revision pointer and reads that
complete snapshot. Compatibility exports can lag after a crash; regenerate them
from the pointer before external export, and never use them for authoritative checks.

### Transaction interface

`propose_edit` takes `operation_id`, `base_revision_id`, `intent`, a bounded ordered
list of operations, and requirement/issue IDs addressed. The tool schema uses
strict objects with enumerated operation types; no embedded executable strings.
Runtime validation is authoritative even if a provider's schema cannot express
all constraints. Initial limit: 64 operations, 1 MiB serialized edit request, and
the existing 1,500 total physical-part ceiling. Assembly transforms can affect all
parts within that total ceiling. Exceeding a bound returns a structured error.

Operations: add/replace/delete parts, transform selected parts or assembly
descendants, recolor, clone selected assemblies, and create/update membership.
Transforms supply a 3×3 matrix, XYZ translation, and pivot, all in world LDU:
`new_position = pivot + rotation * (old_position - pivot) + translation`;
`new_rotation = rotation * old_rotation`. Reject invalid/conflicting IDs early.
Metadata changes use the same revision service and authority checks.

The response includes candidate ID, base revision, affected IDs/counts, bounds
before/after, part-count delta, structure/appearance changes, lock/requirement
conflicts, construction report, and `commit_eligible` with reasons. It does not
change the current revision. `inspect_candidate` can inspect/check/render it.
`commit_candidate` includes candidate ID and expected current revision.
`discard_candidate` records abandonment while retaining evidence.

### Commit policy

- All syntax/catalog requirements and ownership invariants must pass.
- User locks must be respected; unsatisfied requirements remain visible.
- For a valid base, mesh collisions and ground violations are forbidden.
- For an imported invalid base, a repair commit may retain a **subset** of
  pre-existing collision pairs/below-ground offenders (mapped by stable IDs), with
  at least one hard violation removed and no new hard violation. Missing ground
  support cannot regress. Report this as `repair_incomplete`, never accepted.
- Connectivity/equilibrium failures may be committed as `provisional` when hard
  checks permit it. Unsupported mechanics may be preserved as provisional evidence,
  but cannot obtain certified acceptance. These states create explicit open issues.
- Missing/unavailable required validation blocks automatic commit; keep the
  candidate for diagnosis. Unknown evidence is not a repair improvement.
- Schematic concepts live on a separate candidate branch and cannot supply checked
  construction stages or be silently promoted into a completed build.
- Final acceptance is stricter and always requires all five checks plus the
  applicable workflow/coverage contract.

This policy intentionally replaces inconsistent per-tool rollback rules in M2.
Preserve previous results as historical evidence and update prompt/docs/tests.

### Publication and recovery protocol

1. Under the lock, verify expected revision and operation ID; durably save intent
   and its normalized argument hash before doing work.
2. Build/check the candidate in a private directory. Save all candidate artifacts,
   result/receipt, and hashes; flush files and containing directories as needed.
3. Seal the immutable revision. Atomically replace `state.json` to publish the new
   pointer **and** completed operation receipt reference together. This is the
   commit point; no observer sees a partial set of authoritative files.
4. Append/finalize the event and regenerate compatibility exports. If interrupted
   here, recovery derives missing events/exports from the committed receipt.

On restart, reconcile intents, sealed candidates, the pointer, and receipts.
Unpublished candidates stay uncommitted. A committed operation returns the stored
result on retry. The same operation ID with different arguments is an error.
Do not reapply a committed transform. Do not publish an abandoned candidate merely
because its files exist. Persist metadata-only operations by the same protocol.

Use atomic per-event files with monotonic sequence IDs (or an equivalently durable
journal with tested truncation recovery); do not claim unflushed JSONL is crash-safe.
Check and render artifacts are immutable. Failure records retain the original
exception category and relevant candidate identity.

Persist model request intent before network dispatch and completed responses before
executing tool calls. Completed tool results are checkpointed individually, not
only at the end of a response batch. Requests with unknown remote outcomes stop
for reconciliation; safe local replay must not imply safe remote billing replay.

## C4 — Validation and acceptance

Retain these five booleans, with `null` for unavailable evidence:

```text
mesh_collision_free
included_base
no_parts_below_ground
actual_connectivity
approximate_gravity_equilibrium
```

Add a coverage record with `supported`, `unsupported`, or `unknown` applicability
for each relevant check, supported connector/mechanics scope, affected part IDs,
and evidence. Infrastructure failure is `unavailable`, not `unsupported` geometry.
Presence of a special part alone is insufficient to declare a connection invalid
or supported. When required connection mechanics cannot be determined, use unknown.
Keep raw validator outputs unchanged alongside this interpretation. Never silently
convert an existing `false` into `true` because coverage is limited.

An acceptance report contains:

- Policy/schema version, exact candidate and evaluation-environment hashes.
- Construction checks, coverage, limitations, piece count/range, ground Y.
- Stage checkpoints and their exact revision identities, labels, checks, and deltas.
- Render creation/delivery/review records and missing/stale evidence.
- Requirement evidence and unresolved issues; explicit user constraints retained.
- Visual self-review and any separate external review, clearly labeled.
- `construction_passed`, `workflow_passed`, `requirements_status`, and `accepted`.

`accepted` is the engineering/workflow gate, not a claim of beauty or real-world
certification. It requires complete supported passing checks, piece constraints,
valid stage progression, applicable review evidence, and no established unmet
mandatory requirement. Unmeasurable semantic requirements remain explicitly
unverified/self-attested until externally assessed; do not silently mark them
proved. The benchmark has a separate brief/visual assessment.

The architecture workflow requires at least three distinct substantive stage
snapshots (foundation/walls, openings, complete roof), checked after repairs.
Structure hashes must differ; part addition/deletion/movement must be recorded.
Renaming, recoloring, or line reordering cannot satisfy progress. Labels alone do
not establish that an opening or roof exists; stage-role review is attested and
reported as such until a reliable domain-specific test exists.

Require two current explicit views, default `front_left` and `front_right`, and
an explicit review. API delivery records and direct human/agent attestations use
different evidence sources but the same report model. The direct CLI should support
prepare/render, then review/finalize against those exact images. Retain the current
CLI as a compatibility adapter; reject stale image flags rather than re-rendering
different bytes and silently treating them as already inspected.

For the API visual-revision requirement, record the finding and intended change
type. A structural finding needs a structure change; a palette finding may need
only an appearance change. An unrelated geometry edit is not automatically proof
the finding is resolved. Report the author's resolution claim and before/after
evidence separately. Existing direct workflows still require meaningful revision
when the visual review identifies a gap; do not manufacture obligatory damage and
repair for an already satisfactory direct artifact.

## C5 — Technique records

Each technique package includes `technique.json`, original/rights-cleared example
geometry or deterministic generator inputs, review imagery, and test cases.
Required metadata: ID/version, name/tags, purpose, parameter types/ranges, ports
and coordinate frames, required external support, expected materials/piece range,
source and license, tested parameter values, checker/library versions, failure
cases, and reviewer/promotion status.

Use only allowlisted repository generator functions, referenced by ID and version.
A retrieved JSON record cannot load arbitrary code. Runtime parameters are schema
validated. Passing at three parameter values proves those cases, not the entire
continuous range; report the distinction. Apply through candidate transactions and
revalidate the surrounding build. A dependency change makes previous validation
historical until refreshed. Proposals from runs remain separate from reviewed
packages, and benchmark runs use a frozen library snapshot.

## C6 — Budgets, traces, and compatibility

Run states: `ready`, `running`, `paused`, `completed`, `incomplete`, `failed`.
Stop reason is a separate enum including `accepted`, `request_limit`,
`token_limit`, `time_limit`, `cancelled`, `research_stall`, `repair_stall`,
`model_stopped`, `environment_error`, `provider_error`, and
`request_outcome_unknown`. `completed` requires accepted submission. Historical
sessions lacking such evidence are not upgraded to completed during migration.

Record provider/model requested and resolved identity when supplied, generation
settings (including unsupported/unavailable settings), timestamps, request IDs,
input/output/cached/reasoning token categories where available, local tool timing,
and provider cost or an estimate with its price-schedule identity. Do not add a
reasoning-token subset twice to output totals. Unknown values are null. Token
totals include failed/retried calls when known; unknown outcomes are conspicuous.

The existing plan-usage transport has documented enforcement limitations. Keep
those explicit; a configured soft limit is not a hard monetary/account quota.
Live benchmark execution must choose a compatible budget profile first. No
implementation task authorizes spending on inference.

Traces retain prompts, tool definitions/arguments/results, model-visible outputs,
candidate artifacts, and all attempts. Never store authorization headers, access
tokens, credentials, or unrelated home-directory data. Opaque provider reasoning
continuation data may be needed privately for transport replay; do not expose it
as a readable rationale or include it in public benchmark bundles. Public
sanitization must report omissions and hashes without altering the private original.

Keep v1 readers or an explicit migration route. Never mutate ignored historical
run directories while loading/status-checking. Changing tool semantics, context,
acceptance, checker, or rendering increments its recorded version/hash and includes
the canonical prompt/documentation updates required by `AGENTS.md`.

### M2-B compatibility adapter boundary

The `bricksmith-tool-invocation-v1` envelope binds a compatibility tool call to
one operation UUID, exact tool arguments, base revision, and assembled-export
SHA-256. Transaction-backed line operations resolve through verified export
maps; stale line numbers are rejected. Existing v1 session behavior remains a
separate historical baseline. Operation-v2 adds only the bounded logical
`replace_assembly_contents` operation and optional adapter metadata; direct core
operation-v2 requests need not invent a tool invocation, while metadata supplied
by the compatibility dispatcher is strictly validated and bound to the original
invocation. It does not replace
the design document or relax the 64-operation, 1 MiB, 250-per-module, or
1,500-total-part limits. New module contents use fresh stable instance IDs,
while clone relationships explicitly preserve `derived_from`. A candidate is
not the current revision, and provisional/repair-incomplete commits keep their
statuses and open issues. Offline render artifacts prove creation and source
identity only; they do not imply review or acceptance. Live transaction model
execution remains pending M7.

Adapter-specific result metadata is retained under the explicit `tool_details`
namespace. Those values are evidence only and never supply transaction status,
commit eligibility, identity, receipt, policy, or export fields. Render dispatch
durably reserves its complete invocation and source identity under the workspace
writer lock before calling the renderer. A matching retry may recover staging;
an operation ID already reserved for another invocation conflicts before staging
is reconciled.
