# Scope for agents working in this checkout

This checkout is the **frontier-model LEGO design workbench**. Build an agent
harness around external AI APIs, reference retrieval, LDraw editing, rendering,
and structural feedback. Do not treat the former Llama 3B QLoRA training plan
as this project's roadmap. Training scripts, token samplers, and training
datasets were removed from this checkout intentionally.

Before changing the harness, read `README.md`,
`docs/AGENT_WORKBENCH.md`, and
`bricksmith/workbench/system_prompt.md`. The system prompt is canonical: update
it when agent-visible tools or checker semantics change, and keep the prompt
loader and tests aligned. For an API runner, call
`bricksmith.workbench.prompt.load_system_prompt()`.

Retain the reusable construction infrastructure: `bricksmith/core`,
`geometry`, `decomposition`, `io`, `physics`, and `rendering`, the LDraw
reference corpus, and the part-library links. Do not infer that a historical
reference metadata score is a current physics result. Preserve source
provenance and report failed checks accurately.

Keep model runs reproducible: save briefs, provider/model identifiers, tool
calls, intermediate `.ldr` files, validation reports, renders, and costs. When
comparing approaches, include failed attempts and use held-out designs.

## Direct single-agent builds (required)

A user's subject-only request is a complete design brief. Do not require them
to spell out reference study, piece budgeting, checking, rendering, or
iteration. Read `bricksmith/workbench/system_prompt.md` before authoring any
model and apply its default design-quality contract. For an architectural
display set with no stated size, plan for 500–1000 physical pieces; honor an
explicit user budget instead. The goal is a visually convincing, complete,
construction-checked set, not the fastest file that parses. Do not stop at a
failed roof or a sparse preliminary shell; revise until the final gate passes
and the two views communicate the requested subject, or report a genuine
blocker/incomplete result. Never call another AI model for a direct build
unless the user asks for an API-runner test.

- Run commands from this repository root with `./.venv/bin/python`. Do not use
  `python`, `python3`, a global interpreter, or the Codex bundled Python. Before
  placing parts, verify dependencies with
  `./.venv/bin/python -c 'import bricknet, meshlib, matplotlib'`. Stop and
  report an environment failure if that command fails; never count an
  unavailable checker or renderer as a pass.
- Save intermediate `.ldr` files for the foundation/walls, openings, and
  complete roof stages. After each substantial stage run
  `./.venv/bin/python scripts/workbench.py check <stage.ldr> --ground-y <Y>`.
  Partial disconnected stages may be repaired; do not discard them merely
  because they are intermediate. Recheck after repairs and before advancing.
- Render the final model at two angles with `scripts/render.py`, open and
  inspect both images, and make a meaningful visual revision if needed.
- Finish with `scripts/accept_build.py` using `./.venv/bin/python`, every
  saved major-stage model, the correct ground plane, and both inspected-view
  flags. Use `--min-pieces` and `--max-pieces` only when the user gave a
  different budget. The command reruns the five final construction checks
  and renders.
  It exits zero only when every final check passes, all supplied major stages
  pass and show distinct placement progress, the piece target is met, both
  renders were created, and both view inspections are recorded.
  A zero exit code means the acceptance gate passed; mere command success,
  missing checks, or render creation alone is not construction success.
- Report piece count, each of the five checks, stage status, render paths,
  inspected views, and any unavailable or failed steps from
  `acceptance.json`. Never describe an incomplete or failed model as passed.
