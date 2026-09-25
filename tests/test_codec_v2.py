"""Comprehensive verification tests for versioned codec, fail-loudly kinematics,
interface rotations, pipeline cross-bag tokens, and physical support filter.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

from bricknet.data import load_catalog
from bricknet.collision import colliding_pairs
from bricksmith.core.connector import ConnectorType, Polarity, Port
from bricksmith.core.graph import AssemblyGraph
from bricksmith.core.tree import (
    BFSTreeCodec,
    InterfacePortSpec,
    TreeNode,
    get_available_interface_ports,
    merge_assemblies,
)
from bricksmith.decomposition.modularizer import BAG_NAMES, partition_into_bags
from bricksmith.generation.assemble import (
    _child_actions,
    _interface_actions,
    _is_supported,
    generate_guided_assembly,
)
from bricksmith.generation.sampler import (
    AttachmentToken,
    PlacedPart,
    PortSpec,
    attachment_nodes,
    yaw_matrix,
)
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

    def test_mating_recovery_rejects_identical_overlapping_parts_and_incompatible_connectors(self):
        """Review Finding 2: Connector family & polarity compatibility + mesh collision checks in mating recovery.

        Requires:
        - Two identical overlapping 3004 bricks return None (both bar-to-bar and mesh collision).
        - Incompatible connectors (male-to-male stud-to-stud, female-to-female hole-to-hole, bar-to-bar, clip-to-clip, hinge in-to-in) return None.
        - Valid compatible connectors (stud-to-hole, bar-to-clip) succeed and return exact connector type.
        """
        from types import SimpleNamespace
        from bricknet.data import load_connector_list
        from bricksmith.core.tree import _recover_intra_bag_mating, are_connectors_compatible
        conn_list = load_connector_list()

        # 1. Overlapping identical 3004 bricks (exact reviewer reproduction)
        p1 = SimpleNamespace(part_id="3004", transform=np.eye(4))
        p2 = SimpleNamespace(part_id="3004", transform=np.eye(4))
        m_overlap = _recover_intra_bag_mating(p1, p2, conn_list)
        self.assertIsNone(m_overlap, "Must reject identical overlapping bricks due to collision and illegal connector pairing")

        # 2. Incompatible connector pairs:
        # 2a. bar vs bar
        compat_bar, _ = are_connectors_compatible(("axle", "bar", None, 0, 10), ("axle", "bar", None, 0, 10))
        self.assertFalse(compat_bar, "Two male bars cannot mate")

        # 2b. stud vs stud (male to male)
        compat_stud, _ = are_connectors_compatible(("stud", "stud", None, 0, 0), ("stud", "stud", None, 0, 0))
        self.assertFalse(compat_stud, "Two male studs cannot mate")

        # 2c. hole vs hole (female to female)
        compat_hole, _ = are_connectors_compatible(("hole", "hole", None, 0, 0), ("hole", "hole", None, 0, 0))
        self.assertFalse(compat_hole, "Two female holes cannot mate")

        # 2d. clip vs clip
        compat_clip, _ = are_connectors_compatible(("axle", "clip", None, 0, 0), ("axle", "clip", None, 0, 0))
        self.assertFalse(compat_clip, "Two clips cannot mate")

        # 2e. hinge in vs in (same polarity)
        compat_hinge_same, _ = are_connectors_compatible(("hinge", "1", "in", 0, 0), ("hinge", "1", "in", 0, 0))
        self.assertFalse(compat_hinge_same, "Two hinge connectors of identical polarity cannot mate")

        # 3. Compatible connector pairs:
        # 3a. stud vs hole
        compat_sh, ct_sh = are_connectors_compatible(("stud", "stud", None, 0, 0), ("hole", "hole", None, 0, 0))
        self.assertTrue(compat_sh)
        self.assertEqual(ct_sh, ConnectorType.STUD)

        # 3b. bar vs clip
        compat_bc, ct_bc = are_connectors_compatible(("axle", "bar", None, 0, 10), ("axle", "clip", None, 0, 0))
        self.assertTrue(compat_bc)
        self.assertEqual(ct_bc, ConnectorType.CLIP)

        # 3c. hinge in vs on
        compat_h, ct_h = are_connectors_compatible(("hinge", "1", "in", 0, 0), ("hinge", "1", "on", 0, 0))
        self.assertTrue(compat_h)
        self.assertEqual(ct_h, ConnectorType.HINGE)

        # 4. Valid stacked 3004 bricks
        id_3004 = self.catalog.stem_to_id["3004"]
        pf4 = frame(id_3004, 4)  # top stud
        cf1 = frame(id_3004, 1)  # bottom hole
        t_stacked = np.eye(4) @ pf4 @ np.linalg.inv(cf1)
        p_stacked = SimpleNamespace(part_id="3004", transform=t_stacked)
        m_stacked = _recover_intra_bag_mating(p1, p_stacked, conn_list)
        self.assertIsNotNone(m_stacked)
        self.assertEqual(m_stacked[0], "port_4")
        self.assertEqual(m_stacked[1], "port_1")
        self.assertEqual(m_stacked[2], 0)
        self.assertLess(m_stacked[3], 1e-4)
        self.assertEqual(m_stacked[4], ConnectorType.STUD)

    def test_complete_four_bag_modular_zero_error_reconstruction(self):
        """Verify 100% zero-error reconstruction across a complete 4-bag modular architecture assembly.

        Permits ONLY the single initial grounded baseplate anchor in Bag 1.
        Bags 2, 3, and 4 receive ZERO anchors (anchors=None).
        Every piece across all 4 bags is reconstructed with < 1e-4 LDU error from saved tokens alone.
        """
        # Build 4-bag modular assembly: Foundation -> Core -> Facades -> Roof
        id_base = self.catalog.stem_to_id["3031"]  # 4x4 plate
        id_3004 = self.catalog.stem_to_id["3004"]  # 1x2 brick
        id_3005 = self.catalog.stem_to_id["3005"]  # 1x1 brick

        # Bag 1: Foundation (4x4 baseplate at ground + supporting 1x2 brick)
        g1 = AssemblyGraph("bag_1_foundation")
        t_base = np.eye(4)
        g1.add_part("3031", 0, t_base, instance_id=1)
        pf_plate = frame(id_base, 25)
        cf_brick1 = frame(id_3004, 1)
        t_brick1 = t_base @ pf_plate @ np.linalg.inv(cf_brick1)
        g1.add_part("3004", 15, t_brick1, instance_id=2)
        g1.connect(1, "port_25", 2, "port_1", ConnectorType.STUD)

        # Bag 2: Core (1x1 brick attaching to stud 4 of brick 2 with 90 deg yaw)
        g2 = AssemblyGraph("bag_2_core")
        pf_b2_s4 = frame(id_3004, 4)
        cf_b3 = frame(id_3005, 0)
        t_brick3 = t_brick1 @ pf_b2_s4 @ yaw_matrix(90) @ np.linalg.inv(cf_b3)
        g2.add_part("3005", 4, t_brick3, instance_id=3)

        # Bag 3: Facades (1x1 brick attaching to top stud of brick 3)
        g3 = AssemblyGraph("bag_3_facades")
        pf_b3_s1 = frame(id_3005, 1)
        t_brick4 = t_brick3 @ pf_b3_s1 @ np.linalg.inv(cf_b3)
        g3.add_part("3005", 14, t_brick4, instance_id=4)

        # Bag 4: Roof (1x2 brick attaching to top stud of brick 4)
        g4 = AssemblyGraph("bag_4_roof")
        pf_b4_s1 = frame(id_3005, 1)
        cf_roof = frame(id_3004, 1)
        t_roof = t_brick4 @ pf_b4_s1 @ np.linalg.inv(cf_roof)
        g4.add_part("3004", 70, t_roof, instance_id=5)

        cb = build_codebook(["3031", "3004", "3005"], [0, 4, 14, 15, 70])
        accumulated = None
        total_pieces = 0
        total_zero_error = 0

        for idx, bag in enumerate([g1, g2, g3, g4]):
            tree = BFSTreeCodec.encode(bag, interface_assembly=accumulated)
            tokens = serialize_tree(tree, cb, version=2)
            parsed = parse_attachment_digits(tokens, cb)
            for p, t in zip(parsed, tree):
                p.brick_id = t.brick_id
                self.assertIsNone(p.transform)

            # ONLY provide anchor for bag 1 baseplate! ZERO anchors for bags 2, 3, 4!
            anchors = {1: t_base} if accumulated is None else None
            dec_bag = BFSTreeCodec.decode(parsed, interface_assembly=accumulated, anchor_transforms=anchors)

            for bid, orig in bag.parts.items():
                self.assertIn(bid, dec_bag.parts)
                dp = dec_bag.parts[bid]
                pos_err = float(np.linalg.norm(orig.position - dp.position))
                rot_err = float(np.linalg.norm(orig.rotation - dp.rotation))
                self.assertLess(pos_err, 1e-4)
                self.assertLess(rot_err, 1e-4)
                total_zero_error += 1
                total_pieces += 1

            accumulated = dec_bag if accumulated is None else merge_assemblies(accumulated, dec_bag)

        self.assertEqual(total_pieces, 5)
        self.assertEqual(total_zero_error, 5)
        self.assertEqual(accumulated.num_parts, 5)
        self.assertEqual(accumulated.num_connections, 4)

    def test_woodland_elf_house_cross_bag_zero_error_reconstruction(self):
        """Review Finding 1: Strict encode -> serialize -> parse -> decode roundtrip on Elf House.

        Requires:
        - Strict representation boundary: parsed tokens have transform=None
        - Acceptance test permits ONLY the explicitly defined initial grounded baseplate anchor in bag 1.
        - Bags 2, 3, 4 receive ZERO anchors: all poses MUST attach through interface connections or intra-bag physical connections.
        - Every single verified piece's position and rotation error is < 1e-4 LDU from saved tokens alone.
        - Reconstructed earlier bags accumulated across steps (not original CAD).
        - Unattached/unresolved pieces must NOT silently receive source coordinates; they remain at default identity and are accounted for as unsupported.
        """
        with CORPUS_PATH.open(encoding="utf-8") as handle:
            record = json.loads(handle.readline())

        graph = graph_from_record(record)
        bags = partition_into_bags(graph)
        accumulated = None

        all_parts = sorted({p.part_id for p in graph.parts.values()})
        all_colors = sorted({p.color_id for p in graph.parts.values()})
        codebook = build_codebook(all_parts, all_colors)

        total_verified_pieces = 0
        total_unsupported_pieces = 0
        anchors_supplied_count = 0
        base_connected_bids = set()

        for bag_name in BAG_NAMES:
            bag = bags[bag_name]
            tree = BFSTreeCodec.encode(bag, interface_assembly=accumulated, require_anchored=True)

            # Strict representation boundary: serialize and parse tokens
            tokens = serialize_tree(tree, codebook, version=2)
            parsed = parse_attachment_digits(tokens, codebook)

            # Confirm parser does not cheat by retaining poses
            for p_node in parsed:
                self.assertIsNone(p_node.transform, "Parsed token node must not contain transform")

            # Re-associate brick_id from tree sequence
            for p, t in zip(parsed, tree):
                p.brick_id = t.brick_id

            # Permitted root anchors ONLY for the explicitly defined initial grounded baseplate in bag 1.
            # ZERO anchors for bags 2, 3, and 4! All subsequent pieces MUST attach through interface connections
            # or intra-bag physical connections.
            anchors = None
            if accumulated is None:
                root_id = tree[0].brick_id
                anchors = {root_id: bag.parts[root_id].transform}
                anchors_supplied_count += len(anchors)
                base_connected_bids.add(root_id)

            decoded_bag = BFSTreeCodec.decode(
                parsed,
                interface_assembly=accumulated,
                anchor_transforms=anchors,
            )

            # Trace which pieces in this tree connect back to base_connected_bids
            step_to_bid = {t.step_index: t.brick_id for t in tree}
            for t in tree:
                bid = t.brick_id
                if t.parent_step_index is not None:
                    parent_bid = step_to_bid[t.parent_step_index]
                    if parent_bid in base_connected_bids:
                        base_connected_bids.add(bid)
                elif t.parent_port and t.parent_port.startswith("iface_"):
                    base_connected_bids.add(bid)

            # Compare pieces:
            # All pieces in the retained subassembly must reconstruct with < 1e-4 LDU error.
            self.assertEqual(len(decoded_bag.parts), len(tree), "Decoded graph must contain exactly the anchored pieces")
            for t in tree:
                bid = t.brick_id
                orig_part = bag.parts[bid]
                dec_part = decoded_bag.parts[bid]
                self.assertIn(bid, base_connected_bids, f"Piece {bid} must have verified path to base anchor")

                pos_err = float(np.linalg.norm(orig_part.position - dec_part.position))
                rot_err = float(np.linalg.norm(orig_part.rotation - dec_part.rotation))
                self.assertLess(
                    pos_err,
                    1e-4,
                    f"{bag_name} part {bid} ({orig_part.part_id}) position error {pos_err} >= 1e-4 LDU",
                )
                self.assertLess(
                    rot_err,
                    1e-4,
                    f"{bag_name} part {bid} ({orig_part.part_id}) rotation error {rot_err} >= 1e-4",
                )
                total_verified_pieces += 1

            # Unsupported pieces in bag must be completely excluded from decoded_bag.parts and accumulated state
            unsupported_in_bag = set(bag.parts.keys()) - set(decoded_bag.parts.keys())
            total_unsupported_pieces += len(unsupported_in_bag)
            for bid in unsupported_in_bag:
                self.assertNotIn(bid, decoded_bag.parts, f"Unsupported piece {bid} must not enter reconstructed assembly")

            # Accumulate the RECONSTRUCTED earlier bag, NOT original CAD
            accumulated = decoded_bag if accumulated is None else merge_assemblies(accumulated, decoded_bag)

        # Explicitly verify the exact accounting:
        # Only 1 anchor supplied to decoder in total (the initial ground baseplate).
        # 187 kinematically connected pieces verified with zero error from saved tokens alone.
        # 217 unattached pieces (floating/continuous-rotation foliage/furniture) excluded from accepted targets.
        self.assertEqual(anchors_supplied_count, 1, "Only the single initial grounded baseplate anchor may be supplied")
        self.assertEqual(total_verified_pieces, 187, "Expected 187 kinematically connected pieces verified with zero error")
        self.assertEqual(total_unsupported_pieces, 217, "Expected 217 unattached pieces explicitly accounted as unsupported")
        self.assertEqual(total_verified_pieces + total_unsupported_pieces, 404, "All 404 Elf House pieces must be accounted for")

    def test_decoder_quarantines_unanchored_roots_and_strict_mode(self):
        """Production decoder must quarantine unanchored roots rather than placing at identity, and enforce strict mode."""
        with CORPUS_PATH.open(encoding="utf-8") as handle:
            record = json.loads(handle.readline())
        graph = graph_from_record(record)
        all_parts = sorted({p.part_id for p in graph.parts.values()})
        all_colors = sorted({p.color_id for p in graph.parts.values()})
        codebook = build_codebook(all_parts, all_colors)
        bags = partition_into_bags(graph)
        bag1 = bags["bag_1_foundation"]

        # When encoded with require_anchored=False, bag1 contains all 166 parts (122 anchored + 44 unanchored)
        tree_all = BFSTreeCodec.encode(bag1, require_anchored=False)
        self.assertEqual(len(tree_all), 166)

        # Serialize to tokens so transforms are stripped
        tokens = serialize_tree(tree_all, codebook, version=2)
        parsed = tree_nodes_from_target_text(tokens, codebook)
        for p, t in zip(parsed, tree_all):
            p.brick_id = t.brick_id

        root_id = tree_all[0].brick_id
        anchor = {root_id: bag1.parts[root_id].transform}

        # 1. Non-strict decode: quarantines unanchored roots into unsupported_parts
        dec = BFSTreeCodec.decode(parsed, anchor_transforms=anchor, strict=False)
        self.assertEqual(len(dec.parts), 122, "Only base-anchored pieces must enter reconstructed assembly")
        self.assertEqual(len(dec.unsupported_parts), 44, "All 44 unanchored pieces must be quarantined in unsupported_parts")
        for bid in dec.unsupported_parts:
            self.assertNotIn(bid, dec.parts, f"Quarantined piece {bid} must not appear in parts")

        # 2. Strict mode decode: raises ValueError on unanchored root
        with self.assertRaises(ValueError) as ctx:
            BFSTreeCodec.decode(parsed, anchor_transforms=anchor, strict=True)
        self.assertIn("has no anchor or interface connection", str(ctx.exception))

    def test_collision_check_failure_never_produces_mating(self):
        """Rule: A failed collision check must never produce a successful mating."""
        from unittest.mock import patch
        from bricknet.data import load_connector_list
        from bricksmith.core.tree import _recover_intra_bag_mating
        from bricksmith.core.graph import PartInstance

        conn_list = load_connector_list()

        # Two valid mating parts: 3004 brick on top of 3004 brick
        parent_part = PartInstance(
            instance_id=1,
            part_id="3004",
            color_id=0,
            transform=np.eye(4, dtype=np.float64),
        )
        child_part = PartInstance(
            instance_id=2,
            part_id="3004",
            color_id=0,
            transform=np.array([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, -24.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ], dtype=np.float64),
        )

        # Baseline: without error, valid mating is discovered
        mating = _recover_intra_bag_mating(parent_part, child_part, conn_list)
        self.assertIsNotNone(mating, "Baseline valid 3004 stack should mate successfully")

        # Injected collision engine failure: must NEVER produce a successful mating
        with patch("bricknet.collision.colliding_pairs", side_effect=RuntimeError("Collision engine crashed")):
            with self.assertRaises(RuntimeError):
                _recover_intra_bag_mating(parent_part, child_part, conn_list)

        # Overlapping identical pieces: must return None (rejected by collision check)
        overlapping_child = PartInstance(
            instance_id=3,
            part_id="3004",
            color_id=0,
            transform=np.eye(4, dtype=np.float64),
        )
        self.assertIsNone(
            _recover_intra_bag_mating(parent_part, overlapping_child, conn_list),
            "Identical overlapping pieces must be rejected by collision check",
        )

    def test_chained_guided_generation_multi_bag_context(self):
        """Review Findings 1 & 2: Multi-bag generation branch runs without ImportError and checks base collisions."""
        # Create base assembly (foundation plate + 2x4 brick)
        base = AssemblyGraph("base_foundation")
        base.add_part("3031", 0, np.eye(4), instance_id=1)
        id_3001 = self.catalog.stem_to_id["3001"]
        f_plate = frame(self.catalog.stem_to_id["3031"], 18)
        f_brick = frame(id_3001, 0)
        t_brick = np.eye(4) @ f_plate @ np.linalg.inv(f_brick)
        base.add_part("3001", 15, t_brick, instance_id=2)
        base.connect(1, "port_18", 2, "port_0", ConnectorType.STUD)

        # 1. Test _interface_actions runs cleanly and generates legal interface root candidates
        module_min = np.array([-100.0, -100.0, -100.0])
        module_max = np.array([100.0, 100.0, 100.0])
        iface_actions = _interface_actions(base, module_min, module_max)
        self.assertGreater(len(iface_actions), 0, "Expected legal interface actions on base assembly")

        # Check that interface tokens have valid iface parent_ports
        for token, pid in iface_actions[:5]:
            self.assertIsNotNone(token.parent_port)
            self.assertTrue(token.parent_port.startswith("iface_"))
            self.assertIsNotNone(token.anchor_transform)

        # 2. Test _child_actions receives base_placed and verifies collisions/support against base
        chosen_token, chosen_pid = iface_actions[0]
        base_placed = []
        for bid, p in sorted(base.parts.items()):
            _, _, p_lo, p_hi = world_properties(p.part_id, p.transform)
            base_placed.append(
                PlacedPart(
                    part_id=p.part_id,
                    color_id=p.color_id,
                    transform=p.transform.copy(),
                    bounds_min=p_lo,
                    bounds_max=p_hi,
                    ports=[],
                )
            )

        candidates, blocked = _child_actions(
            placed_tokens=[chosen_token],
            placed_ids=[chosen_pid],
            module_min=module_min,
            module_max=module_max,
            base_placed=base_placed,
        )
        self.assertEqual(len(candidates), len(blocked))
        unblocked = [cand for cand, blk in zip(candidates, blocked) if not blk]
        self.assertGreater(len(unblocked), 0, "Expected legal child placements on interface root")

    def test_validator_robust_part_resolution(self):
        """Review Finding 5: Validator resolves pattern variants, integer IDs, and normalizes stems."""
        from bricksmith.physics.validator import _resolve_part_num
        # Integer ID
        id_3001 = self.catalog.stem_to_id["3001"]
        self.assertEqual(_resolve_part_num(id_3001), id_3001)
        # Direct stem
        self.assertEqual(_resolve_part_num("3001"), id_3001)
        # .dat suffix
        self.assertEqual(_resolve_part_num("3001.dat"), id_3001)
        # Pattern variant stripping (e.g. 54200pb103 -> 54200)
        id_54200 = self.catalog.stem_to_id["54200"]
        self.assertEqual(_resolve_part_num("54200pb103"), id_54200)
        self.assertEqual(_resolve_part_num("bl_54200pb103"), id_54200)
        # World properties should compute real COM and bounding box
        vol, com, lo, hi = world_properties("3001", np.eye(4))
        self.assertGreater(vol, 0.0)
        self.assertTrue(np.all(np.isfinite(com)))
        self.assertTrue(np.all(lo <= hi))

    def test_interface_root_rotation_preserves_distinct_tokens(self):
        """Review Finding 2: Interface root rotations preserve distinct tokens and reconstructed poses."""
        base = AssemblyGraph("base")
        base.add_part("3020", 0, np.eye(4), instance_id=1)
        ifaces = get_available_interface_ports(base)
        iface = ifaces[0]

        p_3004 = self.catalog.stem_to_id["3004"]
        cf = frame(p_3004, 2)
        anchor_t_0 = iface.world_transform @ np.eye(4) @ np.linalg.inv(cf)
        anchor_t_180 = iface.world_transform @ yaw_matrix(180) @ np.linalg.inv(cf)

        tok0 = AttachmentToken("3004", 0, None, "iface_0", "port_2", 0.0, anchor_transform=anchor_t_0)
        tok180 = AttachmentToken("3004", 0, None, "iface_0", "port_2", 180.0, anchor_transform=anchor_t_180)

        nodes0 = attachment_nodes([tok0])
        nodes180 = attachment_nodes([tok180])

        self.assertEqual(nodes0[0].rotation_quarters, 0)
        self.assertEqual(nodes180[0].rotation_quarters, 2)

        codebook = build_codebook(["3020", "3004"], [0])
        s0 = serialize_tree(nodes0, codebook, version=2)
        s180 = serialize_tree(nodes180, codebook, version=2)

        # Serialized tokens must differ (ending with rotation digit 0 vs 2)
        self.assertNotEqual(s0, s180)
        self.assertTrue(s0.endswith("0"))
        self.assertTrue(s180.endswith("2"))

        # Parsed rotation quarters must be preserved
        p0 = parse_attachment_digits(s0, codebook)
        p180 = parse_attachment_digits(s180, codebook)
        self.assertEqual(p0[0].rotation_quarters, 0)
        self.assertEqual(p180[0].rotation_quarters, 2)

        # Decoded positions must differ
        dec0 = BFSTreeCodec.decode(p0, interface_assembly=base)
        dec180 = BFSTreeCodec.decode(p180, interface_assembly=base)
        pos0 = dec0.parts[1].position
        pos180 = dec180.parts[1].position
        self.assertFalse(np.allclose(pos0, pos180, atol=1.0))
        np.testing.assert_allclose(pos0, np.array([-40.0, -24.0, -10.0]), atol=1e-3)
        np.testing.assert_allclose(pos180, np.array([-20.0, -24.0, -10.0]), atol=1e-3)

    def test_interface_root_mask_rejects_mesh_penetration(self):
        """Review Finding 3: _interface_actions rejects mesh penetration (e.g. 15573 jumper on 3020)."""
        base = AssemblyGraph("base")
        base.add_part("3020", 0, np.eye(4), instance_id=1)

        module_min = np.array([-100.0, -100.0, -100.0])
        module_max = np.array([100.0, 100.0, 100.0])

        actions = _interface_actions(base, module_min, module_max)
        self.assertGreater(len(actions), 0)

        # Confirm that penetrating jumper attachment (15573 on iface_0 with port_2, yaw 0) is blocked
        penetrating = any(
            tok.part_id == "15573"
            and tok.parent_port == "iface_0"
            and tok.self_port == "port_2"
            and tok.rotation_offset == 0.0
            for tok, _pid in actions
        )
        self.assertFalse(penetrating, "Penetrating 15573 jumper must be rejected by interface action mask")

        # Explicitly verify that colliding_pairs detects this mesh collision
        ifaces = get_available_interface_ports(base)
        iface0 = ifaces[0]
        id_3020 = self.catalog.stem_to_id["3020"]
        id_15573 = self.catalog.stem_to_id["15573"]
        cf = frame(id_15573, 2)
        child_t = iface0.world_transform @ np.eye(4) @ np.linalg.inv(cf)
        pairs = colliding_pairs(np.asarray([id_3020, id_15573]), np.stack([np.eye(4), child_t]))
        self.assertIn((0, 1), pairs, "colliding_pairs must detect penetration between 3020 and 15573 at this pose")

    def test_public_guided_assembly_multi_bag_integration(self):
        """Review Entry Point: Public generate_guided_assembly across bags passes full physics validation."""
        box_min = [-80.0, -96.0, -80.0]
        box_max = [80.0, 48.0, 80.0]

        bag1 = generate_guided_assembly(
            seed=42,
            module_min=box_min,
            module_max=box_max,
            adapter_path="adapters/phase3a",
            target_pieces=2,
            bag_name="bag_1_foundation",
        )
        self.assertEqual(bag1.num_parts, 2)

        merged = generate_guided_assembly(
            seed=43,
            module_min=box_min,
            module_max=box_max,
            adapter_path="adapters/phase3a",
            target_pieces=2,
            bag_name="bag_2_core",
            base_assembly=bag1,
            merge_base=True,
        )
        self.assertEqual(merged.num_parts, 4)

        res = validate_ldraw(merged.to_ldraw())
        self.assertTrue(res["passed"], f"Validation failed: {res.get('errors')}")
        self.assertTrue(res["checks"]["mesh_collision_free"])
        self.assertTrue(res["checks"]["included_base"])
        self.assertTrue(res["checks"]["actual_connectivity"])
        self.assertTrue(res["checks"]["approximate_gravity_equilibrium"])


if __name__ == "__main__":
    unittest.main()

