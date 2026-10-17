# M0 completion record

Milestone: M0 — Reproducible test foundation and provenance

Current reviewer status: **accepted on 2026-10-15**; see
[M0 acceptance](M0-acceptance.md). The submission and follow-up records below
preserve their original evidence and review-open status as history. The final
accepted manifest is [v7](evidence/m0-accepted-v7.json). M1 remains unstarted.

Starting commit and pre-existing working-tree changes: `22cb7c8431117b51b6e3b79ab312719075b06df4` (`chore: ignore clean export files`, 2026-10-14). The initial user changes were the modified `README.md`, four untracked harness planning documents, and unrelated `bricksmith-clean-view 2/`. The latter was not read, used, changed, or staged. M0 is still the only implemented milestone.

Implemented task IDs: M0.1–M0.7, including review corrections R1–R7. The plan's M0 review checkbox remains open for the reviewer.

Changed files and public behavior:
- Added `bricksmith/workbench/provenance.py` with source/data manifests, strict validation, content identity, no-clobber atomic publication, dependency/data preflight, and real checker/render probes.
- Added canonical serialized runtime tools at `bricksmith/workbench/tool_schema.json`; integration coverage verifies byte-decoded schema equality with `agent_session.TOOLS`.
- Added `preflight` and `baseline-export` CLI commands. The CLI lazily imports geometry/runtime modules so preflight can report missing dependencies. Export is offline, validates before writing, refuses an existing output, and marks an incomplete fingerprint explicitly.
- Replaced all ignored `runs/` dependencies in acceptance tests with original tracked fixture files. The real fixture suite verifies the exact five-check outcomes for supported, colliding, floating, and below-ground cases.
- Split new pure tests into `tests/unit/`; retained prior library-dependent tests in their original locations and added real integration tests under `tests/integration/`.
- Updated README setup, test tier, provenance, and local data snapshot instructions. `requirements-lock.txt` records observed package versions for the exercised environment.

Artifact/example demonstrating the behavior: `/tmp/bricksmith-m0-review-final-v4.json` is the offline provenance-only export. Its manifest identity is `c93ddc449105ce7f8aaaa9026be7179a76fe06877f9a8309a60efdb0ee0ed3b3`; capture status is `complete`, classification is `provenance_only_no_design_result`, and it contains no claimed baseline result. It identifies generation baseline commit `22cb7c8431117b51b6e3b79ab312719075b06df4`, while separately marking instrumentation source dirty at that same checked-out commit. Canonical tool schema SHA-256: `3505ef99d68b156a52fbbd40214682d933ccb4cf7be7a3fc8ee85f95e82393c1`. BrickNet source identity: commit `b09a689c4929bd27f59c9bb9446237967aa332c9`, clean VCS state, source-content SHA-256 `ee65eebeef634a102aa4ff4dbe613e7dcccb76aa9a7712a6af2d9987da703e81`. The manifest records the effective library content hashes and diagnostic paths.

Validation:

| command | result | evidence class | evidence |
| --- | --- | --- | --- |
| `./.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py'` | 14 passed | pure contract/unit tests; temporary Git/data fixtures | terminal output |
| `./.venv/bin/python -m unittest discover -s tests/integration -p 'test_*.py'` | 9 passed | real fixture checks, real catalog/mesh/check/render, injected unavailable-path probes, and `python -S` CLI check | terminal output |
| `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | 121 passed | complete suite, including the existing library-dependent tests | terminal output |
| `./.venv/bin/python scripts/workbench.py preflight --no-real-check` | passed; imports, catalog, connectors, and 3024 mesh loaded; real geometry explicitly `not_run` | real environment capability check | terminal JSON output |
| `./.venv/bin/python scripts/workbench.py preflight` | passed; all five fixture checks true and actual PNG render created | real checker and renderer | terminal JSON output |
| `./.venv/bin/python scripts/workbench.py baseline-export /tmp/bricksmith-m0-review-final-v4.json --brief 'M0 review correction provenance evidence' --track historical-operator-assisted` | passed; exact manifest linked above | offline, no inference | `/tmp/bricksmith-m0-review-final-v4.json`; CLI output `/tmp/bricksmith-m0-review-final-v4-cli.json` |
| `git diff --check` | passed | source hygiene | terminal output |

The pure tests cover same-status source-content edits, staged/working source identity representation, location-invariant manifest identity, canonical schema/config/content changes, binary framing, linked file/directory traversal and mutation, dangling/cyclic links, effective `BRICKNET_DATA` overrides, malformed/nonfinite records, failed/no-clobber publication, incomplete-capture labeling, CLI refusal to overwrite, and missing dependency reporting. Integration tests inject catalog, mesh, renderer, and incomplete-check failures and require `unavailable`, not a pass. A `python -S` CLI run confirms missing site packages are reported as unavailable without import-time failure. Real fixture checks at ground Y=8 record:

| fixture | collision-free | base | above ground | connected | equilibrium |
| --- | --- | --- | --- | --- | --- |
| `pass.ldr` | true | true | true | true | true |
| `collision.ldr` | false | true | true | false | true |
| `floating.ldr` | true | true | true | false | false |
| `below_ground.ldr` | true | false | false | true | false |

Compatibility/migration evidence: Existing `prompt`, `search`, `inspect`, and `check` commands remain available. Provenance export is additive and does not edit existing runs. Test files that relied on `tests/`-relative paths remain in place; only tests explicitly added for the integration tier live beneath `tests/integration/`.

No-regression evidence: The full 121-test suite passed. No model call, checker threshold, generation behavior, model selection, or tool capability was changed. Real and mocked evidence are separated and labeled.

Remaining limitations: The tested runtime is CPython 3.14.7 on macOS 26.6.1 arm64. A clean-environment install was not attempted because no isolated environment or offline wheelhouse was supplied; reproducing it without downloads requires a local wheelhouse for `requirements-lock.txt` plus the pinned BrickNet checkout. Other platforms/versions are unverified. `data/ldraw` and `BRICKNET_DATA` resolve to local snapshots under the separate BrickBlender checkout here. The README documents how to obtain/configure snapshots and preflight them; the repository does not bundle third-party libraries or mesh data. The 1×1 plate preflight is plumbing coverage, not broad physical validation. The manifest fingerprints content but does not establish third-party licensing. The `tool_schema.json` parity test catches drift from runtime schemas.

Contract conflicts or proposed deviations: None. The generation baseline is the starting commit. Instrumentation is separately identified by a source manifest, dirty patch digest, and dirty state; until a commit is created, its commit field truthfully names the checked-out base commit rather than inventing a commit ID.

Live inference requests made: 0.

Ready for review: yes.

## M0 review round two follow-up (R1a, R1b, R4a)

The reviewer gate remains **open**; M1 remains unstarted. This bounded follow-up
addresses only the three findings in `M0-review-round-2.md`.

- **R1a:** source fingerprinting now hashes every readable supported file under
  the bounded `bricksmith/`, `scripts/`, and `configs/` roots regardless of Git
  tracking state. It excludes symlinked files and generated/cache directories;
  unreadable discovered files are recorded as omitted and make the capture
  incomplete. A temporary Git regression changes an arbitrary untracked runtime
  module twice while its status remains `??` and checks the resulting full
  manifest identity.
- **R1b:** BrickNet identity now includes the canonical content digest and records
  for the imported runtime's actual `bricknet.data._DATA` package-data tree. It is
  separate from the external `BRICKNET_DATA` mesh snapshot and participates in
  manifest identity and completeness. Missing or unreadable package data is
  incomplete. A temporary package regression changes JSON bytes while preserving
  the Python source, commit, and dirty status; it also verifies relocation
  invariance.
- **R4a:** validation now checks nullable prompt hash semantics, all identity
  digests, nested source and package-data file records, normalized paths, record
  ordering, and aggregate-to-record digest consistency. Complete capture claims
  require complete source/package-data evidence. Publication validates the same
  rules before writing. Tests cover the review's three reproduced mutations,
  malformed nested records, null/incomplete capture, and export rejection.

New offline manifest: `/tmp/bricksmith-m0-review-final-v6.json` (fresh path; prior
evidence was not replaced). Its captured source manifest has 112 files and its
BrickNet package-data snapshot is present. Identity:
`b3fcbe6b9f122ca2a0681c0da76e9f688f00cd29221166dda9965b5805504a84`; capture
status is `complete`. This is provenance-only and contains no design result.

Final validation for this follow-up:

| command | result | evidence |
| --- | --- | --- |
| `./.venv/bin/python -m unittest tests.unit.test_provenance -q` | 18 passed | temporary Git and package-data byte fixtures, structural validation and export regressions |
| `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | 125 passed in 64.816 seconds | complete repository suite |
| `git diff --check` | passed | whitespace and patch hygiene |

No model calls, benchmark, M1 work, dependency downloads, or library mutation
were performed. Clean-environment installation remains unverified as documented
above. The reviewer gate remains open for review of these changes.

## M0 review round three follow-up (R4a presence and type guards)

The accepted R1a/R1b work is preserved; this follow-up addresses only the
remaining R4a checks. The review gate remains **open**, and M1 remains unstarted.

- Available BrickNet source now requires a nonempty validated Python source list.
  The collector reports BrickNet source identity as unavailable if it cannot
  read any Python source files.
- Available package-data trees now require at least one file or symlink-file
  record; a root-directory-only tree cannot substantiate a complete capture.
- Tree record `type` and `capture_status` are checked as strings before enum
  membership, returning useful `ValueError`s for list/object JSON values.
- Regressions recompute the claimed aggregate digests for empty source records
  and directory-only package data, then require validation and publication to
  fail without creating output. They also cover list/object enum values, a valid
  complete export, and explicitly unavailable/incomplete evidence.

Fresh offline manifest: `/tmp/bricksmith-m0-review-final-v7.json`; earlier
artifacts are retained. It validates as complete, with identity
`a23a44205e6cd81857e8215bfb60ab5d4812b9546dc39876675b2edb71858b20` and 13
BrickNet Python source records.

Validation:

| command | result | evidence |
| --- | --- | --- |
| `./.venv/bin/python -m unittest tests.unit.test_provenance -v` | 21 passed | targeted presence, type, collection, validation and publication regressions |
| `./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | 128 passed in 52.225 seconds | complete repository suite |
| `git diff --check` | passed | source hygiene |

No M1 work, model calls, benchmark execution, library mutation, or dependency
downloads were performed. Clean-environment installation remains unverified as
documented above.
