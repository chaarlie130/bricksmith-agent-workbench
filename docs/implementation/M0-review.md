# M0 review — corrections required

Reviewed: 2026-10-15.
Decision: **M0 is not accepted yet. Keep M1 unstarted.**

The additive CLI, original fixture files, provenance-only labeling, and real
check/render smoke test are useful. The reported 102 tests, separate integration
test, and default preflight all passed again during this review. No generation
behavior or checker threshold change was found in the submitted diff.

The remaining problems concern the central purpose of M0: identifying the exact
source/data environment and making the verification reproducible. Passing the
current tests does not cover the counterexamples below.

Implementation source: `bricksmith/workbench/provenance.py` unless stated otherwise.
Line references refer to the submitted version; use symbols after subsequent edits.
All review probes were local, with temporary fixture repositories and no inference.

## R1 — P1: Capture source contents, not only Git status names

Affected tasks: M0.1, M0.6, M0.7. Source: `build_manifest`, lines 76–103.

`generation_source` contains HEAD and porcelain status text, but no working-tree
patch/content hash. Only a few source files receive direct content hashes. Editing
`bricksmith/workbench/references.py` twice while it remains modified produces the
same manifest identity for two different retrieval implementations. Untracked
source is excluded entirely. Both generation and instrumentation revision fields
are populated from HEAD, even when the instrumentation is uncommitted.

Reproduced in a temporary Git repository:

```text
references.py = "changed behavior A\n" -> manifest A
references.py = "changed behavior B\n" -> manifest B
manifest_identity(A) == manifest_identity(B): True
```

The `tool_schema_sha256` field hashes concatenated implementation files, not the
actual serialized model-visible schema. It neither isolates schema changes nor
substitutes for a complete source snapshot. Installed BrickNet is an editable
checkout; package version `0.1.0` alone does not identify its implementation.
The actual imported checkout is clean at `b09a689c4929bd27f59c9bb9446237967aa332c9`
today, but the manifest does not capture that fact.

Correction contract:

- [ ] Record an actual source content manifest and a reproducible dirty patch
  identity, including staged and unstaged changes. Include relevant untracked
  code explicitly; exclude unrelated user directories, credentials, and run output.
  Never scan all untracked files indiscriminately.
- [ ] Separate selected generation baseline identity from instrumentation identity.
  Record clean/dirty state and source hashes truthfully before commits exist.
- [ ] Hash the canonical serialized tool schema under the schema field. Retain
  implementation hashes separately. No model/network call is needed to read it.
- [ ] Record the actual imported BrickNet source identity, VCS/direct-install
  metadata, and editable changes where applicable, not just distribution version.
- [ ] Add a temporary-repository regression that changes a real source file's
  contents twice with the same Git status and proves the identities differ.

## R2 — P1: Exclude physical locations from content identity

Affected task: M0.6. Source: `_library_record` and `manifest_identity`, lines 65–69,
125–133.

The identity includes the complete `libraries` objects, including absolute
`configured_path` values. Changing only those paths changes identity even when
every source/library byte is identical. The relocation test checks `hash_tree`,
so it misses the actual manifest behavior.

Reproduced: copying a manifest and replacing only its configured library paths
with `/different/checkout/...` made the identities unequal.

- [ ] Define an explicit canonical identity projection that includes content and
  relevant settings but excludes configured/resolved filesystem locations, run IDs,
  timestamps, and output destinations. Keep locations available as diagnostic fields.
- [ ] Test the full manifest/export across relocated temporary checkouts, not only
  the helper that hashes a directory. Avoid accidentally including locations through
  future source, dependency, or input-provenance metadata.

## R3 — P1: Make library hashing complete and unambiguous

Affected tasks: M0.1, M0.6. Source: `hash_tree`, lines 34–47; library selection in
`build_manifest`, lines 104–105.

Files that are symlinks are silently excluded. Changing a linked mesh file's bytes
therefore leaves the tree hash unchanged. There is no explicit unresolved-link or
cycle policy. In addition, concatenating `path + NUL + bytes + NUL` is ambiguous
for binary files. These two different trees produced the same hash in review:

```text
Tree A: file a contains b"x\x00b\x00y"
Tree B: file a contains b"x"; file b contains b"y"
```

The manifest always hashes `ROOT/data/bricknet-data`. The validator honors an
existing `BRICKNET_DATA` override, so the exporter can identify a different data
tree from the one actually used by the checker.

- [ ] Hash a canonical manifest of relative paths, record types, byte sizes, and
  per-file content hashes, or use equally unambiguous length framing.
- [ ] Resolve supported library symlinks with an explicit cycle/dangling-link
  policy. If a library cannot be fully fingerprinted, report it incomplete; never
  silently omit files that the runtime can load. Preserve relocation invariance.
- [ ] Capture the effective library locations/configuration the runtime uses,
  including environment overrides, and retain both configured and resolved paths
  outside content identity.
- [ ] Add regressions for linked-file mutation, linked-directory traversal,
  dangling/cyclic links, binary delimiter ambiguity, and an effective data override.

## R4 — P2: Validate manifest values and protect existing evidence on export

Affected tasks: M0.6, M0.7. Source: `validate_manifest`, lines 114–122;
`scripts/workbench.py` baseline-export branch, lines 58–65.

Validation checks field presence but not types or nested structure. A document
with every field set to null except the correct schema string is accepted and can
receive an identity. Invalid hashes and NaN settings are not rejected. The exporter
also overwrites an existing destination directly, which can destroy a previous
baseline manifest or another run artifact.

- [ ] Validate required types, nested shapes, enum values, timestamp format, finite
  JSON values, and SHA-256 syntax. Specify which fields may legitimately be null
  in an offline provenance-only record. Missing evidence must remain identifiable.
- [ ] Emit standards-compliant JSON and validate before publishing. Incomplete
  fingerprints may be reported diagnostically, but must not claim complete baseline
  capture. Provider/model may remain null for a provenance-only export.
- [ ] Make export atomic and no-clobber by default. An existing destination must
  remain byte-identical on refusal or failed serialization; choose a new filename
  for a new export. No extra overwrite feature is necessary for M0.
- [ ] Test malformed nested/null values, invalid hashes, nonfinite numbers, existing
  destinations, and failed export. Test the real CLI entry point as well as helpers.

## R5 — P2: Report unavailable preflight components accurately

Affected task: M0.2. Source: `preflight`, lines 136–194, and eager imports in
`scripts/workbench.py`.

The renderer import happens outside its error handler. A simulated missing renderer
dependency raised `ModuleNotFoundError` instead of returning an unavailable report.
Other eager imports can likewise prevent preflight from reporting dependency
failures. `mesh.available` is set true after catalog/connector reads without loading
a mesh. Distribution-version absence is not distinguished from a successful import;
the no-real-check path can report passed without inspecting the advertised meshes.

- [ ] Perform explicit guarded import/capability probes and record each result.
  Ensure the preflight CLI can run far enough to report missing optional runtime
  components, even when normal check/render commands cannot import them.
- [ ] Load an actual fixture mesh before reporting mesh availability. Distinguish
  import success, absent package metadata, readable data, and successful execution.
- [ ] Preserve `unavailable` through aggregate status instead of relabeling a
  runtime exception as an ordinary construction failure.
- [ ] Confirm all five checks exist and pass before declaring the real check passed.
  A single-part plate tests plumbing; document that scope accurately (3024 is 1×1,
  not the 16×16 plate described in the current comment).
- [ ] Test missing imports, catalog/mesh failures, renderer failures, incomplete
  check output, and the `--no-real-check` path without calling a model.

## R6 — P2: Complete the promised test separation and fixture coverage

Affected tasks: M0.3, M0.4. Sources: `tests/test_physics.py`, real cases in
`tests/test_agent_session.py`, `tests/test_parts.py`, `tests/test_acceptance.py`,
and `tests/integration/test_environment.py`.

The 102-test command still executes real library/physics operations, including
roof construction and catalog/mesh lookup. Adding one integration smoke test did
not separate those cases. README's claim that the first suite does not claim real
geometry results is inaccurate. New provenance unit tests also hash the full local
libraries repeatedly rather than isolated temporary data.

The floating fixture is not an isolated floating case: its brick origin is Y=-8,
so its underside is Y=16. At ground Y=8 it fails `no_parts_below_ground`, just like
the below-ground fixture. The floating fixture is only used under a mocked
environment-error result, and the new below-ground fixture is not exercised.

Observed checks at Y=8:

| Fixture | Collision-free | Ground base | Above ground | Connected | Equilibrium |
| --- | --- | --- | --- | --- | --- |
| pass | true | true | true | true | true |
| collision | false | true | true | false | true |
| floating | true | false | false | true | false |
| below_ground | true | false | false | true | false |

- [ ] Separate pure contract tests from real data/checker/render tests through
  explicit discovery layout or a documented test selector. Move real tests rather
  than weakening/mocking away their intended integration coverage.
- [ ] Use small temporary source/data fixtures for provenance unit tests; actual
  large-library fingerprinting belongs in integration coverage.
- [ ] Make the floating fixture genuinely above ground, preferably a grounded base
  plus a floating part so connectivity/support failures are isolated. Add explicit
  ground metadata or test constants for every fixture.
- [ ] Exercise every advertised positive/negative fixture with the real checker;
  assert the intended diagnostic differences. Preserve all five-check reporting.
- [ ] Update commands, counts, and evidence labels. The pure contract suite must
  not need the user's private data snapshots; integration must fail clearly when
  its required libraries are unavailable, not silently skip required coverage.

## R7 — P2: Correct and verify the setup recipe

Affected task: M0.5. Source: README lines 143–154 and `requirements-lock.txt`.

README recommends Python 3.11–3.14, but installed metadata for the pinned NumPy
2.5.3, SciPy 1.18.1, and contourpy 1.4.0 requires Python >=3.12. The advertised
3.11 installation cannot satisfy that lock. A freeze of the working environment
is useful evidence, but is not evidence that a clean environment has been rebuilt.

- [ ] Narrow the documented runtime/platform to the validated configuration or
  supply separately tested compatible locks. Do not advertise untested versions.
- [ ] Identify the actual BrickNet editable source/commit and effective data
  snapshot configuration in the manifest and setup instructions consistently.
- [ ] Document a concrete compatible-data acquisition/snapshot and verification
  procedure, including which files/capabilities are required. No redistribution of
  third-party data is needed.
- [ ] Validate a clean setup in a separate environment if local artifacts permit
  it; otherwise explicitly report clean installation as unverified and give the
  exact missing external dependency. Do not modify the working project environment
  or launch downloads implicitly while resolving this review.

## Worker follow-up assignment

Implement **only R1–R7** and their regression coverage. Keep the existing M0 work,
generation behavior, checker thresholds, and later milestones unchanged. These are
M0 corrections, not permission to implement M1 or expand the runtime.

Use the existing handoff's environment and scope rules. No model calls or live
benchmark runs. Update `M0-completion.md` with correction IDs, actual test commands,
mocked versus real outcomes, and remaining limitations. Recheck M0 task boxes only
when the associated evidence exists. Leave the reviewer gate open for re-review.

For review, provide one exported manifest plus exact CLI/test reproduction evidence
showing: source changes are detected; relocation preserves identity; linked-data
changes are detected or explicitly rejected; malformed manifests are rejected;
exports do not overwrite prior evidence; missing dependencies are reported; and
all four fixture categories have the intended real checker outcomes.
