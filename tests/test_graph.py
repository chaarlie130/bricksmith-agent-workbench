import unittest
import numpy as np
from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType


class TestGraph(unittest.TestCase):

    def test_assembly_graph_connections(self):
        graph = AssemblyGraph("test_tower")
        b1 = graph.add_part("3005", color_id=0, transform=np.eye(4))
        b2 = graph.add_part("3005", color_id=15, transform=np.eye(4))

        graph.connect(b1, "stud_0", b2, "tube_0", ConnectorType.STUD)

        self.assertEqual(graph.num_parts, 2)
        self.assertEqual(graph.num_connections, 1)
        self.assertTrue(graph.is_single_connected_component())

if __name__ == "__main__":
    unittest.main()
