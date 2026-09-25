# BrickSmith

**State-of-the-Art Generative AI & Physical Assembly System for LEGO® Architecture.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Status: Phase 3a Closed Loop](https://img.shields.io/badge/status-Phase%203a%20Closed%20Loop-blue.svg)](docs/ROADMAP.md)

---

## The Mission

BrickSmith is an engineering-first research project designed to solve **Milestone #1 of Generative Brick Systems**:
Converting natural language architectural briefs into **authentic, physically buildable, aesthetically refined LEGO Architecture sets**—complete with certified LDraw 3D CAD files (`.ldr`), Pick-a-Brick / BrickLink Bills of Materials (BOM), and step-by-step assembly instructions.

Unlike naive approaches that either hallucinate floating 3D coordinates or rely on brittle, hand-coded procedural scripts that pack $1 \times 1$ bricks into blocky brutalist cubes, BrickSmith is built directly on the **academic research consensus** established by landmark papers:
* **LegoGPT** (CMU, ICCV 2025 Best Paper / Marr Prize)
* **BrickNet** (CVPR 2026, Peter Kulits & Cordelia Schmid)
* **BrickAnything** (2026, Structure-Aware BFS Tree Tokenization)
* **PVPO** (2026, Physics-Voxel Policy Optimization & Anti-PhysHack)
* **LTRON / InstructioNet** (UW / NVIDIA, ECCV 2024, Long-Horizon Assembly)

---

## The 4-Stage Architecture

BrickSmith decouples the prompt-to-brick challenge into four well-defined stages:

```
[ Natural Language Brief ]
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: Continuous 3D Volume Prior                         │
│ • Coarse volumetric bounding hull & semantic massing        │
│ • Captures setbacks, proportions, towers, and roof pitch    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: Modular Decomposition ("Numbered Bags")            │
│ • Partitions building into bounded, functional modules:     │
│   [Baseplate Plinth] -> [Core Frame] -> [SNOT Facades] -> [Roof]
│ • Guarantees context stays <300 pieces per generation unit  │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: Structure-Aware Attachment Tree Generation         │
│ • Port-to-Port Assembly Graph (stud, tube, clip, hinge, bar)│
│ • Breadth-First Search (BFS) spanning tree serialization    │
│ • Zero coordinate drift; strictly local attention spans     │
│ • SNOT brackets (99781, 4070), jumpers (3794b), tiles, slopes│
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4: Physical Verification & Manufacturing Export       │
│ • HiGHS Linear Programming static compressive equilibrium   │
│ • MeshLib continuous 0.25 LDU inset collision checking      │
│ • Output: .ldr CAD + Pick-a-Brick BOM CSV + LPub3D Steps    │
└─────────────────────────────────────────────────────────────┘
```

---

## Quickstart & CLI Tools

### 1. Validate an LDraw Model for Physics & Collisions
Run the static equilibrium and collision engine:
```bash
python scripts/validate.py data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr
```
Output:
```text
=== Validation Result: PASSED ===
File: bricksafe_21002_Empire_State_Building.ldr
Piece Count: 77
Checks:
  - mesh_collision_free: ✓
  - included_base: ✓
  - actual_connectivity: ✓
  - approximate_gravity_equilibrium: ✓
Elapsed: 0.5235s
```

### 2. Extract Pick-a-Brick / BrickLink Bill of Materials
Generate exact inventory counts for ordering:
```bash
python scripts/export_bom.py data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr --csv inventory.csv
```

### 3. Render Axonometric Presentation PNGs
Render high-fidelity orthographic previews:
```bash
python scripts/render.py data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr -o preview.png
```

### 4. Sample BFS Spanning Tree Path Sequence
Convert any CAD model into its discrete BFS attachment token sequence:
```bash
python scripts/sample_bfs_tree.py data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr -n 10
```

### 5. Generate Certified LEGO Architecture Plinths
Generate a clean, bordered black baseplate of any dimensions:
```bash
python scripts/generate_baseplate.py --width 16 --depth 24 -o baseplate.ldr
```

### 6. Phase 3 scaffolding
Bag-level training text, a one-step MLX LoRA dry-run, and a masked attachment sample. These scripts are the landed scaffolding in [`docs/ROADMAP.md`](docs/ROADMAP.md). Gate 3a (one codec shared by the corpus, the trainer, and the sampler) is the active mission, specified in [`docs/PHASE_3A_GOAL.md`](docs/PHASE_3A_GOAL.md).

```bash
python scripts/prepare_training_data.py
python scripts/train_mlx.py --dry-run --adapter-path adapters/phase3-dry-run
python scripts/generate_assembly.py --width 16 --depth 16 --height 12 --seed 3 -o assembly.ldr
python scripts/validate.py assembly.ldr
```

---

## Core Documentation

All contributors and autonomous agents **must** read these foundational documents before proposing or implementing changes:

* **[`docs/RESEARCH_FOUNDATIONS.md`](docs/RESEARCH_FOUNDATIONS.md)**: Literature review of LegoGPT, BrickNet, BrickAnything, PVPO, and empirical post-mortem of failed procedural approaches.
* **[`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)**: System design specification, port-socket formulation, and component interfaces.
* **[`docs/ROADMAP.md`](docs/ROADMAP.md)**: Phased milestone plan and quantitative acceptance gates.
* **[`docs/PHASE_3A_GOAL.md`](docs/PHASE_3A_GOAL.md)**: Active mission. Close the training and sampling loop before the 400-piece gate.
* **[`docs/AGENT_GUIDELINES.md`](docs/AGENT_GUIDELINES.md)**: Ground rules for autonomous agents (no silent fallbacks, strict validation, ledger tracking).

---

## Project Structure

```
bricksmith/
├── bricksmith/               # Core Python package
│   ├── core/                 # Parts, Connectors, AssemblyGraph, BFSTree
│   ├── geometry/             # 3D spatial priors, bounding hulls, baseplates
│   ├── decomposition/        # Modular "Numbered Bags" partitioner
│   ├── physics/              # HiGHS LP static equilibrium & collision checks
│   ├── io/                   # LDraw (.ldr), Pick-a-Brick BOM, XML exporters
│   └── rendering/            # Software axonometric projection rasterizer
├── configs/                  # Part scope catalogs (SNOT brackets, jumpers, tiles)
├── data/
│   ├── reference_sets/       # 200 curated gold-standard architecture models
│   ├── ldraw/                # Symlinked official LDraw library (24,500+ parts)
│   └── bricknet-data/        # Symlinked collision meshes (21,000+ parts)
├── docs/                     # Research foundations, architecture & roadmap
├── scripts/                  # CLI tools (validate, render, export_bom, sample_tree)
├── tests/                    # Automated unit and integration test suite
└── requirements.txt
```

---

## Running Tests

```bash
python -m unittest discover tests
```

---

## Disclaimer
LEGO® is a trademark of the LEGO Group, which does not sponsor, authorize, or endorse this research project.
