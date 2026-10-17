# BrickSmith Agent Workbench

Development status: M0–M2 are accepted; M3-A's persistent intent ledger is still
under review. The latest R3b changes are awaiting full validation and reviewer
acceptance. See the [sharing checkpoint](docs/implementation/2026-10-16-sharing-checkpoint.md)
and [implementation plan](docs/HARNESS_IMPLEMENTATION_PLAN.md). Live v2 model
execution and the official benchmark remain disabled/unstarted.

An experimental workbench for frontier AI models to design original LEGO builds
from a brief. The intended loop is: plan, retrieve relevant LDraw examples,
edit a persistent model, validate its geometry and support, inspect renders,
and repair specific issues. The implemented workbench has reference and part
lookup, bounded modular and array authoring, structural feedback, and previews.

This checkout does **not** train or run a local language model. A first
ChatGPT-plan Responses transport, one-request build pilot, and a resumable
tool-calling design session are available. The reusable `bricksmith` package provides geometry, LDraw IO, a
physics checker, rendering, BOM export, and optional model decomposition.

## Start here

For a fresh design agent in this checkout, the user's request can be just the
subject (for example, "build a modern art studio in a desert with a pool").
`AGENTS.md` and the canonical system prompt define the reference, construction,
render-review, and acceptance workflow. An architectural display build defaults
to 500–1000 physical pieces unless the user specifies otherwise. Do not make
the user paste a long operational checklist as part of the design brief.

Use the repository virtual environment with dependencies from `requirements.txt` and BrickNet's
part meshes/connectors. `data/ldraw` and `data/bricknet-data` are symlinks to
local libraries in this checkout; another machine must configure its own
library paths before validation or rendering will work.

**For direct builds, use `./.venv/bin/python` for every command.** Confirm the
checker and renderer dependencies before starting:

```bash
./.venv/bin/python -c 'import bricknet, meshlib, matplotlib'
```

Do not fall back to a system or bundled interpreter if this fails; report the
environment issue. Save and check each substantial model stage so temporary
partial failures can be repaired before the final build.

```bash
./.venv/bin/python scripts/workbench.py prompt
./.venv/bin/python scripts/workbench.py search "modern glass house with terrace" --limit 5
./.venv/bin/python scripts/workbench.py inspect data/reference_sets/ldr/omr_21009-1_Farnsworth_House.ldr --start 1 --count 60
./.venv/bin/python scripts/workbench.py check data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr
```

At the end of a direct build, run the final acceptance gate (repeat the stage
argument for each saved major stage):

```bash
./.venv/bin/python scripts/accept_build.py runs/<build>/<build>.ldr \
  --ground-y 8 \
  --stage-model runs/<build>/01-foundation-walls.ldr \
  --stage-model runs/<build>/02-openings.ldr \
  --stage-model runs/<build>/03-complete-roof.ldr \
  --render-dir runs/<build>/renders \
  --inspected-view front_left --inspected-view front_right
```

Inspect both generated images before setting the view flags. The command writes
`acceptance.json` with the piece count, all five checks, per-stage outcomes,
render paths, and inspection record. It exits nonzero on any failed or
unavailable check, fewer than three distinct major stages, a missed default
500–1000-piece target, failed render, or unrecorded view. Override the target
with `--min-pieces` and `--max-pieces` when the user specifies a different
budget. The gate cannot score visual quality; the agent must critique and
revise the actual renders.
Command completion alone does not establish construction success.

The [agent system prompt](bricksmith/workbench/system_prompt.md) is the
canonical instruction source for a fresh design agent. Future API runners
should load it with `bricksmith.workbench.prompt.load_system_prompt()`.
The [workbench guide](docs/AGENT_WORKBENCH.md) describes command outputs and
current limits.
The [quality benchmark](docs/QUALITY_BENCHMARK.md) keeps visual and
construction comparisons separate, using the user's local Claude/GPT house
artifacts as a private evaluation target rather than retrieval examples.

The [harness implementation plan](docs/HARNESS_IMPLEMENTATION_PLAN.md) defines
the engineering milestones, with [explicit contracts](docs/HARNESS_CONTRACTS.md)
and a [worker handoff](docs/WORKER_HANDOFF.md). M1 now adds an offline stable
design document and explicit v1 migration; it does not change model generation
or enable v2 model execution. M2-A adds a separate offline operator transaction
workspace and CLI; existing live editing tools still do not use that service.
The [official benchmark protocol draft](docs/BENCHMARK_PROTOCOL_DRAFT.md)
defines the setup and fairness requirements; no official benchmark has been run
under that protocol yet.

To inspect a flat LDraw file without a model request, import it to a stable
design record, inspect its IDs, then export a deterministic build and module
views. Import/export destinations must be new paths:

```bash
./.venv/bin/python scripts/workbench.py design-import tests/fixtures/design/tiny.ldr /tmp/tiny-design.json
./.venv/bin/python scripts/workbench.py design-inspect /tmp/tiny-design.json
./.venv/bin/python scripts/workbench.py design-export /tmp/tiny-design.json /tmp/tiny-export
./.venv/bin/python scripts/workbench.py design-inspect /tmp/tiny-design.json \
  --line-map /tmp/tiny-export/line_map.json --export-file /tmp/tiny-export/build.ldr
```

`design-migrate <existing-v1-session> <new-v2-session>` explicitly copies a
legacy session into a read-only v2 snapshot. V2 step/run/mutation remains
disabled until atomic persistence is implemented. See
[`docs/AGENT_WORKBENCH.md`](docs/AGENT_WORKBENCH.md#m1-offline-design-documents)
for command details and migration limits.

For a persistent agent build, use `python scripts/agent_session.py start ...`,
then deliberate `step` invocations as documented in the workbench guide. Each
step consumes one model request; check account usage between steps. The
optional `run` command chains a bounded number of saved model/tool turns;
its token ceiling is soft and is not an account usage guard.
The first request receives a locally retrieved LDraw reference starter pack
and, when suitable, a rendered example; the user's own design image takes
precedence. See the guide for provenance and quality limitations.

For a local personal project, the separate [ChatGPT plan-usage flow](docs/AGENT_WORKBENCH.md#chatgpt-plan-usage) can authorize real Responses API requests without an API key. This is not identity-only website sign-in.

Beyond the local reference corpus, `search_omr_sets`/`fetch_omr_set`
(`bricksmith/workbench/omr.py`) give the agent live, anonymous, unauthenticated
search and raw-file fetch against the LDraw Official Model Repository
(library.ldraw.org) -- covering most, but not every, officially released LEGO
set. Fetched files are real third-party designs with unverified licensing;
treat them as reference data, not as a design cleared for reuse.

Additional reusable commands:

```bash
./.venv/bin/python scripts/render.py path/to/model.ldr -o preview.png
./.venv/bin/python scripts/export_bom.py path/to/model.ldr --csv inventory.csv
./.venv/bin/python scripts/generate_baseplate.py --width 16 --depth 24 -o baseplate.ldr
```

## Reference corpus and validation

`data/reference_sets/ldr` contains 198 curated model files from several
sources. Search currently uses lexical matching over names, a small set of
descriptions, and part IDs. The adjacent JSON files and manifest are retained
as possible metadata sources; their historical stability scores are **not**
the current validator's results. Record provenance and confirm rights before
redistributing source models or derived excerpts.

The validator reports mesh collisions, an explicit ground base, stud-based
connectivity, and approximate static equilibrium. It does not prove insertion
clearance, build sequence, clutch strength, or real-world stability. A model
that fails a check needs diagnosis; a pass is not a physical certification.

## Development

```bash
./.venv/bin/python -m unittest discover -s tests/unit -p 'test_*.py'
./.venv/bin/python -m unittest discover -s tests/integration -p 'test_*.py'
./.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python scripts/workbench.py preflight
./.venv/bin/python scripts/workbench.py baseline-export runs/provenance/baseline.json --track historical-operator-assisted
```

The `tests/unit` command runs the data-independent contract suite against
temporary source/data fixtures. The full `tests` command runs that suite plus
all library-dependent checker, renderer, and existing workbench tests; it fails
when required libraries/data are absent. Real checks are identified as such in
integration modules; mocked seams remain unit evidence only. `preflight` reports
missing runtime or library targets, loads the catalog, connectors, and an actual
part mesh, then runs a tiny real check/render. In this checkout, set
`BRICKNET_DATA="$PWD/data/bricknet-data"` when invoking it; otherwise its mesh
probe can resolve to BrickNet's user cache before the repository library path is
configured. That fixture is a single 1×1 plate
and tests plumbing rather than broad checker coverage. `baseline-export` records
source and environment provenance only, makes no model request, and refuses to
overwrite an existing file. It labels the capture complete only when source,
runtime, LDraw, BrickNet data, and reference-corpus fingerprints are present.

The tested runtime is CPython 3.14.7 on macOS 26.6.1 arm64. Other Python
versions and platforms are not verified. For setup, create `.venv`, install the
dependencies with `./.venv/bin/pip install -r requirements-lock.txt`, clone
`https://github.com/kulits/BrickNet.git`, check out commit
`b09a689c4929bd27f59c9bb9446237967aa332c9`, then install that checkout with
`./.venv/bin/pip install -e ./BrickNet`. BrickNet's catalog, aliases, and
connector tables are read from its installed `bricknet/_data/v1` package data.
For collision geometry, set up a mesh snapshot with BrickNet's documented
fetcher (about 1.6 GB extracted):

```bash
mkdir -p data/bricknet-data
BRICKNET_DATA="$PWD/data/bricknet-data" ./.venv/bin/python -m bricknet fetch-meshes
```

Obtain the LDraw parts library from the official LDraw downloads, extract it
locally, and point `data/ldraw` to its root. It must contain `parts/`, `p/`,
and `LDConfig.ldr`; verify at least `parts/3005.dat` and `parts/3024.dat` exist.
The BrickNet snapshot must contain `inset/3024.ply` and the other part meshes
requested by designs. Run `preflight` to verify catalog and connector loading,
the `3024.dat` mesh, all five checks on a supported fixture, and PNG rendering.
Export a manifest before and after copying snapshots and compare the library
content hashes. The repository does not redistribute these libraries. The lock
pins observed Python packages, but clean-environment installation was not
verified. In this checkout BrickNet is editable from the `bricknet-evaluation`
source tree at the pinned commit (version 0.1.0); the manifest records its
actual source path, commit, dirty state, and source-content hash.

The original BrickSmith repository remains available separately for historical
research and any reusable code we deliberately bring into this workbench.

M2-B adds an explicit offline compatibility adapter for the existing mutation,
read, check, and render tools. Use `transaction-tool-catalog` to inspect its strict
argument schemas and `transaction-tool` with a versioned invocation containing
the exact base revision and assembled-export hash. The adapter routes through the
M2-A transaction service; v1 session execution remains the historical baseline,
and v2/transaction model `step` and `run` remain disabled pending M7.
