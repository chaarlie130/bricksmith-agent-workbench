# Victorian house: retrospective process review

Reviewed 2026-10-16. Conversation:
`f289bdfb-8b37-4cd9-a3c0-037b3b9dce42` in Antigravity.
This is an exploratory case study, not a frozen benchmark or acceptance record.
No model request or geometry modification was made during this review.

## Sources and attribution

Inspected the local conversation's `.system_generated/logs/transcript.jsonl`,
the run's generator and LDraw files, the user-supplied output images, and the
LEGO-style reference image attached to the historical brief. Transcript source:
`/Users/charliecittadini/.gemini/antigravity/brain/f289bdfb-8b37-4cd9-a3c0-037b3b9dce42/`.
Recorded check evidence and hashes: [victorian-review-checks.json](evidence/victorian-review-checks.json).

The UI selection was Gemini 4 Argon (Medium) during the Victorian design segment.
Before the later Blender work it changed to Gemini 3.8 Flash (High), at step 184.
These are recorded UI labels, not independently verified provider model IDs or
claims about public release dates/performance rankings.

Human clarification after review: the user manually stopped Argon after image
creation to inspect the renders, then selected Flash specifically to finish the
rendering work and save tokens. The missing final acceptance record must therefore
be classified as a user-interrupted design run with a rendering-only handoff,
not an observed autonomous stopping failure by Argon. Whether Argon would have
completed the final gate without interruption is unknown.

This was a continued conversation after a modern-house build. The Victorian
brief included detailed text, a real-house image, and a LEGO-style reference.
The observed design segment, steps 110–182, spans 09:47:13–10:02:07 UTC
(14m54s); it is not a compute-only measurement or the time for later Cycles work.
It contains 23 command calls, one file creation, six file-edit calls, and five
file-view calls. Those totals exclude the earlier house and subsequent rendering.

## What worked

1. It researched a roof-bearing reference model and inspected actual part bounds
   and connectors. It tested slope rotations, a two-course roof stack, and small
   porch assemblies with the real validator before composing the full building
   (steps 119–132).
2. It wrote a reusable local grid builder with explicit part dimensions, repeated
   runs, slope origins, and an occupancy check. This reduced repeated placement
   arithmetic while keeping the design strategy under model control.
3. It repaired concrete failures: two generator overlap exceptions, foundation
   connectivity and support, an unsupported porch slab, and roof/attic support.
   The recorded final response was supported by actual checker output, rather
   than merely a successful shell command. The checker CLI returned exit zero
   for several failed reports, and the model correctly read the report contents.
4. The final output communicates the main requested massing, palette, pitched
   roofs, projecting front section, chimney, and wraparound porch. The supplied
   images are substantial evidence of visual progress, although not full brief
   compliance or physical assembly validation.

## Construction evidence

| Artifact | Physical placements | Fresh reviewer checks |
| --- | ---: | --- |
| `01-foundation-walls.ldr` | 281 | All five passed |
| `02-openings.ldr` | 745 | All five passed |
| `03-complete-roof.ldr` | 977 | All five passed |
| `victorian_house.ldr` | 985 | All five passed |

Artifacts are under `runs/victorian_house/`. The five checks are mesh collision,
included base, no parts below ground, actual connectivity, and approximate gravity
equilibrium. Fresh checks used the repository virtual environment and explicit
`BRICKNET_DATA`, after required imports. The transcript also records stage-one
success at step 161 and final stage-two/roof/model successes at step 173.
Fresh results confirm today's saved files in today's environment; they do not
reconstruct the historical source/dependency snapshot or prove real-world strength,
assembly order, insertion clearance, or acceptance-gate completion.

## What the run does not establish

- It used Antigravity's coding tools, a bespoke Python generator, and BrickSmith's
  inspection/check/render APIs and CLI. No M2 transaction invocation appears in
  the Victorian segment. The result predates final M2 acceptance and cannot
  measure an improvement caused by M2. It does demonstrate the usefulness of
  the existing construction infrastructure under an external coding harness.
- The inspected transcript contains `accept_build.py --help` in the earlier
  house segment, but no execution of the final acceptance gate. No
  `acceptance.json` exists in the Victorian run directory. Images were opened,
  but there is no recorded geometry revision after the first two views were
  opened before the user interrupted the design run and handed rendering to Flash.
  This establishes unfinished acceptance evidence, not a failure to follow through
  by a model that was allowed to finish. The individual construction checks had
  already passed; the outstanding work was final gate execution and any further
  visual/brief-compliance review, not an entirely unchecked model.
- Visual comparison shows simplifications: the requested circular gable window
  and ornate gable detailing are absent or substantially simplified, and the
  projecting bay is boxier than the reference. Checker success therefore must
  remain separate from brief fulfillment and architectural quality.
- The build is image-conditioned and benefits from prior-session experience.
  A fair comparison must preserve those inputs or explicitly use a fresh-session
  condition. It is not evidence for text-only or first-attempt performance.
- The later photorealistic presentation includes another selected model and
  renderer setup/debugging. Attribute geometry and presentation separately.
  No reliable dollar-cost comparison or frozen historical run provenance was
  established in this review.

## Consequences for the harness plan

- Preserve procedural design freedom. Give agents a supported way to create and
  test small candidate assemblies, then compose them into a larger transaction.
  A rigid requirement to hand-place every brick could lose a demonstrated strength.
  Any future script execution must still publish through bounded validation and
  transaction interfaces; this run does not authorize a new execution feature.
- M3 should retain proven local techniques, their source/test evidence, failed
  repair attempts, and outstanding visual requirements. A roof-support repair
  must not silently remove the obligation to revisit the circular window or trim.
  Current geometry, intended features, and completed observations need distinct
  records. A context-truncation test can use this failure pattern without copying
  this design into a held-out evaluation target.
- M4/M5/M7 should make finish conditions executable: inspect both source-bound
  views, account for remaining requirements, run the final gate, and record a
  truthful terminal state. For a manual interruption or model handoff, expose
  which checks are complete and which completion requirements remain. The human
  clarification makes this a handoff/status-design lesson, not evidence of an
  autonomous stopping defect or deliberate evasion by the model.
- Reduce environment discovery and renderer setup work with stable part inspection
  and rendering entry points. Preserve fast construction previews separately from
  presentation renders; renderer quality must not hide geometry differences.
- For future benchmarking, record reference images, prior-context policy, provider
  identity and settings, tool/renderer versions, failures, elapsed time, cost,
  and acceptance alongside visual scoring. If this case informs implementation,
  treat it as development evidence rather than an untouched held-out test.

The review changes no milestone scope. M2 remains accepted; M3 remains unstarted.
