"""Bill of Materials (BOM) extraction and export for Pick-a-Brick & BrickLink."""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import List, Union

from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.part import COLORS


@dataclass
class BOMEntry:
    part_id: str
    color_id: int
    color_name: str
    quantity: int


class BillOfMaterials:
    """Computes exact part and color inventories from an AssemblyGraph."""

    def __init__(self, graph: AssemblyGraph):
        self.graph = graph
        self.counts = Counter(
            (part.part_id, part.color_id)
            for part in graph.parts.values()
        )

    @property
    def total_pieces(self) -> int:
        return sum(self.counts.values())

    @property
    def unique_elements(self) -> int:
        return len(self.counts)

    def entries(self) -> List[BOMEntry]:
        """Return sorted inventory entries."""
        items = []
        for (part_id, color_id), count in sorted(self.counts.items(), key=lambda x: (-x[1], x[0][0])):
            items.append(BOMEntry(
                part_id=part_id,
                color_id=color_id,
                color_name=COLORS.get(color_id, f"Color {color_id}"),
                quantity=count,
            ))
        return items

    def to_csv(self, output_path: Union[str, Path]) -> None:
        """Export to standard Pick-a-Brick / BrickLink compatible CSV."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Part ID", "Color ID", "Color Name", "Quantity"])
            for entry in self.entries():
                writer.writerow([entry.part_id, entry.color_id, entry.color_name, entry.quantity])

    def to_bricklink_xml(self, output_path: Union[str, Path]) -> None:
        """Export to BrickLink Mass-Upload XML format for 1-click Want List import."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = ["<INVENTORY>"]
        for entry in self.entries():
            lines.append("  <ITEM>")
            lines.append("    <ITEMTYPE>P</ITEMTYPE>")
            lines.append(f"    <ITEMID>{entry.part_id}</ITEMID>")
            lines.append(f"    <COLOR>{entry.color_id}</COLOR>")
            lines.append(f"    <MINQTY>{entry.quantity}</MINQTY>")
            lines.append("  </ITEM>")
        lines.append("</INVENTORY>")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
