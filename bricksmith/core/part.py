"""Part definitions, catalog models, and metric constants for BrickSmith."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence
import numpy as np

# Standard LDraw Units (LDU)
LDU_PER_STUD: float = 20.0       # 1 stud width = 20 LDU = 8 mm
LDU_PER_PLATE: float = 8.0       # 1 plate height = 8 LDU = 3.2 mm
LDU_PER_BRICK: float = 24.0      # 1 brick height = 24 LDU = 9.6 mm

# Standard LEGO Architecture Color Codes (LDraw)
COLORS = {
    0: "Black",
    15: "White",
    71: "Light Bluish Gray",
    72: "Dark Bluish Gray",
    19: "Tan",
    70: "Reddish Brown",
    28: "Dark Tan",
    288: "Dark Green",
    378: "Sand Green",
    47: "Trans-Light Blue",
    297: "Pearl Gold",
    14: "Yellow",
    4: "Red",
    1: "Blue",
}


class PartCategory(str, Enum):
    BRICK = "brick"
    PLATE = "plate"
    JUMPER = "jumper"
    SNOT_BRACKET = "snot_bracket"
    SLOPE = "slope"
    TILE = "tile"
    CYLINDER = "cylinder"
    ARCH = "arch"
    SPECIAL = "special"


@dataclass(frozen=True)
class PartDefinition:
    """Canonical metadata for an LDraw part stem."""
    part_id: str
    name: str
    category: PartCategory
    # Dimensions in studs/plates
    stud_width: float
    plate_height: float
    stud_depth: float
    # Flags
    has_side_studs: bool = False
    is_hollow_stud: bool = False

    @property
    def ldu_size(self) -> tuple[float, float, float]:
        """Dimensions in LDU: (x_width, y_height, z_depth)."""
        return (
            self.stud_width * LDU_PER_STUD,
            self.plate_height * LDU_PER_PLATE,
            self.stud_depth * LDU_PER_STUD,
        )


@dataclass
class PartInstance:
    """An instantiated brick placed within a model assembly."""
    instance_id: int
    part_id: str
    color_id: int
    transform: np.ndarray = field(default_factory=lambda: np.eye(4, dtype=np.float64))
    metadata: dict = field(default_factory=dict)

    @property
    def position(self) -> np.ndarray:
        """World translation vector [x, y, z] in LDU."""
        return self.transform[:3, 3]

    @property
    def rotation(self) -> np.ndarray:
        """World rotation matrix (3x3)."""
        return self.transform[:3, :3]

    def to_ldraw_line(self) -> str:
        """Serialize to a standard LDraw Type 1 sub-file reference line.
        Format: 1 <colour> x y z a b c d e f g h i <file>
        """
        x, y, z = self.position
        r = self.rotation
        a, b, c = r[0, 0], r[0, 1], r[0, 2]
        d, e, f = r[1, 0], r[1, 1], r[1, 2]
        g, h, i = r[2, 0], r[2, 1], r[2, 2]
        # Clean formatting
        return (
            f"1 {self.color_id} "
            f"{x:.2f} {y:.2f} {z:.2f} "
            f"{a:.4f} {b:.4f} {c:.4f} "
            f"{d:.4f} {e:.4f} {f:.4f} "
            f"{g:.4f} {h:.4f} {i:.4f} "
            f"{self.part_id}.dat"
        )
