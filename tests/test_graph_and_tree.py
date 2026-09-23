import unittest
import numpy as np
from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType
from bricksmith.core.tree import BFSTreeCodec


class TestGraphAndTree(unittest.TestCase):

    def test_assembly_graph_connections(self):
        graph = AssemblyGraph("test_tower")
        b1 = graph.add_part("3005", color_id=0, transform=np.eye(4))
        b2 = graph.add_part("3005", color_id=15, transform=np.eye(4))
        
        graph.connect(b1, "stud_0", b2, "tube_0", ConnectorType.STUD)
        
        self.assertEqual(graph.num_parts, 2)
        self.assertEqual(graph.num_connections, 1)
        self.assertTrue(graph.is_single_connected_component())

    def test_bfs_tree_encoding(self):
        graph = AssemblyGraph("bfs_test")
        b1 = graph.add_part("3005", color_id=0)
        b2 = graph.add_part("3005", color_id=15)
        graph.connect(b1, "top_stud", b2, "bottom_tube", ConnectorType.STUD)

        tree = BFSTreeCodec.encode(graph, root_id=b1)
        self.assertEqual(len(tree), 2)
        self.assertEqual(tree[0].brick_id, b1)
        self.assertIsNone(tree[0].parent_step_index)
        self.assertEqual(tree[1].brick_id, b2)
        self.assertEqual(tree[1].parent_step_index, 0)

        path_text = BFSTreeCodec.serialize_path_text(tree)
        self.assertIn("PART: 3005", path_text)
        self.assertIn("PARENT: 0000", path_text)


if __name__ == "__main__":
    unittest.main()
