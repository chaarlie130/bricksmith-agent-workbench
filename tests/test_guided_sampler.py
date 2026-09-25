"""Forward masks and parent-port pose realization."""
import unittest

import numpy as np

from bricksmith.core.connector import ConnectorType, Polarity
from bricksmith.core.tree import BFSTreeCodec
from bricksmith.generation.sampler import (
    AttachmentToken,
    PortSpec,
    apply_illegal_logit_mask,
    attach_pose,
    attachment_nodes,
    codec_attachment_ids,
    illegal_ids_for_actions,
    illegal_ids_for_continuations,
    illegal_mask,
    place_token,
    realize_assembly,
    sample_masked_token_id,
)


def _port(port_id, connector_type, polarity, position):
    return PortSpec(
        port_id,
        connector_type,
        polarity,
        np.array(position, dtype=np.float64),
        np.eye(3, dtype=np.float64),
    )


class TestGuidedSampler(unittest.TestCase):
    def setUp(self):
        self.module_min = np.array([-5.0, -20.0, -5.0])
        self.module_max = np.array([30.0, 10.0, 30.0])
        self.root = AttachmentToken(
            part_id="3020",
            color_id=0,
            parent_index=None,
            parent_port=None,
            self_port=None,
            rotation_offset=0,
            ports=[
                _port("stud_top", ConnectorType.STUD, Polarity.MALE, [10.0, 0.0, 10.0]),
                _port("tube_side", ConnectorType.TUBE, Polarity.FEMALE, [10.0, 8.0, 10.0]),
            ],
            local_bounds_min=np.array([0.0, 0.0, 0.0]),
            local_bounds_max=np.array([20.0, 8.0, 20.0]),
            anchor_transform=np.eye(4, dtype=np.float64),
            decoy_position=np.array([999.0, 999.0, 999.0]),
        )
        self.placed = [place_token(self.root, [])]

    def _child(self, connector_type, polarity, port_position, bounds_min=None, bounds_max=None, parent_port="stud_top"):
        return AttachmentToken(
            part_id="3001",
            color_id=15,
            parent_index=0,
            parent_port=parent_port,
            self_port="child_port",
            rotation_offset=0,
            ports=[_port("child_port", connector_type, polarity, port_position)],
            local_bounds_min=np.array([0.0, 0.0, 0.0] if bounds_min is None else bounds_min),
            local_bounds_max=np.array([20.0, 8.0, 20.0] if bounds_max is None else bounds_max),
            decoy_position=np.array([999.0, 999.0, 999.0]),
        )

    def test_mask_rejects_bounds_polarity_and_overlap_only(self):
        legal = self._child(ConnectorType.TUBE, Polarity.FEMALE, [10.0, 8.0, 10.0])
        stud_stud = self._child(ConnectorType.STUD, Polarity.MALE, [10.0, 8.0, 10.0])
        tube_tube = self._child(
            ConnectorType.TUBE,
            Polarity.FEMALE,
            [10.0, 8.0, 10.0],
            parent_port="tube_side",
        )
        outside = self._child(ConnectorType.TUBE, Polarity.FEMALE, [-100.0, 8.0, 10.0])
        overlap = self._child(ConnectorType.TUBE, Polarity.FEMALE, [10.0, 4.0, 10.0])
        candidates = [legal, stud_stud, tube_tube, outside, overlap]
        masked = illegal_mask(candidates, self.placed, self.module_min, self.module_max)
        self.assertEqual(masked, [False, True, True, True, True])

    def test_realize_uses_parent_port_pose_not_absolute_xyz(self):
        child = self._child(ConnectorType.TUBE, Polarity.FEMALE, [10.0, 8.0, 10.0])
        graph = realize_assembly([self.root, child])
        self.assertIsInstance(graph, type(BFSTreeCodec.decode([])))
        self.assertEqual(graph.num_parts, 2)
        parent_port = self.root.port("stud_top")
        child_port = child.port("child_port")
        expected = attach_pose(self.placed[0].transform, parent_port, child_port, child.rotation_offset)
        child_part = graph.parts[2]
        self.assertLess(float(np.max(np.abs(child_part.transform - expected))), 1e-8)
        self.assertGreater(float(np.max(np.abs(child_part.position - child.decoy_position))), 100.0)
        self.assertLess(float(np.max(np.abs(graph.parts[1].position))), 1e-8)
        self.assertEqual(graph.num_connections, 1)
        link = graph.connections[0]
        self.assertEqual(link.source_port_id, "stud_top")
        self.assertEqual(link.target_port_id, "child_port")

    def test_illegal_mask_sets_logit_ids_to_negative_infinity(self):
        logits = np.array([0.2, 1.5, -0.3, 0.7], dtype=np.float32)
        blocked = [False, True, True, False]
        illegal = illegal_ids_for_actions(4, [0, 1, 2, 3], blocked)
        masked = apply_illegal_logit_mask(logits, illegal)
        self.assertTrue(np.isneginf(masked[1]))
        self.assertTrue(np.isneginf(masked[2]))
        self.assertAlmostEqual(float(masked[0]), 0.2)
        self.assertAlmostEqual(float(masked[3]), 0.7)
        self.assertEqual(sample_masked_token_id(masked, seed=0), sample_masked_token_id(masked, seed=0))
        self.assertIn(sample_masked_token_id(masked, seed=1), {0, 3})

    def test_codec_attachment_ids_match_training_tokenizer(self):
        from bricksmith.core.connector import ConnectorType
        from bricksmith.generation.assemble import _child_token, _part_token
        from bricksmith.training.codec import load_codebook, serialize_tree, training_tokenizer

        plate, _numeric = _part_token("3020", 0)
        brick, _brick_id = _part_token("3001", 15)
        stud = next(port.port_id for port in plate.ports if port.connector_type == ConnectorType.STUD)
        hole = next(port.port_id for port in brick.ports if port.connector_type == ConnectorType.TUBE)
        child = _child_token(brick, stud, hole, 90, 15)
        actions = [plate, child]
        tokenizer = training_tokenizer()
        ids = codec_attachment_ids(tokenizer, actions)
        text = serialize_tree(attachment_nodes(actions), load_codebook())
        self.assertEqual(ids, list(tokenizer.encode(text, add_special_tokens=False)))
        self.assertGreater(len(ids), 1)
        other = codec_attachment_ids(tokenizer, [plate])
        vocab = max(max(ids), max(other)) + 1
        illegal = illegal_ids_for_continuations(vocab, [ids], 0)
        masked = apply_illegal_logit_mask(np.zeros(vocab, dtype=np.float32), illegal)
        self.assertTrue(np.isfinite(masked[ids[0]]))
        if other[0] != ids[0]:
            self.assertTrue(np.isneginf(masked[other[0]]))

    def test_scope_slope_codec_roundtrip_and_mesh_logit_mask(self):
        from bricksmith.core.connector import ConnectorType, Polarity
        from bricksmith.core.tree import BFSTreeCodec, TreeNode
        from bricksmith.generation.assemble import (
            _child_actions,
            _child_token,
            _ground_anchor,
            _part_token,
            module_box_from_studs,
        )
        from bricksmith.generation.sampler import (
            illegal_mask,
            mask_attachment_candidates,
            masked_logits_for_continuations,
            meshes_penetrate,
            place_token,
        )
        from bricksmith.training.codec import (
            build_codebook,
            parse_attachment_digits,
            serialize_tree,
            training_tokenizer,
        )

        slope = "54200"
        codebook = build_codebook(["3020", slope, "3001"], [0, 15])
        plate, plate_id = _part_token("3020", 0)
        brick, _brick_id = _part_token(slope, 15)
        stud = next(port.port_id for port in plate.ports if port.connector_type == ConnectorType.STUD)
        hole = next(port.port_id for port in brick.ports if port.connector_type == ConnectorType.TUBE)
        nodes = [
            TreeNode(0, 1, "3020", 0, None, None, None, None, np.eye(4)),
            TreeNode(1, 2, slope, 15, 0, stud, hole, ConnectorType.STUD, np.eye(4)),
        ]
        text = serialize_tree(nodes, codebook)
        self.assertNotRegex(text, r"POSE")
        decoded = BFSTreeCodec.decode(parse_attachment_digits(text, codebook))
        self.assertEqual([decoded.parts[1].part_id, decoded.parts[2].part_id], ["3020", slope])
        link = decoded.connections[0]
        self.assertEqual((link.source_port_id, link.target_port_id), (stud, hole))

        module_min, module_max = module_box_from_studs(32, 32, 24)
        plate.anchor_transform = _ground_anchor(plate_id, module_min, module_max)
        children, blocked = _child_actions([plate], [plate_id], module_min, module_max)
        drawable = [token.part_id for token, flag in zip(children, blocked) if not flag]
        self.assertIn("54200", drawable)
        self.assertIn("3794b", drawable)
        self.assertTrue(any(token.part_id == "99781" for token in children))

        brick, brick_id = _part_token("3005", 15)
        jumper, jumper_id = _part_token("15573", 15)
        parent_stud = "port_11"
        brick_hole = next(port.port_id for port in brick.ports if port.connector_type == ConnectorType.TUBE)
        legal = _child_token(brick, parent_stud, brick_hole, 0, 15)
        penetrating = _child_token(jumper, parent_stud, "port_2", 0, 15)
        child_stud = next(port.port_id for port in brick.ports if port.connector_type == ConnectorType.STUD)
        stud_stud = _child_token(brick, parent_stud, child_stud, 0, 15)
        placed = place_token(plate, [])
        self.assertFalse(illegal_mask([penetrating], [placed], module_min, module_max)[0])
        self.assertTrue(
            meshes_penetrate(
                [plate_id, jumper_id],
                [placed.transform, place_token(penetrating, [placed]).transform],
            )
        )
        self.assertFalse(
            meshes_penetrate(
                [plate_id, brick_id],
                [placed.transform, place_token(legal, [placed]).transform],
            )
        )
        candidates = [legal, penetrating, stud_stud]
        flags = mask_attachment_candidates(
            candidates,
            [plate],
            [plate_id],
            [brick_id, jumper_id, brick_id],
            module_min,
            module_max,
        )
        self.assertEqual(flags, [False, True, True])
        tokenizer = training_tokenizer()
        sequences = [
            codec_attachment_ids(tokenizer, [plate, token]) for token in candidates
        ]
        legal_ids, pen_ids, mate_ids = sequences
        offset = next(i for i, (a, b) in enumerate(zip(legal_ids, pen_ids)) if a != b)
        vocab = max(token_id for seq in sequences for token_id in seq) + 1
        masked = masked_logits_for_continuations(
            np.ones(vocab, dtype=np.float32),
            sequences,
            flags,
            offset,
        )
        self.assertTrue(np.isfinite(masked[legal_ids[offset]]))
        self.assertTrue(np.isneginf(masked[pen_ids[offset]]))
        mate_offset = next(i for i, (a, b) in enumerate(zip(legal_ids, mate_ids)) if a != b)
        mate_masked = masked_logits_for_continuations(
            np.ones(vocab, dtype=np.float32),
            sequences,
            flags,
            mate_offset,
        )
        self.assertTrue(np.isneginf(mate_masked[mate_ids[mate_offset]]))

    def test_stack_parent_stays_in_the_building_box(self):
        from bricksmith.core.connector import ConnectorType
        from bricksmith.generation.assemble import _child_actions, _child_token, _ground_anchor, _part_token, module_box_from_studs
        from bricksmith.generation.sampler import mask_attachment_candidates, meshes_penetrate, place_token

        module_min, module_max = module_box_from_studs(32, 32, 24)
        plate, plate_id = _part_token("3022", 0)
        plate.anchor_transform = _ground_anchor(plate_id, module_min, module_max)
        brick, brick_id = _part_token("3001", 15)
        stud = next(port.port_id for port in plate.ports if port.connector_type == ConnectorType.STUD)
        hole = next(port.port_id for port in brick.ports if port.connector_type == ConnectorType.TUBE)
        first = _child_token(brick, stud, hole, 0, 15)
        flags = mask_attachment_candidates(
            [first], [plate], [plate_id], [brick_id], module_min, module_max
        )
        self.assertFalse(flags[0])
        children, blocked = _child_actions(
            [plate, first], [plate_id, brick_id], module_min, module_max
        )
        stacked = [
            token for token, flag in zip(children, blocked) if token.parent_index == 1 and not flag
        ]
        self.assertTrue(stacked)
        placed = place_token(plate, [])
        overhang = place_token(first, [placed])
        past_plate = (
            overhang.bounds_min[0] < placed.bounds_min[0] - 0.5
            or overhang.bounds_max[0] > placed.bounds_max[0] + 0.5
            or overhang.bounds_min[2] < placed.bounds_min[2] - 0.5
            or overhang.bounds_max[2] > placed.bounds_max[2] + 0.5
        )
        self.assertTrue(past_plate)
        self.assertFalse(
            meshes_penetrate(
                [plate_id, brick_id],
                [placed.transform, overhang.transform],
            )
        )

    def test_ensemble_contact_support_filter_allows_running_bonds_and_lintels(self):
        """Task 3 verification: ensemble contact-hull support permits running bonds and lintels."""
        from bricksmith.generation.assemble import _is_supported
        from bricksmith.generation.sampler import PlacedPart

        def make_part(pid, bmin, bmax):
            return PlacedPart(
                part_id=pid,
                color_id=0,
                transform=np.eye(4),
                bounds_min=np.array(bmin, dtype=np.float64),
                bounds_max=np.array(bmax, dtype=np.float64),
                ports=[],
            )

        # 1. Running bond: 1x4 brick resting across two 1x2 bricks
        b1 = make_part("3004", [-20, 0, -10], [20, 24, 10])
        b2 = make_part("3004", [20, 0, -10], [60, 24, 10])
        child_running = make_part("3010", [-20, -24, -10], [60, 0, 10])
        self.assertTrue(_is_supported(child_running, [b1, b2], parent_index=0))

        # 2. Multi-column lintel: 1x4 beam bridging across two separate columns
        col1 = make_part("3004", [-40, 0, -10], [-20, 24, 10])
        col2 = make_part("3004", [20, 0, -10], [40, 24, 10])
        lintel = make_part("3010", [-40, -24, -10], [40, 0, 10])
        self.assertTrue(_is_supported(lintel, [col1, col2], parent_index=0))

        # 3. Direct vertical stack on single parent (fast path)
        stacked = make_part("3004", [-20, -24, -10], [20, 0, 10])
        self.assertTrue(_is_supported(stacked, [b1], parent_index=0))

        # 4. Overhanging cantilever with COM hanging over empty space (must be rejected)
        cantilever = make_part("3010", [-40, -24, -10], [40, 0, 10])
        self.assertFalse(_is_supported(cantilever, [col1], parent_index=0))


if __name__ == "__main__":
    unittest.main()
