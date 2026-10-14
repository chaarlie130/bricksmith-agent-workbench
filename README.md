# BrickSmith Agent Workbench

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
python -m unittest discover tests
```

The original BrickSmith repository remains available separately for historical
research and any reusable code we deliberately bring into this workbench.
