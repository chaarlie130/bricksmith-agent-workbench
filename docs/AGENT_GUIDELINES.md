# BrickSmith: Agent Guidelines & Engineering Discipline

> **Notice to Autonomous AI Agents:** You are working on a high-rigor generative AI and robotic assembly codebase. This repository values ground truth, scientific precision, and working software over superficial metrics or illusory claims.

---

## 1. Prime Directives for Agents

### 1.1 Grounded in Consensus Research
* Always adhere to the architectural principles defined in [`docs/RESEARCH_FOUNDATIONS.md`](RESEARCH_FOUNDATIONS.md) and [`docs/ARCHITECTURE.md`](ARCHITECTURE.md).
* **Never attempt to solve LEGO generation by writing procedural `if/else` loops that place 1x1 bricks.** We already proved in `brickblender` that hardcoding procedural brick-packers produces blocky brutalist Minecraft cubes. BrickSmith is built on **graph-backed generative assembly and BFS attachment trees**.

### 1.2 Zero Silent Fallbacks or Faked Passes
* If a generation step or test fails, **let it fail loudly**.
* Never silently substitute an invalid piece with a generic brick.
* Never weaken physical validation thresholds (e.g. ignoring collision penetration or removing compressive gravity checks) to make a test pass.
* Never report procedural mock data as neural model outputs.

### 1.3 Strict Invariant Checking
* Every piece placement must be backed by valid connection semantics: male-to-female port mating with zero rigid-body mesh collision.
* Every complete model must form a single connected component grounded to an explicit physical baseplate.

---

## 2. Codebase Organization & Responsibilities

```
bricksmith/
├── core/             # Canonical data structures (Part, Connector, AssemblyGraph, BFSTree)
├── geometry/         # 3D spatial priors, voxel envelopes, and bounding hulls
├── decomposition/    # Sub-assembly partitioning ("Numbered Bags")
├── physics/          # HiGHS LP static equilibrium & MeshLib collision checks
├── io/               # LDraw (.ldr, .mpd), Pick-a-Brick BOM, and instruction exporters
└── rendering/        # Axonometric software rasterizer and preview sheet generators
```

### When Modifying Subsystems:
* **`core/`**: Keep data structures lean, immutable where possible, and fully typed (`typing.NamedTuple`, `dataclasses`, or strict Pydantic models).
* **`physics/`**: Treat `construction_validator.py` as a strictly calibrated ground truth. If expanding part scopes, verify connector frames and inset meshes first.
* **`tests/`**: Any new feature or module must be accompanied by unit tests with automated verification.

---

## 3. Daily Execution Workflow

1. **Check the Current Phase in [`docs/ROADMAP.md`](ROADMAP.md)**: The active block is Gate 3a in [`PHASE_3A_GOAL.md`](PHASE_3A_GOAL.md). Training strings and sampler actions must stay the same codec. Do not satisfy generation by searching a fixed part list until `validate_ldraw` passes.
2. **Read Interface Contracts**: Ensure inputs and outputs conform to standard LDraw Units (LDU) and established schemas.
3. **Execute & Test**:
   ```bash
   python -m unittest discover tests/
   ```
4. **Log Experiments**: If running model evaluation or candidate sweeps, record every attempted brief, seed, and raw output in a monotonic ledger.
