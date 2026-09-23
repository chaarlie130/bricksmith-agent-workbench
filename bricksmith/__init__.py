"""BrickSmith: State-of-the-Art Generative AI & Physics System for LEGO Architecture."""
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
    TreeNode,
    BFSTreeCodec,
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
    "TreeNode",
    "BFSTreeCodec",
    "parse_ldr",
    "save_ldr",
    "BillOfMaterials",
    "validate_ldraw",
    "generate_architecture_baseplate",
]
