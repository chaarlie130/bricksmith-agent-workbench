import unittest
from bricksmith.geometry.baseplate import generate_architecture_baseplate


class TestBaseplate(unittest.TestCase):

    def test_generate_baseplate(self):
        graph = generate_architecture_baseplate(width_studs=16, depth_studs=24)
        self.assertGreater(graph.num_parts, 0)
        
        # Check all parts are black (color_id == 0)
        for part in graph.parts.values():
            self.assertEqual(part.color_id, 0)


if __name__ == "__main__":
    unittest.main()
