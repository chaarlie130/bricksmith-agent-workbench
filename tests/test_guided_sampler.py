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


if __name__ == "__main__":
    unittest.main()
