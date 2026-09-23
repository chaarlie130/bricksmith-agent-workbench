"""Unit tests for 3D bounding box and occupancy voxel grid."""
import unittest
from pathlib import Path
import numpy as np

from bricksmith.core.graph import AssemblyGraph
from bricksmith.io.ldraw import parse_ldr
from bricksmith.geometry.bounds import calculate_bounds, BoundingBox3D
from bricksmith.geometry.envelope import generate_occupancy_grid, calculate_grid_centroid

ROOT = Path(__file__).resolve().parents[1]


class TestBoundsAndEnvelope(unittest.TestCase):

    def test_empty_graph_bounds(self):
        graph = AssemblyGraph("empty")
        bounds = calculate_bounds(graph)
        self.assertEqual(bounds.total_mass, 0.0)
        self.assertEqual(bounds.width_ldu, 0.0)
        self.assertEqual(bounds.total_volume_studs, 0.0)

        grid = generate_occupancy_grid(graph)
        self.assertEqual(grid.size, 0)
        self.assertEqual(np.sum(grid), 0)

    def test_single_brick_bounds(self):
        graph = AssemblyGraph("single")
        # 1x1 brick at origin
        graph.add_part("3005", color_id=0, transform=np.eye(4))
        bounds = calculate_bounds(graph)
        self.assertGreater(bounds.total_mass, 0.0)
        self.assertGreater(bounds.width_ldu, 0.0)
        self.assertGreater(bounds.height_ldu, 0.0)
        self.assertGreater(bounds.depth_ldu, 0.0)

        grid = generate_occupancy_grid(graph, resolution_studs=1.0)
        self.assertGreater(int(np.sum(grid)), 0)

    def test_reference_model_bounds_and_occupancy(self):
        sample_path = ROOT / "data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr"
        if not sample_path.exists():
            self.skipTest("Reference model not found")

        graph = parse_ldr(sample_path, infer_connections=True)
        bounds = calculate_bounds(graph)

        # 10x8 studs base, 24 studs tall
        self.assertAlmostEqual(bounds.width_studs, 10.0, delta=0.1)
        self.assertAlmostEqual(bounds.depth_studs, 8.0, delta=0.1)
        self.assertAlmostEqual(bounds.height_studs, 24.0, delta=0.1)

        grid = generate_occupancy_grid(graph, resolution_studs=1.0)
        self.assertGreater(int(np.sum(grid)), 0)

        # Centroid test: within 1.0 stud of physical COM
        diff = np.abs(grid.centroid_studs - bounds.center_of_mass_studs)
        self.assertLess(float(np.max(diff)), 1.0)


if __name__ == "__main__":
    unittest.main()
