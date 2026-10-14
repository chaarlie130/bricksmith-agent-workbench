import unittest

from scripts.test_build import extract_ldr, make_prompt


class BuildPilotTests(unittest.TestCase):
    def test_extract_valid_model_and_reject_bad_placements(self):
        placement = "1 15 0 -8 0 1 0 0 0 1 0 0 0 1 3024.dat"
        model = "0 Test cottage\n" + "\n".join([placement] * 20)
        self.assertEqual(extract_ldr(model).count("3024.dat"), 20)
        with self.assertRaisesRegex(ValueError, "Malformed"):
            extract_ldr(model.replace("3024.dat", "3024.dat nonsense", 1))
        with self.assertRaisesRegex(ValueError, "20–200"):
            extract_ldr(placement)

    def test_prompt_includes_provenance_and_originality_guard(self):
        prompt, refs = make_prompt("A cottage")
        self.assertEqual(len(refs), 2)
        self.assertIn("Do not copy a reference model", prompt)
        self.assertIn(refs[0]["sha256"], prompt)


if __name__ == "__main__":
    unittest.main()
