# M2-B completion report — offline transaction tool adapters

Reviewer disposition: [M2 accepted at v3](M2-acceptance.md), including an
independent 218-test run and real preflight. The worker handback record below
retains its original pending-review language for historical context.

Date: 2026-10-16. Scope: M2.6 / M2-B offline adapter work only. The final M2
review gate remains open for REVIEWER.

## Implementation

- Added `bricksmith/workbench/transaction_tools.py`. The existing dispatcher in
  `agent_session._tool` now routes explicitly initialized transaction workspaces
  through the M2-A service with a strict `bricksmith-tool-invocation-v1`
  envelope. Calls bind the unchanged tool/argument object, operation UUID, base
  revision UUID, and expected assembled-export SHA-256. All mutations go through
  operation-v2 proposal and commit; failed, blocked, stale, or interrupted
  candidates retain their evidence. Existing v1 sessions remain on their
  historical code path.
- Added operation-v2 `replace_assembly_contents`, preserving unrelated design
  records and enforcing the existing operation/request/part limits. Module saves
  replace only direct parts with fresh deterministic IDs; submitted type-0
  comments and source hashes are retained. Clone IDs are fresh and record
  `derived_from`. Leaf discard removes its placements through the checked
  deletion path.
- Routed all assigned mutation names, reads, checks, and offline rendering
  through the adapter. Line selections resolve against verified immutable
  revision maps. Render metadata binds the artifact to its source revision and
  export hash and records creation only. Unsupported transaction tools fail
  explicitly. V2 snapshots and transaction workspaces reject model step/run
  before provider calls; runner integration remains pending M7.
- Added `transaction-tool` and `transaction-tool-catalog` CLI commands, the
  versioned catalog JSON, and updated the canonical prompt, README, workbench
  guide, contracts, and runtime tool descriptions. Revision exports now retain
  an empty `modules/` directory when a design has no assemblies, so deleting the
  last leaf can still seal a revision.

## Verification

All commands ran from the repository root using `./.venv/bin/python` and
`BRICKNET_DATA="$PWD/data/bricknet-data"` where required.

- Focused adapter/core/recovery tests for B1–B5 passed: **47 tests**. Final full
  discovery after the B1a/B2a follow-up passed: **218 tests in 350.985 seconds**.
- The original adapter unit suite contained **11 tests**; the final full discovery
  includes **19 tests** from `tests/unit/test_transaction_tools.py`. It exercises every supported
  mutation name through the actual dispatcher, an 80-part single-operation save,
  a generated support column, stable-ID line operations, lock and stale-line
  rejection, ambiguous names, conflicting retries, a competing commit, and a
  simulated stop after candidate sealing followed by a retry that does not
  publish implicitly. The mutation matrix uses clearly synthetic all-green
  five-check reports to isolate transaction behavior; those synthetic results
  are not construction claims.
- Two focused CLI adapter tests passed. One uses real import, initialization,
  read, and save-module dispatch with the configured real checker and commit
  revalidation. The larger CLI flow performs real-checked save, move, recolor,
  and clone calls; confirms a collision regression stays an uncommitted candidate
  across retry; then calls check and render on the committed revision.
- Configured preflight passed with all five real construction checks and the real
  renderer available. A sealed-revision adapter test also ran actual check and
  render. `py_compile` and `git diff --check` passed.
- B1 replay resolves stored invocation before parsing/generation and reconstructs
  results from the hash-verified report and authoritative receipt. Tests mock
  generation on a committed retry after a later commit, reject changed arguments
  before generation, and compare provisional, repair-incomplete, blocked/discarded,
  and unavailable outcomes.
- B2 render artifacts publish atomically as operation-ID directories under the
  workspace writer lock. Symlink escape, incomplete staging, changed invocation,
  retry without rerendering, subprocess death before/after publication, and a
  competing writer are covered. Interruption tests use fake renderer bytes and
  establish persistence behavior, not visual quality.
- B3 exact Decimal array arithmetic is tested through the CLI JSON decoder under
  low Decimal precision, including fractional steps, a tiny source coordinate,
  zero offsets, evidence retention, and deterministic replay.
- B4 clone enforces the 250-placement module cap at 250 and 251. Core operation-v2
  accepts direct bulk replacement without fabricated adapter metadata and rejects
  malformed supplied metadata; the v1 reader remains covered by full discovery.
- B5 subprocess termination through adapter dispatch is covered after candidate
  seal for an 80-part save and after pointer publication for a multi-module move,
  followed by fresh recovery and replay. Synthetic policy cases are separate from
  real-checker CLI integration cases.

## Provenance

The original v1 and v2 captures remain unchanged. The final follow-up snapshot is
[`m2-b-offline-provenance-v3.json`](evidence/m2-b-offline-provenance-v3.json).
Provider/model are null. Manifest identity:
`de64046de2906550c2786357bd1e122cf7194a8c918535ac9ad173a27e97dc38`.
Artifact SHA-256:
`affe02f5742b849bd397caf07610fe08b402fd73d71e3fe60bd35d5fad68086e`.
The preserved v2 artifact SHA-256 is
`8a0d16f0a4e697b5d52f2a470852f141b5e97091692522bf65256c3fce5442b7`.
The catalog SHA-256 recorded in its settings is
`aa0eedcee28a69c81fde8bb74f32d52cd06aa9b166fe9927b623bfc098a41d56`.

Final configured preflight passed dependency imports, catalog/connectors/mesh,
all five real construction checks, and actual rendering. `git diff --check`
and `py_compile` passed. Accepted M0/M1/M2-A artifact hashes and M2-B v1/v2
remain unchanged. The M2-B v3 manifest validates as complete, recomputes to the
identity above, and records catalog SHA-256
`aa0eedcee28a69c81fde8bb74f32d52cd06aa9b166fe9927b623bfc098a41d56`.

M0, M1, and accepted M2-A evidence were left intact. The unrelated
`bricksmith-clean-view 2/` checkout content was preserved. No provider calls,
benchmarks, downloads, library changes, commits, pushes, or M3–M7 work were
performed. M2.6/final M2 acceptance remains open for REVIEWER.

## Bounded follow-up B1a/B2a

Adapter-supplied operation metadata is now returned only as `tool_details`.
Generator and clone details remain available there, while outcome assembly is
authoritative from the operation report and receipt. Tests supply metadata that
collides with committed/status/eligibility/identity fields through direct core
proposals, then exercise committed, provisional, blocked, discarded, and
immediate-result assembly. Replay outcome fields continue to match state,
receipt, and policy evidence.

Render dispatch now durably reserves the complete invocation, source revision,
and source export hash under the writer lock before invoking the renderer or
creating staging output. Subprocess exits after reservation, after image flush
before metadata, and immediately before publication verify that a changed-view
retry fails without renderer calls or evidence loss, while a matching retry
recovers and publishes. Existing after-publication/no-rerender coverage remains.
The render process-death checks use fake image bytes and establish persistence
behavior, not visual quality.

The final B1a/B2a verification is recorded in the numbered v3 manifest linked above;
the earlier v1/v2 provenance files remain byte-identical. M2.6/final M2 review
remain open pending reviewer acceptance.
