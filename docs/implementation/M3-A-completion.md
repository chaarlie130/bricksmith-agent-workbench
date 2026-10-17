# M3-A completion report — persistent intent ledger (review corrections v3)

Date: 2026-10-16, review correction run. Scope: M3-A offline ledger and authority boundary only.
The full M3 acceptance checklist and reviewer gate remain open. No M3-B work
was started.

## Implementation

- Added `bricksmith-design-v2` while retaining design-v1 import, migration, and
  transaction readers. Explicit `transaction-upgrade-v2` creates the v2 ledger
  through ordinary proposal, validation, commit, and recovery. It retains old
  design records and immutable revisions and does not infer instruction
  authority from historical fields.
- Added `bricksmith-operation-v3` ledger operations, strict record validation,
  append-only requirement/decision supersession, issue observations, repair
  attempt references, and next actions. Ledger IDs enter the shared entity
  lifetime set and design hash. Ledger-only edits retain structure and
  appearance hashes. Existing M2 transaction adapters select operation-v3 on
  upgraded revisions.
- Added `operator-intake` as a separate application entry point. It binds exact
  instruction text and trusted source to the normalized request hash, candidate,
  report, and authoritative receipt. Proposal, commit, and recovery verify this
  binding. Model-callable schemas and the tool catalog do not expose intake.
  Trusted user corrections append records and preserve the original record.
- Added bounded `ledger-read` for a sealed current or historical revision. It
  returns per-collection counts and continuation offsets; verifies instruction
  receipts, repair-attempt evidence, local evidence hashes, and safe paths; and
  does not run construction physics. Construction status remains separate from
  unresolved requirements and pending actions.
- Updated the canonical system prompt, prompt-backed documentation, and workbench
  guide. Added an original ten-event Victorian-inspired fixture. Its note records
  that the historical interruption and render handoff were operator actions.

The trusted intake capability is an application boundary, not a defense against
a process with arbitrary access to workspace files. Metadata changes retain the
existing real-check commit policy; they cannot commit when required checks are
unavailable. No checker policy or model tool catalog was changed.

Reviewer corrections: repair attempts now use `bricksmith-repair-attempt-v2`.
A single resolver validates local intent, candidate/report identity and hashes,
terminal failure evidence, and the authoritative `state.json` receipt. It keeps
`outcome_at_recording` immutable while exposing `current_reconciled_outcome`.
`observed_revision_id` records the exact committed attempted result when committed
at recording, or the attempted base when staged/failed; `recorded_revision_id`
identifies the ledger operation's own base. A blocked unpublished candidate is
validated from its operation evidence. Caller-declared committed receipts without
authoritative publication are rejected.

Issue/requirement/decision claims are decorated with origin operation/revision
and evidence qualification before active projections are made. Historical claims
without verifiable provenance remain unverified. Revision history and trusted
instruction IDs are paged. Design-v2 rejects legacy issue mutations, validates
strict JSON types and 16 KiB text limits on every ingress, and tests aggregate
and record-count boundaries. The fixture now executes ten ordered edits with a
fresh revision load between edits, including a collision-blocked candidate,
a later real CLI checked geometry edit, and a still-pending visual requirement.

Contract limitation: if a repair attempt is recorded while its attempted edit is
only staged, ordinary commit of that attempt would require changing the ledger
revision, so the attempted edit's original base becomes stale. We preserve stale
base rejection and verify candidate-to-discard reconciliation; later commit of
that staged attempt is not a valid transition under the current single-publication
contract. A future contract revision can define an explicit staged-attempt commit
flow without weakening stale-base checks.

## Verification

Commands ran from the repository root with `./.venv/bin/python` and
`BRICKNET_DATA="$PWD/data/bricknet-data"` where applicable.

- Dependency imports passed: `import bricknet, meshlib, matplotlib`.
- `py_compile` passed for workbench modules, CLI, and touched tests.
- `git diff --check` passed.
- Final configured full discovery passed after all source/test edits: `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests` — **235 tests in 617.829 seconds**.
- New unit coverage includes explicit upgrade preserving legacy records, trusted
  correction with byte-preserved original records, forged-authority refusal with
  unchanged state, protected user requirement supersession, exact malformed-type
  and UTF-8/aggregate/count boundaries, self/cycle/branch supersession, corrupt
  evidence, staged disposition reconciliation, paged/history reads without physics,
  competing writers/stale retries, and subprocess death before and after publication
  followed by recovery and idempotent replay.
- A real-check CLI integration upgrades a workspace, records instructions,
  requirements, decisions, issues, and actions, retains a collision-blocked
  candidate, commits a passing geometry transform, records both outcomes, and
  reads the still-pending visual requirement and render action. Its checker runs
  are real; unit policy validators are synthetic and are not construction claims.
- Configured preflight passed imports, LDraw and BrickNet data fingerprints,
  catalog (14,583 parts), connectors, mesh loading, all five real construction
  checks, and the real renderer.

The original ten-event fixture is replayed through real ledger transactions with
a fresh revision load between edits; its real CLI integration separately exercises
upgrade, trusted intake, issue/decision/action records, a blocked collision
candidate, a real passing transform, attempt records, and paging. The ten-event
replay uses a synthetic policy validator for quick deterministic persistence
coverage; the CLI geometry integration and configured preflight use real checks.
Unsafe evidence symlink and digest mismatch cases are covered. No context-window
truncation behavior is claimed; that remains M3-B.

No provider/model calls, official benchmark, downloads, or external writes were
made. No commit, push, or cleanup was performed.

## Provenance and preserved artifacts

The v1 snapshot is retained. The final correction snapshot is
[`m3-a-offline-provenance-v2.json`](evidence/m3-a-offline-provenance-v2.json).
It records the offline catalog hash, `provider: null`, and `model: null`. Prior
accepted evidence artifacts were left unchanged: M0 v7, M1 v2, M2-A v4, and
M2-B v1–v3. The pre-existing `bricksmith-clean-view 2/` directory was retained.
The v1 manifest identity remains `9266395996ca27452f404e71392c57ecf92b2538e34ac18a9adac2eeff56fd77`.
The v2 manifest identity is `9be7b6b049c816d2dc80b454aa8604be5b35354ab17073dae758682770fc9631`;
its artifact SHA-256 and recomputed identity were validated after export. Both record
provider/model as null, a complete offline source fingerprint, and catalog SHA-256
`aa0eedcee28a69c81fde8bb74f32d52cd06aa9b166fe9927b623bfc098a41d56`. Accepted
M0/M1/M2 evidence files were byte-preserved.

## Reviewer handback

Review M3-A corrections R1–R4 only. The full M3 checklist and reviewer acceptance
box remain unchecked. The stale-base semantics for a staged repair attempt are
disclosed above for review; no M3-B work was started.

## R3a follow-up (v3)

The v2 review found that issue observations reused current issue evidence and
counted repair/geometry operations as observations. The derived `ledger-read`
projection now verifies each operation's committed intent, receipt, report, and
candidate, then includes an observation only when the operation explicitly
created/updated that issue or created a matching checker policy issue. Each
snapshot carries its own status, kind, affected IDs, evidence-reference IDs and
hashes, action, operation ID, and revision ID. Issue creation provenance remains
separate from `latest_status_assertion`; current evidence is not retroactively
attached to creation. Repair attempts and geometry-only changes stay in repair
history and do not create issue status observations. Historical entries without
verifiable status-update operations remain unobserved/unverified. Sealed revisions
are unchanged.

Regression coverage now exercises open/no-evidence → resolved/with-evidence →
reopened/no-evidence, checks every immutable snapshot and historical read, source
hashes, creation-versus-latest attribution, and confirms a geometry-only repair
adds no status observation. Ledger reads remain free of physics and preserve
paging and active/full consistency.

Final R3a verification, after all edits:

- `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest tests.unit.test_intent_ledger` — **17 tests passed in 147.431 seconds**.
- `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests` — **236 tests passed in 683.662 seconds**.
- Required dependency imports, `py_compile` for the changed module/test/CLI, `git diff --check`, and configured real preflight passed. Preflight loaded 14,583 catalog/connectors, the 3024 mesh, all five real checks, and the renderer.
- The v1 and v2 M3-A provenance files remain unchanged; accepted M0/M1/M2 evidence hashes remain unchanged. A fresh v3 offline provenance artifact is recorded at `evidence/m3-a-offline-provenance-v3.json`; identity `135042432c062d28493c36fd901526c839dfff83e847ed7315066149efccf2b6`, artifact SHA-256 `fcc72089fd5356c483b58dad7e7c625c92c718340f42ae01878e0a56d7e0942f`, and source fingerprint `d1c724f6f04e07340139971d3f0c98fbcdd9552123c9a970ca99eb7be6426a1b`. It validates complete, recomputes exactly, matches current source fingerprint, and retains the runtime catalog digest.

M3-A and full M3 acceptance remain open. The reviewer-accepted staged-attempt
stale-base limitation is unchanged. No M3-B work was started.
