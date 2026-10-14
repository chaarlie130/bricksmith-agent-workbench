"""Offline tests for the resumable tool-calling design session."""
import json
import hashlib
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bricksmith.workbench.agent_session import TOOLS, VIEWS, _assemble, _auto_preview_views, _expand_array, _floor_ldr, _fresh_render_path, _gable_ldr, _roof_seam_column_ldr, _roof_tile_caps_ldr, _save, _session_status, _starter_reference_pack, _stepped_roof_beams_ldr, _support_column_ldr, _wall_runs_ldr, _tool, load_session, queue_renders, run_session, start_session, step_session
from scripts.agent_session import main as session_cli_main


PLACEMENT = "1 15 0 8 0 1 0 0 0 1 0 0 0 1 3022.dat"


class AgentSessionTests(unittest.TestCase):
    def test_near_complete_checked_build_gets_two_automatic_views(self):
        state = {"target_pieces": "400-800", "last_feedback": {"passed": True}}
        self.assertEqual(_auto_preview_views(state, 319), ("front_left",))
        self.assertEqual(_auto_preview_views(state, 320),
                         ("front_left", "front_right"))
        state["last_feedback"] = {"passed": False}
        self.assertEqual(_auto_preview_views(state, 500), ("front_left",))

    def test_plate_plinth_session_uses_configured_ground_plane(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "Compact display base", ground_y=0)
            plate = "1 0 0 -8 0 1 0 0 0 1 0 0 0 1 3022.dat"
            result = _tool(directory, state, "save_module", {"name": "plinth", "ldr": plate})
            self.assertTrue(result["validation"]["checks"]["included_base"])
            self.assertEqual(load_session(directory)["ground_y"], 0)
            self.assertEqual(state["last_validation"]["ground_y_ldu"], 0)

    def test_starter_pack_prefetches_relevant_source_geometry(self):
        pack = _starter_reference_pack(
            "premium modern hillside house, two-story with stepped terrain and layered roof")
        self.assertGreaterEqual(pack["corpus_size"], 100)
        self.assertEqual(pack["examples"][0]["id"], "omr_21009-1_Farnsworth_House")
        self.assertEqual([item["reference_role"] for item in pack["examples"]],
                         ["subject and style", "modern massing", "terrain and site"])
        self.assertEqual(pack["examples"][2]["id"], "omr_21041-1_Great_Wall_of_China")
        self.assertTrue(pack["examples"][0]["overview"]["placements"])
        self.assertIn("3070b", pack["part_dictionary"])
        self.assertIn("span_studs_xz", pack["part_dictionary"]["3070b"])
        self.assertTrue("house" in pack["examples"][0]["title"].lower())
        self.assertTrue(all("opera house" not in item["title"].lower()
                            for item in pack["examples"]))
        self.assertTrue(pack["examples"][0]["requested_style_matched"])
        self.assertFalse(pack["examples"][2]["requested_style_matched"])
        traditional = _starter_reference_pack("traditional house with porch and pitched roof")
        self.assertEqual(traditional["examples"][0]["id"], "omr_31009-1_Small_Cottage")
        self.assertEqual(traditional["examples"][2]["reference_role"], "roof-window technique")
        gothic = _starter_reference_pack("gothic cathedral with twin towers")
        self.assertEqual(gothic["requested_style"], "gothic")
        self.assertTrue(gothic["examples"])
        self.assertFalse(gothic["examples"][0]["requested_style_matched"])

    def test_first_model_request_receives_saved_starter_pack(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            start_session(directory, "modern hillside house with glass facade")
            with patch("bricksmith.workbench.agent_session.respond", return_value={"output": []}) as mock:
                step_session(directory)
            request = mock.call_args.args[2]
            self.assertTrue(any("Locally prefetched LDraw" in str(item.get("content", ""))
                                for item in request))
            self.assertTrue(any("real-set construction-reference previews" in str(item.get("content", ""))
                                for item in request))
            self.assertEqual(load_session(directory)["starter_references"]["examples"][0]["id"],
                             "omr_21009-1_Farnsworth_House")
            self.assertTrue(load_session(directory)["starter_preview_attempted"])

    def test_bounded_run_continues_lookup_then_stops_on_model_text(self):
        turns = [
            {"step": 1, "text": "", "tools": [{"tool": "search_parts", "result": {"results": []}}],
             "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120}},
            {"step": 2, "text": "Finished", "tools": [],
             "usage": {"input_tokens": 110, "output_tokens": 30, "total_tokens": 140}},
        ]
        with patch("bricksmith.workbench.agent_session.step_session", side_effect=turns) as step:
            result = run_session(Path("unused"), max_requests=4, message="Build a shed")
        self.assertEqual(result["requests"], 2)
        self.assertEqual(result["stopped_because"], "model_stopped")
        self.assertEqual(result["usage"]["total_tokens"], 260)
        self.assertEqual(step.call_args_list[0].kwargs["message"], "Build a shed")
        self.assertIsNone(step.call_args_list[1].kwargs["message"])

    def test_bounded_run_honors_request_and_soft_token_caps(self):
        turn = {"step": 1, "text": "", "tools": [{"tool": "inspect_part", "result": {}}],
                "usage": {"input_tokens": 1200, "output_tokens": 100, "total_tokens": 1300}}
        with patch("bricksmith.workbench.agent_session.step_session", return_value=turn) as step:
            result = run_session(Path("unused"), max_requests=4, max_total_tokens=1000)
        self.assertEqual(result["stopped_because"], "max_total_tokens")
        self.assertEqual(step.call_count, 1)
        with patch("bricksmith.workbench.agent_session.step_session", return_value=turn) as step:
            result = run_session(Path("unused"), max_requests=2)
        self.assertEqual(result["stopped_because"], "max_requests")
        self.assertEqual(step.call_count, 2)
        with self.assertRaises(ValueError):
            run_session(Path("unused"), max_requests=9)

    def test_bounded_run_prompts_after_two_research_only_turns(self):
        lookup = {"step": 1, "text": "", "tools": [{"tool": "search_parts", "result": {}}],
                  "usage": {"total_tokens": 100}}
        build = {"step": 3, "text": "", "tools": [{"tool": "save_module", "result": {
            "module": "garden_feature", "module_parts": 12, "total_parts": 139,
            "validation": {"passed": True}}}],
                 "usage": {"total_tokens": 100}}
        with patch("bricksmith.workbench.agent_session.step_session", side_effect=[lookup, lookup, build]) as step:
            result = run_session(Path("unused"), max_requests=3)
        self.assertEqual(result["requests"], 3)
        self.assertIsNone(step.call_args_list[1].kwargs["message"])
        self.assertIn("two model turns on lookup", step.call_args_list[2].kwargs["message"])
        self.assertEqual(result["steps"][-1]["tools"][0]["module_parts"], 12)

    def test_bounded_run_resumes_lookup_streak_from_saved_events(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A small shed")
            state["events"] = [{"step": 1, "tools": ["search_parts"]},
                               {"step": 2, "tools": ["inspect_part"]}]
            _save(directory, state)
            turn = {"step": 3, "text": "", "tools": [], "usage": {"total_tokens": 100}}
            with patch("bricksmith.workbench.agent_session.step_session", return_value=turn) as step:
                run_session(directory, max_requests=1)
            self.assertIn("two model turns on lookup", step.call_args.kwargs["message"])

    def test_bounded_run_reports_partial_work_before_request_error(self):
        turn = {"step": 1, "text": "", "tools": [{"tool": "set_plan", "result": {"saved": True}}],
                "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110}}
        with patch("bricksmith.workbench.agent_session.step_session",
                   side_effect=[turn, RuntimeError("plan-token sharing limit reached")]):
            result = run_session(Path("unused"), max_requests=3)
        self.assertEqual(result["requests"], 1)
        self.assertEqual(result["stopped_because"], "request_error")
        self.assertIn("sharing limit", result["error"])
        self.assertEqual(result["usage"]["total_tokens"], 110)

    def test_bounded_run_stops_after_three_lookup_only_turns(self):
        lookup = {"step": 1, "text": "", "tools": [{"tool": "render_reference", "result": {}}],
                  "usage": {"total_tokens": 100}}
        with patch("bricksmith.workbench.agent_session.step_session", return_value=lookup) as step:
            result = run_session(Path("unused"), max_requests=8)
        self.assertEqual(result["requests"], 3)
        self.assertEqual(result["stopped_because"], "research_stall")
        self.assertEqual(step.call_count, 3)

    def test_status_cli_compacts_events_but_keeps_full_audit_option(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A small shed")
            state["events"] = [{"step": 1, "tools": ["save_module"],
                                "usage": {"input_tokens": 200, "output_tokens": 50,
                                          "attribution": {"large_detail": "keep-for-audit"}}}]
            _save(directory, state)
            compact_out = StringIO()
            with patch("sys.argv", ["agent_session.py", "status", str(directory)]), redirect_stdout(compact_out):
                self.assertEqual(session_cli_main(), 0)
            compact = json.loads(compact_out.getvalue())
            self.assertEqual(compact["events_total"], 1)
            self.assertEqual(compact["events"][0]["input_tokens"], 200)
            self.assertNotIn("attribution", compact_out.getvalue())
            full_out = StringIO()
            with patch("sys.argv", ["agent_session.py", "status", str(directory), "--full-events"]), redirect_stdout(full_out):
                self.assertEqual(session_cli_main(), 0)
            self.assertIn("keep-for-audit", full_out.getvalue())

    def test_strict_tool_schemas_require_all_declared_properties(self):
        for function in TOOLS[0]["tools"]:
            parameters = function["parameters"]
            self.assertEqual(set(parameters["required"]), set(parameters["properties"]),
                             function["name"])

    def test_discard_module_preserves_audit_revision(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "first", "ldr": PLACEMENT})
            second = PLACEMENT.replace("0 8 0", "40 8 0")
            _tool(directory, state, "save_module", {"name": "second", "ldr": second})
            result = _tool(directory, state, "discard_module", {"name": "second"})
            self.assertEqual(result["discarded_module"], "second")
            self.assertIn(second, Path(result["saved_revision"]).read_text())
            self.assertEqual(state["module_order"], ["first"])
            self.assertNotIn(second, (directory / "build.ldr").read_text())

    def test_save_module_retains_provisional_disconnection_for_later_support(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            base = "1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat"
            first = _tool(directory, state, "save_module", {"name": "base", "ldr": base})
            self.assertTrue(first["validation"]["passed"])
            floating = "1 15 400 -24 0 1 0 0 0 1 0 0 0 1 3005.dat"
            result = _tool(directory, state, "save_module", {"name": "floating", "ldr": floating})
            self.assertTrue(result["provisional"])
            self.assertFalse(result["validation"]["passed"])
            self.assertIn("floating", state["module_order"])
            self.assertFalse(state["last_validation"]["passed"])
            self.assertIn(floating, (directory / "build.ldr").read_text())

    def test_recolor_module_lines_preserves_geometry_and_revision(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A compact display model")
            base = "0 Baseplate\n1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat"
            _tool(directory, state, "save_module", {"name": "base", "ldr": base})
            with self.assertRaisesRegex(ValueError, "not a current placement"):
                _tool(directory, state, "recolor_module_lines", {
                    "name": "base", "lines": [1], "color": 15})
            result = _tool(directory, state, "recolor_module_lines", {
                "name": "base", "lines": [2], "color": 15})
            self.assertTrue(result["validation"]["passed"])
            self.assertEqual(result["module_lines"], [2])
            self.assertIn("1 15 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat",
                          (directory / "modules" / "base.ldr").read_text())
            self.assertIn("1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat",
                          Path(result["previous_revisions"]["base"]).read_text())

    def test_inspect_build_region_returns_both_line_number_systems(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A compact shed")
            _tool(directory, state, "save_module", {"name": "base", "ldr":
                  "0 Base\n1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat"})
            result = _tool(directory, state, "inspect_build_region", {
                "x_min": -1, "x_max": 1, "z_min": -1, "z_max": 1,
                "h_min": 0, "h_max": 0, "offset": 0, "count": 40})
            self.assertEqual(result["total_matches"], 1)
            placement = result["placements"][0]
            self.assertEqual(placement["module"], "base")
            self.assertEqual(placement["module_line"], 2)
            self.assertEqual(placement["line"], 4)
            self.assertIn("3811.dat", placement["text"])

    def test_wall_run_opening_and_staggered_courses(self):
        run = {"axis": "x", "start": -80, "end": 80, "fixed": -70, "courses": 3,
               "openings": [{"start": -20, "end": 20, "from_course": 0, "to_course": 2}]}
        ldr = _wall_runs_ldr([run], -32, 28)
        self.assertIn("-32", ldr)
        self.assertIn("-56", ldr)
        self.assertIn("-80", ldr)
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "base", "ldr":
                  "1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat"})
            _tool(directory, state, "save_floor", {"name": "floor", "color": 70,
                  "y": -8, "rectangles": [{"x_min": -80, "x_max": 80,
                                            "z_min": -80, "z_max": 80}]})
            result = _tool(directory, state, "save_wall_runs", {"name": "front_wall",
                  "color": 28, "bottom_y": -32, "runs": [run]})
            self.assertNotIn("error", result)
            self.assertTrue(result["validation"]["checks"]["mesh_collision_free"])
        with self.assertRaisesRegex(ValueError, "overlap"):
            _wall_runs_ldr([run, run], -32, 28)

    def test_gable_tiers_narrow_and_stagger(self):
        ldr = _gable_ldr("x", -120, 120, -90, -184, 5, 1, 28)
        placements = [line.split() for line in ldr.splitlines() if line.startswith("1 ")]
        self.assertEqual(sorted({int(fields[3]) for fields in placements}),
                         [-280, -256, -232, -208, -184])
        self.assertLess(len(placements), 25)
        self.assertEqual(sum(fields[-1] == "3004.dat" for fields in placements) > 0, True)
        with self.assertRaisesRegex(ValueError, "positive narrowing"):
            _gable_ldr("x", -40, 40, -90, -184, 5, 1, 28)

    def test_stepped_roof_beams_cover_shed_and_pass_checks(self):
        roof = _stepped_roof_beams_ldr(-110, 110, -70, 110, -104, 6, 12, 72)
        caps = _roof_tile_caps_ldr(-110, 110, -70, 110, -104, 6, 12, 72)
        self.assertEqual(sum(line.startswith("1 ") for line in roof.splitlines()), 12)
        self.assertEqual(sum(line.startswith("1 ") for line in caps.splitlines()), 24)
        self.assertIn("1 72 -110 -128 20 0 0 1 0 1 0 -1 0 0 6112.dat", roof)
        self.assertIn("1 72 10 -248 20 0 0 1 0 1 0 -1 0 0 6112.dat", roof)
        self.assertIn("1 72 -110 -136 -20 0 0 1 0 1 0 -1 0 0 4162.dat", caps)
        self.assertIn("1 72 -110 -136 100 0 0 1 0 1 0 -1 0 0 2431.dat", caps)
        with self.assertRaisesRegex(ValueError, "two-stud ridge"):
            _stepped_roof_beams_ldr(-110, 90, -70, 110, -104, 6, 12, 72)
        with self.assertRaisesRegex(ValueError, "match both gable supports"):
            _stepped_roof_beams_ldr(-110, 110, -70, 110, -104, 6, 8, 72)
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A compact shed")
            _tool(directory, state, "save_module", {"name": "base", "ldr":
                  "1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat"})
            _tool(directory, state, "save_floor", {"name": "floor", "color": 28,
                  "y": -8, "rectangles": [{"x_min": -140, "x_max": 140,
                                           "z_min": -100, "z_max": 140}]})
            runs = [
                {"axis": "x", "start": -120, "end": 120, "fixed": -70,
                 "courses": 3, "openings": [{"start": -20, "end": 20,
                                              "from_course": 0, "to_course": 3}]},
                {"axis": "x", "start": -120, "end": 120, "fixed": 110,
                 "courses": 3, "openings": []},
                {"axis": "z", "start": -60, "end": 100, "fixed": -110,
                 "courses": 3, "openings": []},
                {"axis": "z", "start": -60, "end": 100, "fixed": 110,
                 "courses": 3, "openings": []},
            ]
            _tool(directory, state, "save_wall_runs", {"name": "walls", "color": 28,
                  "bottom_y": -32, "runs": runs})
            for name, fixed in (("front_gable", -70), ("rear_gable", 110)):
                result = _tool(directory, state, "save_gable", {"name": name,
                      "color": 28, "axis": "x", "start": -120, "end": 120,
                      "fixed": fixed, "bottom_y": -104, "courses": 6,
                      "inset_studs": 1})
                self.assertTrue(result["validation"]["passed"])
            result = _tool(directory, state, "save_stepped_roof_beams", {
                "name": "roof", "color": 72, "left_x": -110, "right_x": 110,
                "front_z": -70, "rear_z": 110, "gable_bottom_y": -104,
                "courses": 6, "beam_studs": 12})
            self.assertEqual(result["generated_roof_parts"], 12)
            self.assertTrue(result["validation"]["passed"])
            capped = _tool(directory, state, "save_roof_tile_caps", {
                "name": "roof_caps", "color": 72, "left_x": -110, "right_x": 110,
                "front_z": -70, "rear_z": 110, "gable_bottom_y": -104,
                "courses": 6, "beam_studs": 12})
            self.assertEqual(capped["generated_roof_cap_parts"], 24)
            self.assertTrue(capped["validation"]["passed"])

    def test_support_column_height_and_stud_phase(self):
        ldr = _support_column_ldr(-170, -30, -32, 9, 28, 15, True)
        placements = [line.split() for line in ldr.splitlines() if line.startswith("1 ")]
        self.assertEqual(len(placements), 10)
        self.assertEqual(placements[-2][3], "-224")
        self.assertEqual(placements[-1][3], "-232")
        self.assertEqual(placements[-1][-1], "3024.dat")
        with self.assertRaisesRegex(ValueError, "stud centers"):
            _support_column_ldr(-160, -30, -32, 9, 28, 15, True)
        wide = _support_column_ldr(-200, 60, -32, 8, 28, 15, True, 2)
        self.assertIn("3003.dat", wide)
        self.assertIn("3022.dat", wide)
        with self.assertRaisesRegex(ValueError, "2x2 origins"):
            _support_column_ldr(-190, 60, -32, 8, 28, 15, True, 2)

    def test_roof_seam_column_supports_two_adjacent_z_studs(self):
        ldr = _roof_seam_column_ldr(-170, 60, -32, 9, 28, 15)
        placements = [line.split() for line in ldr.splitlines() if line.startswith("1 ")]
        self.assertEqual(len(placements), 10)
        self.assertTrue(all(fields[5:14] == ["0", "0", "1", "0", "1", "0", "-1", "0", "0"]
                            for fields in placements))
        self.assertEqual(placements[-1][3], "-232")
        self.assertEqual(placements[-1][-1], "3023.dat")
        with self.assertRaisesRegex(ValueError, "stud-edge Z"):
            _roof_seam_column_ldr(-170, 70, -32, 9, 28, 15)

    def test_roof_seam_column_physically_stacks_on_floor(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "base", "ldr":
                  "1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat"})
            _tool(directory, state, "save_floor", {"name": "floor", "color": 70,
                  "y": -8, "rectangles": [{"x_min": -240, "x_max": -120,
                                           "z_min": 40, "z_max": 120}]})
            lower = _tool(directory, state, "save_support_column", {
                "name": "lower", "x": -200, "z": 60, "bottom_y": -32,
                "bricks": 8, "color": 28, "cap_color": 15,
                "cap_plate": True, "size_studs": 2})
            self.assertTrue(lower["validation"]["passed"])
            result = _tool(directory, state, "save_roof_seam_column", {
                "name": "seam", "x": -170, "z": 60, "bottom_y": -32,
                "bricks": 9, "color": 28, "cap_color": 15})
            self.assertTrue(result["validation"]["passed"])
            self.assertEqual(result["generated_column_parts"], 10)

    def test_save_module_rolls_back_collision_regression(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "first", "ldr": PLACEMENT})
            original = (directory / "build.ldr").read_text()
            result = _tool(directory, state, "save_module", {"name": "overlap", "ldr": PLACEMENT})
            self.assertIn("rolled back", result["error"])
            self.assertGreater(result["candidate_collisions"], result["before_collisions"])
            self.assertNotIn("overlap", state["module_order"])
            self.assertFalse((directory / "modules" / "overlap.ldr").exists())
            self.assertEqual((directory / "build.ldr").read_text(), original)

    def test_floor_tiler_covers_rectangles_without_intersections(self):
        rectangles = [{"x_min": -240, "x_max": 40, "z_min": -100, "z_max": 260},
                      {"x_min": 40, "x_max": 240, "z_min": -60, "z_max": 220},
                      {"x_min": -180, "x_max": -60, "z_min": -160, "z_max": -100}]
        ldr = _floor_ldr(rectangles, 0, 70)
        self.assertIn("3035.dat", ldr)
        self.assertLess(sum(line.startswith("1 ") for line in ldr.splitlines()), 60)
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "base", "ldr":
                  "1 2 0 8 0 1 0 0 0 1 0 0 0 1 3811.dat"})
            result = _tool(directory, state, "save_floor", {"name": "floor", "color": 70,
                                "y": 0, "rectangles": rectangles})
            self.assertEqual(result["generated_floor_parts"],
                             sum(line.startswith("1 ") for line in ldr.splitlines()))
            self.assertTrue(result["validation"]["checks"]["mesh_collision_free"])
        with self.assertRaisesRegex(ValueError, "must not overlap"):
            _floor_ldr(rectangles + [rectangles[0]], 0, 70)

    def test_floating_upper_floor_gets_support_hint(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "base", "ldr":
                  "1 2 0 0 0 1 0 0 0 1 0 0 0 1 3811.dat"})
            result = _tool(directory, state, "save_floor", {"name": "floating",
                  "color": 15, "y": -88, "rectangles": [
                      {"x_min": -40, "x_max": 40, "z_min": -40, "z_max": 40}]})
            self.assertFalse(result["validation"]["checks"]["actual_connectivity"])
            self.assertIn("stud-connect", result["floor_support_hint"])
            self.assertIn("floating", state["module_order"])

    def test_render_revisions_never_overwrite_a_prior_png(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            (directory / "renders").mkdir()
            first = _fresh_render_path(directory, "step-00-front_left")
            first.write_bytes(b"first")
            second = _fresh_render_path(directory, "step-00-front_left")
            self.assertEqual(second.name, "step-00-front_left-v2.png")
            second.write_bytes(b"second")
            self.assertEqual(_fresh_render_path(directory, "step-00-front_left").name,
                             "step-00-front_left-v3.png")
            self.assertEqual(first.read_bytes(), b"first")

    def test_reference_render_is_source_bound_and_queued(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            reference = SimpleNamespace(id="official_house", title="House",
                                        path=Path(root) / "house.ldr", sha256="abc", license="CC BY")
            with patch("bricksmith.workbench.agent_session.load_references", return_value=[reference]), \
                 patch("bricksmith.workbench.agent_session.render_ldr_to_png") as render:
                result = _tool(directory, state, "render_reference",
                               {"reference_id": "official_house", "view": "front_left"})
                self.assertEqual(result["sha256"], "abc")
                self.assertEqual(state["pending_images"], [result["image_path"]])
                render.assert_called_once()
                self.assertEqual(render.call_args.args[0], reference.path)
                with self.assertRaisesRegex(ValueError, "Unknown reference ID"):
                    _tool(directory, state, "render_reference",
                          {"reference_id": "invented", "view": "front_left"})

    def test_reference_render_reports_missing_mesh_parts(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            source = Path(root) / "house.ldr"
            source.write_text(PLACEMENT + "\n" + PLACEMENT.replace("3022.dat", "missing.dat") + "\n")
            reference = SimpleNamespace(id="house", title="House", path=source,
                                        sha256="abc", license=None)
            catalog = SimpleNamespace(stem_to_id={"3022": 3022})
            with patch("bricksmith.workbench.agent_session.load_references", return_value=[reference]), \
                 patch("bricksmith.workbench.agent_session.load_catalog", return_value=catalog), \
                 patch("bricksmith.workbench.agent_session.render_ldr_to_png",
                       side_effect=[KeyError("missing"), None]) as render:
                result = _tool(directory, state, "render_reference",
                               {"reference_id": "house", "view": "front_left"})
            self.assertEqual(render.call_count, 2)
            self.assertEqual(result["omitted_unsupported_parts"], {"missing": 1})
            self.assertNotIn("missing.dat", render.call_args.args[0].read_text())

    def test_queue_renders_uses_no_model_request(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT})
            from bricksmith.workbench.agent_session import _save
            _save(directory, state)
            with patch("bricksmith.workbench.agent_session.render_ldr_to_png") as render, \
                 patch("bricksmith.workbench.agent_session.respond") as respond:
                result = queue_renders(directory, ["front_left", "back_right"])
            self.assertEqual(render.call_count, 2)
            respond.assert_not_called()
            self.assertEqual(len(result["queued_images"]), 2)
            self.assertEqual(load_session(directory)["rendered_views"], ["front_left", "back_right"])
            with self.assertRaisesRegex(ValueError, "distinct"):
                queue_renders(directory, ["front_left", "front_left"])

    def test_clone_module_reuses_verified_geometry(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "front", "ldr": "0 course\n" + PLACEMENT})
            result = _tool(directory, state, "clone_module", {"source": "front", "name": "rear",
                                                                "dx": 0, "dy": 0, "dz": 220})
            self.assertEqual(result["cloned_from"], "front")
            self.assertEqual(result["total_parts"], 2)
            self.assertIn("1 15 0 8 220", (directory / "modules" / "rear.ldr").read_text())
            self.assertIn("0 course", (directory / "modules" / "rear.ldr").read_text())
            with self.assertRaisesRegex(ValueError, "new module"):
                _tool(directory, state, "clone_module", {"source": "front", "name": "rear",
                                                            "dx": 0, "dy": 0, "dz": 220})

    def test_move_lines_preserves_parts_and_checks_repair(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT})
            result = _tool(directory, state, "move_lines", {"lines": [3], "dx": 10, "dy": -8, "dz": 20})
            self.assertEqual(result["translation_groups"][0]["offset_ldu"], [10, -8, 20])
            self.assertIn("1 15 10 0 20", (directory / "modules" / "foundation.ldr").read_text())
            self.assertIn(PLACEMENT, Path(result["previous_revisions"]["foundation"]).read_text())
            self.assertIn("validation", result)
            with self.assertRaisesRegex(ValueError, "not a current assembled placement"):
                _tool(directory, state, "move_lines", {"lines": [2], "dx": 10, "dy": 0, "dz": 0})
            with self.assertRaisesRegex(ValueError, "distinct"):
                _tool(directory, state, "move_lines", {"lines": [3, 3], "dx": 10, "dy": 0, "dz": 0})

    def test_move_groups_applies_multiple_offsets_atomically(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            second = PLACEMENT.replace("0 8 0", "40 8 0")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT + "\n" + second})
            result = _tool(directory, state, "move_groups", {"groups": [
                {"lines": [3], "dx": 10, "dy": 0, "dz": 0},
                {"lines": [4], "dx": 20, "dy": 0, "dz": 20}]})
            self.assertEqual(result["edited_build_lines"], [3, 4])
            updated = (directory / "modules" / "foundation.ldr").read_text()
            self.assertIn("1 15 10 8 0", updated)
            self.assertIn("1 15 60 8 20", updated)
            with self.assertRaisesRegex(ValueError, "distinct"):
                _tool(directory, state, "move_groups", {"groups": [
                    {"lines": [3], "dx": 10, "dy": 0, "dz": 0},
                    {"lines": [3], "dx": 0, "dy": -8, "dz": 0}]})

    def test_regressive_move_is_rolled_back(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            second = PLACEMENT.replace("0 8 0", "40 8 0")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT + "\n" + second})
            original = (directory / "modules" / "foundation.ldr").read_text()
            result = _tool(directory, state, "move_lines", {"lines": [4], "dx": -40, "dy": 0, "dz": 0})
            self.assertIn("rolled back", result["error"])
            self.assertGreater(result["candidate_metrics"]["collisions"],
                               result["before_metrics"]["collisions"])
            self.assertEqual(original, (directory / "modules" / "foundation.ldr").read_text())

    def test_line_edit_repairs_module_and_preserves_revision(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            second = PLACEMENT.replace("0 8 0", "40 8 0")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT + "\n" + second})
            replacement = PLACEMENT.replace("0 8 0", "20 8 0")
            result = _tool(directory, state, "edit_lines", {"edits": [
                {"line": 4, "action": "replace", "text": replacement}]})
            self.assertEqual(result["edited_build_lines"], [4])
            self.assertIn(replacement, (directory / "modules" / "foundation.ldr").read_text())
            self.assertIn(second, Path(result["previous_revisions"]["foundation"]).read_text())
            with self.assertRaises(ValueError):
                _tool(directory, state, "edit_lines", {"edits": [
                    {"line": 2, "action": "delete", "text": ""}]})
            with self.assertRaisesRegex(ValueError, "Too many deletions"):
                _tool(directory, state, "edit_lines", {"edits": [
                    {"line": 3, "action": "delete", "text": ""} for _ in range(9)]})

    def test_camera_views_match_negative_z_front(self):
        self.assertLess(VIEWS["front_left"][0], VIEWS["front_right"][0])
        self.assertEqual(VIEWS["front_left"][0], 215)
        self.assertEqual(VIEWS["back_right"][0], 35)

    def test_reference_image_is_copied_and_sent_on_first_step(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "house.png"
            source.write_bytes(b"small-image-placeholder")
            directory = Path(root) / "session"
            start_session(directory, "Match this home's style", reference_image=source)
            source.unlink()
            with patch("bricksmith.workbench.agent_session.respond",
                       return_value={"output": []}) as mock:
                step_session(directory)
            history = mock.call_args.args[2]
            self.assertEqual(history[-1]["content"][1]["type"], "input_image")
            self.assertTrue(history[-1]["content"][1]["image_url"].startswith("data:image/png;base64,"))

    def test_operator_message_reaches_model_and_saved_history(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            start_session(directory, "A detailed house")
            with patch("bricksmith.workbench.agent_session.respond", return_value={"output": []}) as mock:
                step_session(directory, message="Repair the roof before adding trees.")
            self.assertEqual(mock.call_args.args[2][-1]["content"],
                             "Repair the roof before adding trees.")
            self.assertEqual(load_session(directory)["history"][-1]["content"],
                             "Repair the roof before adding trees.")

    def test_array_expands_in_ldu_and_rejects_oversize(self):
        ldr = _expand_array(PLACEMENT, [2, 2, 1],
                            [[20, 0, 0], [0, -24, 0], [0, 0, 0]])
        self.assertEqual(len(ldr.splitlines()), 4)
        self.assertIn("1 15 20 -16 0 ", ldr)
        with self.assertRaises(ValueError):
            _expand_array(PLACEMENT, [20, 20, 1],
                          [[20, 0, 0], [0, -24, 0], [0, 0, 0]])
        commented = _expand_array("0 Upper wall course\n" + PLACEMENT, [1, 2, 1],
                                  [[0, 0, 0], [0, -24, 0], [0, 0, 0]])
        self.assertEqual(len(commented.splitlines()), 2)

    def test_start_is_offline_and_persists_brief(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            start_session(directory, "A detailed house", target_pieces="400-800")
            state = load_session(directory)
            self.assertEqual(state["step"], 0)
            self.assertIn("A detailed house", state["history"][0]["content"])
            self.assertEqual(state["module_order"], [])

    def test_one_response_executes_and_replays_tool_results(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            start_session(directory, "A detailed house")
            response = {"output": [
                {"type": "function_call", "name": "bricksmith.save_module", "call_id": "call_1",
                 "arguments": json.dumps({"name": "foundation", "ldr": PLACEMENT})},
                {"type": "function_call", "name": "bricksmith.save_module", "call_id": "call_2",
                 "arguments": json.dumps({"name": "../escape", "ldr": PLACEMENT})},
            ], "usage": {"input_tokens": 1, "output_tokens": 1}}
            with patch("bricksmith.workbench.agent_session.respond", return_value=response) as mock:
                result = step_session(directory)
            self.assertEqual(mock.call_count, 1)
            self.assertEqual(result["step"], 1)
            self.assertEqual(result["tools"][0]["result"]["total_parts"], 1)
            self.assertIn("validation", result["tools"][0]["result"])
            self.assertTrue((directory / "checks" / "step-01-foundation.json").is_file())
            self.assertIn("error", result["tools"][1]["result"])
            self.assertTrue((directory / "build.ldr").exists())
            state = load_session(directory)
            self.assertEqual(state["module_order"], ["foundation"])
            self.assertEqual(state["history"][-1]["call_id"], "call_2")

    def test_excess_calls_return_errors_and_preserve_history(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            start_session(directory, "A detailed house")
            response = {"output": [
                {"type": "function_call", "name": "bricksmith.check", "call_id": f"call_{i}",
                 "arguments": "{}"} for i in range(9)
            ]}
            with patch("bricksmith.workbench.agent_session.respond", return_value=response):
                result = step_session(directory)
            self.assertEqual(result["step"], 1)
            self.assertIn("limit", result["tools"][-1]["result"]["error"])
            self.assertEqual(len(load_session(directory)["history"]), 20)

    def test_old_turns_are_compacted_but_saved_plan_survives(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            start_session(directory, "A detailed house")
            responses = [
                {"output": [{"type": "function_call", "name": "bricksmith.set_plan",
                             "call_id": "p1", "arguments": json.dumps({"plan": "A 16 by 12 stud two-story house with a pitched roof and porch."})}]},
                {"output": [{"type": "message", "content": [{"type": "output_text", "text": "Moving to foundation."}]}]},
                {"output": []},
                {"output": []},
            ]
            with patch("bricksmith.workbench.agent_session.respond", side_effect=responses) as mock:
                step_session(directory)
                step_session(directory)
                step_session(directory)
                third_input = mock.call_args.args[2]
                self.assertTrue(any(item.get("call_id") == "p1" for item in third_input))
                step_session(directory)
            self.assertIn("save a substantial first module", mock.call_args_list[1].args[2][1]["content"])
            latest_input = mock.call_args.args[2]
            self.assertIn("16 by 12", latest_input[1]["content"])
            self.assertFalse(any(item.get("call_id") == "p1" for item in latest_input))
            self.assertEqual(load_session(directory)["step"], 4)

    def test_status_includes_top_geometry_without_read_module(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            start_session(directory, "A detailed house")
            response = {"output": [{"type": "function_call", "name": "bricksmith.save_module",
                                    "call_id": "save1", "arguments": json.dumps({"name": "foundation", "ldr": PLACEMENT})}]}
            with patch("bricksmith.workbench.agent_session.respond", return_value=response):
                step_session(directory)
            with patch("bricksmith.workbench.agent_session.respond", return_value={"output": []}) as mock:
                step_session(directory)
            status = mock.call_args.args[2][1]["content"]
            self.assertIn('"top_y_ldu":8.0', status)
            self.assertIn(PLACEMENT, status)

    def test_status_keeps_late_modules_after_large_geometry_digest(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house")
            names = [f"architectural_feature_{number:02d}" for number in range(30)]
            for number, name in enumerate(names):
                (directory / "modules" / f"{name}.ldr").write_text(
                    f"1 28 {number * 20} -32 0 1 0 0 0 1 0 0 0 1 3005.dat\n",
                    encoding="utf-8")
            state["module_order"] = names
            status = _session_status(directory, state)
            self.assertGreater(status.index("Geometry digest:"), 0)
            self.assertIn('"module":"architectural_feature_29"', status)
            self.assertIn('"top_y_ldu":-32.0', status)

    def test_submit_design_rejects_unchecked_or_unreviewed_build(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house", target_pieces="1-2")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT})
            args = {"visual_review": "A carefully reviewed small object with appropriate scale and silhouette. " * 3,
                    "signature_features": ["A", "B", "C"], "known_limits": "Not tested for assembly order."}
            with self.assertRaisesRegex(ValueError, "construction checks fail"):
                _tool(directory, state, "submit_design", args)
            digest = hashlib.sha256((directory / "build.ldr").read_bytes()).hexdigest()
            state["inspected_view_digests"] = {"front_left": digest, "front_right": digest}
            state["visual_revision_checkpoint"] = {"geometry_digest": "prior-design"}
            with patch("bricksmith.workbench.agent_session._check_and_record",
                       return_value={"passed": True}):
                result = _tool(directory, state, "submit_design", args)
            self.assertTrue(result["accepted"])
            self.assertEqual(result["pieces"], 1)

    def test_submit_design_enforces_full_piece_range(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "A detailed house", target_pieces="2-3")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT})
            args = {"visual_review": "A carefully reviewed miniature with a clear design and well considered finish. " * 3,
                    "signature_features": ["A", "B", "C"], "known_limits": "Assembly order not tested."}
            with patch("bricksmith.workbench.agent_session._check_and_record", return_value={"passed": True}):
                with self.assertRaisesRegex(ValueError, "below the 2-part target minimum"):
                    _tool(directory, state, "submit_design", args)
                state["target_pieces"] = "1-0"
                with self.assertRaisesRegex(ValueError, "above the 0-part target maximum"):
                    _tool(directory, state, "submit_design", args)

    def test_visual_review_requires_a_real_revision_and_fresh_views(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "Detailed house", target_pieces="1-2")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT})
            initial_digest = hashlib.sha256((directory / "build.ldr").read_bytes()).hexdigest()
            state["inspected_view_digests"] = {"front_left": initial_digest,
                                                "front_right": initial_digest}
            review_args = {
                "visual_strengths": "The low roof and front entry have a coherent silhouette.",
                "largest_gap": "The front elevation lacks a clearly articulated entrance.",
                "revision_plan": "Add a projecting portal and compare the fresh frontal views.",
            }
            self.assertTrue(_tool(directory, state, "review_renders", review_args)["recorded"])
            submit_args = {
                "visual_review": "The entrance is now a distinct part of the front elevation. " * 3,
                "signature_features": ["Portal", "Roof", "Garden"],
                "known_limits": "Assembly sequence remains unverified.",
            }
            with patch("bricksmith.workbench.agent_session._check_and_record",
                       return_value={"passed": True}):
                with self.assertRaisesRegex(ValueError, "Revise actual LDraw placements"):
                    _tool(directory, state, "submit_design", submit_args)
            _tool(directory, state, "save_module", {"name": "portal", "ldr":
                  "1 15 80 8 0 1 0 0 0 1 0 0 0 1 3022.dat"})
            with patch("bricksmith.workbench.agent_session._check_and_record",
                       return_value={"passed": True}):
                with self.assertRaisesRegex(ValueError, "current geometry"):
                    _tool(directory, state, "submit_design", submit_args)
                fresh_digest = hashlib.sha256((directory / "build.ldr").read_bytes()).hexdigest()
                state["inspected_view_digests"] = {"front_left": fresh_digest,
                                                    "front_right": fresh_digest}
                self.assertTrue(_tool(directory, state, "submit_design", submit_args)["accepted"])

    def test_submission_rejects_stale_or_undelivered_renders(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "Detailed house", target_pieces="1-2")
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT})
            args = {"visual_review": "A carefully reviewed small object with appropriate scale and silhouette. " * 3,
                    "signature_features": ["A", "B", "C"], "known_limits": "No assembly order."}
            old_digest = hashlib.sha256((directory / "build.ldr").read_bytes()).hexdigest()
            state["rendered_views"] = ["front_left", "front_right"]
            state["pending_render_views"] = {"front_left": old_digest, "front_right": old_digest}
            with patch("bricksmith.workbench.agent_session._check_and_record", return_value={"passed": True}):
                with self.assertRaisesRegex(ValueError, "current geometry"):
                    _tool(directory, state, "submit_design", args)
            state["inspected_view_digests"] = dict(state["pending_render_views"])
            _tool(directory, state, "save_module", {"name": "detail", "ldr":
                  "1 15 80 8 0 1 0 0 0 1 0 0 0 1 3022.dat"})
            with patch("bricksmith.workbench.agent_session._check_and_record", return_value={"passed": True}):
                with self.assertRaisesRegex(ValueError, "current geometry"):
                    _tool(directory, state, "submit_design", args)

    def test_step_replaces_queued_stale_build_preview(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "Detailed house")
            state["step"] = 1  # Avoid unrelated first-turn reference prefetch.
            _tool(directory, state, "save_module", {"name": "foundation", "ldr": PLACEMENT})

            def fake_render(_source, destination, **_kwargs):
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"test image")

            with patch("bricksmith.workbench.agent_session.render_ldr_to_png", side_effect=fake_render):
                old = _tool(directory, state, "render", {"view": "back_right"})["image_path"]
                _tool(directory, state, "save_module", {"name": "detail", "ldr":
                      "1 15 80 8 0 1 0 0 0 1 0 0 0 1 3022.dat"})
                _save(directory, state)
                with patch("bricksmith.workbench.agent_session.respond", return_value={"output": []}) as respond:
                    step_session(directory)
            request = respond.call_args.args[2]
            self.assertNotIn(Path(old).stem, str(request))
            self.assertIn("front_left-auto", str(request))
            saved = load_session(directory)
            self.assertNotIn("back_right", saved["inspected_view_digests"])
            self.assertIn("front_left", saved["inspected_view_digests"])

    def test_near_target_step_delivers_two_current_images_without_render_tool(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root) / "session"
            state = start_session(directory, "Large architectural house",
                                  target_pieces="200-350")
            state["step"] = 1
            state["module_order"] = ["foundation"]
            lines = [f"1 15 {index * 20} -8 0 1 0 0 0 1 0 0 0 1 3022.dat"
                     for index in range(200)]
            (directory / "modules" / "foundation.ldr").write_text(
                "\n".join(lines) + "\n", encoding="utf-8")
            path, count = _assemble(directory, state)
            self.assertEqual(count, 200)
            state["checked_digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
            state["last_feedback"] = {"passed": True, "checks": {}, "errors": []}
            _save(directory, state)

            def fake_render(_source, destination, **_kwargs):
                destination.write_bytes(b"test image")

            with patch("bricksmith.workbench.agent_session.render_ldr_to_png",
                       side_effect=fake_render) as render, \
                 patch("bricksmith.workbench.agent_session.respond",
                       return_value={"output": []}) as respond:
                step_session(directory)
            self.assertEqual(render.call_count, 2)
            request = respond.call_args.args[2]
            image_items = [block for item in request
                           for block in item.get("content", [])
                           if isinstance(block, dict) and block.get("type") == "input_image"]
            self.assertEqual(len(image_items), 2)
            self.assertEqual(set(load_session(directory)["inspected_view_digests"]),
                             {"front_left", "front_right"})


if __name__ == "__main__":
    unittest.main()
