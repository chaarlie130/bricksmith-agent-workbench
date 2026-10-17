# M1 completion report — stable design state and explicit migration

Status: **accepted after reviewer re-review on 2026-10-15**; see
[M1 acceptance](M1-acceptance.md). M2 work has not started. No model/provider
request was made. Worker validation below is preserved; the acceptance record
contains the independent reviewer results.

## Scope and result

Implemented M1.1–M1.6 from the bounded assignment. The new
`bricksmith-design-v1` document stores stable part/assembly IDs, exact decimal
placements, source provenance, generic design intent, and versioned file,
appearance, structure, and design hashes. Strict flat LDraw import accepts
type-0 comments and type-1 catalog parts; unsupported geometry, MPD/submodels,
unknown part/color IDs, and malformed records fail with source locations.
Deterministic exports include a build, per-assembly module views, and an exact
file-hash/revision-bound line map. Persisted comments are constrained to one
supported type-0 physical line. Exports are reparsed and checked against the
design's physical multiset and each mapped stable ID/owner. Inspection validates
line-map shape and recomputes exact expected export hashes and placements before
reporting lines. Offline selectors use stable IDs and include assembly
descendants. Move arithmetic is exact for finite Decimal inputs and independent
of ambient Decimal precision. V1 sessions can be explicitly migrated to an inert,
read-only v2 snapshot; legacy evidence remains historical. Existing v1 session
behavior is retained, and v2 step/run/mutation is refused before provider use
or writes.

No agent-visible tool behavior changed, so the canonical system prompt and
`tool_schema.json` were left unchanged. M1 adds representation and offline
inspection; it does not improve generation or enable live design mutations.

## Files

- `bricksmith/workbench/design.py` — schema validation, exact-decimal hashing,
  strict import/export, selectors, copied-document move/recolor helpers, and
  explicit deterministic-ID migration.
- `bricksmith/workbench/agent_session.py` — v2 read-only refusal boundary.
- `scripts/workbench.py` — `design-import`, `design-export`, `design-inspect`,
  and `design-migrate` commands.
- `tests/fixtures/design/tiny.ldr`, `tests/unit/test_design.py`,
  `tests/integration/test_design_cli.py`, and `tests/test_agent_session.py` —
  identity, validation, migration, CLI, and refusal coverage.
- `README.md`, `docs/AGENT_WORKBENCH.md`, and
  `docs/HARNESS_IMPLEMENTATION_PLAN.md` — documented M1 commands, boundaries,
  and completion status. M1.1–M1.6 and M1 review are now checked by the reviewer.
- `docs/implementation/M1-review.md` — recorded bounded review findings and
  return checklist.
- `docs/implementation/evidence/m1-offline-provenance-v1.json` — original M1
  offline provenance capture, retained unchanged.
- `docs/implementation/evidence/m1-offline-provenance-v2.json` — new review
  correction provenance capture, classified `provenance_only_no_design_result`.

## Verification

All Python commands below ran from the repository root with `./.venv/bin/python`.

| Command | Result |
| --- | --- |
| `./.venv/bin/python -c 'import bricknet, meshlib, matplotlib'` | Passed |
| `./.venv/bin/python -m py_compile bricksmith/workbench/design.py bricksmith/workbench/agent_session.py scripts/workbench.py` | Passed |
| `./.venv/bin/python -m unittest tests.unit.test_design -v` | Initial M1 run: 14 passed. Review correction run: 17 passed, including multiline and MPD comment rejection, forged map cases, and exact arithmetic under precision 5. |
| `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest tests.integration.test_design_cli -v` | 3 tests passed; actual CLI rejects multiline/MPD comments and forged line maps, verifies exported physical placements and stable ID/owner mappings, and migrates a v1 session. |
| `./.venv/bin/python -m unittest tests.test_agent_session.AgentSessionTests.test_v2_session_refuses_step_run_and_mutation_before_provider_or_write -v` | Passed; provider stub was not called and source bytes were unchanged |
| `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | 149 tests passed in 81.584s. |
| `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python scripts/workbench.py preflight` | Passed: configured repository 3024 mesh loaded; all five real checks and render passed. |
| Unconfigured `./.venv/bin/python scripts/workbench.py preflight` | Historical initial probe returned unavailable because the mesh lookup resolved to `/Users/charliecittadini/Library/Application Support/bricknet/inset/3024.ply`; the repository file at `data/bricknet-data/inset/3024.ply` exists. No library was missing or downloaded. |
| `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python scripts/workbench.py baseline-export docs/implementation/evidence/m1-offline-provenance-v2.json --brief 'M1 review corrections: strict exports and exact edits' --track offline-provenance` | Capture complete and validates; stored/recomputed identity `8d99cc05b7487bc5a7042cd7fe225a2738d8658cd9629916f33af8b72f6a046d`; provider/model null; provenance-only, no design result. |
| `./.venv/bin/python -m unittest tests.unit.test_design -v` | 17 tests passed. |
| `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest tests.integration.test_design_cli -v` | 3 tests passed. |
| `git diff --check` | Passed. |

Runnable demo (creates new paths):

```bash
./.venv/bin/python scripts/workbench.py design-import tests/fixtures/design/tiny.ldr /tmp/tiny-design.json
./.venv/bin/python scripts/workbench.py design-inspect /tmp/tiny-design.json
./.venv/bin/python scripts/workbench.py design-export /tmp/tiny-design.json /tmp/tiny-export
./.venv/bin/python scripts/workbench.py design-inspect /tmp/tiny-design.json \
  --line-map /tmp/tiny-export/line_map.json --export-file /tmp/tiny-export/build.ldr
```

## Provenance and preserved state

The accepted M0 provenance artifact remains byte-for-byte unchanged:

```text
docs/implementation/evidence/m0-accepted-v7.json
SHA-256 4f4c2722e4d492730aff84d8375000bc3edf8368c65ed7e1f70cb357b213f873
```

The original M1 v1 provenance artifact was also retained unchanged (SHA-256
`db0f4f4ff26da7a2568f26f0cdf0820d79ba1ffa8ae19cf1b4473f00beea256b`). The
new v2 capture has SHA-256
`6dbce8aec941c0e61267c9acb02651ac3c4d87d640bae013a56092717ce9a9fd`.

The M1 capture is a separate provenance-only artifact; it does not relabel the
M0 snapshot or claim benchmark/model results. It records the working-source
fingerprint and local runtime/library identities. The unrelated
`bricksmith-clean-view 2/` and other pre-existing M0/user changes were
preserved. No commit or push was made.

## Review boundary and limitations

- M1 re-review is complete and accepted. M2 remains unstarted and requires its
  own implementation and review evidence.
- V2 sessions are intentionally inert pending M2 atomic persistence.
- The importer intentionally supports flat type-0/type-1 files only; it does
  not flatten submodels or preserve unsupported geometry by dropping it.
- This checkout needs `BRICKNET_DATA="$PWD/data/bricknet-data"` for preflight
  and configured CLI/provenance verification. The initial unconfigured probe
  looked under `/Users/charliecittadini/Library/Application Support/bricknet/`;
  the repository mesh exists and configured preflight passed.
- No official benchmark, inference, or design-quality claim was produced.
