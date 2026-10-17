# M1 review — three bounded corrections

Reviewed: 2026-10-15. Final decision: **M1 accepted after re-review**; see
[M1 acceptance](M1-acceptance.md). M2 remains unstarted. Findings and initial
verification below are retained as review history; they are resolved blockers.

## Evidence and accepted work

The reviewer reran the prescribed dependency imports and full discovery:
**145 tests passed in 79.976 seconds**. The submitted M1 provenance manifest
validates, matches current source records, and recomputes to
`f65a44940c852f96181db70f22c666f5542f475de5f8e06c368d29051b136613`.
The accepted M0 artifact remains byte-identical, with SHA-256
`4f4c2722e4d492730aff84d8375000bc3edf8368c65ed7e1f70cb357b213f873`.

The offline import/export/migration entry points exist. Generic assembly/intent
representation, deterministic migration, source preservation, explicit historical
evidence, and the v2 execution refusal have supporting implementation and tests.
M1.4 and M1.5 evidence is accepted for this milestone. Preserve that work.

## Correction verification

The worker completed R1–R3 without adding live tools or M2 persistence:

- Persisted comments and parsed type-0 records share strict one-line/directive
  validation. Export and migrated revision files are reparsed; their physical
  multisets and per-line stable ID/owner mappings are checked before publication.
- `load_line_map` validates nested shape, and inspection recomputes all expected
  build/module exports and requires exact hashes, lines, IDs, and ownership.
- `move_parts` adds Decimal coefficients exactly, independent of ambient context.
- Targeted suites passed: 17 unit tests and 3 CLI integration tests. Final full
  discovery passed 149 tests in 82.026 seconds with `BRICKNET_DATA` explicitly
  configured. `git diff --check` passed.
- Configured preflight passed with the repository 3024 mesh loaded, all five real
  checks passed, and rendering passed. The earlier unconfigured preflight looked
  under the user cache; `data/bricknet-data/inset/3024.ply` exists.
- New v2 provenance validates and recomputes to
  `8d99cc05b7487bc5a7042cd7fe225a2738d8658cd9629916f33af8b72f6a046d`.
  M0 and M1 v1 evidence remain unchanged.

The subsequent reviewer rerun passed 149 tests in 85.445 seconds and closed M1.
See the acceptance record for independent probes and provenance verification.
M2 remains unstarted.

The following counterexamples were reproduced independently using temporary
documents/directories and the actual installed catalog. The first two also
reproduce through the CLI. No library, historical run, production source, or
model/provider was modified or invoked by the reviewer.

## M1-R1 — P1: accepted comments can change exported physical geometry

Locations: `design.py:637–640` and `design.py:865–884`.

Persisted design comments are checked only with `lstrip().startswith("0")`.
They can contain additional lines or unsupported directives, which are emitted
verbatim. The export check counts only lines starting exactly with `1 `, so an
indented injected placement escapes its count check.

Reproduction: import the tracked three-part fixture; replace its first source
comment with the string below; recompute design hashes and save the document.

```python
"0 source note\n 1 15 100 0 0 1 0 0 0 1 0 0 0 1 3005.dat"
```

`design-export` exits zero. Reimporting its `build.ldr` yields **four** parts,
while the design, physical hashes, and line map describe three. Replacing the
comment with `0 FILE hidden.ldr` also exports successfully despite MPD input being
unsupported. This breaks the authoritative-design/export boundary.

- [x] Use one strict type-0 validation rule for parsed source and persisted
  comments: exactly one physical line, exact record token `0`, and the same
  unsupported-directive policy. Reject embedded line separators rather than
  sanitizing away content. Preserve supported ordinary comments verbatim.
- [x] Before publishing exports, verify that the emitted placements and mapping
  agree with the design's physical multiset and owning IDs. Counting raw strings
  starting with `1 ` is insufficient. Apply the invariant to migrated revision
  exports as well without introducing M2 persistence.
- [x] Add regressions for the exact multiline/indented-placement case, CR/LF and
  other line separators recognized by the parser, malformed `0` prefixes, and
  persisted MPD directives. Recompute input hashes so tests reach structural
  validation. Exercise load/write/export and the CLI; rejection leaves no output.
  Retain a positive comment and duplicate-placement round trip with correct maps.

## M1-R2 — P1: line-map contents are trusted without checking correspondence

Locations: `design.py:809–819`, `load_line_map`.

Inspection compares the supplied export digest with a digest stored in the line
map, but does not establish that its placement entries match that file/design.
Starting with a valid export, change the first mapping's `line` to `999` and
leave its file hash and revision unchanged. The actual `design-inspect` CLI
exits zero and returns line 999. Wrong part/assembly associations could similarly
misdirect future edits even though the cited file hash is correct.

- [x] Validate line-map schema and nested entry shapes with field-specific
  `DesignError`s, including revision, positive integer lines, unique line/part
  entries, and known part/assembly ownership. Malformed inputs must not leak
  incidental `KeyError`/`TypeError` exceptions.
- [x] Bind the requested map to the actual deterministic export for this design.
  For M1, recomputing the expected export bytes and entries for `build.ldr` or
  a known assembly module is sufficient. Compare both the file digest and the
  exact correspondence, including complete placement coverage. The caller's
  file digest and a matching unverified string in a JSON record are not enough.
  Do not add signatures, a database, or a generic external-map import protocol.
- [x] Test wrong/out-of-range lines, swapped IDs between distinct placements,
  incorrect ownership, missing/duplicate entries, stale revision/file identities,
  and malformed nested records. Include rejection through the real CLI, plus a
  valid build and assembly-map inspection. Verify inspected IDs against actual
  placement contents, not merely membership in the set of known IDs.

## M1-R3 — P2: move arithmetic silently rounds supported coordinates

Location: `design.py:836–837`.

Parsing/serialization retain exact decimal tokens, but `move_parts` uses the
ambient Decimal arithmetic context (normally 28 significant digits). Importing
X=`1.00000000000000000000000000001` and applying a zero-distance move changes X
to `1.000000000000000000000000000`. Its structure hash changes even though the
requested physical operation was a no-op. Small nonzero offsets can also vanish.

- [x] Make translation addition exact for supported finite decimal operands,
  independent of ambient Decimal precision. Use an operand-derived local context
  or exact coefficient/exponent arithmetic. Do not choose another arbitrary global
  precision or silently quantize inputs. Keep matrix validation tolerance separate.
- [x] Test more than 28 significant digits, a zero move, a tiny nonzero offset
  added to a nonzero coordinate, and inverse moves. Repeat under a lower caller
  Decimal precision. Check exact coordinates, stable part IDs, unchanged source
  documents, and physical hashes through save/load/export/reimport. A new revision
  ID is allowed for a no-op; fabricated structure/appearance changes are not.

## Environment correction — no missing library download is needed

The standalone preflight failure is reproducible, but the reported cause needs
correction: `data/bricknet-data/inset/3024.ply` **exists**. The failed probe looks
under `~/Library/Application Support/bricknet/inset/3024.ply` instead. The existing
validator sets a repository default later in import order; integration tests
import that validator before probing, explaining their different result.

The reviewer ran the following against the existing snapshot:

```bash
BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python scripts/workbench.py preflight
```

It exited **zero**, with the actual mesh loaded, all five construction checks
passed, rendering passed, and overall status passed. Nothing was downloaded or
changed in the library. The mesh probe is required for this preflight's success;
it should not be described as an optional missing asset.

- [x] Correct the completion report and document the explicit configured command
  for this checkout. Preserve the failed unconfigured result as historical
  evidence with its actual path-resolution cause. Use the same explicit data
  configuration for fresh CLI integration/provenance verification. No preflight
  redesign, threshold changes, dependency downloads, or M0 artifact edits are
  assigned in this bounded follow-up. Unconfigured import-order behavior remains
  a disclosed environment-setup limitation until separately addressed.

## Return for review

- [x] Implement M1-R1–R3 and the environment documentation correction only.
- [x] Run the targeted regressions, full discovery, configured real preflight,
  and `git diff --check`; report exact outcomes and real versus mocked evidence.
- [x] Update M1 completion evidence and write a new provenance artifact without
  replacing the submitted v1 or accepted M0 artifacts.
- [x] Leave M1's reviewer gate open. Do not start M2, make model requests,
  change live tool schemas/checker thresholds, or commit/push.

These fixes enforce the existing M1 contracts. They do not add new design tools,
expand supported LDraw formats, or authorize benchmark execution.
