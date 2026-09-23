"""Breadth-First Search (BFS) Spanning Tree Codec for BrickSmith."""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import numpy as np

from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType


@dataclass
class TreeNode:
    """A node in the BFS assembly spanning tree."""
    step_index: int
    brick_id: int
    part_id: str
    color_id: int
    parent_step_index: Optional[int]    # None for the root baseplate
    parent_port: Optional[str]
    self_port: Optional[str]
    conn_type: Optional[ConnectorType]
    transform: np.ndarray


class BFSTreeCodec:
    """Encodes an AssemblyGraph into a BFS spanning tree path sequence,
    and decodes path sequences back into an AssemblyGraph.
    """

    @staticmethod
    def encode(graph: AssemblyGraph, root_id: Optional[int] = None) -> List[TreeNode]:
        """Traverse the graph in Breadth-First Search order starting from root_id.
        If root_id is None, the brick with the lowest Y coordinate (lowest in gravity)
        or lowest instance ID is selected as root.
        """
        if not graph.parts:
            return []

        if root_id is None:
            # Pick lowest brick in physical space (maximum positive Y in LDraw is lowest)
            root_id = max(
                graph.parts.keys(),
                key=lambda bid: (graph.parts[bid].position[1], -bid)
            )

        visited = {root_id}
        queue = [(root_id, None, None, None, None)]  # (curr, parent_step, parent_port, self_port, conn_type)
        tree_nodes: List[TreeNode] = []
        brick_to_step: dict[int, int] = {}

        step = 0
        while queue:
            curr_id, parent_step, p_port, s_port, c_type = queue.pop(0)
            part = graph.parts[curr_id]
            brick_to_step[curr_id] = step

            node = TreeNode(
                step_index=step,
                brick_id=curr_id,
                part_id=part.part_id,
                color_id=part.color_id,
                parent_step_index=parent_step,
                parent_port=p_port,
                self_port=s_port,
                conn_type=c_type,
                transform=part.transform,
            )
            tree_nodes.append(node)

            # Discover neighbors
            curr_step = step
            for conn in graph.connections:
                neighbor_id = None
                neighbor_port = None
                my_port = None

                if conn.source_brick_id == curr_id and conn.target_brick_id not in visited:
                    neighbor_id = conn.target_brick_id
                    my_port = conn.source_port_id
                    neighbor_port = conn.target_port_id
                elif conn.target_brick_id == curr_id and conn.source_brick_id not in visited:
                    neighbor_id = conn.source_brick_id
                    my_port = conn.target_port_id
                    neighbor_port = conn.source_port_id

                if neighbor_id is not None and neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, curr_step, my_port, neighbor_port, conn.connection_type))

            step += 1

        return tree_nodes

    @staticmethod
    def serialize_path_text(tree_nodes: List[TreeNode]) -> str:
        """Serialize BFS tree nodes into a clean tokenized path-text format.
        Format per line:
        STEP: <step> | PART: <part_id> | COLOR: <color_id> | PARENT: <p_step> | PORTS: <p_port>-><s_port> | TYPE: <conn_type>
        """
        lines = []
        for node in tree_nodes:
            p_step = node.parent_step_index if node.parent_step_index is not None else -1
            p_port = node.parent_port or "ROOT"
            s_port = node.self_port or "ROOT"
            c_type = node.conn_type.value if node.conn_type else "ROOT"
            lines.append(
                f"STEP: {node.step_index:04d} | PART: {node.part_id} | COLOR: {node.color_id} | "
                f"PARENT: {p_step:04d} | PORTS: {p_port}->{s_port} | TYPE: {c_type}"
            )
        return "\n".join(lines)
