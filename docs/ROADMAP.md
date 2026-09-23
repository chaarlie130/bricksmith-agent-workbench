# BrickSmith: Development Roadmap & Milestones

> **Objective:** Systematically progress from ground-truth foundations to an end-to-end Text-to-Brick system capable of generating 500–2,500+ piece LEGO Architecture sets meeting Milestone #1.

---

## Milestone Overview

```
Phase 0: Foundations & Port Verification
   │
   ▼
Phase 1: Port-Graph Engine & Micro-Architecture Catalog (SNOT, Jumpers)
   │
   ▼
Phase 2: Modular Decomposition ("Numbered Bags") & 3D Envelope Prior
   │
   ▼
Phase 3: Neural Attachment Generator & Guided Decoding
   │
   ▼
Phase 4: Production Pipeline: Prompt-to-Box (LDraw + BOM + Instructions)
```

---

## Phase 0: Foundations, Invariants & Verification Engine (CURRENT)
**Goal:** Establish clean data pipelines, verification infrastructure, and exact test baselines.

* [x] **0.1 Repository Setup:** Clean layout, symlinked LDraw catalog (24,500+ parts) and BrickNet collision meshes (21,000+ parts).
* [x] **0.2 Reference Dataset:** Curate 200 gold-standard LEGO Architecture sets in `data/reference_sets/`.
* [ ] **0.3 Physics & Verification Engine (`bricksmith.physics`):** Port and verify HiGHS LP compressive static equilibrium, MeshLib collision detection, and vertical insertion clearance.
* [ ] **0.4 CAD & Manufacturing IO (`bricksmith.io`):** Robust LDraw parser/writer and Pick-a-Brick / BrickLink CSV BOM exporter.
* [ ] **0.5 Multi-View Software Rasterizer (`bricksmith.rendering`):** Fast multi-view and 2x2 comparison sheet axonometric renderer.
* **Gate 0:** 100% of curated reference sets pass LDraw roundtrip, validation, and BOM extraction without errors.

---

## Phase 1: Port-Graph Engine & Micro-Architecture Vocabulary
**Goal:** Formalize discrete port-socket connections and build the SNOT/jumper catalog.

* [ ] **1.1 Expanded Architecture Catalog (`configs/architecture_scope.json`):**
  - Standard bricks & plates ($1 \times 1$ up to $2 \times 8$).
  - Jumper plates (`3794b`, `15573`) for half-stud staggered rhythms.
  - SNOT brackets (`99781`, `99780`, `36840`, `36841`) and headlight bricks (`4070`, `87087`) for sideways facade tiling.
  - Slopes & Cheese slopes (`54200`, `3039`, `3040`, `15068`) for cornices and pitched roofs.
  - Grille tiles (`2412b`) and smooth tiles (`3069b`, `3070b`, `6636`) for finished micro-textures.
* [ ] **1.2 Assembly Graph Engine (`bricksmith.core.graph`):**
  - Implement rigid port kinematics: calculating absolute transforms from relative port connections.
  - Collision-aware port mating verification.
* [ ] **1.3 BFS Spanning Tree Codec (`bricksmith.core.tree`):**
  - Bidirectional parser: `LDR -> AssemblyGraph -> BFSTree Path Text -> LDR`.
  - Validate round-trip fidelity on reference architecture models.
* **Gate 1:** Zero geometric drift on BFS tree reconstruction over 50 held-out reference architecture models.

---

## Phase 2: Modular Decomposition ("Numbered Bags") & 3D Envelope Prior
**Goal:** Solve high piece counts by breaking large buildings into bounded sub-assemblies.

* [ ] **2.1 Architectural Massing Prior (`bricksmith.geometry`):**
  - Generate coarse volumetric bounding hulls (SDF / Voxel bounds / Point clouds) capturing setbacks, towers, wings, and roof pitch.
* [ ] **2.2 Modular Bag Partitioner (`bricksmith.decomposition`):**
  - Automatically partition volume into functional layers:
    1. Baseplate & Border Plinth (incorporating the verified black-tile foundation generator).
    2. Structural Core & Internal Bearing Walls.
    3. Facade Envelopes, Fenestration & SNOT Cladding.
    4. Roof Crowns, Cornices & Cantilevers.
  - Guarantee each module remains under 300 pieces to stay well within transformer context limits.
* **Gate 2:** Successful automatic decomposition of complex reference models (e.g. *Robie House*, *Empire State Building*) into 3–5 logically ordered sub-assemblies with interface port compatibility.

---

## Phase 3: Neural Attachment Generator & Guided Decoding
**Goal:** Train and steer the generative model to place pieces via BFS graph prediction.

* [ ] **3.1 Dataset Preparation:**
  - Tokenize reference architecture sets and synthetic modular sub-structures into BFS path sequences.
* [ ] **3.2 Fine-Tuning Setup:**
  - Fine-tune small local models (e.g., Qwen-3.5-9B or LLaMA-3.2-3B via MLX on Apple Silicon) on attachment path prediction conditioned on coarse geometry.
* [ ] **3.3 Validity-Constrained Logit Masking:**
  - Replace expensive rollback with dynamic forward masking: mask out part/port tokens that would cause physical collisions or boundary overruns before sampling.
* [ ] **3.4 PVPO Reinforcement Alignment:**
  - Post-train with coupled rewards (physical equilibrium + geometric/semantic fidelity) to prevent "PhysHack" degeneration.
* **Gate 3:** Generation of novel, non-memorized architecture models exceeding 400+ pieces with >90% physical validity and zero floating pieces.

---

## Phase 4: Production Pipeline: Prompt-to-Box
**Goal:** End-to-end delivery of factory-ready LEGO Architecture sets from natural language prompts.

* [ ] **4.1 Prompt-to-CAD Pipeline:**
  - `Text Brief -> 3D Envelope -> Modular Partitioning -> BFS Tree Generation -> Physical Validation Gate -> LDraw CAD`.
* [ ] **4.2 Automated Assembly Instructions (`bricksmith.io.studio`):**
  - Synthesize step-by-step instruction booklets (camera angles, part-callout boxes, ghosting of previous steps) exportable via LPub3D / Studio 2.0.
* [ ] **4.3 Pick-a-Brick / BrickLink Ordering:**
  - Automated XML / CSV export formatted for 1-click import into BrickLink Want Lists and LEGO Pick-a-Brick carts.
* **Gate 4:** Milestone #1 Full Verification: User inputs "Art Deco Skyscraper with tiered setbacks and bronze crown", system outputs certified `.ldr`, validated BOM CSV, and step-by-step PDF instructions.
