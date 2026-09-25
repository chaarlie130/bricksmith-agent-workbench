#!/usr/bin/env python3
"""LoRA fine-tune a cached MLX instruct model on bag-level attachment text.

Dry-run loads the local 4-bit model, applies LoRA with gradient checkpointing,
and takes one optimizer step (batch size 1, gradient accumulation) so peak
memory can be checked on a 16 GB machine.
"""
import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import mlx.core as mx
import mlx.optimizers as optim

from mlx_lm.tuner.datasets import CacheDataset, TextDataset
from mlx_lm.tuner.trainer import TrainingArgs, TrainingCallback, train
from mlx_lm.tuner.utils import linear_to_lora_layers, print_trainable_parameters
from mlx_lm.utils import load

from bricksmith.training.codec import MODEL_REPO, cached_model_dir
from bricksmith.training.format_dataset import TRAIN_PATH, VAL_PATH

RUNS = ROOT / "data" / "training" / "runs"


class _LossCapture(TrainingCallback):
    def __init__(self, curve_path: Path, accum_steps: int):
        self.losses: list[float] = []
        self.val_losses: list[float] = []
        self.curve_path = curve_path
        self.accum_steps = accum_steps
        self.updates = 0
        curve_path.parent.mkdir(parents=True, exist_ok=True)

    def _write(self, row: dict) -> None:
        with self.curve_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row) + "\n")

    def on_train_loss_report(self, train_info: dict):
        loss = float(train_info["train_loss"])
        if not math.isfinite(loss):
            raise SystemExit(f"training loss became non-finite at step {train_info.get('iteration')}")
        self.losses.append(loss)
        step = int(train_info["iteration"])
        self.updates = step // self.accum_steps
        peak = float(train_info.get("peak_memory", 0.0))
        self._write({"step": step, "train_loss": loss, "val_loss": None, "peak_memory_gb": peak, "optimizer_updates": self.updates})
        if peak >= 16.0:
            raise SystemExit(f"peak memory {peak:.3f} GB reached 16 GB")

    def on_val_loss_report(self, val_info: dict):
        loss = float(val_info["val_loss"])
        self.val_losses.append(loss)
        self._write({"step": int(val_info.get("iteration", -1)), "train_loss": None, "val_loss": loss, "peak_memory_gb": None, "optimizer_updates": self.updates})


def _encoded_length(tokenizer, text: str) -> int:
    """Match mlx_lm TextDataset: encode, then append eos when it is missing."""
    ids = list(tokenizer.encode(text))
    eos = tokenizer.eos_token_id
    if eos is not None and (not ids or ids[-1] != eos):
        ids.append(eos)
    return len(ids)


def _read_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append({"text": json.loads(line)["text"]})
    return rows


def _training_text(tokenizer, max_seq_length: int) -> tuple[str, int]:
    """Longest shipped training line that fits in max_seq_length, else a short fallback."""
    import json

    chosen = None
    chosen_len = -1
    if TRAIN_PATH.exists():
        with TRAIN_PATH.open(encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                text = json.loads(line)["text"]
                length = _encoded_length(tokenizer, text)
                if length <= max_seq_length and length > chosen_len:
                    chosen = text
                    chosen_len = length
    if chosen is None:
        chosen = (
            "[INPUT: Bounding Box 16x16x12 + Aspect Ratio 1.00:1.00:0.75"
            " + Target Bag Name bag_1_foundation + Coarse Voxel Tokens 0]\n"
            "[TARGET: Discrete BFS Spanning Tree Path Tokens for that Bag]\n"
        )
        chosen_len = _encoded_length(tokenizer, chosen)
    return chosen, chosen_len


def main() -> None:
    parser = argparse.ArgumentParser(description="MLX LoRA fine-tune for BrickSmith attachment tokens.")
    parser.add_argument("--model", default=MODEL_REPO, help="HF repo id. Resolved to the local cache.")
    parser.add_argument("--dry-run", action="store_true", help="One optimizer step at max sequence length >= 1500.")
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--grad-accumulation-steps", type=int, default=4)
    parser.add_argument("--iters", type=int, default=None, help="Training iterations. Dry-run defaults to the accumulation length.")
    parser.add_argument("--num-layers", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--max-seq-length", type=int, default=2048, help="Token cap. Dry-run raises this to at least 1500.")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--adapter-path", type=Path, default=ROOT / "adapters" / "phase3a")
    parser.add_argument("--curve", type=Path, default=RUNS / "phase3a.jsonl")
    parser.add_argument("--resume", type=Path, default=None, help="Adapter weights to keep training.")
    parser.add_argument("--lora-rank", type=int, default=8)
    args = parser.parse_args()

    if args.model != MODEL_REPO:
        model_path = args.model
    else:
        model_path = str(cached_model_dir())

    iters = args.iters
    if args.dry_run:
        iters = args.grad_accumulation_steps if iters is None else iters
        if args.max_seq_length < 1500:
            args.max_seq_length = 1500
    elif iters is None:
        # 200 Adam updates when gradients accumulate every 4 microsteps.
        iters = 200 * args.grad_accumulation_steps

    print("fine_tune_type: LoRA")
    print("gradient checkpointing: enabled")
    print(f"batch size: {args.batch_size}")
    print(f"gradient accumulation steps: {args.grad_accumulation_steps}")
    print(f"max sequence length: {args.max_seq_length}")
    print(f"model: {MODEL_REPO}")
    print(f"model path: {model_path}")

    model, tokenizer = load(model_path)
    model.freeze()
    linear_to_lora_layers(
        model,
        args.num_layers,
        {"rank": args.lora_rank, "dropout": 0.0, "scale": 20.0},
        use_dora=False,
    )
    print_trainable_parameters(model)
    if args.resume is not None:
        print(f"resume adapter: {args.resume}")
        model.load_weights(str(args.resume), strict=False)

    mx.random.seed(args.seed)
    if args.dry_run:
        text, text_tokens = _training_text(tokenizer, args.max_seq_length)
        if text_tokens > args.max_seq_length:
            raise SystemExit(
                f"training text is {text_tokens} tokens, above max sequence length {args.max_seq_length}"
            )
        print(f"training tokens: {text_tokens}")
        train_rows = [{"text": text}]
        val_rows = None
    else:
        train_rows = _read_rows(TRAIN_PATH)
        val_rows = _read_rows(VAL_PATH)
        print(f"train examples: {len(train_rows)}")
        print(f"val examples: {len(val_rows)}")
    dataset = TextDataset(train_rows, tokenizer)
    val_dataset = TextDataset(val_rows, tokenizer) if val_rows else None
    if len(dataset) < args.batch_size:
        raise SystemExit("training set is smaller than the batch size")

    args.adapter_path.mkdir(parents=True, exist_ok=True)
    (args.adapter_path / "adapter_config.json").write_text(
        json.dumps(
            {
                "fine_tune_type": "lora",
                "num_layers": args.num_layers,
                "lora_parameters": {
                    "rank": args.lora_rank,
                    "scale": 20.0,
                    "dropout": 0.0,
                },
            }
        ),
        encoding="utf-8",
    )
    if args.curve.exists():
        args.curve.unlink()
    training_args = TrainingArgs(
        batch_size=args.batch_size,
        iters=iters,
        val_batches=1,
        steps_per_report=1,
        steps_per_eval=200 if val_dataset is not None else 10**9,
        steps_per_save=iters,
        max_seq_length=args.max_seq_length,
        adapter_file=str(args.adapter_path / "adapters.safetensors"),
        grad_checkpoint=True,
        grad_accumulation_steps=args.grad_accumulation_steps,
    )
    optimizer = optim.Adam(learning_rate=args.learning_rate)
    capture = _LossCapture(args.curve, args.grad_accumulation_steps)
    train(
        model=model,
        optimizer=optimizer,
        train_dataset=CacheDataset(dataset),
        val_dataset=CacheDataset(val_dataset) if val_dataset is not None else None,
        args=training_args,
        training_callback=capture,
    )
    peak_gb = mx.get_peak_memory() / 1e9
    print(f"peak memory {peak_gb:.3f} GB")
    if not capture.losses:
        print("training step missing", file=sys.stderr)
        sys.exit(1)
    loss = capture.losses[-1]
    print(f"training loss {loss:.6f}")
    updates = iters // args.grad_accumulation_steps
    print(f"optimizer updates: {updates}")
    if capture.val_losses:
        print(f"validation loss {capture.val_losses[-1]:.6f}")
    if not math.isfinite(loss):
        print("training loss is not finite", file=sys.stderr)
        sys.exit(1)
    if capture.val_losses and not math.isfinite(capture.val_losses[-1]):
        print("validation loss is not finite", file=sys.stderr)
        sys.exit(1)
    if not args.dry_run and updates < 200:
        print(f"only {capture.updates} optimizer updates", file=sys.stderr)
        sys.exit(1)
    if not args.dry_run and not (loss < capture.losses[0]):
        print(
            f"training loss did not fall ({capture.losses[0]:.6f} -> {loss:.6f})",
            file=sys.stderr,
        )
        sys.exit(1)
    if peak_gb >= 16.0:
        print("peak memory is not under 16 GB", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
