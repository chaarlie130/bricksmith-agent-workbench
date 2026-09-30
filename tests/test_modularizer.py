"""Tests for reusable construction-module decomposition."""
import unittest
from pathlib import Path

from bricksmith.core.connector import ConnectorType
from bricksmith.core.graph import AssemblyGraph
from bricksmith.decomposition.modularizer import BAG_NAMES, partition_into_bags
from bricksmith.io.ldraw import parse_ldr

ROOT = Path(__file__).resolve().parents[1]


class TestModularizer(unittest.TestCase):
    def test_empty_graph_partition(self):
        bags = partition_into_bags(AssemblyGraph("empty"))
        self.assertEqual(set(bags), set(BAG_NAMES))
        self.assertTrue(all(bag.num_parts == 0 for bag in bags.values()))

    def test_parts_are_conserved(self):
        graph = AssemblyGraph("tower")
        bottom = graph.add_part("3005", color_id=0)
        top = graph.add_part("3005", color_id=15)
        graph.connect(bottom, "stud_0", top, "tube_0", ConnectorType.STUD)
        bags = partition_into_bags(graph)
        self.assertEqual(sum(bag.num_parts for bag in bags.values()), 2)
        self.assertEqual({part for bag in bags.values() for part in bag.parts}, {bottom, top})

    def test_reference_model_parts_are_conserved(self):
        path = ROOT / "data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr"
        graph = parse_ldr(path, infer_connections=True)
        bags = partition_into_bags(graph)
        self.assertEqual(sum(bag.num_parts for bag in bags.values()), graph.num_parts)
        self.assertEqual({part for bag in bags.values() for part in bag.parts}, set(graph.parts))


if __name__ == "__main__":
    unittest.main()
