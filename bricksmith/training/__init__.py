"""Bag-level BFS attachment dataset formatting for Phase 3."""

from bricksmith.training.codec import (
    Codebook,
    count_tokens,
    load_codebook,
    set_active_codebook,
    tree_nodes_from_target_text,
)
from bricksmith.training.format_dataset import (
    build_codebook_from_corpus,
    example_text,
    iter_bag_examples,
)

__all__ = [
    "Codebook",
    "build_codebook_from_corpus",
    "count_tokens",
    "example_text",
    "iter_bag_examples",
    "load_codebook",
    "set_active_codebook",
    "tree_nodes_from_target_text",
]
