"""Unit tests for modular 'Numbered Bags' partitioner."""
import unittest
from pathlib import Path

from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.connector import ConnectorType
from bricksmith.io.ldraw import parse_ldr
from bricksmith.decomposition.modularizer import (
    BAG_NAMES,
    CrossBagConnection,
    get_cross_bag_connections,
    partition_into_bags,
)

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

    def test_explicit_bag_interface_connections(self):
        sample_path = ROOT / "data/reference_sets/ldr/bricksafe_21002_Empire_State_Building.ldr"
        if not sample_path.exists():
            self.skipTest("Reference model not found")

        graph = parse_ldr(sample_path, infer_connections=True)
        bags = partition_into_bags(graph)
        cross_conns = get_cross_bag_connections(graph, bags)
        self.assertGreater(len(cross_conns), 0)
        # Check that interface connections are preserved on the subgraphs
        for name in BAG_NAMES:
            self.assertTrue(hasattr(bags[name], "interface_connections"))
        # Foundation or core should have interface connections to other bags
        has_iface = any(len(b.interface_connections) > 0 for b in bags.values())
        self.assertTrue(has_iface)

    def test_two_bag_assembly_reconstruction_from_tokens_alone(self):
        """Task 2 verification: Prove reconstruction of a 2-bag assembly purely from saved tokens."""
        import numpy as np
        from bricksmith.core.tree import (
            BFSTreeCodec,
            TreeNode,
            get_available_interface_ports,
            merge_assemblies,
        )
        from bricksmith.physics.validator import frame, validate_ldraw, world_properties
        from bricknet.data import load_catalog
        from bricksmith.generation.sampler import yaw_matrix
        from bricksmith.training.codec import build_codebook, parse_attachment_digits, serialize_tree

        catalog = load_catalog()

        # Part 1: Ground baseplate 3031 at Y=8
        id_3031 = catalog.stem_to_id["3031"]
        _, _, lo, hi = world_properties(id_3031, np.eye(4))
        ground_t = np.eye(4)
        ground_t[1, 3] = 8.0 - float(hi[1])

        # Part 2: 3004 on plate stud 25
        id_3004 = catalog.stem_to_id["3004"]
        pf_plate = frame(id_3031, 25)
        cf_brick1 = frame(id_3004, 1)
        brick1_t = ground_t @ pf_plate @ yaw_matrix(0) @ np.linalg.inv(cf_brick1)

        # Part 3: 3004 stacked on brick 1 (port 4 -> port 1)
        pf_brick1 = frame(id_3004, 4)
        cf_brick2 = frame(id_3004, 1)
        brick2_t = brick1_t @ pf_brick1 @ yaw_matrix(0) @ np.linalg.inv(cf_brick2)

        # Part 4: 3004 stacked on brick 2 (port 4 -> port 1)
        pf_brick2 = frame(id_3004, 4)
        cf_brick3 = frame(id_3004, 1)
        brick3_t = brick2_t @ pf_brick2 @ yaw_matrix(0) @ np.linalg.inv(cf_brick3)

        gt_transforms = [ground_t, brick1_t, brick2_t, brick3_t]

        # Build Bag 1 (Foundation)
        g1 = AssemblyGraph("bag_1_foundation")
        g1.add_part("3031", 0, ground_t, instance_id=1)
        g1.add_part("3004", 15, brick1_t, instance_id=2)
        g1.connect(1, "port_25", 2, "port_1", ConnectorType.STUD)

        codebook = build_codebook(["3031", "3004"], [0, 4, 14, 15])
        tree_1 = BFSTreeCodec.encode(g1)
        tokens_1 = serialize_tree(tree_1, codebook)

        # Decode Bag 1 from tokens alone
        parsed_1 = parse_attachment_digits(tokens_1, codebook)
        dec_g1 = BFSTreeCodec.decode(parsed_1, anchor_transform=ground_t)

        # Identify upward interface stud on Bag 1 matching Part 2 stud 4
        iface_ports = get_available_interface_ports(dec_g1)
        target_iface_idx = next(
            p.index for p in iface_ports if p.brick_id == 2 and p.port_id == "port_4"
        )

        # Build Bag 2 (Core) referencing Bag 1 interface stud
        tree_2 = [
            TreeNode(
                step_index=0,
                brick_id=1,
                part_id="3004",
                color_id=4,
                parent_step_index=None,
                parent_port=f"iface_{target_iface_idx}",
                self_port="port_1",
                conn_type=ConnectorType.STUD,
                transform=np.eye(4),
                rotation_quarters=0,
            ),
            TreeNode(
                step_index=1,
                brick_id=2,
                part_id="3004",
                color_id=14,
                parent_step_index=0,
                parent_port="port_4",
                self_port="port_1",
                conn_type=ConnectorType.STUD,
                transform=np.eye(4),
                rotation_quarters=0,
            ),
        ]
        tokens_2 = serialize_tree(tree_2, codebook)

        # Decode Bag 2 from tokens alone using dec_g1 interface ports
        parsed_2 = parse_attachment_digits(tokens_2, codebook)
        dec_g2 = BFSTreeCodec.decode(parsed_2, interface_assembly=dec_g1)
        self.assertEqual(len(dec_g2.interface_connections), 1)

        # Merge assemblies across interface contract
        full_graph = merge_assemblies(dec_g1, dec_g2)
        self.assertEqual(full_graph.num_parts, 4)
        self.assertEqual(full_graph.num_connections, 3)

        # Verify transforms match ground truth CAD exactly
        for inst_id, gt_t in zip([1, 2, 3, 4], gt_transforms):
            rec_t = full_graph.parts[inst_id].transform
            diff = float(np.max(np.abs(rec_t - gt_t)))
            self.assertLess(diff, 1e-6, f"Part {inst_id} transform difference {diff} exceeds tolerance")

        # Verify physical validity with validator
        report = validate_ldraw(full_graph.to_ldraw())
        self.assertTrue(report["passed"])
        self.assertTrue(report["checks"]["mesh_collision_free"])
        self.assertTrue(report["checks"]["included_base"])
        self.assertTrue(report["checks"]["actual_connectivity"])
        self.assertTrue(report["checks"]["approximate_gravity_equilibrium"])
        self.assertEqual(report["errors"], [])


if __name__ == "__main__":
    unittest.main()
