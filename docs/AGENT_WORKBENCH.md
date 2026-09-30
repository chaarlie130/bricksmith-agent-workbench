# Agent workbench: first slice

This workstream gives an API-driven design agent a small set of inspectable
tools before adding provider-specific orchestration. It reuses BrickSmith's
construction checker and rendering utilities; it does not include the former
local language-model training pipeline.

## Commands

The canonical system instructions for every fresh design agent are in
[`bricksmith/workbench/system_prompt.md`](../bricksmith/workbench/system_prompt.md).
Future API runners should call `bricksmith.workbench.prompt.load_system_prompt()`
for their system message, so the instructions do not drift from this file.
`python scripts/workbench.py prompt` prints the same text for manual setups.

Run from the repository root with the BrickSmith Python environment:

```bash
python scripts/workbench.py prompt
python scripts/workbench.py search "modern glass house with terrace" --limit 5
python scripts/workbench.py inspect data/reference_sets/ldr/omr_21009-1_Farnsworth_House.ldr --start 1 --count 80
python scripts/workbench.py check path/to/candidate.ldr
```

All successful commands return JSON. `search` scans the checked-in reference
models and ranks title, a small set of reviewed seed descriptions, and part IDs
with lexical matching. Results include an absolute source path, source prefix,
SHA-256 digest, piece count, and any license line found in the file. A missing
license line is reported as `null`, not permission to redistribute. `inspect`
returns at most 200 numbered lines per call so an agent can read an example
without filling its context with an entire set. `check` wraps BrickSmith's
existing validator and maps collision pair indices to LDraw source lines.

These tools are deliberately modest. Search does not yet retrieve semantic
subassemblies or use embeddings. Validation does not establish assembly order,
insertion clearance, clutch strength, or real-world stability. The ground
height is configurable because a model's origin may differ from the default.

## Next vertical slice

Add a versioned build session with module-level edits and saved checkpoints.
Then connect one API provider to a bounded plan → retrieve → edit → check →
render loop. Record every attempt and cost before comparing it to the existing
static context-pack experiment. Hold out designs, not just filenames, when
evaluating retrieval gains.
