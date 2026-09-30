"""BrickSmith construction tools for a frontier-model design workbench."""
__version__ = "0.1.0"

from bricksmith.core import (
    PartDefinition,
    PartInstance,
    PartCategory,
    COLORS,
    ConnectorType,
    Port,
    PortConnection,
    AssemblyGraph,
)
from bricksmith.io import parse_ldr, save_ldr, BillOfMaterials
from bricksmith.physics import validate_ldraw
from bricksmith.geometry import generate_architecture_baseplate

__all__ = [
    "PartDefinition",
    "PartInstance",
    "PartCategory",
    "COLORS",
    "ConnectorType",
    "Port",
    "PortConnection",
    "AssemblyGraph",
    "parse_ldr",
    "save_ldr",
    "BillOfMaterials",
    "validate_ldraw",
    "generate_architecture_baseplate",
]
