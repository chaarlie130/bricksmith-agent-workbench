# Agent workbench

This workstream gives a frontier-model design agent reference search, modular
LDraw authoring, construction checks, and rendered feedback. It reuses
BrickSmith's checker and renderer; it does not include the former local
language-model training pipeline.

## Commands

The canonical system instructions for every fresh design agent are in
[`bricksmith/workbench/system_prompt.md`](../bricksmith/workbench/system_prompt.md).
Future API runners should call `bricksmith.workbench.prompt.load_system_prompt()`
for their system message, so the instructions do not drift from this file.
`./.venv/bin/python scripts/workbench.py prompt` prints the same text for
manual setups. Direct builds must use the repository `.venv`; check imports
for `bricknet`, `meshlib`, and `matplotlib` before construction. See the direct
build acceptance workflow in `AGENTS.md` and the canonical system prompt.
A subject-only design brief is sufficient: the agent supplies the construction
plan, iterative checks, two-view visual review, and final acceptance. Without
an explicit budget, an architectural display set targets 500–1000 physical
pieces. This is a quality-oriented default, not permission to pad a weak
design. The direct-build acceptance command enforces that range and three
distinct major-stage placement files by default; a user-specified budget is
passed as `--min-pieces` and `--max-pieces`. It cannot determine whether the
model *looks* like the subject, so the agent still has to inspect and revise
the renders. A failed build remains incomplete, not a production-ready result.

Run from the repository root with the BrickSmith Python environment:

```bash
./.venv/bin/python scripts/workbench.py prompt
./.venv/bin/python scripts/workbench.py search "modern glass house with terrace" --limit 5
./.venv/bin/python scripts/workbench.py inspect data/reference_sets/ldr/omr_21009-1_Farnsworth_House.ldr --start 1 --count 80
./.venv/bin/python scripts/workbench.py check path/to/candidate.ldr
```

All successful commands return JSON. `search` scans the checked-in reference
models and ranks title, a small set of reviewed seed descriptions, and part IDs
with lexical matching. Results include an absolute source path, source prefix,
SHA-256 digest, piece count, and any license line found in the file. A missing
license line is reported as `null`, not permission to redistribute. `inspect`
returns at most 200 numbered lines per call so an agent can read an example
without filling its context with an entire set. `check` wraps BrickSmith's
existing validator and maps collision pair indices to LDraw source lines.

These tools are deliberately modest. Search does not yet retrieve semantic
subassemblies or use embeddings. Validation does not establish assembly order,
insertion clearance, clutch strength, or real-world stability. The ground
height is configurable because a model's origin may differ from the default.

## M1 offline design documents

The offline design document commands import a supported flat LDraw file into a
`bricksmith-design-v1` record with stable part and assembly IDs, then inspect,
export, or explicitly migrate session data. They make no model request and do
not change the live agent tool set. Type-0 comments and type-1 `.dat` placements
are supported; MPD/submodels and type-2–5 geometry fail with source locations.
Import/export destinations must be new paths. Export includes deterministic
`build.ldr`, one module view per assembly, and `line_map.json`; line addresses
are valid only for the exact exported-file hash and revision.

```bash
./.venv/bin/python scripts/workbench.py design-import tests/fixtures/design/tiny.ldr /tmp/tiny-design.json
./.venv/bin/python scripts/workbench.py design-inspect /tmp/tiny-design.json
./.venv/bin/python scripts/workbench.py design-export /tmp/tiny-design.json /tmp/tiny-export
./.venv/bin/python scripts/workbench.py design-inspect /tmp/tiny-design.json \
  --line-map /tmp/tiny-export/line_map.json --export-file /tmp/tiny-export/build.ldr
```

To migrate a legacy session, use
`./.venv/bin/python scripts/workbench.py design-migrate <v1-session> <new-v2-session>`.
Migration reads `module_order` and its module files, compares their placements
to the saved derived build, and refuses disagreements or path escapes. The v1
source remains untouched. Migrated v2 sessions are inert and read-only for model
execution; legacy validation/review evidence remains historical. M1 provides editable in-memory helper functions for stable-ID move
and recolor semantics, but it does not enable live mutations.

## M2-A offline operator transactions

The transaction CLI creates a new, separate workspace from an M1 design or an
explicitly selected inert v2 design revision. It never overwrites a source or
implicitly migrates a historical v1 folder. This offline operator path does not
enable v2 `step`/`run` or route existing model tools through transactions; those
adapters remain deferred to M2-B.

```bash
./.venv/bin/python scripts/workbench.py design-import tests/fixtures/acceptance/pass.ldr /tmp/m2-design.json --ground-y 8
./.venv/bin/python scripts/workbench.py transaction-init /tmp/m2-design.json /tmp/m2-session
# Write a strict bricksmith-operation-v1 request to /tmp/m2-operation.json.
./.venv/bin/python scripts/workbench.py transaction-propose /tmp/m2-session /tmp/m2-operation.json
./.venv/bin/python scripts/workbench.py transaction-inspect /tmp/m2-session <operation-uuid>
./.venv/bin/python scripts/workbench.py transaction-commit /tmp/m2-session <operation-uuid> <candidate-revision-uuid>
./.venv/bin/python scripts/workbench.py transaction-discard /tmp/m2-session <operation-uuid>
./.venv/bin/python scripts/workbench.py transaction-recover /tmp/m2-session
```

`propose` resolves selectors against the declared base and saves the frozen
selection, candidate, raw validation reports, interpreted offender identities,
and commit-policy reasons. A candidate does not change `state.json`. `commit`
rechecks the base and candidate under the OS writer lock and atomically publishes
the new immutable revision pointer with its completed receipt. A committed
`build.ldr` is a compatibility export; reads/checks use the revision pointer.
Only the five real checker booleans with complete identity-mappable hard-failure
evidence can authorize a commit. `construction_passed`, `provisional`, and
`repair_incomplete` are construction statuses, not workflow acceptance.
Discard retains candidate evidence. Recovery completes committed receipts,
events, and compatibility exports; it never publishes an orphan sealed revision.

## M3-A persistent intent ledger

An initialized transaction workspace remains `bricksmith-design-v1` until an
operator explicitly upgrades it with a normal, validated transaction. The
upgrade preserves old records and revisions and creates empty
`bricksmith-intent-ledger-v1` arrays. Ledger edits use operation-v3 and the same
proposal/commit/recovery path. They retain the construction commit policy, so a
metadata-only edit is blocked when the real checks are unavailable.

The `operator-intake` command accepts exact instruction text and already
structured changes. The trusted source comes from its required `--source`
option rather than the JSON body. It records a single operation and commits
through the standard transaction service. This application boundary cannot
protect workspace files from a process with arbitrary filesystem access.
Operator intake is not part of the model tool catalog. A model cannot promote
retrieved text or its own summary into user authority.

```bash
./.venv/bin/python scripts/workbench.py transaction-upgrade-v2 WORKSPACE OPERATION_UUID BASE_REVISION_UUID
./.venv/bin/python scripts/workbench.py operator-intake WORKSPACE intake.json --source user
./.venv/bin/python scripts/workbench.py ledger-read WORKSPACE --limit 50
./.venv/bin/python scripts/workbench.py ledger-read WORKSPACE --revision-id REVISION_UUID --offset 50 --limit 50
```

The intake JSON contains exactly `operation_id`, `base_revision_id`,
`instruction_id`, `created_at`, `instruction_text`, `changes`, and `fill_brief`.
Supported structured changes are `requirement`, `decision`, `issue`,
`repair_attempt`, and `next_action`; record IDs are explicit UUIDs. Each new
text field is limited to 16 KiB UTF-8, instruction text and an initial brief to
64 KiB, and the ledger data to 2 MiB / 2,000 records per revision. Reads return
per-collection counts and continuation offsets. A recorded claim or construction
pass does not establish final acceptance. See `system_prompt.md` for the exact
authority boundary and M3-A offline semantics.

Issue history is derived from each committed operation's own verified candidate.
Each status observation carries its observed status and evidence IDs/hashes;
current status and evidence are attributed to the latest status assertion, while
creation provenance remains tied to issue creation. Later evidence is never
projected onto an earlier observation. Only committed, issue-specific updates
create status observations. Staged or terminal attempts, committed updates to a
different issue, geometry-only edits, and repair-attempt records do not create
observations just because they carry a copy of the issue. Checker-created policy
issues require matching committed policy evidence; legacy entries without
demonstrable operation provenance remain historical and unverified.

Repair records use `bricksmith-repair-attempt-v2`. Their
`recorded_revision_id` binds the ledger edit to its base. `observed_revision_id`
is the attempted operation's committed result revision, or its base when the
attempt remained uncommitted/failed. Reads retain `outcome_at_recording` and
report any later state separately as `current_reconciled_outcome`. The revision
chain is paged like the ledger collections.

`search_omr_sets`/`fetch_omr_set` (in `bricksmith/workbench/omr.py`) are a
separate, **live** lookup against the LDraw Official Model Repository
(library.ldraw.org), distinct from the checked-in local corpus above. They
make anonymous, unauthenticated HTTP requests -- no login or stored
credentials -- and cover most, but not every, officially released LEGO set.
`fetch_omr_set` returns raw third-party LDraw file text with unverified
licensing; it is reference data for study, not a design cleared for reuse.

## Persistent design session

`scripts/agent_session.py` is the first tool-calling runner. Start a session
without model usage, then advance it one model request at a time:

```bash
./.venv/bin/python scripts/agent_session.py start runs/traditional-house --brief "A detailed traditional house with a porch, bay window, and pitched roof"
python scripts/agent_session.py status runs/traditional-house
python scripts/agent_session.py step runs/traditional-house
python scripts/agent_session.py step runs/traditional-house --message "Please repair the listed collisions before adding another floor."
python scripts/agent_session.py queue-render runs/traditional-house --view front_left --view back_right
```

`start --ground-y 0` selects a compact plate-built display plinth convention
(bottom plates at Y=-8, underside at Y=0); the default `--ground-y 8` fits a
standard `3811.dat` baseplate at Y=0. The chosen ground plane is saved in
session state and used on every automatic construction check. Existing
sessions without this field remain at Y=8. This is a scale/composition
choice, not permission to omit a connected base or other physics checks.

When usage headroom is available, `run` can carry tool results into several
successive model requests without an operator issuing each `step` manually:

```bash
python scripts/agent_session.py run runs/traditional-house --max-requests 4 --max-total-tokens 60000
```

It stops when the model replies without tools, submits an accepted design,
hits the request cap, or reaches its aggregate token ceiling. Each completed
request is saved before the next one starts, so an interruption can resume
with `step` or `run`. The token ceiling is **soft** (one request can exceed
the remaining allowance) and does **not** check account-level quota; check
plan usage separately, especially near a user-defined floor. The one-request
`step` command remains the safest option when quota is tight.
If a later request fails after earlier requests succeeded, `run` reports
`stopped_because: request_error` with the completed steps and their usage;
the failed request does not add a step. If the first request fails, the CLI
returns the error directly.
After two consecutive lookup-only turns, `run` reminds the agent to use the
information already found to build a coherent feature at the requested
scale. The summary includes each saved module's part count and total build
count alongside validation. This is an advisory prompt, not a visual-quality
guarantee; review the render before accepting an addition.
If three consecutive model requests only search, inspect, or render
references, `run` stops with `stopped_because: research_stall` so the operator
can adjust the brief or resume with a focused `step` message. A saved plan or
construction tool breaks that lookup streak.

`status` shows the latest validation, modules, pending previews, and at most
12 compact recent tool events by default. The complete event history and
token-attribution detail remain in `state.json`; use `status --full-events`
only when that larger audit output is needed.

Add `--reference-image /absolute/path/to/house.png` to `start` when a photo is
part of the brief. The runner copies that PNG, JPEG, or WebP into the session
and sends it as image input on the first model request. The image stays in the
saved audit history but later live context retains the agent's saved plan
rather than resending the full image. Keep the image small enough for practical
plan usage. A rendered `.ldr` preview is a separate image, sent after `render`.
The local rasterizer reads LDraw `ALPHA` values and composites transparent
parts over opaque geometry, so glazing can reveal interior structure in
previews. Its back-to-front transparency sorting is approximate for
intersecting clear meshes; use the image for design feedback, not as a
photorealistic or physical guarantee.

On the first model request, the runner locally searches the reference corpus
from the build brief and provides up to three purpose-labeled examples with
source ID, hash, license field, top parts, and a compact height-sorted
placement sample, plus a small geometry-backed dictionary of those common
parts' names, approximate spans, and heights. The primary source matches the
subject and style when available; further sources may illustrate a related
architectural mass, terrain, or roof technique. A terrain source is not a
house-style source. This is a starter pack, not a
claim of semantic search or
permission to redistribute a source set. The agent should use it to set a
dimensional plan and only spend a further lookup turn on a specific missing
construction detail. The starter pack is recorded in session state for audit.
Reference search also indexes literal part-family names from the local
catalog (for example `hinge`, `arch`, `window`, `slope`) when those parts
appear in an `.ldr`. Results report `matched_part_families`. These tags help
locate parts-in-use, but do **not** prove a complete hinged bay, archway, or
roof technique; inspect the actual placements before adopting one.
For a style-matching reference of at least 200 pieces, the runner also
renders one local front-left preview and sends it on the first request, so
visual proportion study need not consume a separate tool turn. The model is
explicitly told that this is a real-set reference, not its current build.
If the local preview fails, the textual starter pack remains usable and the
error is recorded in session state.
When a user supplies a design photo, that photo is sent after the example
preview and explicitly takes priority over it; the real set is only a
construction reference.

The runner saves `state.json`, named `.ldr` modules, an assembled `build.ldr`,
checker reports, and renders under the session directory. Every module save
runs the checker and returns its current failures. A module save that increases
mesh collisions or turns a passing build into a failing one is rolled back
and returns `candidate_validation` for repair;
a partial build may have expected gaps, but collisions and lost contacts still
need attention. Its tool calls are `search`,
`inspect`, `study_reference`, `inspect_reference_region`, `inspect_build_region`, `render_reference`, `search_parts`, `inspect_part`, `inspect_alignment`,
`search_omr_sets`, `fetch_omr_set`,
`set_plan`, `save_module`, `clone_module`, `discard_module`, `read_module`, `recolor_module_lines`, `edit_lines`, `move_lines`,
`move_groups`, `save_array`, `save_floor`, `save_wall_runs`, `save_gable`, `save_stepped_roof_beams`, `save_roof_tile_caps`, `save_support_column`, `save_roof_seam_column`, `check`, `render`, `review_renders`, and `submit_design`; the exact agent-visible
contracts are in the canonical system instructions. `render_reference` queues
a searched real-set model image, with source identity and license, for visual
study of proportions and techniques; it is not permission to copy a set.
`inspect_reference_region` uses the stud/plate coordinates reported by
`study_reference` to return exact, line-numbered placements from a bounded
spatial region of a searched source, with SHA and license. It pages 40
placements at a time. Region membership uses part origins, not mesh body
intersection; this is retrieval evidence, not proof of an isolated buildable
subassembly.
`review_renders` records a strength, the largest visible weakness, and a
specific architectural revision after two current views have been delivered.
`submit_design` then requires changed LDraw placements and two fresh views.
This enforces an iteration, not aesthetic quality; a token detail that leaves
the named weakness unresolved should still be rejected.
`inspect_build_region` uses the same bounds on the current assembly and adds
both assembled build line numbers and module-local line numbers. This lets an
agent inspect a facade or collision neighborhood before `edit_lines`, moves,
or `recolor_module_lines`, without paging through unrelated modules.
`save_floor` tiles disjoint stud-edge LDU rectangles with catalog-backed
plates, avoiding the overlapping large-plate placements seen in early pilots.
For the normal `3811.dat` baseplate at Y=0 (underside at checker ground Y=8),
put a floor plate on top with `save_floor` Y=-8. The checker flags
`parts_below_ground` with source line samples when this datum is wrong.
For a three-course wall above that plate, brick origins are -32, -56, -80;
the next plate sits at Y=-88. Whole-room upper floors need support below
each tile or overlapping bonding plates: edge-touching tiles are not stud-
connected. The tool now returns a floor-support hint when its checker finds
disconnected components, and the agent should repair or discard that module.
`save_wall_runs` generates staggered one-stud-thick brick courses from
explicit wall segments and half-open door/window opening ranges. It rejects
overlapping generated wall cells; the module-save rollback guard catches
collisions with already saved geometry.
`save_gable` generates a narrowing, brick-height-stepped end wall over a
supported lintel; it does not supply a roof plane. Gravity failures now include
line-addressable suspect parts from a relaxed force-balance solve. They are
diagnostic hints to inspect nearby supports, not proof of the unique cause.
`save_stepped_roof_beams` pairs with matching front/rear gables to cover a
small building in longitudinal 1xN bricks, one stepped course per stud of
width on each roof side. It enforces full width, support-stud phase, and a
short end overhang before saving; the normal checker then tests the assembled
roof. It is intentionally a *stepped* roof, not a smooth slope, and the static
checker does not measure long-brick bending or assembly order.
`save_roof_tile_caps` accepts the same dimensions and closes the exposed
roof-beam studs with non-overlapping tile lengths. On the Luna shed it added
24 tiles, bringing the model to 109 parts; all five checks passed and the
render had a visibly cleaner, though still stepped, roof. A single 3037 slope
attached over a roof beam connected without collision but failed gravity
because its outboard underside row had no support. Flipping the slope solved
gravity but collided with the adjacent higher course. Do not present those
failed probes as a verified smooth-roof technique.
`save_support_column` stacks aligned 1x1 or 2x2 bricks and an optional cap
plate to support a precisely identified overhang. A 2x2 column can bridge
the seam between two adjacent 4-stud roof-slope segments. It is a repair
primitive, not a substitute for designing a roof-wide support lattice.
`save_roof_seam_column` makes a narrower 1x2-Z post at the next roof course's
inner stud row; it avoids overlap with the preceding 2x2 posts while
supporting adjacent four-stud slope segments.
`discard_module` saves an audit revision before removing a failed module and
rechecking the remaining assembly.
`recolor_module_lines` changes only selected placements' colors using the
module-local numbers returned by `read_module`; it preserves coordinates,
part IDs, and rotations, saves an audit revision, and runs the checker. This
supports rapid palette and trim revisions without whole-module LDraw rewrites.
A render is sent as an
image to the model on the *following* step. Each `step` makes exactly one
model request and may execute up to eight local tool calls. A step can stop
after planning or retrieval; repeat deliberately until the design has been
rendered, critiqued, and checked. It is not a timed 30-second generator.
After a changed build, the next step automatically checks the latest assembly
and sends a front-left preview. A passing build near 80% of its target's lower
piece count (and at least 200 pieces) also receives front-right, so a design
review need not spend a request obtaining a second angle. Explicit `render`
calls add other views.
`queue-render` prepares up to four distinct camera images locally, without a
model request, for the next `step`. It helps with multi-angle visual review
while keeping plan usage deliberate. Re-rendering the same view within a step
keeps the prior PNG as a numbered revision rather than overwriting it.
The ChatGPT plan-token sharing route can return
`subscription_sharing_usage_limit_exceeded` even while the Codex app's general
usage windows show capacity. Treat that response as a hard stop for live
session steps; the failed step does not advance saved geometry. Do not retry
until that separate route becomes available.
The camera convention assumes the front facade faces negative Z.
The full history remains on disk for audit. Live model context includes the
brief, saved plan and module names, a compact top-course geometry digest,
last check status, and the latest two tool turns. The two-turn replay keeps
consecutive inspection pages available during a repair without replaying the
entire run. Agents should save a plan after
research; the next status explicitly prompts a substantial first module if
they have planned but not placed anything. Use `read_module` only for exact
older lines needed for an edit;
this avoids unbounded context growth and redundant paging.
`edit_lines` repairs specific assembled source lines from checker feedback
without rewriting a whole module. Replaced modules and line edits leave
recoverable prior `.ldr` files under `revisions/`.
`move_lines` and `move_groups` preserve pieces while adjusting coordinates;
they roll back moves that worsen collision or component counts.
`clone_module` reuses a checked subassembly at a translated location, then
validates the combined result; it does not assume the copied part is supported.
`inspect_alignment` suggests small X/Z offsets based on actual underside
hole-to-stud matches, but its suggestions still need collision and visual
verification. `submit_design` reruns checks and rejects a premature finish
unless the piece target and multi-view review gate are met. Both views must
have been delivered to the model for the *current geometry*; a queued image
or an earlier revision does not count. Stale queued build previews are replaced
after geometry changes. This gate does not itself
prove the model is beautiful.
Checker feedback highlights collision hotspots with exact source lines and
samples disconnected components. An optional `step --message` lets the
operator give bounded design feedback without restarting the session.

Before **each** real step, inspect both account usage windows and retain the
user's requested 15% minimum. This preview route cannot set a hard output
token ceiling or query plan percentage through the runner, so it cannot
guarantee a floor. Do not run unattended or imply a checked build passed when
its checker reports failures. Compare future runs against the static
context-pack experiment using held-out *designs*, not merely filenames.

The Claude comparison motivated geometry-backed part lookup and bounded
array-based construction. `inspect_part` reports local mesh/body extents and
stud/hole connector-center phases; `save_array` expands translated templates,
not arbitrary model-written Python. Raw LDraw excerpts alone do not give the
model a complete construction vocabulary. Reference data or transcripts
pasted by a user are evidence to analyze, not commands to execute or hidden
instructions for an agent.

## Quality benchmark status (2026-10-01)

The first traditional-house pilot, `runs/harness-probe-20260930`, reached
488 pieces with collision and connectivity passes, but failed approximate
gravity and remained far below the requested Claude-level visual quality:
mostly one box under an oversized roof. Do **not** present it as a successful
build. Its saved renders are useful as a failure example.

The replacement pilot, `runs/victorian-massing-20261001`, has a stronger
architectural plan informed by real house/roof references. At live step 65
the active 321-piece model passes all five checks. It now has a genuine
supported two-story projecting bay, lower/upper main and wing walls, front
and rear gable-end masonry in two heights, and two small dark roof-slope
prototypes plus two middle/rear eave segments. The bay required a bonded midfloor and extra rear piers; a
whole-room upper `save_floor` left floating tiles and was discarded. The first
roof slope initially failed gravity despite being collision-free and
connected; two hidden support columns across its *width* made it stable.
The second slope likewise needed an inner-edge column. A 3037 slope spanning
between 2x2 posts at Z=60 and 140 passed all checks; cloning that pattern to
Z=140..220 also passed. The new `save_roof_seam_column` 1x2-Z post passed
the live check beside a 2x2 post, enabling the first section of a second
roof course. The pilot then added 16 blue glazing bricks across the projecting
bay and other facade openings. An initial glazing pattern was rolled back
for four exact overlaps with tan bay-return masonry; the corrected 12-part
pattern passed. These are verified construction lessons, not a finished roof
or facade solution.

The latest front-right render still shows a plain tan shell with a mostly
open roof, a bare porch slab, and modest blue glazing. It is **not** at the
user's Claude-level visual target. The next development priority is an
efficient, reusable roof support-and-covering pattern (ideally interior
trusses/rafters instead of a full-height post under every slope), then porch,
trim, and a two-angle visual critique. The session status now includes the
entire module geometry digest and current checked piece count; the old
3,500-character truncation hid the newest modules and caused the agent to
spend a turn rereading wall files. Do not submit this pilot yet.
At step 67, a proposed outer porch column landed off the supported pad and
failed connectivity/gravity. Its module was discarded with an audit revision,
restoring the 321-piece passing build. Incremental construction can now keep
a provisional, collision-free module even if it temporarily fails support or
connectivity; new collisions and ground regressions still roll back. The
agent must repair provisional failures before `submit_design` can pass.
The bounded `gpt-5.6-luna` shed pilot, `runs/shed-luna-20261002`, revealed that
repeated lookup and one-tool-per-turn pacing are costly even for a small
design. Its initial 58-piece shell passed construction checks but remained
roofless; a 30-part slope attempt caused 97 collisions and was rolled back.
Using the new stepped-roof tool after extending both gables to six rows gave
a complete 74-piece roofed shed with all five checks passing. Luna then added
a green door and blue side glazing. A first landscaping attempt collided with
the floor; corrected path and shrubs brought the model to 85 pieces, again
passing all five checks. This is a successful small-roof primitive and a
credible compact shed, **not** a finished premium set: trim and display-scale
landscape design still need work.
The checked tile-cap pass subsequently improved roof surfacing without live
model usage; facade trim and landscape composition remain open.
A later Luna pass used `inspect_build_region` to find exact front-facade
placements and added a seven-part, stud-supported white doorway frame.
An attempted 20-part planter then failed with 54 mesh collisions: the agent
placed 1x2 parts on 1x1 origin parity and overlapped their long axes at
20-LDU intervals. `save_module` rolled that revision back. The canonical
agent instructions now spell out 1x2 origin parity and non-overlap spacing;
on a bounded retry, Luna built an eight-part 1x1 planter. The saved shed has
124 parts and passes all five checks. The `step-17-front_right.png` render
reads clearly as a shed but still has a plain side wall and small,
unconvincing landscaping. Treat the passing checks as construction evidence,
not a premium-design rating.
The next aesthetic pass surfaced a catalog-search bug: `search_parts("flower
foliage")` returned no matches despite many indexed flower parts. The
multiword search now falls back to actual single-term matches when no joint
match exists, while preserving requested part-family and dimension filters.
A three-plate flower accent then brought the shed to 127 parts, again passing
all five checks; this remains a modest display build rather than evidence
that the harness reaches the earlier Claude visual-quality target.
At step 20, Luna used the geometry-preserving recolor tool to turn one
existing right-wall brick into a blue horizontal window; all five checks
stayed green and the piece count remained 127. The step-20 front-right render
shows the window, but also makes the remaining quality gap clear: the roof
looks heavy relative to the short walls, the window reads more like a vent,
and the landscape is sparse. In a final bounded critique turn, Luna declined
another cosmetic recolor. No claim of premium visual quality follows from
this pilot.
An initial live `run --max-requests 3` test on the same saved shed spent all
three requests on part lookup and saved nothing (38,572 reported tokens).
After adding a lookup-streak reminder, a two-request retest attempted a
garden module, rolled back a collision, and saved a passing six-part repair.
Its render showed two weak posts rather than the requested coherent display
feature. That module was discarded through the audited `discard_module`
path, restoring the 127-piece passing build. The reminder now explicitly
retains the brief's visual and piece-count requirements, and the run summary
exposes module size. This behavior has offline coverage, but the revised
wording has not yet passed a live visual-quality test.
The first six-request `gpt-6-astra` modern-house run,
`runs/astra-modern-house-20261002`, also saved **no** geometry: every turn
searched, studied, or rendered references (61,744 reported tokens). This
showed that an advisory lookup reminder alone is insufficient. The first-turn
reference starter pack now prefetches a relevant example and placement sample
locally, and the initial session instructions tell the model to plan from
that pack before further searching. The later Astra continuation verifies
that this moved the agent to geometry, though its build still misses the
held-out visual quality bar.
In a new Astra session with the starter pack, the first completed request
saved a detailed two-story plan; the second rendered Farnsworth House for
visual study. The third request hit
`subscription_sharing_usage_limit_exceeded`, so no geometry was built and
the initial live test could not establish visual quality. It was later
resumed after the route became available; see the hybrid-run note in
`docs/QUALITY_BENCHMARK.md`. Inspection also found an
offline retrieval error: the broad brief ranked Sydney Opera House as a
residential example because its title contains "House". Starter selection
now filters ambiguous Opera House matches for residential briefs and favors
the requested architectural style; the exact modern-house brief now selects
Farnsworth House. The resumed session did use that selection.
A separate seeded-shell control run, `runs/roof-tool-eval-luna-20261002`,
checked whether an agent could actually use the new capability. Given the
gable coordinates in an operator message, `gpt-5.6-luna` chose
`save_stepped_roof_beams` in one turn (74 parts, all five checks passed) and
`save_roof_tile_caps` in the next (98 parts, all five passed). This supports
tool usability for a compact known-geometry gable; it does not establish
autonomous roof design from an unconstrained brief or a smooth-slope solution.
The older 58-collision attempt and failed floor/bay revisions are preserved
under the run's `revisions/` for audit. A prior
`subscription_sharing_usage_limit_exceeded` cleared after the usage reset;
stop again if it recurs. Offline tests and local renders do not use that route.

## ChatGPT plan usage

This local-personal-project integration requests `chatgpt.tokens.use.direct`
along with the required OAuth scopes. It saves the OAuth credential under
`~/.config/bricksmith/chatgpt-plan.json` (owner-only), **outside this repo**.
It sends that authorized access token as a Bearer credential to the public
`https://api.openai.com/v1/responses` endpoint. It does not scrape a ChatGPT
browser session, use an API key, or mistake identity-only sign-in for inference.
Install `requirements.txt`, then:

```bash
python scripts/chatgpt_plan.py login
python scripts/chatgpt_plan.py models
python scripts/chatgpt_plan.py ask --model MODEL_FROM_LIST --prompt "Describe one sound roof attachment technique."
```

`login` opens a browser and waits up to three minutes for a `127.0.0.1`
callback. Grant ChatGPT **plan usage**, not merely identity. The login command
validates the signed ID token, checks the granted usage scope, and saves tokens
only after both pass. `models` discovers the account's available models before
requests. `ask` uses the canonical design-agent system instructions and makes
one streamed, real model request with `store: false`; it refuses to report a
partial stream as success. For a minimal transport check only, add
`--no-system-prompt`. No requests are sent until you run these commands.

`ask` remains a transport check: it does not expose reference search or
physics tools to the model or save a build. Use `agent_session.py` for the
bounded tool-calling design loop, or `workbench.py` for manual checks.
Plan usage is subject to the signed-in account's model availability and usage
limits. Paid or remotely hosted BrickSmith deployments require separate OpenAI
approval; do not repurpose this personal/local flow for that product.

### One-request build pilot

`scripts/test_build.py` runs a bounded RAG → generate → local check → render
pilot. It sends the canonical system prompt and bounded source excerpts from
two architectural models, saves the raw response and parsed `.ldr`, and records
checker feedback in an ignored `runs/` directory. `--repair-from` makes one
new request with the previous `.ldr` and exact checker errors. Every invocation
without `--dry-run` makes **one** plan-usage model request; there is no
autonomous retry loop.

```bash
python scripts/test_build.py --brief "A compact cottage with porch and pitched roof" --dry-run
python scripts/test_build.py --brief "A compact cottage with porch and pitched roof" --model gpt-5.6-sol
```

Before each real invocation, check remaining five-hour and weekly plan usage
in ChatGPT Settings → Usage (or a trusted account usage tool). This preview
Responses flow has no supported `max_output_tokens` field or programmatic
remaining-plan percentage, so this script cannot enforce a percentage floor
by itself. Do not run it unattended with a strict minimum-remaining policy.
Review `report.json`: a rendered image is not proof of structural stability.
The pilot exposed that lexical retrieval can return a stylistically irrelevant
house and that a single repair may improve connectivity without achieving a
physics pass. These are inputs to the next tool-calling design loop.

Implementation contract:
[registration and sign-in](https://developers.openai.com/siwc/token-sharing-open-source/sign-in),
[models and inference](https://developers.openai.com/siwc/token-sharing-open-source/models-and-inference),
[preview limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations).

## M2-B offline tool adapters

M2-B exposes the existing compatibility tool names through the same
`agent_session._tool` dispatcher when the caller supplies an exact versioned
offline invocation. This path operates only on an explicitly initialized
transaction workspace and routes every mutation through M2-A. It is distinct
from historical v1 session file writes. V2 snapshots and transaction workspaces
remain unavailable to model `step`/`run` until M7.

```sh
./.venv/bin/python scripts/workbench.py transaction-tool-catalog
./.venv/bin/python scripts/workbench.py transaction-tool /tmp/m2-session /tmp/invocation.json
```

The invocation binds the tool name, unchanged argument object, operation UUID,
expected base revision UUID, and SHA-256 of that revision's assembled `build.ldr`.
Mutation line numbers are valid only for that sealed export; after a revision
change, read the new export/map and form a new invocation. `save_module` replaces
the named assembly's direct parts using fresh stable part IDs while preserving
its assembly identity and unrelated records. `clone_module` likewise allocates
fresh instance IDs and records source relationships. Blocked evidence remains
available; a committed `provisional` or `repair_incomplete` construction status
is not final acceptance. Offline render results record creation and source
identity, not visual review.
