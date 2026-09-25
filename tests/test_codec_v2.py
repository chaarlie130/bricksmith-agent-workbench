"""Comprehensive verification tests for versioned codec, fail-loudly kinematics,
interface rotations, pipeline cross-bag tokens, and physical support filter.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from bricknet.data import load_catalog
from bricksmith.core.connector import ConnectorType, Polarity, Port
from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.tree import (
    BFSTreeCodec,
    InterfacePortSpec,
    TreeNode,
    get_available_interface_ports,
    merge_assemblies,
)
from bricksmith.decomposition.modularizer import partition_into_bags
from bricksmith.generation.assemble import _is_supported
from bricksmith.generation.sampler import PlacedPart, PortSpec, yaw_matrix
from bricksmith.physics.validator import frame, validate_ldraw, world_properties
from bricksmith.training.codec import (
    TokenizationError,
    build_codebook,
    parse_attachment_digits,
    port_code_v1,
    port_from_v2_entry,
    port_name_v1,
    port_to_v2_entry,
    serialize_tree,
    tree_nodes_from_target_text,
)
from bricksmith.training.format_dataset import CORPUS_PATH, example_text, graph_from_record


class TestCodecV2AndKinematics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = load_catalog()
        cls.codebook = build_codebook(["3031", "3001", "3004", "3005", "3010"], [0, 4, 14, 15, 72])

    def test_versioned_codec_namespaces_and_headers(self):
        """Review Finding 1: V2 has distinct physical and interface namespaces, starts with 00002."""
        # V2 port entries
        self.assertEqual(port_to_v2_entry(None), (0, 0))
        self.assertEqual(port_to_v2_entry("stud_0"), (1, 0))
        self.assertEqual(port_to_v2_entry("tube_0"), (2, 0))
        self.assertEqual(port_to_v2_entry("port_528"), (3, 528))
        self.assertEqual(port_to_v2_entry("port_643"), (3, 643))
        self.assertEqual(port_to_v2_entry("iface_0"), (4, 0))
        self.assertEqual(port_to_v2_entry("iface_528"), (4, 528))

        self.assertIsNone(port_from_v2_entry(0, 0))
        self.assertEqual(port_from_v2_entry(1, 0), "stud_0")
        self.assertEqual(port_from_v2_entry(2, 0), "tube_0")
        self.assertEqual(port_from_v2_entry(3, 528), "port_528")
        self.assertEqual(port_from_v2_entry(4, 528), "iface_528")

        # Serialized tree with physical and interface ports
        nodes = [
            TreeNode(
                step_index=0,
                brick_id=1,
                part_id="3001",
                color_id=0,
                parent_step_index=None,
                parent_port="iface_528",
                self_port="port_643",
                conn_type=ConnectorType.STUD,
                transform=np.eye(4),
                rotation_quarters=1,
            )
        ]
        v2_tokens = serialize_tree(nodes, self.codebook, version=2)
        self.assertTrue(v2_tokens.startswith("00002"))

        parsed = parse_attachment_digits(v2_tokens, self.codebook)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0].parent_port, "iface_528")
        self.assertEqual(parsed[0].self_port, "port_643")
        self.assertEqual(parsed[0].rotation_quarters, 1)

    def test_legacy_v1_compatibility(self):
        """Review Finding 1: V1 legacy decoder preserves physical ports 0..996 without reinterpretation."""
        self.assertEqual(port_code_v1("port_528"), 531)
        self.assertEqual(port_name_v1(531), "port_528")
        self.assertEqual(port_code_v1("port_643"), 646)
        self.assertEqual(port_name_v1(646), "port_643")

        node = TreeNode(
            step_index=0,
            brick_id=1,
            part_id="3001",
            color_id=0,
            parent_step_index=None,
            parent_port="port_528",
            self_port="port_643",
            conn_type=ConnectorType.STUD,
            transform=np.eye(4),
        )
        v1_tokens = serialize_tree([node], self.codebook, version=1)
        self.assertFalse(v1_tokens.startswith("00002"))
        parsed_v1 = parse_attachment_digits(v1_tokens, self.codebook)
        self.assertEqual(parsed_v1[0].parent_port, "port_528")
        self.assertEqual(parsed_v1[0].self_port, "port_643")

    def test_interface_rotations_preserved_across_all_quarters(self):
        """Review Finding 2: Root and interface node rotations 0, 1, 2, 3 must survive serialization."""
        for quarters in (0, 1, 2, 3):
            node = TreeNode(
                step_index=0,
                brick_id=1,
                part_id="3004",
                color_id=15,
                parent_step_index=None,
                parent_port="iface_2",
                self_port="port_1",
                conn_type=ConnectorType.STUD,
                transform=np.eye(4),
                rotation_quarters=quarters,
            )
            tokens = serialize_tree([node], self.codebook, version=2)
            parsed = parse_attachment_digits(tokens, self.codebook)
            self.assertEqual(
                parsed[0].rotation_quarters,
                quarters,
                f"Failed to preserve rotation_quarters={quarters}",
            )

    def test_kinematics_fail_loudly(self):
        """Review Finding 3: Remove except: pass. Fail loudly on bad ports, missing interfaces, bad stems."""
        root = TreeNode(0, 1, "3004", 0, None, None, None, None, np.eye(4))

        # 1. Invalid physical port index
        bad_port = TreeNode(1, 2, "3004", 0, 0, "port_99999", "port_1", ConnectorType.STUD, np.eye(4))
        with self.assertRaises((IndexError, ValueError)):
            BFSTreeCodec.decode([root, bad_port])

        # 2. Missing interface assembly/ports
        iface_node = TreeNode(0, 1, "3004", 0, None, "iface_0", "port_1", ConnectorType.STUD, np.eye(4))
        with self.assertRaises(ValueError):
            BFSTreeCodec.decode([iface_node])

        # 3. Out-of-range interface port index
        with self.assertRaises(IndexError):
            BFSTreeCodec.decode([iface_node], interface_ports=[])

        # 4. Unknown part stem
        bad_stem = TreeNode(1, 2, "unknown_part_xyz", 0, 0, "port_4", "port_1", ConnectorType.STUD, np.eye(4))
        with self.assertRaises(KeyError):
            BFSTreeCodec.decode([root, bad_stem])

    def test_rigorous_support_filter(self):
        """Review Finding 5: Rejects side-adjacent floating overhangs, verifies running bonds."""
        def make_placed(pid, bmin, bmax, transform=None):
            t = np.eye(4) if transform is None else transform
            return PlacedPart(
                part_id=pid,
                color_id=0,
                transform=t,
                bounds_min=np.array(bmin, dtype=np.float64),
                bounds_max=np.array(bmax, dtype=np.float64),
                ports=[],
            )

        parent = make_placed("3004", [-20, 0, -10], [20, 24, 10])

        # A: Floating side-adjacent overhang (Reviewer reproduction bug)
        side_floating = make_placed("3004", [20, 0, -10], [60, 24, 10])
        self.assertFalse(
            _is_supported(side_floating, [parent], parent_index=0),
            "Side-adjacent overhang with zero lower support must be rejected",
        )

        # B: Running bond across two supporting bricks
        b1 = make_placed("3004", [-20, 0, -10], [20, 24, 10])
        b2 = make_placed("3004", [20, 0, -10], [60, 24, 10])
        child_running = make_placed("3010", [-20, -24, -10], [60, 0, 10])
        self.assertTrue(_is_supported(child_running, [b1, b2], parent_index=0))

        # C: Cantilever overhanging into empty space
        cantilever = make_placed("3010", [-40, -24, -10], [40, 0, 10])
        col = make_placed("3004", [-40, 0, -10], [-20, 24, 10])
        self.assertFalse(_is_supported(cantilever, [col], parent_index=0))

    def test_real_partition_tokens_nonzero_rotation_merged_cad(self):
        """Review Finding 4: Multi-bag partitioned reference building with nonzero rotations and multiple roots.
        Decodes from tokens alone, merges into full CAD, and validates physics.
        """
        # Build Bag 1 (Ground foundation plate 3031 + supporting brick 3004)
        g1 = AssemblyGraph("bag_1_foundation")
        id_3031 = self.catalog.stem_to_id["3031"]
        _, _, lo, hi = world_properties(id_3031, np.eye(4))
        ground_t = np.eye(4)
        ground_t[1, 3] = 8.0 - float(hi[1])

        id_3004 = self.catalog.stem_to_id["3004"]
        pf_plate = frame(id_3031, 25)
        cf_brick1 = frame(id_3004, 1)
        brick1_t = ground_t @ pf_plate @ yaw_matrix(0) @ np.linalg.inv(cf_brick1)

        g1.add_part("3031", 0, ground_t, instance_id=1)
        g1.add_part("3004", 15, brick1_t, instance_id=2)
        g1.connect(1, "port_25", 2, "port_1", ConnectorType.STUD)

        # Get available interface ports on Bag 1
        ifaces_1 = get_available_interface_ports(g1)
        # Select stud 4 on brick 2
        spec_brick1_stud4 = next(p for p in ifaces_1 if p.brick_id == 2 and p.port_id == "port_4")

        # Select stud 26 on baseplate 1
        spec_plate_stud26 = next(p for p in ifaces_1 if p.brick_id == 1 and p.port_id == "port_26")

        # Build Bag 2 with MULTIPLE ROOTS and NONZERO ROTATIONS (yaw = 90 deg, quarters = 1)
        # Root 1 on brick 2 stud 4 with 90 degree yaw
        id_3005 = self.catalog.stem_to_id["3005"]
        cf_3005 = frame(id_3005, 0)
        rot_deg_1 = 90
        brick3_t = spec_brick1_stud4.world_transform @ yaw_matrix(rot_deg_1) @ np.linalg.inv(cf_3005)

        # Root 2 on baseplate stud 26 with 180 degree yaw (quarters = 2)
        rot_deg_2 = 180
        brick4_t = spec_plate_stud26.world_transform @ yaw_matrix(rot_deg_2) @ np.linalg.inv(cf_3005)

        g2 = AssemblyGraph("bag_2_structure")
        g2.add_part("3005", 4, brick3_t, instance_id=3)
        g2.add_part("3005", 14, brick4_t, instance_id=4)
        from bricksmith.core.connector import PortConnection
        g2.interface_connections = [
            PortConnection(source_brick_id=2, source_port_id="port_4", target_brick_id=3, target_port_id="port_0", connection_type=ConnectorType.STUD),
            PortConnection(source_brick_id=1, source_port_id="port_26", target_brick_id=4, target_port_id="port_0", connection_type=ConnectorType.STUD),
        ]

        # 1. Encode Bag 2 conditioning on Bag 1
        tree_2 = BFSTreeCodec.encode(g2, interface_assembly=g1)
        self.assertEqual(len(tree_2), 2)
        # Verify both roots encoded interface ports and exact nonzero rotation quarters
        r1 = next(n for n in tree_2 if n.brick_id == 3)
        self.assertEqual(r1.parent_port, f"iface_{spec_brick1_stud4.index}")
        self.assertEqual(r1.rotation_quarters, 1)

        r2 = next(n for n in tree_2 if n.brick_id == 4)
        self.assertEqual(r2.parent_port, f"iface_{spec_plate_stud26.index}")
        self.assertEqual(r2.rotation_quarters, 2)

        # 2. Serialize to V2 pure digit tokens
        tokens_2 = serialize_tree(tree_2, self.codebook, version=2)
        self.assertTrue(tokens_2.startswith("00002"))

        # 3. Parse digits back
        parsed_2 = parse_attachment_digits(tokens_2, self.codebook)
        self.assertEqual(parsed_2[0].rotation_quarters, tree_2[0].rotation_quarters)
        self.assertEqual(parsed_2[1].rotation_quarters, tree_2[1].rotation_quarters)

        # 4. Decode Bag 2 from tokens alone using Bag 1 interface assembly
        dec_g2 = BFSTreeCodec.decode(parsed_2, interface_assembly=g1)
        self.assertEqual(len(dec_g2.interface_connections), 2)

        # 5. Verify reconstructed poses match ground truth exactly
        dec_parts = list(dec_g2.parts.values())
        self.assertEqual(len(dec_parts), 2)
        self.assertLess(float(np.max(np.abs(dec_parts[0].transform - brick3_t))), 1e-6)
        self.assertLess(float(np.max(np.abs(dec_parts[1].transform - brick4_t))), 1e-6)

        # 6. Merge across interface connections and validate full CAD physics
        merged = merge_assemblies(g1, dec_g2)
        self.assertEqual(merged.num_parts, 4)
        self.assertEqual(merged.num_connections, 3)

        # Validate physics with HiGHS LP equilibrium and collision detection
        res = validate_ldraw(merged.to_ldraw())
        self.assertTrue(res["passed"], f"Validation failed: {res.get('errors')}")
        self.assertTrue(res["checks"]["approximate_gravity_equilibrium"], "Static equilibrium failed")
        self.assertTrue(res["checks"]["mesh_collision_free"], "Collisions detected")


if __name__ == "__main__":
    unittest.main()
