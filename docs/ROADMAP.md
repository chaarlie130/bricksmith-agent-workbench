# BrickSmith: Development Roadmap & Milestones

> **Objective:** Systematically progress from ground-truth foundations to an end-to-end Text-to-Brick system capable of generating 500–2,500+ piece LEGO Architecture sets meeting Milestone #1.

---

## Milestone Overview

```
Phase 0: Foundations & Port Verification [COMPLETED]
   │
   ▼
Phase 1: Port-Graph Engine & Micro-Architecture Catalog (SNOT, Jumpers) [COMPLETED]
   │
   ▼
Phase 2: Modular Decomposition ("Numbered Bags") & 3D Envelope Prior [COMPLETED]
   │
   ▼
Phase 3: Neural Attachment Generator & Guided Decoding [ACTIVE]
   │     3a Closed loop (one codec, mesh-aware mask, short LoRA run)
   │     3  400+ piece validity gate, after PVPO
   ▼
Phase 4: Production Pipeline: Prompt-to-Box (LDraw + BOM + Instructions)
```

---

## Phase 0: Foundations, Invariants & Verification Engine (COMPLETE)
**Goal:** Establish clean data pipelines, verification infrastructure, and exact test baselines.

* [x] **0.1 Repository Setup:** Clean layout, symlinked LDraw catalog (24,500+ parts) and BrickNet collision meshes (21,000+ parts).
* [x] **0.2 Reference Dataset:** Curate 200 gold-standard LEGO Architecture sets in `data/reference_sets/`.
* [x] **0.3 Physics & Verification Engine (`bricksmith.physics`):** Port and verify HiGHS LP compressive static equilibrium and MeshLib collision detection (vertical insertion clearance planned for Phase 4 instruction sequencing).
* [x] **0.4 CAD & Manufacturing IO (`bricksmith.io`):** Robust LDraw parser/writer and Pick-a-Brick / BrickLink CSV BOM exporter.
* [x] **0.5 Multi-View Software Rasterizer (`bricksmith.rendering`):** Fast multi-view and presentation axonometric renderer.
* **Gate 0:** 100% of curated reference sets pass LDraw roundtrip, validation, and BOM extraction without errors. [PASSED]

---

## Phase 1: Port-Graph Engine & Micro-Architecture Vocabulary (CURRENT ACTIVE)
**Goal:** Formalize discrete port-socket connections and build the SNOT/jumper catalog.

* [x] **1.1 Expanded Architecture Catalog (`configs/architecture_scope.json`):**
  - Standard bricks & plates ($1 \times 1$ up to $2 \times 8$).
  - Jumper plates (`3794b`, `15573`) for half-stud staggered rhythms.
  - SNOT brackets (`99781`, `99780`, `36840`, `36841`) and headlight bricks (`4070`, `87087`) for sideways facade tiling.
  - Slopes & Cheese slopes (`54200`, `3039`, `3040`, `15068`) for cornices and pitched roofs.
  - Grille tiles (`2412b`) and smooth tiles (`3069b`, `3070b`, `6636`) for finished micro-textures.
* [x] **1.2 Assembly Graph Engine (`bricksmith.core.graph`):**
  - Implement rigid port kinematics: calculating absolute transforms from relative port connections.
  - Collision-aware port mating verification.
* [x] **1.3 BFS Spanning Tree Codec (`bricksmith.core.tree`):**
  - Bidirectional parser: `LDR -> AssemblyGraph -> BFSTree Path Text -> LDR`.
  - Validate round-trip fidelity on reference architecture models.
* [x] **1.4 Large-Scale BFS Tree Corpus Generation:**
  - Batch convert all reference architecture models into tokenized training paths (`data/corpus/reference_bfs_trees.jsonl`).
* **Gate 1:** Zero geometric drift on BFS tree reconstruction over 50 held-out reference architecture models. [PASSED]

---

## Phase 2: Modular Decomposition ("Numbered Bags") & 3D Envelope Prior (COMPLETED)
**Goal:** Solve high piece counts by breaking large buildings into bounded sub-assemblies.

* [x] **2.1 Architectural Massing Prior (`bricksmith.geometry`):**
  - Generate exact 3D bounding boxes, volume, aspect ratios, and boolean voxel occupancy grids capturing setbacks, towers, wings, and massing.
* [x] **2.2 Modular Bag Partitioner (`bricksmith.decomposition`):**
  - Automatically partition volume into functional layers:
    1. Baseplate & Border Plinth (incorporating the verified black-tile foundation generator).
    2. Structural Core & Internal Bearing Walls.
    3. Facade Envelopes, Fenestration & SNOT Cladding.
    4. Roof Crowns, Cornices & Cantilevers.
  - Guarantee each module remains under 300 pieces to stay well within transformer context limits.
* **Gate 2:** Successful automatic decomposition of complex reference models into 4 logically ordered sub-assemblies with conservation of matter and interface port connectivity. [PASSED]

---

## Phase 3: Neural Attachment Generator & Guided Decoding
**Goal:** Train and steer the generative model to place pieces via BFS graph prediction.

Scaffolding for 3.1–3.3 is on disk. It is not Gate 3, and it is not yet a closed training loop. The corpus, the trainer, and the sampler must speak one attachment language before a long fine-tune. The active target is **Gate 3a**. PVPO and the 400-piece bar stay after that.

### Landed scaffolding

* [x] **3.1 Bag dataset:** `scripts/prepare_training_data.py` writes `data/training/train.jsonl` and `data/training/val.jsonl` from `data/corpus/reference_bfs_trees.jsonl`. One example per non-empty numbered bag, split by source model. Targets are parent-relative codec strings (part, color, parent index, parent port, self port, rotation offset), not absolute `(x, y, z)`. Sequences stay under 1,500 Llama 3.2 tokens. `BFSTreeCodec.decode` restores part ids and parent-port links.
* [x] **3.2 MLX LoRA dry-run:** `scripts/train_mlx.py` loads cached `mlx-community/Llama-3.2-3B-Instruct-4bit` (Qwen 2.5 7B is not required). Dry-run uses gradient checkpointing, batch size 1, gradient accumulation, and sequence length 1,500. One verified optimizer step fits under 16 GB. This is not a trained attachment model.
* [x] **3.3 Mask prototype:** `bricksmith/generation/sampler.py` can set illegal next-token ids to `-inf` for out-of-bounds placement, stud-to-stud or tube-to-tube mating, and bounding-box overlap, then realize a pose from the parent port through `BFSTreeCodec.decode`. The live sampler's legal set is still a small plate-and-brick joint pool. Mesh penetration is not part of that mask. `scripts/validate.py` remains the equilibrium gate.

### Gate 3a — closed loop [PASSED]

The prompt for this block is [`docs/PHASE_3A_GOAL.md`](PHASE_3A_GOAL.md).

* [x] **3.5 One attachment language:** Corpus, trainer, and sampler use the same codec strings and the same Llama tokenizer ids. Every in-scope part and legal port (including SNOT brackets, jumpers, slopes, and tiles from `configs/architecture_scope.json`) is a token the mask can accept or reject. A training target and a generation step are the same kind of object.
* [x] **3.6 Mesh-aware forward mask:** Before a token is sampled, also mask actions whose realized mesh penetrates a piece already placed. Keep bounds, mating, and box-overlap checks. Leave HiGHS equilibrium to `scripts/validate.py`.
* [x] **3.7 Conditioning that carries massing:** Replace the few-bit voxel token with a coarse occupancy signature that still leaves every sequence under 1,500 tokens.
* [x] **3.8 Short LoRA run:** Hundreds of optimizer steps on the train split. Training loss falls. Validation loss on held-out buildings stays finite. Record the curve.
* **Gate 3a:** From a held-out building's bag box, sample attachment tokens through the mask, decode with `BFSTreeCodec.decode`, and pass `scripts/validate.py`. The parts in the file are the sampled tokens. One bag is enough (under 100 pieces). Zero floating pieces. [PASSED on `bricksafe_21003_Seattle_Space_Needle.ldr`: Seed 6 (two identical runs, 8 pieces, 7 part ids: 3004, 3005, 3031, 3069b, 3070b, 3794b, 63864) and Seed 3 (8 pieces, 5 part ids including SNOT 4070). Both pass scripts/validate.py.]

### After Gate 3a

* [ ] **3.4 PVPO Reinforcement Alignment:** Post-train with coupled rewards (physical equilibrium + geometric/semantic fidelity) to prevent "PhysHack" degeneration.
* [ ] **3.9 Multi-bag scale-up:** Chain foundation, core, facade, and roof samples into one connected model without switching back to coordinate prediction.
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
