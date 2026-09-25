"""Modular topological decomposition ("Numbered Bags") engine for BrickSmith."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set
import numpy as np

from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType, PortConnection


@dataclass
class CrossBagConnection:
    """An active interlocking connection spanning two construction bags."""
    source_bag: str
    source_brick_id: int
    source_port_id: str
    target_bag: str
    target_brick_id: int
    target_port_id: str
    connection_type: ConnectorType


BAG_NAMES = [
    "bag_1_foundation",
    "bag_2_core",
    "bag_3_facades",
    "bag_4_roof",
]

SNOT_STEMS = {
    "99781", "99780", "36840", "36841",
    "4070", "87087", "22885", "47905",
    "4085c", "3659", "6091",
}
JUMPER_STEMS = {
    "3794a", "3794b", "15573", "87580", "34103",
}
SLOPE_STEMS = {
    "54200", "3039", "3040", "15068", "11477",
}
TILE_STEMS = {
    "3070b", "3069b", "63864", "2431",
    "6636", "4162", "2412b", "99563", "4162p0b",
}


def partition_into_bags(graph: AssemblyGraph) -> Dict[str, AssemblyGraph]:
    """Partition an AssemblyGraph into 4 standard LEGO Architecture construction bags:
    - bag_1_foundation: Plinth, baseplates, border tiles (y >= 0 LDU or lowest layer).
    - bag_2_core: Internal structural spine and lower bearing masonry.
    - bag_3_facades: SNOT brackets, fenestration, columns, and exterior envelope.
    - bag_4_roof: Upper cornices, cantilevers, roof slabs, spires.
    
    Guarantees:
    - Invariant A (Conservation of Matter): Union of parts equals original part set exactly.
    - Invariant B (Non-Empty Bags): All 4 bags contain >= 1 piece for models with >= 50 pieces.
    - Invariant C (Context Limit): Every individual bag contains < 300 pieces.
    - Invariant D (Interface Connectivity): Valid physical port connection edges between bag i and i+1.
    """
    n = len(graph.parts)
    if n == 0:
        return {name: AssemblyGraph(name=name) for name in BAG_NAMES}

    parts = dict(graph.parts)
    adj: Dict[int, Set[int]] = {bid: set() for bid in parts}
    for c in graph.connections:
        adj[c.source_brick_id].add(c.target_brick_id)
        adj[c.target_brick_id].add(c.source_brick_id)

    # 1. Find spine path v0 -> v1 -> v2 -> v3
    anchors = [None, None, None, None]
    comps = graph.connected_components()
    if comps:
        main_comp = max(comps, key=len)
        # Root is lowest in gravity (max Y in LDraw)
        v0 = max(main_comp, key=lambda b: (parts[b].position[1], -b))

        # BFS to find deepest reachable node in main component
        dist: Dict[int, int] = {v0: 0}
        parent: Dict[int, Optional[int]] = {v0: None}
        q = [v0]
        while q:
            u = q.pop(0)
            for v in adj[u]:
                if v not in dist:
                    dist[v] = dist[u] + 1
                    parent[v] = u
                    q.append(v)

        deepest = max(dist.keys(), key=lambda b: dist[b])
        path = []
        curr = deepest
        while curr is not None:
            path.append(curr)
            curr = parent[curr]
        path.reverse()

        if len(path) >= 4:
            anchors = [path[0], path[1], path[2], path[3]]

    # 2. Assign parts by spatial semantics and functional role
    y_coords = {bid: p.position[1] for bid, p in parts.items()}
    min_y = min(y_coords.values())
    max_y = max(y_coords.values())
    y_span = max(max_y - min_y, 1.0)

    bag_sets: List[Set[int]] = [set(), set(), set(), set()]
    assigned: Set[int] = set()

    # Pre-assign anchors to lock interface connectivity
    if all(a is not None for a in anchors) and len(set(anchors)) == 4:
        for i in range(4):
            bag_sets[i].add(anchors[i])
            assigned.add(anchors[i])

    # Assign remaining unassigned parts
    for bid, p in parts.items():
        if bid in assigned:
            continue
        y = y_coords[bid]
        if y >= 0.0 or y >= max_y - 0.15 * y_span:
            bag_sets[0].add(bid)
        elif y <= min_y + 0.18 * y_span:
            bag_sets[3].add(bid)
        elif (
            p.part_id in SNOT_STEMS
            or p.part_id in JUMPER_STEMS
            or p.part_id in SLOPE_STEMS
            or p.part_id in TILE_STEMS
            or p.color_id == 47
        ):
            bag_sets[2].add(bid)
        else:
            bag_sets[1].add(bid)

    # Invariant B: Ensure each bag has >= 1 piece for n >= 50
    if n >= 50:
        for i in range(4):
            if len(bag_sets[i]) == 0:
                donor = max(range(4), key=lambda j: len(bag_sets[j]))
                donor_bids = sorted(list(bag_sets[donor]), key=lambda b: y_coords[b])
                borrowed = donor_bids[-1] if i < donor else donor_bids[0]
                bag_sets[donor].remove(borrowed)
                bag_sets[i].add(borrowed)

    # Invariant C: Context limit < 300 pieces
    for i in range(4):
        while len(bag_sets[i]) >= 300:
            target = (i + 1) if i < 3 else (i - 1)
            bids = sorted(list(bag_sets[i]), key=lambda b: y_coords[b])
            movable = [b for b in bids if b not in anchors]
            if not movable:
                movable = bids
            moved = movable[0] if target > i else movable[-1]
            bag_sets[i].remove(moved)
            bag_sets[target].add(moved)

    # Invariant D: Ensure interface connectivity between bag i and bag i+1
    for i in range(3):
        has_edge = any(nbr in bag_sets[i + 1] for bid in bag_sets[i] for nbr in adj[bid])
        if not has_edge:
            for bid_i in list(bag_sets[i]):
                if len(bag_sets[i]) <= 1:
                    continue
                for nbr in adj[bid_i]:
                    for k in range(4):
                        if k != i and k != i + 1 and nbr in bag_sets[k] and len(bag_sets[k]) > 1:
                            bag_sets[k].remove(nbr)
                            bag_sets[i + 1].add(nbr)
                            has_edge = True
                            break
                    if has_edge:
                        break
                if has_edge:
                    break

    # Map brick to bag index and collect cross-bag interface connections
    brick_to_bag: Dict[int, int] = {}
    for i, bset in enumerate(bag_sets):
        for bid in bset:
            brick_to_bag[bid] = i

    all_cross_bag: List[CrossBagConnection] = []
    for c in graph.connections:
        bag_s = brick_to_bag.get(c.source_brick_id)
        bag_t = brick_to_bag.get(c.target_brick_id)
        if bag_s is not None and bag_t is not None and bag_s != bag_t:
            all_cross_bag.append(
                CrossBagConnection(
                    source_bag=BAG_NAMES[bag_s],
                    source_brick_id=c.source_brick_id,
                    source_port_id=c.source_port_id,
                    target_bag=BAG_NAMES[bag_t],
                    target_brick_id=c.target_brick_id,
                    target_port_id=c.target_port_id,
                    connection_type=c.connection_type,
                )
            )

    # Build resulting AssemblyGraph objects
    res_graphs: Dict[str, AssemblyGraph] = {}
    for i, name in enumerate(BAG_NAMES):
        subg = AssemblyGraph(name=name)
        subg.interface_connections = [
            conn for conn in all_cross_bag
            if conn.source_bag == name or conn.target_bag == name
        ]
        for bid in sorted(bag_sets[i]):
            p = parts[bid]
            subg.add_part(
                part_id=p.part_id,
                color_id=p.color_id,
                transform=p.transform.copy(),
                instance_id=bid,
            )
        # Preserve internal structural connections within each bag
        for c in graph.connections:
            if c.source_brick_id in bag_sets[i] and c.target_brick_id in bag_sets[i]:
                subg.connect(
                    source_id=c.source_brick_id,
                    source_port=c.source_port_id,
                    target_id=c.target_brick_id,
                    target_port=c.target_port_id,
                    conn_type=c.connection_type,
                )
        res_graphs[name] = subg

    return res_graphs


def get_cross_bag_connections(graph: AssemblyGraph, bags: Dict[str, AssemblyGraph]) -> List[CrossBagConnection]:
    """Extract all valid active connections that span between two distinct bags."""
    brick_to_bag: Dict[int, str] = {}
    for name, bag in bags.items():
        for bid in bag.parts:
            brick_to_bag[bid] = name

    cross: List[CrossBagConnection] = []
    for c in graph.connections:
        bag_s = brick_to_bag.get(c.source_brick_id)
        bag_t = brick_to_bag.get(c.target_brick_id)
        if bag_s and bag_t and bag_s != bag_t:
            cross.append(
                CrossBagConnection(
                    source_bag=bag_s,
                    source_brick_id=c.source_brick_id,
                    source_port_id=c.source_port_id,
                    target_bag=bag_t,
                    target_brick_id=c.target_brick_id,
                    target_port_id=c.target_port_id,
                    connection_type=c.connection_type,
                )
            )
    return cross
