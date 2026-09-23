"""Connector port types, polarity rules, and kinematics for BrickSmith."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import numpy as np


class ConnectorType(str, Enum):
    STUD = "stud"              # Top stud (positive Y normal in local frame)
    TUBE = "tube"              # Bottom anti-stud / tube (negative Y normal)
    CLIP = "clip"              # Mechanical clip
    BAR = "bar"                # Rigid bar (fits into clip or hollow stud)
    AXLE = "axle"              # Technic axle
    HOLE = "hole"              # Technic pin/axle hole
    BALL = "ball"              # Ball joint
    SOCKET = "socket"          # Ball socket
    HINGE = "hinge"            # Hinge fork/tongue


class Polarity(str, Enum):
    MALE = "male"              # e.g., stud, pin, ball, bar
    FEMALE = "female"          # e.g., anti-stud tube, axle hole, socket, clip
    NEUTRAL = "neutral"        # symmetric or genderless mating


# Compatibility lookup: (Male_Type, Female_Type) -> allowed
COMPATIBILITY_MATRIX = {
    (ConnectorType.STUD, ConnectorType.TUBE): True,
    (ConnectorType.BAR, ConnectorType.CLIP): True,
    (ConnectorType.AXLE, ConnectorType.HOLE): True,
    (ConnectorType.BALL, ConnectorType.SOCKET): True,
    (ConnectorType.HINGE, ConnectorType.HINGE): True,
}


@dataclass(frozen=True)
class Port:
    """A connection interface on a brick."""
    port_id: str
    connector_type: ConnectorType
    polarity: Polarity
    local_position: np.ndarray      # [x, y, z] in part local LDU
    local_orientation: np.ndarray   # 3x3 local frame matrix

    def can_mate_with(self, other: Port) -> bool:
        """Check if two ports are geometrically and semantically compatible."""
        # Polarity check: must be opposite or neutral
        if self.polarity == other.polarity and self.polarity != Polarity.NEUTRAL:
            return False

        # Determine male and female
        if self.polarity == Polarity.MALE:
            m, f = self.connector_type, other.connector_type
        else:
            m, f = other.connector_type, self.connector_type

        return COMPATIBILITY_MATRIX.get((m, f), False)


@dataclass(frozen=True)
class PortConnection:
    """An active structural edge connecting two ports in the assembly graph."""
    source_brick_id: int
    source_port_id: str
    target_brick_id: int
    target_port_id: str
    connection_type: ConnectorType
