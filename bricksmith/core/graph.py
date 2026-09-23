"""AssemblyGraph representation for discrete structural LEGO models."""
from __future__ import annotations

from typing import Dict, List, Optional, Set
import numpy as np

from bricksmith.core.part import PartInstance
from bricksmith.core.connector import PortConnection, ConnectorType


class AssemblyGraph:
    """Rigid structural assembly graph.
    Nodes = PartInstance (bricks with transforms and colors)
    Edges = PortConnection (active interlocking connections)
    """

    def __init__(self, name: str = "assembly"):
        self.name = name
        self.parts: Dict[int, PartInstance] = {}
        self.connections: List[PortConnection] = []
        self._next_id: int = 1
        # Adjacency map: brick_id -> set of connected neighbor brick_ids
        self._adjacency: Dict[int, Set[int]] = {}

    def add_part(
        self,
        part_id: str,
        color_id: int,
        transform: Optional[np.ndarray] = None,
        metadata: Optional[dict] = None,
        instance_id: Optional[int] = None,
    ) -> int:
        """Add a brick to the graph."""
        if instance_id is None:
            instance_id = self._next_id
            self._next_id += 1
        else:
            self._next_id = max(self._next_id, instance_id + 1)

        if transform is None:
            transform = np.eye(4, dtype=np.float64)

        part = PartInstance(
            instance_id=instance_id,
            part_id=part_id,
            color_id=color_id,
            transform=transform,
            metadata=metadata or {},
        )
        self.parts[instance_id] = part
        self._adjacency[instance_id] = set()
        return instance_id

    def connect(
        self,
        source_id: int,
        source_port: str,
        target_id: int,
        target_port: str,
        conn_type: ConnectorType = ConnectorType.STUD,
    ) -> None:
        """Add a validated connection edge between two parts."""
        if source_id not in self.parts or target_id not in self.parts:
            raise KeyError("Both source and target brick IDs must exist in the graph.")

        conn = PortConnection(
            source_brick_id=source_id,
            source_port_id=source_port,
            target_brick_id=target_id,
            target_port_id=target_port,
            connection_type=conn_type,
        )
        self.connections.append(conn)
        self._adjacency[source_id].add(target_id)
        self._adjacency[target_id].add(source_id)

    @property
    def num_parts(self) -> int:
        return len(self.parts)

    @property
    def num_connections(self) -> int:
        return len(self.connections)

    def connected_components(self) -> List[Set[int]]:
        """Return connected components as sets of brick IDs."""
        visited: Set[int] = set()
        components: List[Set[int]] = []

        for node in self.parts:
            if node not in visited:
                comp: Set[int] = set()
                queue = [node]
                visited.add(node)
                while queue:
                    curr = queue.pop(0)
                    comp.add(curr)
                    for neighbor in self._adjacency.get(curr, set()):
                        if neighbor not in visited:
                            visited.add(neighbor)
                            queue.append(neighbor)
                components.append(comp)
        return components

    def is_single_connected_component(self) -> bool:
        """Check if all bricks form a single unified rigid structure."""
        if not self.parts:
            return True
        comps = self.connected_components()
        return len(comps) == 1

    def to_ldraw(self, title: Optional[str] = None) -> str:
        """Export the assembly graph to standard LDraw (.ldr) text."""
        lines = [
            f"0 {title or self.name}",
            "0 Name: model.ldr",
            "0 Author: BrickSmith Generative Engine",
            "0 !LICENSE Licensed under CC0 / Public Domain",
            "",
        ]
        # Sort parts deterministically by instance ID
        for instance_id in sorted(self.parts.keys()):
            part = self.parts[instance_id]
            lines.append(part.to_ldraw_line())
        lines.append("0 NOFILE")
        return "\n".join(lines) + "\n"
