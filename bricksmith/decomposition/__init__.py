"""Modular decomposition package for BrickSmith."""
from bricksmith.decomposition.modularizer import (
    BAG_NAMES,
    CrossBagConnection,
    get_cross_bag_connections,
    partition_into_bags,
)

__all__ = ["partition_into_bags", "BAG_NAMES", "CrossBagConnection", "get_cross_bag_connections"]
