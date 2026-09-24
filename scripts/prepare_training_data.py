#!/usr/bin/env python3
"""Format the reference BFS corpus into bag-level train and validation jsonl."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.training.codec import TokenizationError
from bricksmith.training.format_dataset import write_splits


def main() -> None:
    try:
        summary = write_splits()
    except TokenizationError as exc:
        print(f"tokenization error: {exc}", file=sys.stderr)
        print("tokenization errors: 1", file=sys.stderr)
        sys.exit(1)
    if summary.get("tokenization_errors", 1) != 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
