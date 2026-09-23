"""Unit tests for modular 'Numbered Bags' partitioner."""
import unittest
from pathlib import Path

from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType
from bricksmith.io.ldraw import parse_ldr
from bricksmith.decomposition.modularizer import partition_into_bags, BAG_NAMES

ROOT = Path(__file__).resolve().parents[1]


class TestModularizer(unittest.TestCase):

    def test_empty_graph_partition(self):
        graph = AssemblyGraph("empty")
        bags = partition_into_bags(graph)
        self.assertEqual(len(bags), 4)
        for name in BAG_NAMES:
            self.assertIn(name, bags)
            self.assertEqual(bags[name].num_parts, 0)

    def test_small_connected_graph_partition(self):
        graph = AssemblyGraph("tower")
        b1 = graph.add_part("3005", color_id=0)
        b2 = graph.add_part("3005", color_id=15)
        graph.connect(b1, "stud_0", b2, "tube_0", ConnectorType.STUD)

        bags = partition_into_bags(graph)
        # Invariant A: Conservation of matter
        total_parts = sum(b.num_parts for b in bags.values())
        self.assertEqual(total_parts, 2)
        all_ids = set()
        for b in bags.values():
            all_ids.update(b.parts.keys())
        self.assertEqual(all_ids, {b1, b2})

    def test_reference_model_invariants(self):
        sample_path = ROOT / "data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr"
        if not sample_path.exists():
            self.skipTest("Reference model not found")

        graph = parse_ldr(sample_path, infer_connections=True)
        bags = partition_into_bags(graph)

        # Invariant A: Conservation of Matter
        total_parts = sum(b.num_parts for b in bags.values())
        self.assertEqual(total_parts, graph.num_parts)
        all_ids = set()
        for b in bags.values():
            all_ids.update(b.parts.keys())
        self.assertEqual(all_ids, set(graph.parts.keys()))

        # Invariant B: Non-empty bags (model has 77 >= 50 parts)
        for name in BAG_NAMES:
            self.assertGreaterEqual(bags[name].num_parts, 1, f"Bag '{name}' should not be empty")

        # Invariant C: Context limit (< 300 pieces)
        for name in BAG_NAMES:
            self.assertLess(bags[name].num_parts, 300, f"Bag '{name}' exceeded context limit")

        # Invariant D: Interface connectivity between bag i and bag i+1
        for idx in range(len(BAG_NAMES) - 1):
            name_a, name_b = BAG_NAMES[idx], BAG_NAMES[idx + 1]
            parts_a = set(bags[name_a].parts.keys())
            parts_b = set(bags[name_b].parts.keys())
            edges = [
                c for c in graph.connections
                if (c.source_brick_id in parts_a and c.target_brick_id in parts_b)
                or (c.source_brick_id in parts_b and c.target_brick_id in parts_a)
            ]
            self.assertGreater(
                len(edges), 0,
                f"Expected physical interface edge between '{name_a}' and '{name_b}'"
            )


if __name__ == "__main__":
    unittest.main()
