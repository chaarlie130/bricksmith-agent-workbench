"""Formatter and decoder agreement on real corpus bags."""
import json
import unittest

from bricksmith.core.tree import BFSTreeCodec
from bricksmith.decomposition.modularizer import BAG_NAMES, partition_into_bags
from bricksmith.training.codec import (
    DATASET_TOKEN_CAP,
    count_tokens,
    set_active_codebook,
    tree_nodes_from_target_text,
)
from bricksmith.training.format_dataset import (
    CORPUS_PATH,
    build_codebook_from_corpus,
    example_text,
    graph_from_record,
)


class TestTrainingFormat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.codebook = build_codebook_from_corpus(CORPUS_PATH)
        set_active_codebook(cls.codebook)
        with CORPUS_PATH.open(encoding="utf-8") as handle:
            cls.record = json.loads(handle.readline())

    def test_real_bag_targets_roundtrip_under_token_limit(self):
        graph = graph_from_record(self.record)
        bags = partition_into_bags(graph)
        seen = set()
        for bag_name in BAG_NAMES:
            bag = bags[bag_name]
            self.assertGreater(bag.num_parts, 0, bag_name)
            text = example_text(bag, bag_name, self.codebook)
            seen.add(bag_name)
            self.assertIn("[INPUT: Bounding Box", text)
            self.assertIn("Aspect Ratio", text)
            self.assertIn("Target Bag Name", text)
            self.assertIn(bag_name, text)
            self.assertIn("Coarse Voxel Tokens", text)
            self.assertIn("[TARGET: Discrete BFS Spanning Tree Path Tokens for that Bag]", text)
            target = text.split("[TARGET:", 1)[1]
            self.assertNotIn("POSE:", target)
            payload = target.split("\n", 1)[1].strip()
            self.assertRegex(payload, r"^[0-9]+$")
            self.assertLess(count_tokens(text), DATASET_TOKEN_CAP)

            source = BFSTreeCodec.encode(bag)
            decoded_nodes = tree_nodes_from_target_text(text, self.codebook)
            graph_out = BFSTreeCodec.decode(decoded_nodes)
            self.assertEqual(len(decoded_nodes), len(source))
            self.assertEqual(graph_out.num_parts, bag.num_parts)
            for src, dec in zip(source, decoded_nodes):
                self.assertEqual(dec.part_id, src.part_id)
                self.assertEqual(dec.color_id, src.color_id)
                self.assertEqual(dec.parent_step_index, src.parent_step_index)
                self.assertEqual(dec.parent_port, src.parent_port)
                self.assertEqual(dec.self_port, src.self_port)
                if src.parent_step_index is not None:
                    self.assertEqual(dec.conn_type, src.conn_type)
                    self.assertIsNotNone(dec.parent_port)
                    self.assertIsNotNone(dec.self_port)
            # String form also goes through BFSTreeCodec.decode.
            from_text = BFSTreeCodec.decode(text)
            self.assertEqual(
                sorted(part.part_id for part in from_text.parts.values()),
                sorted(part.part_id for part in graph_out.parts.values()),
            )
        self.assertEqual(seen, set(BAG_NAMES))


if __name__ == "__main__":
    unittest.main()
