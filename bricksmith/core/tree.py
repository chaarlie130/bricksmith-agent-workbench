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

        visited = set()
        tree_nodes: List[TreeNode] = []
        brick_to_step: dict[int, int] = {}
        step = 0

        while len(visited) < len(graph.parts):
            if not visited and root_id is not None and root_id in graph.parts:
                curr_root = root_id
            else:
                # Pick lowest unvisited brick in physical space (max positive Y is ground level in LDraw)
                unvisited = [bid for bid in graph.parts if bid not in visited]
                curr_root = max(
                    unvisited,
                    key=lambda bid: (graph.parts[bid].position[1], -bid)
                )

            visited.add(curr_root)
            queue = [(curr_root, None, None, None, None)]  # (curr, parent_step, parent_port, self_port, conn_type)

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
                    transform=part.transform.copy(),
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
        STEP: <step> | PART: <part_id> | COLOR: <color_id> | PARENT: <p_step> | PORTS: <p_port>-><s_port> | TYPE: <conn_type> | POSE: <x y z a b c d e f g h i>
        """
        lines = []
        for node in tree_nodes:
            p_step = node.parent_step_index if node.parent_step_index is not None else -1
            p_port = node.parent_port or "ROOT"
            s_port = node.self_port or "ROOT"
            c_type = node.conn_type.value if node.conn_type else "ROOT"
            x, y, z = node.transform[:3, 3]
            r = node.transform[:3, :3]
            a, b, c = r[0, 0], r[0, 1], r[0, 2]
            d, e, f = r[1, 0], r[1, 1], r[1, 2]
            g, h, i = r[2, 0], r[2, 1], r[2, 2]
            lines.append(
                f"STEP: {node.step_index:04d} | ID: {node.brick_id:04d} | PART: {node.part_id} | COLOR: {node.color_id} | "
                f"PARENT: {p_step:04d} | PORTS: {p_port}->{s_port} | TYPE: {c_type} | "
                f"POSE: {x:.4f} {y:.4f} {z:.4f} {a:.6f} {b:.6f} {c:.6f} {d:.6f} {e:.6f} {f:.6f} {g:.6f} {h:.6f} {i:.6f}"
            )
        return "\n".join(lines)

    @staticmethod
    def deserialize_path_text(path_text: str) -> List[TreeNode]:
        """Deserialize tokenized path-text into a list of TreeNode objects."""
        tree_nodes: List[TreeNode] = []
        for line in path_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [seg.strip() for seg in line.split("|")]
            meta = {}
            for seg in parts:
                k, _, v = seg.partition(":")
                meta[k.strip()] = v.strip()

            step = int(meta["STEP"])
            brick_id = int(meta["ID"]) if "ID" in meta else step + 1
            part_id = meta["PART"]
            color_id = int(meta["COLOR"])
            p_step_raw = int(meta["PARENT"])
            parent_step = p_step_raw if p_step_raw >= 0 else None

            ports_str = meta.get("PORTS", "ROOT->ROOT")
            p_port_raw, _, s_port_raw = ports_str.partition("->")
            parent_port = None if p_port_raw == "ROOT" else p_port_raw
            self_port = None if s_port_raw == "ROOT" else s_port_raw

            c_type_raw = meta.get("TYPE", "ROOT")
            try:
                conn_type = None if c_type_raw == "ROOT" else ConnectorType(c_type_raw)
            except ValueError:
                conn_type = ConnectorType.STUD

            transform = np.eye(4, dtype=np.float64)
            if "POSE" in meta:
                vals = [float(x) for x in meta["POSE"].split()]
                if len(vals) == 12:
                    x, y, z, a, b, c, d, e, f, g, h, i = vals
                    transform = np.array([
                        [a, b, c, x],
                        [d, e, f, y],
                        [g, h, i, z],
                        [0.0, 0.0, 0.0, 1.0],
                    ], dtype=np.float64)

            node = TreeNode(
                step_index=step,
                brick_id=brick_id,
                part_id=part_id,
                color_id=color_id,
                parent_step_index=parent_step,
                parent_port=parent_port,
                self_port=self_port,
                conn_type=conn_type,
                transform=transform,
            )
            tree_nodes.append(node)
        return tree_nodes

    @staticmethod
    def decode(tree_nodes_or_text: Union[List[TreeNode], str], name: str = "reconstructed") -> AssemblyGraph:
        """Decode a BFS spanning tree path sequence or list of TreeNodes back into an AssemblyGraph."""
        if isinstance(tree_nodes_or_text, str):
            if "STEP:" in tree_nodes_or_text:
                tree_nodes = BFSTreeCodec.deserialize_path_text(tree_nodes_or_text)
            else:
                # Compact parent-relative attachment digits (no absolute pose).
                from bricksmith.training.codec import tree_nodes_from_target_text

                tree_nodes = tree_nodes_from_target_text(tree_nodes_or_text)
        else:
            tree_nodes = tree_nodes_or_text

        graph = AssemblyGraph(name=name)
        step_to_inst: dict[int, int] = {}

        for node in tree_nodes:
            inst_id = graph.add_part(
                part_id=node.part_id,
                color_id=node.color_id,
                transform=node.transform.copy(),
                instance_id=node.brick_id,
            )
            step_to_inst[node.step_index] = inst_id

            if node.parent_step_index is not None and node.parent_step_index in step_to_inst:
                parent_inst = step_to_inst[node.parent_step_index]
                p_port = node.parent_port or "port_0"
                s_port = node.self_port or "port_0"
                c_type = node.conn_type or ConnectorType.STUD
                graph.connect(
                    source_id=parent_inst,
                    source_port=p_port,
                    target_id=inst_id,
                    target_port=s_port,
                    conn_type=c_type,
                )

        return graph
