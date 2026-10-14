import unittest

from bricksmith.workbench.parts import inspect_part, search_parts


class PartLookupTests(unittest.TestCase):
    def test_slope_search_and_mesh_bounds(self):
        results = search_parts("slope brick", limit=12)
        self.assertTrue(results)
        self.assertTrue(all("part_id" in item and "name" in item for item in results))
        part = inspect_part("3039")
        self.assertIn("slope", part["name"].lower())
        self.assertAlmostEqual(part["body_span_studs_xz"][0], 2, places=1)
        self.assertAlmostEqual(part["body_height_plates"], 3, places=1)
        self.assertGreater(part["reference_uses"], 0)

    def test_rejects_path_lookup(self):
        with self.assertRaises(ValueError):
            inspect_part("../3039.dat")

    def test_spaced_dimensions_find_catalog_part(self):
        results = search_parts("plate 1 x 10", limit=5)
        self.assertIn("4477", [item["part_id"] for item in results])

    def test_descriptive_intent_words_do_not_hide_parts(self):
        results = search_parts("round brick 1 x 1 column porch", limit=12)
        self.assertTrue(results)
        self.assertTrue(any("round" in item["name"] for item in results))

    def test_synonym_request_falls_back_to_single_term_matches(self):
        results = search_parts("flower foliage", limit=12)
        self.assertTrue(results)
        self.assertIn("3742", [item["part_id"] for item in results])

    def test_requested_dimension_is_not_replaced_by_another(self):
        results = search_parts("tile 1x10", limit=12)
        self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
