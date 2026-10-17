# M2 reviewer acceptance

Date: 2026-10-16. Decision: **M2 accepted (M2.1–M2.7).**
The accepted M2-A transaction core and reviewed M2-B offline adapters together
satisfy this milestone. B1–B5 and follow-up B1a/B2a are resolved. M3–M7 remain
unstarted; this record does not assign the next milestone.

## Accepted snapshot

Artifact: [m2-b-offline-provenance-v3.json](evidence/m2-b-offline-provenance-v3.json).

- Manifest identity:
  `de64046de2906550c2786357bd1e122cf7194a8c918535ac9ad173a27e97dc38`.
- Artifact SHA-256:
  `affe02f5742b849bd397caf07610fe08b402fd73d71e3fe60bd35d5fad68086e`.
- Transaction catalog SHA-256:
  `aa0eedcee28a69c81fde8bb74f32d52cd06aa9b166fe9927b623bfc098a41d56`.
- Reviewer validated the complete provenance-only manifest, recomputed its
  identity, and confirmed its source manifest matches the checkout and its
  catalog bytes match runtime serialization.
- Accepted M0/M1/M2-A artifacts and submitted M2-B v1/v2 remain byte-identical.
  This accepts recorded working-tree contents, not a new implementation commit.

## Independent verification

- Required dependency imports passed using the repository virtual environment.
- Full discovery passed **218 tests in 356.649 seconds**:
  `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`.
  Reviewer log: `/tmp/bricksmith-m2b-review-tests-v3.log` (temporary local output).
- Configured preflight passed mesh collision, included base, below-ground,
  actual connectivity, approximate gravity equilibrium, and actual rendering.
  Reviewer output: `/tmp/bricksmith-m2b-review-preflight-v3.json`.
- Reviewed actual dispatcher/CLI integration, immutable export and line-map
  binding, exact Decimal movement/arrays, module limits, and core bulk replacement.
- Reviewed durable replay, authoritative receipt/report outcomes, and isolation
  of supplied metadata under `tool_details`. Synthetic policy tests cover passed,
  provisional, repair-incomplete, blocked, unavailable, and terminal outcomes.
- Reviewed real subprocess termination at candidate sealing/pointer publication
  and render reservation/image/publication boundaries. Render identity conflicts
  precede staging reconciliation; matching retries recover without changing the
  original invocation. Mutation retries do not implicitly publish staged work.
- Additional reviewer probes rejected four malformed reservation representations
  and a symlinked reservation without renderer calls or evidence overwrite.
- `git diff --check` passed. Reviewer edits are review/planning documentation and
  clarification of the completion report's historical versus final test counts.

## What is now established

Explicit transaction workspaces have one publication path for save, edit, move,
clone, discard, and the assigned geometry generators. Calls bind an operation ID,
base revision, and export identity; compatible retries recover the same outcome.
Multi-assembly changes publish as a whole or remain uncommitted, with evidence
retained for inspection. Locks, stable identities, bounded requests, exact
coordinates, and construction-policy labels survive adapter integration.

Offline reads/checks/renders identify their sealed source revision. Render output
and metadata publish together; a reserved render ID cannot silently change its
instructions after interruption. Tool-specific details cannot overwrite the
authoritative commit/status/identity fields.

## Limits and next boundary

Legacy v1 behavior remains a separate historical baseline. V2 model step/run
remain disabled before any provider call; runner integration is M7. No live
inference, official benchmark, dependency download, library change, commit, or
push was performed in this review cycle.

This acceptance covers the tested local environment and process-crash boundaries,
not arbitrary storage/hardware failure. Clean installation remains unverified.
Synthetic policy and fake-render tests establish transaction/persistence behavior;
real fixture tests establish checker/render integration. Neither proves general
LEGO buildability, visual acceptance, or improved design quality.

M3 is the next planned milestone: persistent requirements, decisions, unresolved
issues, and bounded context. Its worker assignment and implementation are separate
from this acceptance. The official benchmark remains a later frozen evaluation.
