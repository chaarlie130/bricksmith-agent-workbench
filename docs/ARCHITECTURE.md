# BrickSmith: System Architecture & Technical Specification

> **Mission:** Build a state-of-the-art generative AI system that converts natural language architectural prompts into authentic, buildable, aesthetic LEGO Architecture sets—complete with 3D CAD files (`.ldr`), Pick-a-Brick Bills of Materials (BOM), and step-by-step assembly instructions.

---

## 1. System Overview

BrickSmith rejects both monolithic coordinate prediction (which drifts) and hand-coded procedural compilers (which create simplistic Minecraft blocks). Instead, it implements a **4-stage decoupled pipeline**:

```
[ Natural Language Brief ]
           │
           ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: Continuous 3D Volume Prior                         │
│ • Input: Text brief (e.g. "Prairie house with low-pitched   │
│   cantilevered hip roofs and continuous window bands")       │
│ • Output: Coarse 3D volumetric massing & semantic bounding  │
│   envelope (SDF / Voxel Grid / Point Cloud)                 │
└──────────────────────────────┬──────────────────────────────┘
                               │ Envelope & Massing Hulls
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: Modular Topological Decomposition ("Numbered Bags")│
│ • Partitions the 3D volume into hierarchical sub-modules:   │
│   Bag 1: Baseplate & Foundation Plinth                      │
│   Bag 2: Structural Spine & Internal Frame                  │
│   Bag 3: SNOT Facades, Columns & Micro-Fenestration         │
│   Bag 4: Cornices, Overhangs & Roof Slabs                   │
│ • Bounded context length per module (<300 pieces each)      │
└──────────────────────────────┬──────────────────────────────┘
                               │ Sub-Module Boundaries & Interfaces
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: Structure-Aware Attachment Tree Generation         │
│ • Parameterizes assembly as an ATTACHMENT GRAPH:            │
│   Nodes = Parts from expanded LDraw catalog (SNOT, jumpers) │
│   Edges = Port-to-port connections (stud, tube, clip, hinge)│
│ • Order: Breadth-First Search (BFS) spanning tree           │
│ • Tokenization: Predicts discrete graph actions relative to │
│   parent ports, keeping attention dependencies strictly     │
│   local and preventing floating/misaligned parts.           │
└──────────────────────────────┬──────────────────────────────┘
                               │ Candidate Assembly Graph
                               ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 4: Physical Verification & Manufacturing Export       │
│ • HiGHS Linear Programming for static gravity equilibrium   │
│ • Continuous MeshLib collision checking (0.25 LDU inset)    │
│ • Monotonic assembly clearance (insertion trajectory check) │
│ • Multi-format export:                                      │
│   1. Standard LDraw CAD (.ldr / .mpd)                       │
│   2. Pick-a-Brick / BrickLink CSV Bill of Materials         │
│   3. LPub3D / Studio 2.0 step-by-step instruction metadata  │
│   4. Multi-view axonometric preview renders                 │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. Core Data Structures & Mathematical Formalism

### 2.1 The LEGO Metric System (LDraw Standard)
All spatial calculations in BrickSmith are performed in native **LDraw Units (LDU)**:
* $1 \text{ stud width} = 20 \text{ LDU} = 8.0 \text{ mm}$
* $1 \text{ plate height} = 8 \text{ LDU} = 3.2 \text{ mm}$
* $1 \text{ brick height} = 24 \text{ LDU} = 9.6 \text{ mm}$ ($3 \times \text{plate height}$)
* Coordinate convention: $Y$ axis points **downwards** (towards gravity in standard LDraw).

### 2.2 The Port-Socket Connector Formulation
A brick $B_i$ is not an arbitrary point cloud; it is a rigid body characterized by an intrinsic coordinate frame and a set of discrete **Connection Ports**:
$$\mathcal{P}(B_i) = \{ p_{i, 1}, p_{i, 2}, \dots, p_{i, k} \}$$

Each port $p_{i, j}$ is defined by a tuple:
$$p = (\mathbf{t}_{\text{local}}, \; \mathbf{R}_{\text{local}}, \; \tau, \; \pi)$$
Where:
* $\mathbf{t}_{\text{local}} \in \mathbb{R}^3$: Offset from the part origin in LDU.
* $\mathbf{R}_{\text{local}} \in SO(3)$: Local orientation frame.
* $\tau \in \{\text{stud}, \; \text{tube/socket}, \; \text{clip}, \; \text{bar}, \; \text{axle}, \; \text{pin}, \; \text{hinge}, \; \text{ball}\}$: Connector type.
* $\pi \in \{\text{male}, \; \text{female}, \; \text{neutral}\}$: Polarity.

#### Attachment Rule:
Two bricks $B_u$ and $B_v$ can form an edge $e = (u, v)$ if and only if:
1. Port types $\tau(p_{u, j})$ and $\tau(p_{v, k})$ are compatible.
2. Polarities $\pi(p_{u, j})$ and $\pi(p_{v, k})$ are complementary (e.g. male stud $\leftrightarrow$ female tube).
3. The rigid transformation $\mathbf{T}_{u \to v}$ that aligns port frames results in collision-free geometry for both parts.

### 2.3 The Assembly Graph $G = (V, E)$
* **Vertices $V$:** Instances of bricks with $(\text{Part\_ID}, \text{Color\_ID}, \mathbf{T}_{\text{world}})$.
* **Edges $E$:** Validated port-to-port connections between bricks.

### 2.4 BFS Tree & Path Text Serialization (The BrickNet / BrickAnything Codec)
Rather than predicting absolute global coordinates, generation traverses the assembly graph $G$ starting from the ground baseplate ($v_0$) using a **Breadth-First Search (BFS) spanning tree** $T \subseteq G$.

Each generation step predicts:
$$\text{Token} = \big[\text{Part\_ID}, \; \text{Color\_ID}, \; \text{Parent\_Index}, \; \text{Parent\_Port}, \; \text{Self\_Port}, \; \text{Rotation\_Offset}\big]$$

**Why BFS Tree Tokenization is mathematically superior:**
1. **Zero Coordinate Drift:** Piece poses are computed by traversing the kinematic tree from the root. Parts are guaranteed to snap to allowable grid and SNOT offsets.
2. **Local Attention Spans:** Parent-child connections are temporally close in the transformer context, completely eliminating the long-horizon decay observed in linear Z-scans.
3. **No Floating Parts:** Every generated part is by definition connected to an existing sub-structure.

---

## 3. Subsystem Breakdown

### 3.1 `bricksmith.core`
Defines the foundational domain models:
* `Part`: Encapsulates LDraw part IDs, categories (brick, plate, tile, bracket, slope), physical dimensions, and bounding boxes.
* `Connector`: Defines port geometries, stud/tube pitches, and mating rules.
* `AssemblyGraph`: Manages graph construction, cycle detection, kinematic forward passes, and component extraction.
* `BFSTree`: Implements the serialization and deserialization between graph topologies and autoregressive token sequences.

### 3.2 `bricksmith.physics`
The non-negotiable physical verification gate:
* **Static Equilibrium Solver:** Formulates compressive gravity load transfer as a **Linear Program (LP)** using SciPy / HiGHS. Tests whether contact patches under each brick can support gravity moments without tensile failure.
* **Collision Engine:** Utilizes exact 0.25 LDU inset surface meshes (`scratch/bricknet-data/inset/`) and MeshLib/trimesh kernels to guarantee zero solid-solid volume interpenetration.
* **Assembly Clearance:** Verifies that a continuous vertical insertion trajectory exists for each piece in sequence, preventing impossible enclosed assemblies.

### 3.3 `bricksmith.decomposition`
Handles long-horizon piece count scaling:
* Implements the **"Numbered Bags"** architecture.
* Automatically clusters dense sub-graphs into independent construction stages with well-defined interface ports.

### 3.4 `bricksmith.io`
The factory output pipeline:
* `LDrawWriter`: Emits certified `.ldr` and multi-part `.mpd` files formatted with official color codes and title headers.
* `BOMExporter`: Computes exact part and color inventories, mapping them to official LEGO Design IDs and BrickLink catalog IDs for automated purchasing.
* `InstructionBuilder`: Emits step-by-step sub-model build sequences compatible with LPub3D and Studio 2.0.

### 3.5 `bricksmith.rendering`
Fast visual QA:
* Pure-Python / software axonometric projection renderer.
* Generates front, side, top, and 3D oblique views with studio lighting, drop shadows, and stud ring details.

---

## 4. Key Architectural Invariants

1. **No Silent Fallbacks:** An invalid candidate must fail fast, log its exact violation, and register in the experiment ledger. Never substitute a solid block or silently alter user constraints.
2. **No Procedural "1x1 Brick Extrusion":** Generation must be driven by combinatorial port-graph search or neural prediction, not hardcoded Python loops that manually pack $1 \times 1$ bricks.
3. **Full Micro-Scale Catalog Access:** SNOT brackets (`99781`, `99780`, `4070`), jumper plates (`3794b`), cheese slopes (`54200`), and smooth tiles (`3069b`, `2412b`) must be first-class citizens in the generator vocabulary.
4. **One Attachment Language:** The training corpus, the LoRA trainer, and the guided sampler consume the same parent-relative codec and the same tokenizer ids. A generation step predicts that codec string. The world pose is the parent-port attachment, computed after the token is chosen.
5. **Mask Before Sampling:** Bounds, port polarity, bounding-box overlap, and mesh penetration are applied to next-token logits before the draw. `scripts/validate.py` remains the HiGHS equilibrium gate. A hand-picked plate-and-brick catalog is not a substitute for that mask.
