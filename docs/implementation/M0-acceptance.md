# M0 reviewer acceptance

Date: 2026-10-15. Decision: **M0 accepted. M0.1–M0.7 and the review gate closed.**
M1 remains unstarted; its bounded offline assignment is now prepared.

This decision supersedes the open findings in `M0-review.md`,
`M0-review-round-2.md`, and `M0-review-round-3.md`. Those reports remain historical
records of the counterexamples and corrections, not current blockers.

## Accepted artifact and source state

The submitted v7 manifest is retained byte-for-byte at
[evidence/m0-accepted-v7.json](evidence/m0-accepted-v7.json), copied from
`/tmp/bricksmith-m0-review-final-v7.json`. Content identity:

`a23a44205e6cd81857e8215bfb60ab5d4812b9546dc39876675b2edb71858b20`.

The reviewer recomputed that identity, validated complete capture, compared its
source records with the current checkout, and compared its package-data digest
with the actual imported BrickNet data tree. All matched.

The manifest is **provenance-only**, not a generated design or benchmark score.
The generator starting commit remains
`22cb7c8431117b51b6e3b79ab312719075b06df4`. M0 instrumentation is accepted as a
dirty working-tree snapshot identified by the manifest; no new commit or push
was made by the reviewer. The stored manifest includes local diagnostic paths.

## Reviewer verification

- Prescribed imports (`bricknet`, `meshlib`, `matplotlib`) succeeded.
- `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` passed:
  **128 tests in 73.893 seconds**, including the real integration coverage.
- Independent mutations of the actual v7 artifact confirmed rejection by both
  validation and publication of empty BrickNet source evidence, directory-only
  package data with recomputed aggregate hashes, list/object tree-record types,
  and list/object capture statuses. Each raises `ValueError`; no output appears.
- Explicit unavailable source and package-data records remain valid incomplete
  evidence. They cannot obtain complete status.
- The collector now reports unavailable source when no readable Python source
  files exist; its regression is included in the passing suite.
- The previously accepted R1a/R1b identity and relocation regressions and the
  earlier no-clobber, preflight, fixture, and test-tier corrections remain covered.
- `git diff --check` passed. No model calls, downloads, library mutations, or
  production-code changes were made during this review.

## Limits and next assignment

Clean-environment installation remains unverified, as already accepted and
disclosed in M0. It must be verified before a portable benchmark reproduction
claim. Tiny-fixture integration establishes functioning check/render plumbing,
not broad physical validity or improved design quality.

The next implementation assignment is
[M1 — stable design state and explicit migration](M1-worker-assignment.md).
It adds offline representation and inspection while preserving v1 generation;
v2 live execution remains disabled until M2. Official benchmark selection,
budget authorization, baseline execution, and scoring remain separate work under
the draft protocol. Preserve the original generator commit for that comparison.
