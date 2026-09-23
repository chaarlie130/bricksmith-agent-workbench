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

    def test_bfs_tree_decode_and_reconstruction(self):
        graph = AssemblyGraph("recon_test")
        t1 = np.eye(4)
        t1[:3, 3] = [0.0, -24.0, 0.0]
        t2 = np.eye(4)
        t2[:3, 3] = [20.0, -24.0, 0.0]

        b1 = graph.add_part("3005", color_id=0, transform=t1)
        b2 = graph.add_part("3004", color_id=71, transform=t2)
        graph.connect(b1, "stud_0", b2, "tube_0", ConnectorType.STUD)

        tree = BFSTreeCodec.encode(graph)
        path_text = BFSTreeCodec.serialize_path_text(tree)
        recon = BFSTreeCodec.decode(path_text)

        self.assertEqual(len(recon.parts), 2)
        self.assertEqual(recon.parts[b1].color_id, 0)
        self.assertEqual(recon.parts[b2].color_id, 71)
        self.assertEqual(recon.parts[b1].part_id, "3005")
        self.assertEqual(recon.parts[b2].part_id, "3004")

        # Zero coordinate drift
        pos1_diff = np.max(np.abs(recon.parts[b1].position - t1[:3, 3]))
        pos2_diff = np.max(np.abs(recon.parts[b2].position - t2[:3, 3]))
        self.assertLess(pos1_diff, 0.001)
        self.assertLess(pos2_diff, 0.001)

        # Connection restored
        self.assertEqual(recon.num_connections, 1)


if __name__ == "__main__":
    unittest.main()

