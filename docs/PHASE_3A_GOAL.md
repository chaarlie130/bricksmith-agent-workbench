# Goal: Close the Phase 3 loop (Gate 3a)

You are the lead architect on `~/github/bricksmith`. Phases 0–2 are complete. Phase 3 scaffolding is on disk and is not the goal. Read `docs/ROADMAP.md` (Phase 3), `docs/ARCHITECTURE.md` invariants 4 and 5, and `docs/AGENT_GUIDELINES.md` before editing.

## Why this goal exists

The bag dataset, the MLX dry-run, and the sampler do not yet form one generator.

- Training targets are parent-relative codec strings over the reference vocabulary (`bricksmith/training/codec.py`, `data/training/train.jsonl`).
- Sampling still draws from a small plate-and-brick joint pool. SNOT brackets, jumpers, slopes, and tiles are in the training strings and absent from the legal set.
- The forward mask covers bounds, mating polarity, and bounding-box overlap. It does not cover mesh penetration. `scripts/validate.py` does.
- `scripts/train_mlx.py --dry-run` has taken one optimizer step. The loss has not been shown to fall.
- Conditioning voxels are only a few bits, so the model barely sees massing.

A longer fine-tune on that split will not show up in `scripts/generate_assembly.py`. Fix the loop, then train.

## Mission

Make corpus, trainer, and sampler one attachment language. Train long enough to see learning. Sample a held-out bag through that language and pass physical validation.

## Work

### 1. One codec

- Generation steps emit the same parent-relative strings `serialize_tree` writes, tokenized by the same Llama 3.2 tokenizer the trainer uses (`mlx-community/Llama-3.2-3B-Instruct-4bit`, already cached). Do not bind actions to arbitrary vocabulary ids.
- The legal vocabulary is the in-scope catalog in `configs/architecture_scope.json`: standard bricks and plates, jumper plates, SNOT brackets and headlight bricks, slopes, tiles, columns and arches. A part that appears in a training target must be maskable at sample time.
- Poses are computed from parent-port attachment after the token is chosen. Do not predict absolute `(x, y, z)`. Do not pack 1×1 bricks procedurally. Do not copy a reference model's coordinates in place of sampled tokens.
- Rebuild `data/training/train.jsonl` and `data/training/val.jsonl` if the codec or the conditioning text changes. Keep the split by source model. Keep every sequence under 1,500 tokenizer tokens, with margin (aim for a max under 1,400). Zero tokenization errors. `BFSTreeCodec.decode` still restores part ids and parent-port links.

### 2. Mesh-aware mask

Before each sampled token, set illegal next-token ids to `-inf` when the action would:

- place geometry outside the module box,
- mate incompatible ports (stud-to-stud, tube-to-tube, or any pair `Port.can_mate_with` rejects),
- overlap a placed brick's bounding box,
- penetrate a placed brick's collision mesh (`bricknet` / the same meshes `scripts/validate.py` uses).

HiGHS equilibrium stays outside the inner loop. `scripts/validate.py` is the equilibrium gate after the sample is decoded. Do not walk candidates until `validate_ldraw` returns true and call that the model.

### 3. Conditioning that carries massing

The input block stays:

`[INPUT: Bounding Box WxDxH + Aspect Ratio + Target Bag Name + Coarse Voxel Tokens]`

`[TARGET: Discrete BFS Spanning Tree Path Tokens for that Bag]`

Replace the few-bit voxel token with a coarse occupancy signature derived from `generate_occupancy_grid`. It must be a real function of that bag's massing, stable across runs, and small enough that the longest bag stays under the token cap.

### 4. Short LoRA run

Use `scripts/train_mlx.py` on the cached Llama 3.2 3B 4-bit model. Do not download Qwen 2.5 7B.

- LoRA, gradient checkpointing, batch size 1, gradient accumulation.
- At least 200 optimizer updates on the train split. More if loss is still dropping and memory stays under 16 GB.
- Sequence length must cover the training strings without truncation warnings.
- Print peak memory. Abort if it reaches 16 GB.
- Save the loss curve (step, train loss, and periodic val loss on held-out buildings) under `data/training/runs/`. Adapters stay under `adapters/` (gitignored).
- Training loss at the end of the run is lower than the loss at step 1. Validation loss stays finite.

### 5. Gate 3a sample

`scripts/generate_assembly.py` takes a coarse 3D bound from a **held-out** reference building (a model id present only in `val.jsonl`).

- Load the adapter from the run in section 4.
- Sample attachment tokens through the mask. Log the model path, the adapter path, each sampled codec token-id sequence, and `BFSTreeCodec.decode`.
- Write an `.ldr` whose parts are those tokens.
- Two launches with the same seed exit 0, pass `scripts/validate.py`, and produce the same piece count.
- Piece count is at least 8 and comes from more than one part id. The file is a connected assembly on a real base plate, not a single brick duplicated by a hand-written loop.
- Same-seed piece counts match. A second seed may differ. Both seeds that you ship must pass validation.

## Invariants

- No absolute coordinate tokens in the target.
- No silent substitution of a failed piece with a generic brick.
- No weakening of `scripts/validate.py` thresholds.
- No 1×1 packing script. The model predicts graph actions; the mask only deletes illegal ones.
- Fail loudly if the mask empties or validation fails. Do not fall back to a stored reference pose.

## Verification

Run these yourself and keep the logs:

1. `python -m unittest discover tests` using the project virtualenv that already imports `bricknet`. New tests must call the shipped codec, mask, and sampler. Assert a SNOT or jumper or slope token is representable, an illegal mating and a mesh penetration are masked to `-inf`, and `BFSTreeCodec.decode` of a sampled string restores part ids and parent ports. Pose matches the parent-port attachment.
2. `python scripts/prepare_training_data.py` exits 0, reports zero tokenization errors, and both jsonl files are a non-empty disjoint split by model id. Max token count is under 1,400.
3. The training run exits 0, logs at least 200 optimizer steps, a falling train loss, a finite val loss, and peak memory under 16 GB.
4. Two same-seed generations plus `scripts/validate.py` on each `.ldr`: both `Validation Result: PASSED`, equal piece counts, count ≥ 8.

## Out of scope

- PVPO (roadmap 3.4) and the 400-piece Gate 3.
- Phase 4 prompt-to-box, instruction booklets, BrickLink XML.
- Downloading a model that is not already cached.
- Rewriting Phase 0–2 modules except where a call site must read them.
