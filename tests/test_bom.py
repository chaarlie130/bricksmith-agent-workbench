import unittest
from bricksmith.core.graph import AssemblyGraph
from bricksmith.io.bom import BillOfMaterials


class TestBOM(unittest.TestCase):

    def test_bom_inventory(self):
        graph = AssemblyGraph("bom_test")
        graph.add_part("3005", color_id=0)
        graph.add_part("3005", color_id=0)
        graph.add_part("3004", color_id=15)
        
        bom = BillOfMaterials(graph)
        self.assertEqual(bom.total_pieces, 3)
        self.assertEqual(bom.unique_elements, 2)
        
        entries = bom.entries()
        self.assertEqual(entries[0].part_id, "3005")
        self.assertEqual(entries[0].quantity, 2)
        self.assertEqual(entries[1].part_id, "3004")
        self.assertEqual(entries[1].quantity, 1)


if __name__ == "__main__":
    unittest.main()
