import unittest
from pathlib import Path
from bricksmith.core.graph import AssemblyGraph
from bricksmith.io.ldraw import parse_ldr


class TestLDrawIO(unittest.TestCase):

    def test_parse_simple_ldr(self):
        sample_ldr = """
0 Test Model
1 15 0.0 -24.0 0.0 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0 3005.dat
1 71 20.0 -24.0 0.0 1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0 3004.dat
0 NOFILE
"""
        graph = parse_ldr(sample_ldr)
        self.assertEqual(graph.num_parts, 2)
        self.assertIn(1, graph.parts)
        self.assertIn(2, graph.parts)
        self.assertEqual(graph.parts[1].part_id, "3005")
        self.assertEqual(graph.parts[1].color_id, 15)
        self.assertEqual(graph.parts[2].part_id, "3004")
        self.assertEqual(graph.parts[2].color_id, 71)

    def test_roundtrip(self):
        graph = AssemblyGraph("roundtrip_test")
        graph.add_part("3005", color_id=0)
        graph.add_part("3004", color_id=15)
        
        exported_text = graph.to_ldraw()
        reparsed = parse_ldr(exported_text)
        
        self.assertEqual(reparsed.num_parts, 2)
        self.assertEqual(reparsed.parts[1].part_id, "3005")
        self.assertEqual(reparsed.parts[2].part_id, "3004")


if __name__ == "__main__":
    unittest.main()
