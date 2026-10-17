# Worker implementation handoff

Use this assignment for one milestone at a time. The planning agent selects the
milestone, resolves architectural changes, and reviews the evidence. The worker
implements within those boundaries and may make ordinary local coding decisions.

## Current assignment — M3-A review corrections

The human authorized direct assignment to WORKER and a completion message back
to REVIEWER. [M2 is accepted](implementation/M2-acceptance.md) at the M2-B v3
snapshot. Implement [M3-A v3 follow-up R3b](implementation/M3-A-review-v3.md) within
the original [M3-A assignment](implementation/M3-A-worker-assignment.md), then
send completion evidence to REVIEWER and stop. M3-B, M4–M7, live model requests,
and official benchmark execution are not assigned. Preserve accepted evidence
and the disabled live v2 execution boundary.

## Accepted prerequisites — M0 and M1

See [M0 acceptance](implementation/M0-acceptance.md) and
[M1 acceptance](implementation/M1-acceptance.md). The M1 correction pass is
complete. M2-A atomic edits, candidate revisions, and recovery under Contracts C3
are accepted at v4. Preserve all accepted artifacts and the v2 model-execution
boundary after M2-B. No live inference or official benchmark execution is
authorized here.

## Historical assignment — M1

M0 is accepted; see [reviewer acceptance](implementation/M0-acceptance.md).
Give the worker [the bounded M1 assignment](implementation/M1-worker-assignment.md)
and this instruction:

> Implement only M1.1–M1.6 according to `docs/implementation/M1-worker-assignment.md`.
> Follow its prerequisite, scope, validation, and completion requirements. Leave
> the M1 review box open and stop before M2. No live inference or benchmark runs.

## Historical initial assignment — M0

Copy the following into the worker's chat:

> Work in the existing `bricksmith-agent-workbench` repository. Implement only
> milestone **M0 — Reproducible test foundation and provenance** from
> `docs/HARNESS_IMPLEMENTATION_PLAN.md`. Read `AGENTS.md`, `README.md`,
> `docs/AGENT_WORKBENCH.md`, and `bricksmith/workbench/system_prompt.md` first,
> then the plan, `docs/HARNESS_CONTRACTS.md`, and
> `docs/BENCHMARK_PROTOCOL_DRAFT.md`.
>
> The assigned scope is M0.1–M0.7 and the milestone completion evidence. The
> contracts describe future milestones too; do not implement those early. M0
> establishes provenance and portable tests without changing generation behavior,
> checker thresholds, tool capabilities, or model selection. Preserve the starting
> generator commit and distinguish your instrumentation commit from it.
>
> Use `./.venv/bin/python` from the repository root for Python commands. Check
> the environment before real physics/render tests. Replace private ignored-run
> test dependencies with small original tracked fixtures that preserve the tested
> behaviors. Mocked checks must not be reported as real physics passes.
>
> Inspect current Git status and any applicable nested instructions before edits.
> Do not modify/stage the unrelated `bricksmith-clean-view 2/` directory or other
> user changes. Do not call another AI model, consume inference usage, run an
> official benchmark, change authentication, publish artifacts, or start subagents.
> Do not remove the reusable BrickSmith engine, reference corpus, or library links.
>
> Implement and test the assigned work. Update checkboxes only when their evidence
> exists. Add a completion record using the format below. Leave the M0 review box
> for the reviewing agent. If a contract conflicts with the actual repository,
> record the conflict and smallest proposed resolution; continue independent work
> rather than silently changing architecture or weakening a check. Finish by
> reporting changed files, commands/outcomes, demonstrated behavior, limitations,
> and decisions requiring review. Do not continue to M1 in this assignment.

## Reusing the assignment

Replace M0 with the next reviewed milestone and its task IDs. List accepted
prerequisite commits and any reviewed deviations explicitly. Keep the offline,
scope, environment, and reporting rules. Do not hand a worker the entire roadmap
with an instruction to implement everything in one pass.

For a later live smoke test or benchmark, use a separate assignment that names
the exact model, protocol, attempt count, permitted spending, and stop conditions.
Implementation approval is not implicit authorization for repeated live requests.

## Completion record

Create `docs/implementation/M0-completion.md` (substitute the milestone ID).

```text
Milestone:
Starting commit and pre-existing working-tree changes:
Implemented task IDs:
Changed files and public behavior:
Artifact/example demonstrating the behavior:

Validation:
  command | result | real/mocked | skipped/unavailable | evidence path

Compatibility/migration evidence:
No-regression evidence:
Remaining limitations:
Contract conflicts or proposed deviations:
Live inference requests made: 0 [or separately authorized count and usage]
Ready for review: yes/no
```

Do not fill success fields speculatively. If a required dependency is unavailable,
report the exact failure and which claims remain unverified. A test skip is not a
pass. Existing unrelated failures should be identified and reproduced where useful,
not repaired through unrelated refactoring.

## Reviewer checklist

- [ ] The assigned behavior works through the real entry point, not only helpers.
- [ ] Tests exercise specified failures and invariants, not just implementation shape.
- [ ] Required real checker/render coverage ran with the documented environment.
- [ ] No unrelated files, new live spending, or concealed policy changes are present.
- [ ] Prompt, tool schemas, implementation, and docs agree where agent behavior changed.
- [ ] Versioning, historical evidence, and user constraints remain intact.
- [ ] The next milestone's prerequisites are actually satisfied.

The reviewer either accepts the milestone or gives a bounded correction list with
task IDs. Benchmark improvement is judged later by the frozen protocol, not by
the worker's confidence or the number of completed checkboxes.
