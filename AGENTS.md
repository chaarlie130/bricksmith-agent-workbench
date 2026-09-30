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
