# BrickSmith Agent Workbench

An experimental workbench for frontier AI models to design original LEGO builds
from a brief. The intended loop is: plan, retrieve relevant LDraw examples,
edit a persistent model, validate its geometry and support, inspect renders,
and repair specific issues. The first implemented slice is reference search,
bounded source inspection, and structured validation feedback.

This checkout does **not** train or run a local language model. API-provider
orchestration, persistent editing sessions, and design critique are upcoming
work. The reusable `bricksmith` package provides geometry, LDraw IO, a
physics checker, rendering, BOM export, and optional model decomposition.

## Start here

Use Python 3.10+ with dependencies from `requirements.txt` and BrickNet's
part meshes/connectors. `data/ldraw` and `data/bricknet-data` are symlinks to
local libraries in this checkout; another machine must configure its own
library paths before validation or rendering will work.

```bash
python scripts/workbench.py prompt
python scripts/workbench.py search "modern glass house with terrace" --limit 5
python scripts/workbench.py inspect data/reference_sets/ldr/omr_21009-1_Farnsworth_House.ldr --start 1 --count 60
python scripts/workbench.py check data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr
```

The [agent system prompt](bricksmith/workbench/system_prompt.md) is the
canonical instruction source for a fresh design agent. Future API runners
should load it with `bricksmith.workbench.prompt.load_system_prompt()`.
The [workbench guide](docs/AGENT_WORKBENCH.md) describes command outputs and
current limits.

Additional reusable commands:

```bash
python scripts/render.py path/to/model.ldr -o preview.png
python scripts/export_bom.py path/to/model.ldr --csv inventory.csv
python scripts/generate_baseplate.py --width 16 --depth 24 -o baseplate.ldr
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
