# M1 reviewer acceptance

Date: 2026-10-15. Decision: **M1 accepted. M1.1–M1.6 and the review gate closed.**
M2 and later milestones remain unstarted.

This decision resolves M1-R1, M1-R2, and M1-R3 from
[the first review](M1-review.md), including its environment documentation
correction. No remaining blocker was found in this bounded re-review.

## Accepted source and evidence

The accepted provenance artifact is
[m1-offline-provenance-v2.json](evidence/m1-offline-provenance-v2.json).

- Manifest content identity:
  `8d99cc05b7487bc5a7042cd7fe225a2738d8658cd9629916f33af8b72f6a046d`.
- Exact artifact SHA-256:
  `6dbce8aec941c0e61267c9acb02651ac3c4d87d640bae013a56092717ce9a9fd`.
- The reviewer validated the manifest, recomputed its identity, confirmed complete
  capture, and compared its source-file records against the current checkout.
- Accepted M0 artifact SHA-256 remains
  `4f4c2722e4d492730aff84d8375000bc3edf8368c65ed7e1f70cb357b213f873`.
- Original M1 v1 artifact SHA-256 remains
  `db0f4f4ff26da7a2568f26f0cdf0820d79ba1ffa8ae19cf1b4473f00beea256b`.

This acceptance identifies the submitted working-tree snapshot; it does not
invent an implementation commit. The original generator commit remains
`22cb7c8431117b51b6e3b79ab312719075b06df4`. No commit or push was made. All
three artifacts remain unchanged. They are provenance records, not benchmark
results or evidence of improved model-generated designs.

## Independent reviewer verification

- Required dependency imports succeeded.
- Configured full discovery passed **149 tests in 85.445 seconds**:
  `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`.
- Configured preflight exited zero, loaded the repository 3024 mesh, passed all
  five real construction checks, and rendered successfully:
  `BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python scripts/workbench.py preflight`.
- Independently reconstructed multiline-comment, Unicode-line-separator, and MPD
  comment cases were rejected by the real export CLI without a published output.
- A valid export retained the exact physical multiset. Independent corruption of
  its map to line 999 was rejected by the real inspection CLI.
- Exact zero, tiny nonzero, and inverse moves preserved the expected coordinates
  and stable part ID under Decimal precision 5. Zero/inverse moves retained the
  original structure hash.
- Reviewed implementation verifies serialized build/module placements and stable
  ID/owner correspondence, including migrated revision exports. Mapping tests
  cover malformed shapes, coverage, ownership, revision, and digest failures.
- `git diff --check` passed. The reviewer changed documentation only and made no
  model calls, dependency downloads, library mutations, or production-code edits.

## Accepted capabilities and limits

M1 supplies offline stable design state, supported flat LDraw import/export,
inspection by stable IDs, explicit migration, and exact in-memory translations.
Its v2 sessions remain inert: live step/run/mutation is disabled pending M2's
atomic persistence. Acceptance does not enable later milestones or live spending.

Use the explicit `BRICKNET_DATA` setting above for this checkout. The earlier
unconfigured preflight failure came from path resolution/import order, not a
missing optional mesh. Unconfigured behavior remains a disclosed setup limitation;
no preflight redesign was included in this review. Clean-environment installation
also remains unverified. Tiny-fixture checks establish functioning integration,
not general physical validity or design quality.

The next roadmap milestone is M2 — atomic edits, candidate revisions, and
recovery under Contracts C3. Preserve the accepted artifacts and original
generator baseline as that work proceeds. Official benchmark setup and execution
remain separate from this acceptance.
