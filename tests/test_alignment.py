import tempfile
import unittest
from pathlib import Path

from bricksmith.workbench.alignment import analyze_alignment


class AlignmentTests(unittest.TestCase):
    def test_suggests_half_stud_shift_for_plate_on_baseplate(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "build.ldr"
            path.write_text(
                "0 alignment test\n"
                "1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat\n"
                "1 15 10 -8 0 1 0 0 0 1 0 0 0 1 3022.dat\n",
                encoding="utf-8")
            result = analyze_alignment(path, [3])["placements"][0]
            self.assertEqual(result["current_matching_holes"], 0)
            self.assertTrue(any(abs(item["dx"]) == 10 and item["dz"] == 0
                                and item["matching_holes"] > 0
                                for item in result["candidate_xy_moves_ldu"]))
            with self.assertRaisesRegex(ValueError, "Not current placement"):
                analyze_alignment(path, [1])


if __name__ == "__main__":
    unittest.main()
