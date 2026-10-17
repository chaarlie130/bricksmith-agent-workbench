# M0 re-review — three remaining corrections

Reviewed: 2026-10-15.
Decision: **not accepted yet; M1 remains unstarted.**

This review narrows the previous R1–R7 assignment. Relocation projection, framed
tree hashes, library symlink traversal, no-clobber publication, unavailable CLI
reporting, the fixture categories, test-tier documentation, and the narrowed setup
claims have been addressed. Do not redo those changes or expand into M1.

The disclosed lack of a clean-environment install is accepted as an M0 limitation,
consistent with R7's explicit allowance to report it unverified. Before an official
portable benchmark claim, that installation evidence still needs to be obtained.
It is not the reason this review remains open.

## Evidence inspected

- Submitted manifest: `/tmp/bricksmith-m0-review-final-v4.json`.
- Its recorded identity recomputes correctly:
  `c93ddc449105ce7f8aaaa9026be7179a76fe06877f9a8309a60efdb0ee0ed3b3`.
- Its `capture_status` is `complete`, although the coverage gaps below remain.
- Review probes used temporary Git repositories and fake imported package paths;
  no project/library bytes were edited and no model calls were made.
- Full-suite reviewer rerun is recorded below after completion.

## R1a — P1: Newly added runtime modules are still omitted

Source: `_source_fingerprint`, `bricksmith/workbench/provenance.py:128`.

The collector discovers source files but records them only if tracked or present
in a four-entry, hard-coded filename allowlist. An ordinary new runtime module
such as `bricksmith/workbench/helper.py` is omitted. Changing its contents changes
neither `content_sha256` nor `dirty_patch_sha256`, because Git diff excludes
untracked content and only the pathname appears in status.

Reproduced with a temporary committed Python module and an untracked helper:

```text
helper.py: value = 1 -> source fingerprint A
helper.py: value = 2 -> source fingerprint B
helper.py included in source records: False
A and B differ in content or dirty-patch identity: False
```

This is directly relevant to M1, which will introduce new source files. It would
otherwise allow two different uncommitted implementations to share an identity.

- [ ] Include supported source files under the already bounded repository source
  roots regardless of Git tracking state, or explicitly mark omitted eligible
  sources as an incomplete capture. Do not solve this by adding only `helper.py`
  or future milestone filenames to the current hard-coded list.
- [ ] Preserve exclusions for unrelated checkout copies, run artifacts, credentials,
  and generated caches. Do not expand to scanning the whole home directory.
- [ ] Add a regression that adds an arbitrary new runtime module, changes its
  bytes twice while its Git status remains `??`, and checks the **full manifest
  identity** or explicit incomplete status. Retain the existing tracked-dirty test.

## R1b — P1: The actual BrickNet catalog and connector data are not fingerprinted

Source: `_bricknet_identity`, `bricksmith/workbench/provenance.py:192`.

The imported BrickNet source fingerprint includes only `*.py`. Its actual catalog,
aliases, palette mappings, and connector tables are non-Python package data under
the installed `bricknet/_data/v1` directory. They are distinct from the external
mesh tree identified by `BRICKNET_DATA`.

In this environment `bricknet.data._DATA` resolves to the editable package's
`src/bricknet/_data/v1`, and the manifest's `source_files` contains no JSON files.
Two different edits to a tracked package-data JSON file retain the same VCS commit,
dirty boolean, and Python-source hash. Those are the fields projected into identity.

Reproduced against a temporary imported package:

```text
catalog.json: catalog A -> BrickNet identity A
catalog.json: catalog B -> BrickNet identity B
commit, dirty flag, or source-content digest differs: False
```

- [ ] Fingerprint the package data actually read by the imported BrickNet runtime,
  including catalog/aliases/connectors and applicable color data. Record a distinct
  package-data identity if useful; keep it separate from the external mesh snapshot.
- [ ] Include this fingerprint in manifest identity and capture completeness.
  A missing/unreadable required package-data snapshot must not be complete.
- [ ] Add a temporary-package regression changing real JSON bytes with unchanged
  Python files, VCS commit, and dirty status. Verify identity changes and relocation
  still does not. Do not merely mutate a precomputed hash in a test dictionary.

## R4a — P2: Nested malformed records can still be labeled complete

Sources: `validate_manifest` at line 272 and `manifest_capture_complete` at line 374
of the submitted provenance module.

Starting from the actual exported manifest, each independent mutation below was
accepted by validation and returned `True` from `manifest_capture_complete`:

| Mutation | Validation | Complete capture |
| --- | --- | --- |
| Set `prompt_sha256` to `not-a-hash` | accepted | true |
| Set `environment.bricknet_source.source_content_sha256` to `not-a-hash` | accepted | true |
| Remove `generation_source.source_manifest.files` | accepted | true |

The first two are digest-validation omissions. The third removes the inspectable
source records while leaving their claimed aggregate hash. Existing tests primarily
exercise top-level fields and a few nested values, so these cases are missed.

- [ ] Validate every digest used in identity/completeness, with explicit nullable
  rules, and validate the required nested source/package/file record structures.
  Invalid types should consistently raise a useful `ValueError`, not escape as
  an incidental regex `TypeError` or dictionary `KeyError`.
- [ ] Require the source records needed to substantiate a complete capture. When
  an aggregate digest is derived from stored records, check their consistency
  using the same canonicalization function rather than trusting unrelated fields.
- [ ] Ensure completeness depends on structurally valid, present evidence and the
  R1a/R1b coverage status. Truthiness of arbitrary strings is insufficient.
- [ ] Add regressions for all three mutations above, malformed nested file records,
  and the allowed null/incomplete cases. Test export as well as validation so no
  malformed record can be published with `capture_status: complete`.

## Bounded follow-up assignment

Implement **R1a, R1b, and R4a only**, with their regression coverage. Preserve the
resolved R2/R3/R5/R6/R7 work and no-clobber export. No model calls, live benchmark,
M1 changes, library mutation, or dependency downloads are needed.

Update the M0 completion record, export a new manifest without replacing the
previous one, and return the exact test outcomes and new manifest path. Keep the
review gate open. The new tests must exercise collection from actual temporary
files through identity/completeness, so they cannot pass merely because an already
computed digest field was manually changed.

## Reviewer validation result

The reviewer reran dependency imports and
`./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`:
**121 tests passed in 73.887 seconds**, including the unit and integration suites.
The three targeted counterexamples above were reproduced independently and are
not covered by those passing tests. No model calls were made.
