# BrickSmith: Research Foundations & Literature Grounding

> **Purpose:** This document preserves the theoretical and empirical grounding for BrickSmith. It serves as the immutable "ground truth" for all contributors and autonomous agents, ensuring that development remains anchored in cutting-edge computer vision, robotic assembly, and generative AI research rather than repeating known dead-ends.

---

## 1. Executive Summary: The "Text-to-Brick" Challenge

Generative AI has achieved remarkable results in continuous visual media (text-to-image diffusion, NeRFs, 3D Gaussian Splats). However, **Text-to-LEGO** is an entirely different class of computational problem:

1. **Discrete & Combinatorial:** Surfaces cannot be interpolated; space is quantized into precise metric units (LDraw Units: 1 stud = 20 LDU, 1 plate height = 8 LDU, 1 brick height = 24 LDU).
2. **Strict Physical Validity:** Unlike continuous 3D meshes which can be hollow, self-intersecting, or floating, LEGO assemblies must satisfy:
   - **Static Compressive Equilibrium:** Supporting centers of mass under gravity.
   - **Tensile Clutch Power & Shear Resistance:** Staggered brick bonding vs. unstable vertical seams.
   - **Rigid Body Non-Penetration:** Exact micro-mesh collision clearance.
   - **Monotonic Assembly Reachability:** Every brick must have a collision-free insertion trajectory during human or robotic construction.
3. **Micro-Scale Semantic Representation:** LEGO Architecture sets (e.g., *Fallingwater*, *Villa Savoye*, *Brandenburg Gate*) rely on **NPU** (*Nice Part Usage*): brackets for **SNOT** (*Studs Not On Top*), jumper plates for half-stud offsets, and grille tiles for micro-fenestration.

---

## 2. Landmark Research Papers

### 2.1 LegoGPT: "Generating Physically Stable and Buildable LEGO® Designs from Text"
* **Authors:** Ava Pun, Kangle Deng, Ruixuan Liu, Deva Ramanan, Changliu Liu, Jun-Yan Zhu (Carnegie Mellon University)
* **Venue:** ICCV 2025 (**Best Paper / Marr Prize**) | [arXiv:2505.05469](https://arxiv.org/abs/2505.05469)
* **Core Architecture:** Autoregressive fine-tuning of `LLaMA-3.2-1B-Instruct` treating LEGO brick placement as a next-token prediction task.
* **Dataset:** Introduced **StableText2Lego** (47,000+ stable structures derived from 28,000 unique 3D objects with GPT-4o captions).
* **Key Innovations:**
  - Introduced **physics-aware rollback** and rejection sampling during inference to prune tokens that create floating or unstable structures.
  - Demonstrated end-to-end export to LDraw CAD and physical robotic arm assembly.
* **Identified Limitations:**
  - Tokenized placement as simple Cartesian tuples: `{h}x{w} (x, y, z)`.
  - Restricted to 1-unit-tall cuboid bricks on a fixed $20 \times 20 \times 20$ grid across ~21 simple categories (chairs, tables, cars).
  - Exponential branching factor ($O(b^d)$) during rollback when scaling to high piece counts.

### 2.2 BrickNet: "Graph-Backed Generative Brick Assembly"
* **Authors:** Peter Kulits, Cordelia Schmid (Inria, Google Research)
* **Venue:** CVPR 2026 | [arXiv:2604.22984](https://arxiv.org/abs/2604.22984) | [kulits.github.io/BrickNet](https://kulits.github.io/BrickNet)
* **Core Architecture:** Autoregressive language modeling over a **graph-based program representation** parameterized by connectivity semantics rather than continuous or voxel 3D coordinates.
* **Dataset:** 100,000+ human-designed LDraw brick objects/scenes and 320,000 structures.
* **Key Innovations:**
  - **Port-to-Port Connectivity Semantics:** Solves mold variety by formalizing connections across 5 discrete joint types:
    $$\text{Joint Types} \in \{\text{stud}, \; \text{hinge}, \; \text{axle}, \; \text{ball}, \; \text{fixed/clip}\}$$
  - Predicts connections: $\text{Attach}(\text{Part}, \text{Port}_A, \text{Parent}, \text{Port}_B)$.
  - Prevents coordinate drift and eliminates floating pieces by mathematical construction.
  - Scales to thousands of distinct LDraw part geometries with 21,000+ exact collision meshes.

### 2.3 BrickAnything: "Geometry-Conditioned Buildable Brick Generation with Structure-Aware Tokenization"
* **Venue:** 2026 | [arXiv:2605.26182](https://arxiv.org/abs/2605.26182)
* **Core Architecture:** Geometry-conditioned autoregressive generation converting 3D point-cloud hulls into physically stable brick structures.
* **Key Innovations:**
  - **Structure-Aware Tree Tokenization:** Constructs a vertical attachment DAG where edges represent planar overlap and vertical adjacency, then traverses it via a **Breadth-First Search (BFS) spanning tree**.
  - **Localizing Dependencies:** BFS ordering ensures parent-child references stay local in the transformer's attention span, avoiding the catastrophic forgetting of linear bottom-to-top Z-scans.
  - Employs validity-constrained decoding and adaptive rollback to ensure 100% buildability.

### 2.4 PVPO: "Sample-Efficient Post-Training for LEGO Spatial-Physics Reasoning"
* **Venue:** 2026 | [arXiv:2606.07602](https://arxiv.org/abs/2606.07602)
* **Key Innovations:**
  - Discovered and defined **"PhysHack"**: A fundamental reinforcement learning failure mode where models trained solely on physical stability rewards learn to build solid, thick pyramids or slabs of $2 \times 4$ bricks because they are indestructible, completely discarding the semantic prompt.
  - Proposed **PVPO (Physics-Voxel Policy Optimization)**: A dual-reward RL framework coupling physical validity rewards with voxel-space geometric alignment rewards.
  - Demonstrated that value-guided data selection using only 5% of training samples outperforms full-scale imitation learning.

### 2.5 LTRON & InstructioNet: "Break-and-Make" & Instruction Learning
* **Authors:** Aaron Walsman, Muru Zhang, Adam Fishman, Ali Farhadi, Dieter Fox (UW / NVIDIA)
* **Venue:** ECCV 2024 | [arXiv:2410.01111](https://arxiv.org/abs/2410.01111) | [GitHub: aaronwalsman/ltron](https://github.com/aaronwalsman/ltron)
* **Core Innovations:**
  - Developed **LTRON**, an interactive 3D simulator for LEGO assembly and disassembly using LDraw and LDCAD data.
  - Formulated the **"Break-and-Make"** challenge: learning structure by taking models apart and rebuilding them.
  - **InstructioNet:** Demonstrates that agents need **explicit visual step-by-step memory** (like LEGO instruction books) to solve long-horizon assemblies beyond 100+ steps.

---

## 3. Empirical Post-Mortem of "BrickBlender" (What NOT to Do)

In previous experiments under the `brickblender` repository, an attempt was made to decouple the problem using an "AlphaGeometry-style" split:
$$\text{User Brief} \xrightarrow{\text{LLM}} \text{15-Param Compact JSON} \xrightarrow{\text{Procedural CAD Compiler}} \text{1x1 Brick Packing} \xrightarrow{\text{HiGHS LP}} \text{Validator}$$

### Why this approach failed:
1. **The "Minecraft Bunker" Trap:**
   The LLM only acted as a form-filler picking macro dimensions (`width_studs`, `bay_count`, `height_courses`). The actual LEGO assembly was delegated to a deterministic Python compiler (`architecture_plan_v3.py`). Because no human can write procedural rules for every architectural nuance, the compiler defaulted to packing standard $1 \times 1$ bricks in repetitive horizontal layers, producing blocky brutalist cubes.
2. **Extreme Information Bottleneck:**
   Compressing architectural intent into 15 scalar fields discarded 99% of design entropy before brick selection even began.
3. **The "Upright-Only" Self-Imposed Prison:**
   Restricting parts to 37 standard upright bricks and plates made it mathematically impossible to express LEGO Architecture design idioms (SNOT brackets, jumper offsets, sideways tiles, cheese slopes).

---

## 4. The Golden Consensus: What BrickSmith Must Implement

| Dimension | Failed Naive Approach | Consensus Research Solution (BrickSmith) |
| :--- | :--- | :--- |
| **Part Placement** | Cartesian $(x,y,z)$ coordinates or procedural loops | **Port-to-Port Attachment Graph** (BrickNet) |
| **Token Ordering** | Linear Z-raster scan or raw string dumping | **BFS Spanning Tree on Attachment DAG** (BrickAnything) |
| **Design Process** | End-to-end prompt $\to$ single brick tokens | **Coarse 3D Shape Prior $\to$ Modular Brick Infilling** |
| **Scalability** | Single monolithic 3,000-token sequence | **Modular Sub-Assemblies ("Numbered Bags")** |
| **Physics** | Ignored or unconstrained rollback | **HiGHS LP Static Equilibrium + MeshLib Collision Gate** |
| **Mold Variety** | 37 standard upright bricks | **Rich Catalog with SNOT brackets, jumpers, slopes, tiles** |
| **Output Deliverable** | Raw CAD file only | **CAD (.ldr) + Pick-a-Brick BOM + Step-by-Step Instructions** |
