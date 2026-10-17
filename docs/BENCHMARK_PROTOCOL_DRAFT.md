# BrickSmith first official benchmark — protocol draft

Status: **DRAFT; not frozen, funded, or executed.** Prepared 2026-10-15.
This document defines the setup work following the harness assessment. It does
not declare existing example renders or historical sessions official results.

Related: [implementation plan](HARNESS_IMPLEMENTATION_PLAN.md),
[contracts](HARNESS_CONTRACTS.md), and the existing historical
[quality notes](QUALITY_BENCHMARK.md).

## 1. Evaluation questions

The primary question is: with the same model and resource allowance, does a
harness revision more reliably deliver a complete, visually convincing,
construction-checked original LEGO build?

Keep three experiments separate:

| Track | What varies | What stays fixed |
| --- | --- | --- |
| Harness iteration — primary | Harness code, its tools/context/prompt/controller | Model/configuration, task inputs, libraries, evaluation checks/renders, external references, budget policy |
| Model comparison | Provider/model and explicitly declared necessary adapter differences | Harness, tasks, available capabilities, evaluator, resource policy |
| Runtime comparison | Custom runner versus a mature coding harness | Domain engine and task inputs; model/settings/budgets where both support parity |

A runtime comparison with different hidden prompts, models, tools, context limits,
or budget enforcement is a declared system comparison, not a causal measurement
of one harness change. Do not invent parity when an interface cannot provide it.

## 2. Order of work

- [ ] B0.1 Complete M0's portable fixtures, environment manifest, and baseline
  provenance export. Preserve the inspected starting source commit and any
  uncommitted source patch separately from the instrumentation/evaluator code.
- [ ] B0.2 Implement an external evaluation adapter that can inspect artifacts
  from the frozen baseline without changing its generation behavior. Record the
  generator and evaluator commits independently.
- [ ] B0.3 Select and freeze the task suite, actual model/transport/settings,
  budgets, rubric, execution policy, and reference snapshots with the planning agent.
  All required fields must be concrete before official execution is enabled.
- [ ] B0.4 Capture the original harness baseline before behavior changes, or run
  its preserved checkout later with the same frozen evaluator/environment. Never
  compare an old screenshot to a freshly evaluated candidate as a controlled result.
- [ ] B1 Implement manifest validation, scheduling, offline dry-run, and fake
  provider execution. Test scoring/reporting with synthetic pass/fail/error cases.
- [ ] B2 Run authorized baseline and candidate trials under the frozen protocol.
  Preserve every assigned attempt and any intervention. No best-of selection.
- [ ] B3 Complete blinded review, publish an immutable result bundle in the
  existing repository's benchmark history, and record the reviewer decision.

This setup need not wait for M7. Freezing/capturing the baseline early prevents
losing the comparison point while the harness is being improved.

## 3. Task design and contamination control

Recommended initial scale: **six original briefs, three independent repetitions
per brief per harness version**: 18 attempts per version, 36 for a baseline/candidate
comparison. This is a proposed small first study, not an approved spending plan
or enough evidence for a universal capability claim. A cheaper two-case/one-repeat
smoke suite is useful during development but is not the official score.

The first suite should focus on architectural display builds, matching the current
product and checker scope. Suggested coverage slots, not final briefs:

1. Modern composition with glazing, a usable terrace, and layered roof forms.
2. A compact building with intersecting pitched roofs and a legible entrance.
3. A building integrated into terrain with a coherent approach/stair route.
4. A vertically organized subject with distinctive silhouette and base proportions.
5. A civic or industrial subject requiring facade rhythm and subordinate masses.
6. A supplied-reference interpretation with clear defining features.

The photo-guided case must use an original or rights-cleared image and is reported
separately as well as in the prespecified aggregate. Do not reuse the user's
attached benchmark images or source house models as scored target geometry.
Exact briefs, required features, ground convention, piece ranges, and assets are
selected later and frozen verbatim. Each task should fit the frozen checker's
supported mechanics; expanding mechanics coverage becomes a separate challenge.

Use a **development split** for the modern-house revision fixture and debugging.
Use separate evaluation briefs/geometry for the initial official suite. Keep
evaluation assets out of retrieval indexes, technique libraries, examples, and
worker-generated fixes. Original design evaluation must not retrieve its answer.

Once a suite is repeatedly inspected and optimized against, call it a public
regression suite rather than indefinitely claiming it is held out. Track exposure
and add fresh evaluation tasks in a new version. An initial held-out claim requires
that implementation workers actually did not have/use those task details before
the evaluated change was frozen. Folder names alone do not establish this.

No shared writable learning memory between scored attempts. Start each in a clean
workspace with the same reviewed technique snapshot. If evaluating learning across
tasks later, define it as a separate protocol with a fixed task order.

## 4. Frozen manifest

The evaluator refuses an official run if any required field is absent or a
placeholder. The planning agent sets these at benchmark setup:

| Field | Freeze requirement |
| --- | --- |
| Benchmark ID/version | Immutable task/rubric/protocol identifier and content hash |
| Cases | Exact briefs, feature rubrics, ground Y, integer minimum/maximum pieces, input image hashes |
| Repetitions/order | Three per case by default; prespecified shuffled/interleaved schedule and schedule seed |
| Model | Provider, requested model, resolved snapshot when available, reasoning/generation settings and unavailable settings |
| Resource profile | Request ceiling, total-token accounting/ceiling, soft overshoot rule if applicable, wall-time limit, local tool timeout, monetary ceiling if enforceable |
| References | Exact corpus/technique/data manifests, exclusions, permitted access methods |
| Evaluator | Frozen checker code/config, coverage profile, renderer, palette/data, cameras and framing algorithm |
| Judgment | Rubric version, rater procedure, blinding/randomization, adjudication and pass thresholds |
| Environment | Dependency lock/snapshot, OS/architecture, CPU/memory and library resolution |
| Execution | Autonomy rules, stop/continue policy, retry policy, network policy, attempt registration |
| Accounting | Price schedule identity/currency or explicit unavailable-cost state; all provider usage categories |

Record unsupported sampling seeds as unsupported. A scheduling seed can reproduce
assignment order but cannot guarantee deterministic model output. An unstable
provider alias limits repeatability; run versions interleaved in the same period,
record dates/resolved identifiers, and avoid claiming exact model equivalence later.

Disable live OMR/web retrieval in the primary track. Use a fixed allowed local
snapshot for both versions. A future live-retrieval track must be separate.
Retrieval ranking improvements are valid harness changes within that same corpus.
Expanding the corpus/technique library changes an input; evaluate that as a declared
additional experiment or new baseline instead of silently combining it.

The existing plan-usage route has soft-limit/account-visibility limitations.
Choose either an explicitly shared soft-budget protocol with measured overshoot,
or a transport that supports the required enforcement. Do not write a fake
`max_output_tokens` parameter into an unsupported adapter. A strict spend-limited
study cannot start until its transport can support the selected profile.

## 5. Attempt execution

Register the complete case × repetition × version matrix before any calls. Each
attempt has its own immutable ID, directory, initial input manifest, and budget.
The scheduler records not-started, started, and terminal outcomes; failed attempts
remain visible in the denominator.

Use one model session per attempt, clean initial state, and only prespecified
inputs. No human repair, hidden extra prompt, manual insertion of geometry, quota
extension, or reuse of a stronger run's output. Operator intervention makes the
attempt assisted; retain it but do not count it as autonomous success.

For the baseline, repeated bounded `run` invocations may continue only when the
stop reason was an internal request/token batch limit and the global attempt budget
permits continuation. No added operator message or rewritten controller advice is
allowed. Accepted submission, model stop, research/repair stall, hard quota error,
or exhausted global budget are terminal under the frozen policy. Record this
adapter behavior for both versions before execution.

Budget accounting spans all batches and failed/retried calls. A soft ceiling may
overshoot by the final in-flight request; expose the overshoot and use the same
dispatch rule for both versions. Wall-time expiry stops new work and interrupts
local tools where safe. Unknown remote completion/billing prevents automatic
resubmission. Local completed tool calls replay from receipts without new charges.

Pre-dispatch infrastructure failures prevent starting the scheduled block and
are reported. Failures after a run starts remain attempt outcomes. If a provider
outage compromises a block, label the block and, if agreed, repeat the entire
matched block under a new ID; preserve the original. Do not selectively replace
weak outcomes with favorable retries.

Freeze the final candidate as the runner's submitted revision, or its last committed
revision at termination if no submission exists. Do not let the evaluator choose
the prettiest intermediate. Score incomplete final artifacts where possible and
keep their delivery status separate. Evaluation renders/checks do not repair them
or retroactively create model review/stage evidence.

## 6. Independent evaluation and reported metrics

The frozen evaluator checks final geometry, not the harness's prose claim of success.
Rerun all five checks at the task ground Y, calculate physical count, and record
coverage. Use a frozen evaluation policy across compared generator versions.
If the checker changes, re-evaluate archived geometry in a separately identified
evaluation series; do not compare old and new checker pass rates as harness gains.

Report these distinct outcomes for every attempt:

- **Construction pass:** all five final checks pass with sufficient supported
  coverage; unavailable/unsupported evidence cannot count as a pass.
- **Budget compliance:** piece range and execution-resource policy are satisfied.
- **Brief pass:** all prespecified mandatory features satisfy the external rubric.
- **Visual pass:** the frozen visual rubric threshold is met.
- **Artifact qualified:** construction, budget, brief, and visual pass together.
- **Autonomous delivery:** a qualified final artifact was explicitly submitted
  by the runner without operator intervention. Merely having a good last snapshot
  after a crash or stall does not count as delivery.
- **Internal workflow status:** the runner's own acceptance, stage/review evidence,
  and stop reason, with its policy version. Report separately from artifact quality.

**Primary metric:** autonomous delivery rate over all scheduled attempts in the
completed evaluation block. Also report artifact-qualified rate, each component
pass rate, and counts of unavailable, stalled, incomplete, and assisted attempts.
This prevents both a pretty invalid model and an unfinished passing shell from
becoming a headline success. For an unexecuted schedule, show pending slots and
do not publish a final success rate.

Report total and per-attempt tokens, elapsed/model/tool time, tool counts, rejected
candidate counts, and intervention counts. Cost per autonomous delivery is **all
attempt costs divided by delivered successes**, not just successful-run costs.
With zero successes it is undefined; with missing billing it is unknown. Always
show the numerator/denominator and the failed-work cost. Token cost and financial
cost remain separate metrics.

Report per-case results and distribution/ranges as well as aggregates. Repetitions
within a task are not six times as many distinct task types. For version deltas,
show matched case/repetition outcomes and uncertainty grouped by task (e.g. a
prespecified case-level bootstrap). With six tasks, qualify uncertainty and avoid
declaring significance from a tiny convenience sample.

## 7. Visual/brief review

Generate a standard contact sheet from the actual final LDraw, with front-left,
front-right, back-left, and top views. Freeze camera angles, backdrop, resolution,
palette, lighting, and framing. For pairwise version comparisons, use the same
per-view scale/target derived from both models' union bounds. Do not let one version
win through a closer crop, hidden rear facade, or higher-quality render settings.

Raters see the brief/reference and anonymous render IDs. Hide model/version,
checker outcomes, author self-review, and token cost until visual judgments are
recorded. Randomize left/right presentation with the saved schedule seed. Require
at least two independent human ratings for the first official benchmark; retain
both and adjudicate disagreements that change pass/fail. If only one reviewer is
available, publish it as single-rater exploratory evidence.

Proposed rubric to freeze before scoring: 0–4 on each dimension.

| Dimension | What the rater assesses |
| --- | --- |
| Subject/brief fidelity | Defining requested features are recognizable and integrated |
| Proportion/silhouette | Major masses, roof/body relationships, scale and composition |
| Completeness | Intended enclosure/roof/entrance/site work is visibly finished |
| Detail/material coherence | Openings, trim, palette, interiors/landscape support the design |
| Overall design quality | The artifact reads as an intentional, convincing display set |

Common anchors: 0 absent/unusable; 1 major deficiencies; 2 recognizable but
substantial weaknesses; 3 convincing with minor weaknesses; 4 strongly resolved.
Recommended initial visual pass: mean at least 3, with no dimension below 2, plus
all task-mandatory feature checks passing. Final thresholds and adjudication are
planning decisions at B0.3; never tune them after seeing version labels.

A model-based visual judge is optional secondary evidence, not the sole first
benchmark judge. If later adopted, freeze its model/prompt, calibrate against human
judgments, preserve disagreements, and account for evaluation cost separately.
Self-review text supplied by the design agent never substitutes for external scoring.

## 8. Repository and artifact layout

Proposed tracked layout:

```text
benchmarks/
  README.md
  protocols/<protocol-version>.json
  suites/<suite-version>/manifest.json
  suites/<suite-version>/cases/*.json
  results/<experiment-id>/manifest.json
  results/<experiment-id>/attempts/<attempt-id>/summary.json
  results/<experiment-id>/attempts/<attempt-id>/final.ldr
  results/<experiment-id>/attempts/<attempt-id>/acceptance.json
  results/<experiment-id>/attempts/<attempt-id>/reviews.json
  results/<experiment-id>/attempts/<attempt-id>/artifact-index.json
  results/<experiment-id>/report.md
```

Keep compact configs, original geometry, metrics, and sanitized evidence in Git.
Use narrowly scoped `.gitignore` exceptions for benchmark review images where
needed; do not unignore all PNGs or `runs/`. Large complete trace/render archives
can use GitHub Release assets in this same repository, with hashes and relative
artifact indexes committed alongside results. Choose and document that retention
policy at setup; do not upload files or add LFS implicitly during implementation.

Store every failed/rejected candidate, tool event, check, render, and usage record
in the full archive, not only the final accepted model. Preserve source and settings
needed to replay local tools. Generative outputs need auditability, not a false
promise of bit-for-bit model determinism. An exporter must detect missing files or
hash mismatches before marking an archive complete.

Review assets for user privacy and reference redistribution rights. Unknown-license
third-party geometry stays out of public bundles; retain provenance and lawful
acquisition instructions without claiming the public bundle is fully self-contained.
No credentials, auth headers, or private provider continuation material in Git.

Results are immutable. Corrections use a new report revision referencing the
original. New briefs, budgets, reference inputs, rubric, or evaluator semantics
require a new protocol/suite identity. A new harness commit alone produces a new
result row under the same frozen protocol.

## 9. Setup decisions intentionally still open

- [ ] Exact six evaluation briefs/assets and which development examples are excluded.
- [ ] Model/provider/transport and actual supported generation settings.
- [ ] Request, token, time, and monetary budget values; total authorized study spend.
- [ ] Final rubric/thresholds, two raters, and adjudication procedure.
- [ ] Baseline/candidate generation commits and frozen evaluator/data snapshots.
- [ ] Storage/publication choice and rights/privacy clearance for included assets.
- [ ] Whether the first report includes only harness iteration or a separate runtime comparison.

Workers implement validators that reject unset fields. They must not fill these
decisions with convenient defaults and start an official experiment.
