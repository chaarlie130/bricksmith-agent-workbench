"""Resumable, one-model-request-per-step BrickSmith design session."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path

from bricksmith.workbench.chatgpt_plan import respond
from bricksmith.workbench.alignment import analyze_alignment
from bricksmith.workbench.feedback import check_model
from bricksmith.workbench.prompt import load_system_prompt
from bricksmith.workbench.references import DEFAULT_CORPUS, inspect_model, inspect_reference_region, load_references, search, study_reference
from bricksmith.workbench.parts import inspect_part, search_parts
from bricksmith.workbench.omr import LICENSE_NOTE as OMR_LICENSE_NOTE, fetch_omr_file, search_omr
from bricksmith.rendering.rasterizer import render_ldr_to_png
from bricksmith.physics.validator import load_catalog

SCHEMA = "bricksmith-agent-session-v1"
READ_ONLY_V2_SCHEMA = "bricksmith-agent-session-v2"
MAX_PARTS = 1500
MAX_MODULE_PARTS = 250
MAX_TOOLS_PER_STEP = 8
VIEWS = {"front_left": (215, 28), "front_right": (325, 28),
         "back_left": (145, 28), "back_right": (35, 28), "top": (215, 70)}
RESEARCH_TOOLS = {"search", "inspect", "study_reference", "render_reference", "inspect_reference_region",
                  "inspect_build_region", "search_parts", "inspect_part", "inspect_alignment",
                  "search_omr_sets", "fetch_omr_set"}
RESEARCH_NUDGE = (
    "You have spent two model turns on lookup tools without modifying the build. "
    "Use the parts and geometry already inspected to build a coherent feature "
    "that honors the current brief's appearance and piece-count requirements, "
    "then read construction and rendered feedback. A few trivial posts do not "
    "satisfy a requested display feature. If a specific missing fact truly blocks "
    "placement, name it explicitly; do not keep refining synonym searches for "
    "optional details."
)


def _compact_study(result: dict) -> dict:
    rows = []
    for p in result["placements"][:40]:
        matrix = p["matrix"]
        identity = [1, 0, 0, 0, 1, 0, 0, 0, 1]
        rotation = "r0" if matrix == identity else "m(" + ",".join(str(v) for v in matrix) + ")"
        rows.append(f"L{p['line']} @h={p['h_plates']} {p['part_id']} c{p['color']} x={p['x_studs']} z={p['z_studs']} {rotation}")
    return {"reference_id": result["reference_id"], "sha256": result["sha256"],
            "license": result.get("license"), "focus": result["focus"],
            "piece_count": result["piece_count"], "origin_extent_studs": result.get("origin_extent_studs"),
            "height_layers": ", ".join(f"{layer['h_plates']}:{layer['parts']}" for layer in result.get("height_layers", [])),
            "placements": rows,
            "note": "Rows are source line, origin height in plates, part, LDraw colour, x/z in studs, orientation. Special parts may not have top-face origins."}


def _compact_history_item(item: dict) -> dict:
    if item.get("type") != "function_call_output":
        return item
    try:
        value = json.loads(item["output"])
    except (KeyError, ValueError, TypeError):
        return item
    if isinstance(value, dict) and "height_layers" in value and "placements" in value:
        if value["placements"] and isinstance(value["placements"][0], dict):
            value = _compact_study(value)
    elif isinstance(value, dict) and "excerpt" in value and len(value["excerpt"]) > 40:
        value["excerpt"] = value["excerpt"][:40]
        value["note"] = "Earlier raw excerpt truncated in replay; use study_reference or inspect again if needed."
    return {**item, "output": json.dumps(value, separators=(",", ":"))}


def _starter_reference_pack(brief: str) -> dict:
    """Prefetch bounded, provenance-bearing construction context locally."""
    corpus = load_references(DEFAULT_CORPUS)
    hits = search(corpus, brief, limit=20)
    subjects = ("house", "shed", "cathedral", "chapel", "bridge", "tower", "church", "castle")
    subject = next((word for word in subjects if re.search(rf"\b{word}\b", brief.lower())), None)
    styles = ("modern", "traditional", "victorian", "gothic", "classical", "roman")
    style = next((word for word in styles if re.search(rf"\b{word}\b", brief.lower())), None)
    eligible = [hit for hit in hits if hit["matched_query_terms"] and
                (not subject or re.search(rf"\b{subject}\b",
                                          f"{hit['title']} {hit['description']}".lower()))]
    if subject == "house":
        eligible = [hit for hit in eligible if "opera house" not in hit["title"].lower()]
    styled = [hit for hit in eligible if style and
              re.search(rf"\b{style}\b", f"{hit['title']} {hit['description']}".lower())]
    if styled:
        eligible = styled
    chosen: list[tuple[dict, str]] = []
    seen: set[str] = set()

    def add_first(candidates: list[dict], role: str, *, minimum_parts: int = 0) -> None:
        for hit in candidates:
            if hit["id"] not in seen and hit["piece_count"] >= minimum_parts:
                chosen.append((hit, role))
                seen.add(hit["id"])
                return

    # Prefer a complete architecture example over a tiny historical vignette
    # whose title happens to have a perfect lexical match.
    add_first(eligible, "subject and style", minimum_parts=200)
    if not chosen:
        add_first(eligible, "subject and style")
    if subject == "house" and style == "modern":
        add_first(search(corpus, "modern museum", limit=5), "modern massing", minimum_parts=200)
    elif subject == "house" and style == "traditional":
        add_first(search(corpus, "traditional cottage", limit=8), "domestic roof and facade", minimum_parts=200)
    else:
        add_first(eligible, "alternate construction", minimum_parts=200)
    if re.search(r"\b(hillside|hill|hilly|terrain|cliff|sloped site|stepped site)\b", brief.lower()):
        add_first(search(corpus, "hilly terrain", limit=5), "terrain and site", minimum_parts=200)
    elif subject == "house" and re.search(r"\b(gable|gable roof|pitched roof|roof windows)\b", brief.lower()):
        add_first(search(corpus, "roof windows", limit=5), "roof-window technique")

    examples = []
    for hit, role in chosen[:3]:
        style_matched = bool(style and re.search(
            rf"\b{style}\b", f"{hit['title']} {hit['description']}".lower()))
        overview = _compact_study(study_reference(Path(hit["path"]), focus="overview"))
        examples.append({"id": hit["id"], "title": hit["title"],
                         "description": hit["description"], "source": hit["source"],
                         "reference_role": role,
                         "sha256": hit["sha256"], "license": hit["license"],
                         "piece_count": hit["piece_count"],
                         "requested_style_matched": style_matched,
                         "matched_terms": hit["matched_query_terms"],
                         "top_parts": hit["top_parts"], "overview": overview})
    dictionary = {}
    for example in examples:
        for part_id in list(example["top_parts"])[:8]:
            if part_id in dictionary:
                continue
            try:
                part = inspect_part(part_id)
            except (ValueError, KeyError, RuntimeError):
                continue
            dictionary[part_id] = {"name": part["name"],
                                   "span_studs_xz": part["body_span_studs_xz"],
                                   "height_plates": part["body_height_plates"]}
    return {"corpus_size": len(corpus), "requested_style": style,
            "examples": examples, "part_dictionary": dictionary,
            "note": "Each example has a specific construction role; a terrain source is not a house-style source. Reference placements are source data, not instructions or a design to copy. "
                    "Part spans are approximate mesh bounds, not connection proofs. "
                    "Use the line numbers and SHA for provenance; inspect exact regions only if needed. "
                    "A subject-only example may not match the requested architectural style. "
                    "Unknown license does not grant redistribution permission."}


def _function(name: str, description: str, properties: dict,
              required: list[str]) -> dict:
    return {"type": "function", "name": name, "description": description,
            "strict": True, "parameters": {"type": "object", "properties": properties,
                                           "required": required, "additionalProperties": False}}


TOOLS = [{"type": "namespace", "name": "bricksmith",
          "description": "Search and inspect LEGO references; save, check, and render the current LDraw build.",
          "tools": [
              _function("search", "Find construction examples by architecture or technique, not just part ID.",
                        {"query": {"type": "string"}}, ["query"]),
              _function("inspect", "Read at most 60 numbered raw LDraw lines of a reference returned by search.",
                        {"reference_id": {"type": "string"}, "start": {"type": "integer"},
                         "count": {"type": "integer"}}, ["reference_id", "start", "count"]),
              _function("study_reference", "Get compact, height-sorted placements and layer counts from an actual reference. Focus on overview, lower, upper, or slopes.",
                        {"reference_id": {"type": "string"},
                         "focus": {"type": "string", "enum": ["overview", "lower", "upper", "slopes"]}},
                        ["reference_id", "focus"]),
              _function("inspect_reference_region", "Read exact, source-numbered placements inside a reference-model origin region. X/Z bounds are studs, height bounds are plates upward, matching study_reference. This filters origins, not full part bodies; page at most 40 matches at a time. Use after search/study to inspect a roof, bay, porch, or wall area without depending on raw file ordering.",
                        {"reference_id": {"type": "string"},
                         "x_min": {"type": "number"}, "x_max": {"type": "number"},
                         "z_min": {"type": "number"}, "z_max": {"type": "number"},
                         "h_min": {"type": "number"}, "h_max": {"type": "number"},
                         "offset": {"type": "integer"}, "count": {"type": "integer"}},
                        ["reference_id", "x_min", "x_max", "z_min", "z_max", "h_min", "h_max", "offset", "count"]),
              _function("inspect_build_region", "Read current assembled placements by an origin region; include both build.ldr line and module-local line numbers for targeted edits or recoloring. X/Z are studs and height is plates upward. Page at most 40 matches; origin filtering does not include full part bodies.",
                        {"x_min": {"type": "number"}, "x_max": {"type": "number"},
                         "z_min": {"type": "number"}, "z_max": {"type": "number"},
                         "h_min": {"type": "number"}, "h_max": {"type": "number"},
                         "offset": {"type": "integer"}, "count": {"type": "integer"}},
                        ["x_min", "x_max", "z_min", "z_max", "h_min", "h_max", "offset", "count"]),
              _function("render_reference", "Render a searched real-set reference for visual study; the image appears in your next turn. Do not copy the set as your original design.",
                        {"reference_id": {"type": "string"},
                         "view": {"type": "string", "enum": ["front_left", "front_right", "back_left", "back_right", "top"]}},
                        ["reference_id", "view"]),
              _function("search_parts", "Find real parts by name, e.g. slope brick, hinge, lattice fence.",
                        {"query": {"type": "string"}}, ["query"]),
              _function("search_omr_sets", "Search the live LDraw Official Model Repository "
                        "(library.ldraw.org) for real LEGO sets by name or keyword; covers most but "
                        "not every officially released set. Returns model numbers to fetch with "
                        "fetch_omr_set.",
                        {"query": {"type": "string"}}, ["query"]),
              _function("fetch_omr_set", "Fetch the raw LDraw file for an OMR set by model number "
                        "(e.g. '21006-1', as returned by search_omr_sets). This is a real "
                        "third-party design with unverified licensing -- reference data for study, "
                        "not permission to copy verbatim into a submitted design.",
                        {"model_number": {"type": "string"}}, ["model_number"]),
              _function("inspect_part", "Get verified local LDraw mesh bounds and origin offsets for a part ID.",
                        {"part_id": {"type": "string"}}, ["part_id"]),
              _function("inspect_alignment", "For up to 30 current assembled placement lines, count matching underside holes on other parts' studs and suggest small XY shifts. Diagnostic only; also check collisions.",
                        {"lines": {"type": "array", "items": {"type": "integer"}}}, ["lines"]),
              _function("set_plan", "Save a concise architectural plan and current decisions for later steps. Must be 50-3000 characters; keep coordinates and silhouette priorities, omit repeated prose.",
                        {"plan": {"type": "string"}}, ["plan"]),
              _function("save_module", "Replace one named build module with LDraw type-0/type-1 lines. In transaction workspaces this replaces direct parts with fresh stable IDs (delete/add); it does not infer identity from line order or coordinates. "
                        "Keep modules focused so repairs do not rewrite the entire building. "
                        "A new floor may be saved provisionally before its supports; add supports next. "
                        "New collisions or ground violations roll back, and final submission requires all checks pass.",
                        {"name": {"type": "string"}, "ldr": {"type": "string"}}, ["name", "ldr"]),
              _function("clone_module", "Copy a verified leaf module into a new module with an LDU translation; creates fresh stable instance IDs while preserving catalog part IDs, colors, and orientations, and records derived_from. Useful for symmetric front/rear construction.",
                        {"source": {"type": "string"}, "name": {"type": "string"},
                         "dx": {"type": "integer"}, "dy": {"type": "integer"},
                         "dz": {"type": "integer"}}, ["source", "name", "dx", "dy", "dz"]),
              _function("discard_module", "Remove one failed saved module while preserving an audit revision, then reassemble and recheck the remaining build. Use when a module is too broken to repair in place.",
                        {"name": {"type": "string"}}, ["name"]),
              _function("read_module", "Read up to 60 numbered lines from one saved module before revising it.",
                        {"name": {"type": "string"}, "start": {"type": "integer"},
                         "count": {"type": "integer"}}, ["name", "start", "count"]),
              _function("recolor_module_lines", "Change only the LDraw color of 1-30 existing placements in one saved module. Lines are the module-local numbers returned by read_module, not assembled build.ldr line numbers. Preserves part, rotation, and coordinates; saves an audit revision and rechecks.",
                        {"name": {"type": "string"},
                         "lines": {"type": "array", "items": {"type": "integer"}},
                         "color": {"type": "integer"}}, ["name", "lines", "color"]),
              _function("edit_lines", "Replace or delete specific assembled build.ldr placement lines from checker feedback; no whole-module rewrite needed.",
                        {"edits": {"type": "array", "items": {"type": "object",
                            "properties": {"line": {"type": "integer"},
                                           "action": {"type": "string", "enum": ["replace", "delete"]},
                                           "text": {"type": "string"}},
                            "required": ["line", "action", "text"], "additionalProperties": False}}},
                        ["edits"]),
              _function("move_lines", "Translate existing assembled placement lines in LDU, preserving parts, colors, and rotations. Use for coordinate/parity repairs; lines must be current build.ldr numbers.",
                        {"lines": {"type": "array", "items": {"type": "integer"}},
                         "dx": {"type": "integer"}, "dy": {"type": "integer"},
                         "dz": {"type": "integer"}}, ["lines", "dx", "dy", "dz"]),
              _function("move_groups", "Atomically translate multiple groups of current assembled placement lines by different LDU offsets in one call; preserves every part and rechecks once.",
                        {"groups": {"type": "array", "items": {"type": "object", "properties": {
                            "lines": {"type": "array", "items": {"type": "integer"}},
                            "dx": {"type": "integer"}, "dy": {"type": "integer"},
                            "dz": {"type": "integer"}},
                            "required": ["lines", "dx", "dy", "dz"], "additionalProperties": False}}}, ["groups"]),
              _function("save_array", "Save a module by translating a small LDraw template on a 3D lattice. "
                        "Coordinates and strides are LDU; negative Y goes up. No automatic overlap or opening removal.",
                        {"name": {"type": "string"}, "template": {"type": "string"},
                         "counts": {"type": "array", "items": {"type": "integer"}},
                         "step_x": {"type": "array", "items": {"type": "number"}},
                         "step_y": {"type": "array", "items": {"type": "number"}},
                         "step_z": {"type": "array", "items": {"type": "number"}}},
                        ["name", "template", "counts", "step_x", "step_y", "step_z"]),
              _function("save_floor", "Tile non-overlapping rectangular footprints with real plates. Bounds are stud-edge LDU coordinates and may touch but not overlap; y is the top-face LDraw coordinate. Saves one module and checks it.",
                        {"name": {"type": "string"}, "color": {"type": "integer"},
                         "y": {"type": "integer"},
                         "rectangles": {"type": "array", "items": {"type": "object",
                             "properties": {"x_min": {"type": "integer"}, "x_max": {"type": "integer"},
                                            "z_min": {"type": "integer"}, "z_max": {"type": "integer"}},
                             "required": ["x_min", "x_max", "z_min", "z_max"],
                             "additionalProperties": False}}},
                        ["name", "color", "y", "rectangles"]),
              _function("save_wall_runs", "Generate staggered 1-stud-thick brick wall runs, with course-specific window/door gaps. start/end are stud-edge LDU, fixed is the other axis stud-center LDU; bottom_y is the first brick top (typically -32 above a floor plate at -8). Saves one module and checks it.",
                        {"name": {"type": "string"}, "color": {"type": "integer"},
                         "bottom_y": {"type": "integer"},
                         "runs": {"type": "array", "items": {"type": "object",
                             "properties": {"axis": {"type": "string", "enum": ["x", "z"]},
                                            "start": {"type": "integer"}, "end": {"type": "integer"},
                                            "fixed": {"type": "integer"}, "courses": {"type": "integer"},
                                            "openings": {"type": "array", "items": {"type": "object",
                                                "properties": {"start": {"type": "integer"},
                                                               "end": {"type": "integer"},
                                                               "from_course": {"type": "integer"},
                                                               "to_course": {"type": "integer"}},
                                                "required": ["start", "end", "from_course", "to_course"],
                                                "additionalProperties": False}}},
                             "required": ["axis", "start", "end", "fixed", "courses", "openings"],
                             "additionalProperties": False}}},
                        ["name", "color", "bottom_y", "runs"]),
              _function("save_gable", "Generate a stepped triangular one-stud-thick brick gable end over an already supported lintel. start/end are stud-edge LDU, fixed is the other axis stud center; bottom_y is first brick origin, then each row rises 24 LDU and narrows by inset_studs on both ends. This builds gable masonry, not the sloped roof. Saves and checks one module.",
                        {"name": {"type": "string"}, "color": {"type": "integer"},
                         "axis": {"type": "string", "enum": ["x", "z"]},
                         "start": {"type": "integer"}, "end": {"type": "integer"},
                         "fixed": {"type": "integer"}, "bottom_y": {"type": "integer"},
                         "courses": {"type": "integer"}, "inset_studs": {"type": "integer"}},
                        ["name", "color", "axis", "start", "end", "fixed", "bottom_y", "courses", "inset_studs"]),
              _function("save_stepped_roof_beams", "Cover a small X-width gabled building with two complete, visibly stepped roof planes made from real 1xN longitudinal bricks. Each beam rests on matching front/rear gable studs; this is not a smooth slope and the checker does not test bending strength. Both gables must already have `courses` rows, inset one stud per row, at front_z/rear_z. left_x/right_x are the outermost gable stud centers and gable_bottom_y is the first gable brick origin. beam_studs is even 4/6/8/10/12 and must span both gables with at most a two-stud overhang. Saves and checks one module.",
                        {"name": {"type": "string"}, "color": {"type": "integer"},
                         "left_x": {"type": "integer"}, "right_x": {"type": "integer"},
                         "front_z": {"type": "integer"}, "rear_z": {"type": "integer"},
                         "gable_bottom_y": {"type": "integer"},
                         "courses": {"type": "integer"},
                         "beam_studs": {"type": "integer", "enum": [4, 6, 8, 10, 12]}},
                        ["name", "color", "left_x", "right_x", "front_z", "rear_z", "gable_bottom_y", "courses", "beam_studs"]),
              _function("save_roof_tile_caps", "Cover every stud on a previously saved stepped-roof beam assembly with aligned real 1x8/1x4/1x2 tiles. Pass exactly the same geometry as save_stepped_roof_beams; this adds only a smooth tile surface, not beams or support. Saves and checks one module; do not use on an absent or failed roof.",
                        {"name": {"type": "string"}, "color": {"type": "integer"},
                         "left_x": {"type": "integer"}, "right_x": {"type": "integer"},
                         "front_z": {"type": "integer"}, "rear_z": {"type": "integer"},
                         "gable_bottom_y": {"type": "integer"},
                         "courses": {"type": "integer"},
                         "beam_studs": {"type": "integer", "enum": [4, 6, 8, 10, 12]}},
                        ["name", "color", "left_x", "right_x", "front_z", "rear_z", "gable_bottom_y", "courses", "beam_studs"]),
              _function("save_support_column", "Stack 1x1 or 2x2 bricks on supported studs, optionally capped by a matching plate. size_studs=1 uses odd-10 stud-center X/Z; size_studs=2 uses even-20 origins and can support adjacent roof segments across a seam. bottom_y is first brick origin; each higher brick rises 24 LDU. Saves and checks one module.",
                        {"name": {"type": "string"}, "x": {"type": "integer"},
                         "z": {"type": "integer"}, "bottom_y": {"type": "integer"},
                         "bricks": {"type": "integer"}, "color": {"type": "integer"},
                         "cap_color": {"type": "integer"}, "cap_plate": {"type": "boolean"},
                         "size_studs": {"type": "integer", "enum": [1, 2]}},
                        ["name", "x", "z", "bottom_y", "bricks", "color", "cap_color", "cap_plate", "size_studs"]),
              _function("save_roof_seam_column", "Stack 1x2 bricks lengthwise along Z at a roof-segment seam, capped by a matching plate. X is a stud center (odd tens), Z is a stud edge (multiple of 20); the two top studs support the rear of one 4-stud roof slope and front of the next. bottom_y is first brick origin. Saves and checks one module.",
                        {"name": {"type": "string"}, "x": {"type": "integer"},
                         "z": {"type": "integer"}, "bottom_y": {"type": "integer"},
                         "bricks": {"type": "integer"}, "color": {"type": "integer"},
                         "cap_color": {"type": "integer"}},
                        ["name", "x", "z", "bottom_y", "bricks", "color", "cap_color"]),
              _function("check", "Validate the current assembled model and return exact failures.",
                        {}, []),
              _function("render", "Render one selected view; all requested images appear in your next turn.",
                        {"view": {"type": "string", "enum": ["front_left", "front_right", "back_left", "back_right", "top"]}},
                        ["view"]),
              _function("review_renders", "After inspecting front_left and another current view, record the largest visual weakness and a concrete architectural revision. Submission requires revising the geometry after this review, then inspecting fresh views.",
                        {"visual_strengths": {"type": "string"},
                         "largest_gap": {"type": "string"},
                         "revision_plan": {"type": "string"}},
                        ["visual_strengths", "largest_gap", "revision_plan"]),
              _function("submit_design", "Request final acceptance only after physics passes, the rough piece target is met, and a two-view review_renders checkpoint led to a geometry revision that was inspected from fresh views. Include a candid visual review and limitations.",
                        {"visual_review": {"type": "string"},
                         "signature_features": {"type": "array", "items": {"type": "string"}},
                         "known_limits": {"type": "string"}},
                        ["visual_review", "signature_features", "known_limits"]),
          ]}]


def _state_path(directory: Path) -> Path:
    return directory / "state.json"


def _save(directory: Path, state: dict) -> None:
    if state.get("schema") == READ_ONLY_V2_SCHEMA:
        raise RuntimeError("bricksmith-agent-session-v2 remains an inert historical snapshot; offline transaction adapters are available separately, while runner integration is pending M7")
    if state.get("schema") != SCHEMA:
        raise ValueError("Refusing to save an unsupported BrickSmith session schema")
    path = _state_path(directory)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def load_session(directory: Path) -> dict:
    state = json.loads(_state_path(directory).read_text(encoding="utf-8"))
    if isinstance(state, dict) and state.get("schema") == READ_ONLY_V2_SCHEMA:
        raise RuntimeError("bricksmith-agent-session-v2 remains an inert historical snapshot; offline transaction adapters are available separately, while runner integration is pending M7")
    if isinstance(state, dict) and state.get("schema") == "bricksmith-transaction-state-v1":
        raise RuntimeError("Transaction workspaces support offline tool adapters only; model step/run integration is pending M7")
    if state.get("schema") != SCHEMA:
        raise ValueError("Unsupported BrickSmith session schema")
    return state


def start_session(directory: Path, brief: str, *, model: str = "gpt-5.6-sol",
                  target_pieces: str = "500–1000", reference_image: Path | None = None,
                  ground_y: float = 8.0) -> dict:
    if not brief.strip():
        raise ValueError("A build brief is required")
    if not math.isfinite(ground_y) or abs(ground_y) > 1000:
        raise ValueError("ground_y must be a finite LDraw coordinate within ±1000")
    if reference_image is not None:
        if reference_image.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError("Reference image must be PNG, JPEG, or WebP")
        if not reference_image.is_file() or reference_image.stat().st_size > 10_000_000:
            raise ValueError("Reference image must exist and be at most 10 MB")
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "modules").mkdir()
    (directory / "revisions").mkdir()
    (directory / "renders").mkdir()
    (directory / "checks").mkdir()
    copied_image = None
    if reference_image is not None:
        copied_image = directory / f"reference{reference_image.suffix.lower()}"
        shutil.copy2(reference_image, copied_image)
    if abs(ground_y) <= 1e-6:
        ground_hint = (
            "Use a compact, joined plate-built display plinth with bottom plate origins "
            "at Y=-8 and underside at the session ground Y=0. Do not assume a 32x32 baseplate. "
        )
    elif abs(ground_y - 8.0) <= 1e-6:
        ground_hint = (
            "For the standard 32x32 baseplate at origin Y=0, its underside sits at "
            "the session ground Y=8. Other base geometry is allowed if its underside "
            "meets the configured ground plane. "
        )
    else:
        ground_hint = "Place a connected base or foundation with its underside at this exact ground plane. "
    state = {"schema": SCHEMA, "model": model, "brief": brief,
             "target_pieces": target_pieces, "reference_image": str(copied_image) if copied_image else None,
             "ground_y": ground_y,
             "step": 0, "module_order": [], "plan": "",
             "history": [{"role": "user", "content": (
                 f"Design an original LEGO build: {brief}\n"
                 f"Session ground plane is LDraw Y={ground_y}. {ground_hint}\n"
                 f"Target roughly {target_pieces} pieces, with architectural detail at the "
                 "quality of a display set. Review the locally prefetched reference starter pack "
                 "before using search; look up more only for a specific missing construction fact. "
                 "Save a plan promptly with a distinct architectural character, silhouette hierarchy, "
                 "roof masses, and three visible signature features—not just a rectangular "
                 "shell. Save modular LDraw, check it, "
                 "render it, inspect the render, and repair both aesthetics and physical failures. "
                 "Use real pieces. Do not settle for a featureless box or call an unverified "
                 "model complete. Use submit_design only after physics and visual review "
                 "meet the acceptance gate. Work across multiple turns; this session is persistent."
             )}], "pending_images": [], "last_validation": None, "events": []}
    _save(directory, state)
    return state


def _validate_ldr(text: str) -> int:
    lines = text.splitlines()
    if len(lines) > 300:
        raise ValueError("A module may have at most 300 lines")
    count = 0
    for line in lines:
        if not line.strip() or line.startswith("0 "):
            continue
        fields = line.split()
        if not line.startswith("1 ") or len(fields) != 15 or not re.fullmatch(r"[\w.-]+\.dat", fields[-1], re.I):
            raise ValueError("Module contains a malformed or non-LDraw placement")
        int(fields[1])
        for value in fields[2:14]:
            float(value)
        count += 1
    if not 1 <= count <= MAX_MODULE_PARTS:
        raise ValueError(f"A module must contain 1–{MAX_MODULE_PARTS} parts")
    return count


def _assemble(directory: Path, state: dict) -> tuple[Path, int]:
    lines = ["0 BrickSmith agent design"]
    count = 0
    for name in state["module_order"]:
        text = (directory / "modules" / f"{name}.ldr").read_text(encoding="utf-8")
        count += _validate_ldr(text)
        lines.append(f"0 // Module: {name}")
        lines.extend(text.splitlines())
    if count > MAX_PARTS:
        raise ValueError(f"Build exceeds the {MAX_PARTS}-part limit")
    path = directory / "build.ldr"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path, count


def _placement_digest(path: Path) -> str:
    """Hash physical placements, ignoring module headers and source order."""
    placements = sorted(line.strip() for line in path.read_text(encoding="utf-8").splitlines()
                        if line.startswith("1 "))
    return hashlib.sha256("\n".join(placements).encode("utf-8")).hexdigest()


def _auto_preview_views(state: dict, count: int) -> tuple[str, ...]:
    """Send two angles once a checked build is near its requested scale."""
    target_match = re.search(r"\d+", state.get("target_pieces", ""))
    lower_target = int(target_match.group()) if target_match else 0
    near_target = count >= max(200, int(lower_target * 0.8))
    if near_target and (state.get("last_feedback") or {}).get("passed"):
        return ("front_left", "front_right")
    return ("front_left",)


def _module_lines(directory: Path, state: dict) -> tuple[dict[int, tuple[str, int]], dict[str, list[str]]]:
    """Map assembled 1-based line numbers to module-local placement lines."""
    mapping = {}
    modules = {}
    build_line = 1  # `0 BrickSmith agent design`
    for name in state["module_order"]:
        lines = (directory / "modules" / f"{name}.ldr").read_text(encoding="utf-8").splitlines()
        modules[name] = lines
        build_line += 1  # `0 // Module: ...`
        for local_index, line in enumerate(lines):
            build_line += 1
            if line.startswith("1 "):
                mapping[build_line] = (name, local_index)
    return mapping, modules


def _geometry_digest(directory: Path, state: dict) -> list[dict]:
    """Keep the model oriented without repeatedly paging through old modules."""
    digest = []
    for name in state["module_order"]:
        placements = []
        for line in (directory / "modules" / f"{name}.ldr").read_text(encoding="utf-8").splitlines():
            if line.startswith("1 "):
                fields = line.split()
                placements.append((float(fields[3]), line))
        if not placements:
            continue
        top = min(y for y, _ in placements)
        origins = [[float(field) for field in line.split()[2:5]] for _, line in placements]
        digest.append({"module": name, "parts": len(placements),
                       "top_y_ldu": top,
                       "origin_bounds_ldu": {axis: [min(row[i] for row in origins),
                                                    max(row[i] for row in origins)]
                                             for i, axis in enumerate(("x", "y", "z"))},
                       "top_placements": [line for y, line in placements if y == top][:2]})
    return digest


def _session_status(directory: Path, state: dict) -> str:
    """Replay every module's geometry, including recently added modules."""
    errors = [{key: value for key, value in error.items()
               if key in ('kind', 'count', 'hotspots', 'component_line_samples',
                          'component_sizes', 'suspect_line_samples')}
              for error in (state.get('last_feedback') or {}).get('errors', [])]
    current_checks = (state.get("last_feedback") or {}).get("checks", {})
    review = state.get("visual_revision_checkpoint") or {}
    review_status = (
        f"Visual revision priority: {review['largest_gap']} — {review['revision_plan']}"
        if review else
        "Visual revision checkpoint: not recorded; inspect two current views, "
        "then call review_renders before a finishing revision."
    )
    needs_support = state["module_order"] and (
        not current_checks.get("actual_connectivity", True) or
        not current_checks.get("approximate_gravity_equilibrium", True)
    )
    next_action = (
        "The current stage is provisional: add real studs, walls, beams, or bonding "
        "plates under the reported unsupported parts before adding decoration. "
        "Do not repeatedly recolor geometry to fix a structural failure."
        if needs_support else
        "The plan is saved but no geometry exists. On this turn, save a substantial first "
        "module (foundation and/or main architectural mass) using the available construction "
        "tools. Do not spend another turn on general reference browsing unless one specific "
        "placement fact blocks you."
        if state.get("plan") and not state["module_order"] else
        "Use the current render and construction feedback to add or repair a visible feature."
        if state["module_order"] else
        "Set a compact architectural plan, then begin geometry promptly."
    )
    return (
        "Persistent session status (saved by the harness):\n"
        f"Next action: {next_action}\n"
        f"Plan: {state.get('plan') or '(not yet saved; use the starter references and call set_plan promptly)'}\n"
        f"{review_status}\n"
        f"Session ground plane: LDraw Y={state.get('ground_y', 8.0)} (checker uses this value)\n"
        f"Starter reference IDs: {', '.join(example['id'] for example in (state.get('starter_references') or {}).get('examples', [])) or '(none)'}\n"
        f"Current physical piece count: {(state.get('last_validation') or {}).get('physical_piece_count', 'not checked')} (the saved plan may describe an older count)\n"
        f"Modules: {', '.join(state['module_order']) or '(none)'}\n"
        f"Geometry digest: {json.dumps(_geometry_digest(directory, state), separators=(',', ':'))}\n"
        f"Last check: {json.dumps({'passed': (state.get('last_feedback') or {}).get('passed', 'not run'), 'errors': errors})[:4000]}\n"
        "The latest two tool turns are replayed below so consecutive inspection pages remain visible. "
        "The digest gives current top-course geometry; use read_module only for exact older lines you must edit."
    )


def _revision(directory: Path, state: dict, name: str, previous: str) -> Path:
    revision_dir = directory / "revisions"
    revision_dir.mkdir(exist_ok=True)
    index = len(list(revision_dir.glob(f"{name}-*.ldr"))) + 1
    path = revision_dir / f"{name}-{index:03d}.ldr"
    path.write_text(previous, encoding="utf-8")
    return path


def _check_and_record(directory: Path, state: dict, path: Path, label: str) -> dict:
    result = check_model(path, ground_y=state.get("ground_y", 8.0))
    state["last_validation"] = result
    state["checked_digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
    report_path = directory / "checks" / f"step-{state['step']:02d}-{label}.json"
    report_path.parent.mkdir(exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    source_lines = path.read_text(encoding="utf-8").splitlines()
    errors = []
    for error in result.get("errors", []):
        compact = {key: value for key, value in error.items() if key not in ("pairs", "component_members")}
        if "line_pairs" in compact:
            compact["line_pairs"] = compact["line_pairs"][:30]
            counts = Counter(n for pair in error["line_pairs"] for n in pair)
            compact["hotspots"] = [
                {"line": n, "collision_pairs": frequency, "text": source_lines[n - 1]}
                for n, frequency in counts.most_common(12) if 1 <= n <= len(source_lines)
            ]
        if "component_line_samples" in compact:
            compact["component_line_samples"] = compact["component_line_samples"][:15]
        errors.append(compact)
    feedback = {"passed": result.get("passed", False), "checks": result.get("checks", {}),
                "errors": errors, "report_path": str(report_path)}
    state["last_feedback"] = feedback
    return feedback


def _fresh_render_path(directory: Path, stem: str) -> Path:
    """Keep every visual revision, including repeated renders within one step."""
    root = directory / "renders"
    candidate = root / f"{stem}.png"
    index = 2
    while candidate.exists():
        candidate = root / f"{stem}-v{index}.png"
        index += 1
    return candidate


def _repair_metrics(feedback: dict | None) -> tuple[int, int]:
    errors = (feedback or {}).get("errors", [])
    collisions = next((error.get("count", 0) for error in errors
                       if error.get("kind") == "mesh_collision"), 0)
    components = next((len(error.get("component_sizes", [])) for error in errors
                      if error.get("kind") == "disconnected_assembly"), 1)
    return collisions, components


def _expand_array(template: str, counts: list[int], steps: list[list[float]]) -> str:
    """Expand a translated placement pattern without executing model-written code."""
    if len(counts) != 3 or any(type(n) is not int or not 1 <= n <= 30 for n in counts):
        raise ValueError("counts must contain three integers from 1 to 30")
    if any(len(step) != 3 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or abs(v) > 2000 for v in step)
           for step in steps):
        raise ValueError("Each step must contain three LDU coordinates within ±2000")
    template_lines = [line for line in template.splitlines() if line.startswith("1 ")]
    other_lines = [line for line in template.splitlines() if line.strip() and not line.startswith(("1 ", "0 "))]
    if not 1 <= len(template_lines) <= 20 or other_lines:
        raise ValueError("Array template must contain 1-20 placement lines")
    _validate_ldr(template)
    if len(template_lines) * counts[0] * counts[1] * counts[2] > MAX_MODULE_PARTS:
        raise ValueError(f"Expanded array exceeds {MAX_MODULE_PARTS} parts")
    out = []
    for ix in range(counts[0]):
        for iy in range(counts[1]):
            for iz in range(counts[2]):
                offset = [ix * steps[0][d] + iy * steps[1][d] + iz * steps[2][d]
                          for d in range(3)]
                for line in template_lines:
                    fields = line.split()
                    for d in range(3):
                        value = float(fields[2 + d]) + offset[d]
                        fields[2 + d] = f"{value:.6f}".rstrip("0").rstrip(".")
                    out.append(" ".join(fields))
    return "\n".join(out)


def _translate_module(text: str, offsets: list[int]) -> str:
    translated = []
    for line in text.splitlines():
        if not line.startswith("1 "):
            translated.append(line)
            continue
        fields = line.split()
        for index, delta in enumerate(offsets, start=2):
            fields[index] = f"{float(fields[index]) + delta:g}"
        translated.append(" ".join(fields))
    return "\n".join(translated)


def _floor_ldr(rectangles: list[dict], y: int, color: int) -> str:
    """Tile disjoint stud-grid rectangles with centered, catalog-backed plates."""
    if not 1 <= len(rectangles) <= 8 or type(y) is not int or y % 8 or abs(y) > 2000:
        raise ValueError("Use 1-8 rectangles and a plate-aligned integer y within ±2000 LDU")
    if type(color) is not int or not 0 <= color <= 999:
        raise ValueError("color must be an LDraw integer color code")
    bounds = []
    for rect in rectangles:
        if set(rect) != {"x_min", "x_max", "z_min", "z_max"}:
            raise ValueError("Each rectangle needs x_min, x_max, z_min, z_max")
        x0, x1, z0, z1 = (rect[key] for key in ("x_min", "x_max", "z_min", "z_max"))
        if any(type(v) is not int or v % 20 or abs(v) > 2000 for v in (x0, x1, z0, z1)):
            raise ValueError("Floor bounds must be stud-edge multiples of 20 LDU within ±2000")
        if x1 <= x0 or z1 <= z0:
            raise ValueError("Each floor rectangle must have positive width and depth")
        for a, b, c, d in bounds:
            if x0 < b and x1 > a and z0 < d and z1 > c:
                raise ValueError("Floor rectangles may touch but must not overlap")
        bounds.append((x0, x1, z0, z1))
    # Width/depth are in studs; the part origin is the body center.
    options = [(8, 4, "3035", False), (4, 8, "3035", True),
               (6, 4, "3032", False), (4, 6, "3032", True),
               (4, 4, "3031", False), (8, 2, "3034", False),
               (2, 8, "3034", True), (6, 2, "3795", False),
               (2, 6, "3795", True), (4, 2, "3020", False),
               (2, 4, "3020", True), (2, 2, "3022", False),
               (6, 1, "3666", False), (1, 6, "3666", True),
               (4, 1, "3710", False), (1, 4, "3710", True),
               (1, 1, "3024", False)]
    options.sort(key=lambda option: -(option[0] * option[1]))
    identity = "1 0 0 0 1 0 0 0 1"
    quarter_turn = "0 0 1 0 1 0 -1 0 0"
    lines = ["0 Generated floor; edge-aligned rectangles tiled without overlaps"]
    for x0, x1, z0, z1 in bounds:
        nx, nz = (x1-x0)//20, (z1-z0)//20
        occupied = [[False] * nx for _ in range(nz)]
        for rz in range(nz):
            for rx in range(nx):
                if occupied[rz][rx]:
                    continue
                for width, depth, part, rotated in options:
                    cw, cd = width, depth
                    if rx+cw <= nx and rz+cd <= nz and all(
                        not occupied[zz][xx]
                        for zz in range(rz, rz+cd) for xx in range(rx, rx+cw)
                    ):
                        for zz in range(rz, rz+cd):
                            for xx in range(rx, rx+cw):
                                occupied[zz][xx] = True
                        cx = x0 + rx*20 + width*10
                        cz = z0 + rz*20 + depth*10
                        lines.append(f"1 {color} {cx} {y} {cz} "
                                     f"{quarter_turn if rotated else identity} {part}.dat")
                        break
                else:
                    raise RuntimeError("Floor tiler could not cover the requested rectangle")
    return "\n".join(lines)


def _wall_runs_ldr(runs: list[dict], bottom_y: int, color: int) -> str:
    """Build staggered 1-stud wall courses with explicit empty opening cells."""
    if not 1 <= len(runs) <= 16 or type(bottom_y) is not int or bottom_y % 8 or abs(bottom_y) > 2000:
        raise ValueError("Use 1-16 wall runs and a plate-aligned bottom_y within ±2000")
    if type(color) is not int or not 0 <= color <= 999:
        raise ValueError("color must be an LDraw integer color code")
    parts = {6: "3009", 4: "3010", 2: "3004", 1: "3005"}
    identity = "1 0 0 0 1 0 0 0 1"
    quarter_turn = "0 0 1 0 1 0 -1 0 0"
    occupied: set[tuple[int, int, int]] = set()
    lines = ["0 Generated staggered wall runs; opening ranges use [from_course,to_course)"]
    for run in runs:
        axis, start, end, fixed, courses = (run[key] for key in
                                            ("axis", "start", "end", "fixed", "courses"))
        if axis not in ("x", "z") or any(type(v) is not int for v in (start, end, fixed, courses)):
            raise ValueError("Wall runs require axis x/z and integer coordinates/courses")
        if start % 20 or end % 20 or fixed % 20 != 10 or start >= end or not 1 <= courses <= 12:
            raise ValueError("Wall start/end are stud edges, fixed is a stud center, courses 1-12")
        if any(abs(v) > 2000 for v in (start, end, fixed)):
            raise ValueError("Wall coordinates must be within ±2000 LDU")
        openings = run["openings"]
        if len(openings) > 12:
            raise ValueError("At most 12 openings per wall run")
        for opening in openings:
            a, b, low, high = (opening[key] for key in
                               ("start", "end", "from_course", "to_course"))
            if any(type(v) is not int for v in (a, b, low, high)) or not (
                start <= a < b <= end and a % 20 == b % 20 == 0 and 0 <= low < high <= courses
            ):
                raise ValueError("Opening must be a stud-edge subrange and a valid half-open course range")
        width = (end-start)//20
        for course in range(courses):
            available = [not any(o["start"] <= start+i*20 and start+(i+1)*20 <= o["end"]
                                 and o["from_course"] <= course < o["to_course"]
                                 for o in openings) for i in range(width)]
            i = 0
            while i < width:
                if not available[i]:
                    i += 1
                    continue
                stop = i
                while stop < width and available[stop]:
                    stop += 1
                while i < stop:
                    remaining = stop-i
                    # Alternating two-stud starter offsets joints between courses.
                    length = 2 if course % 2 and i == 0 and remaining > 2 else next(
                        size for size in (6, 4, 2, 1) if size <= remaining)
                    for cell in range(i, i+length):
                        along = start + cell*20 + 10
                        xc, zc = (along, fixed) if axis == "x" else (fixed, along)
                        key = (course, xc, zc)
                        if key in occupied:
                            raise ValueError("Wall runs overlap at a stud cell; shorten one run at the corner")
                        occupied.add(key)
                    center = start + i*20 + length*10
                    x, z = (center, fixed) if axis == "x" else (fixed, center)
                    y = bottom_y - course*24
                    lines.append(f"1 {color} {x} {y} {z} "
                                 f"{identity if axis == 'x' else quarter_turn} {parts[length]}.dat")
                    i += length
    return "\n".join(lines)


def _gable_ldr(axis: str, start: int, end: int, fixed: int, bottom_y: int,
               courses: int, inset_studs: int, color: int) -> str:
    """A bonded, stepped triangular brick end wall; roof covering is separate."""
    if axis not in ("x", "z") or any(type(v) is not int for v in
             (start, end, fixed, bottom_y, courses, inset_studs, color)):
        raise ValueError("Gable coordinates, courses, inset, and color must be integers")
    if start % 20 or end % 20 or fixed % 20 != 10 or bottom_y % 8:
        raise ValueError("Gable start/end are stud edges; fixed is a stud center; Y is plate-aligned")
    width = (end - start) // 20
    if not (2 <= width <= 64 and 1 <= courses <= 10 and 1 <= inset_studs <= 3
            and width - 2 * inset_studs * (courses - 1) >= 1
            and all(abs(v) <= 2000 for v in (start, end, fixed, bottom_y))
            and 0 <= color <= 999):
        raise ValueError("Gable needs a positive narrowing footprint, 1-10 courses, and valid LDraw coordinates")
    parts = {6: "3009", 4: "3010", 2: "3004", 1: "3005"}
    rotation = "1 0 0 0 1 0 0 0 1" if axis == "x" else "0 0 1 0 1 0 -1 0 0"
    lines = ["0 Generated stepped gable end; cover with a separately supported roof"]
    for course in range(courses):
        row_start = start + course * inset_studs * 20
        cells = width - 2 * course * inset_studs
        used = 0
        while used < cells:
            remaining = cells - used
            length = 2 if course % 2 and used == 0 and remaining > 2 else next(
                size for size in (6, 4, 2, 1) if size <= remaining)
            center = row_start + used * 20 + length * 10
            x, z = (center, fixed) if axis == "x" else (fixed, center)
            lines.append(f"1 {color} {x} {bottom_y - course * 24} {z} "
                         f"{rotation} {parts[length]}.dat")
            used += length
    return "\n".join(lines)


def _stepped_roof_beams_ldr(left_x: int, right_x: int, front_z: int,
                            rear_z: int, gable_bottom_y: int, courses: int,
                            beam_studs: int, color: int) -> str:
    """Two complete gable-supported roof planes, one stud wide per tier."""
    values = (left_x, right_x, front_z, rear_z, gable_bottom_y,
              courses, beam_studs, color)
    if any(type(value) is not int for value in values):
        raise ValueError("Stepped-roof coordinates, courses, length, and color must be integers")
    if (not 1 <= courses <= 10 or not 0 <= color <= 999
            or any(abs(value) > 2000 for value in values[:5])
            or gable_bottom_y % 8
            or left_x % 20 != 10 or right_x % 20 != 10
            or front_z % 20 != 10 or rear_z % 20 != 10):
        raise ValueError("Stepped roof needs stud-center X/Z, plate-aligned Y, and bounded courses")
    if right_x - left_x != 20 * (2 * courses - 1):
        raise ValueError("Roof courses must meet at a two-stud ridge without a gap or overlap")
    parts = {4: "3010", 6: "3009", 8: "3008", 10: "6111", 12: "6112"}
    if beam_studs not in parts or rear_z <= front_z:
        raise ValueError("Beam must be 4, 6, 8, 10, or 12 studs and rear Z must follow front Z")
    span_intervals = (rear_z - front_z) // 20
    spare_intervals = beam_studs - 1 - span_intervals
    if not (0 <= spare_intervals <= 4 and spare_intervals % 2 == 0):
        raise ValueError("Beam studs must match both gable supports with at most two-stud overhangs")
    center_z = (front_z + rear_z) // 2
    rotation = "0 0 1 0 1 0 -1 0 0"
    lines = ["0 Generated complete gable-supported stepped roof planes; check bending separately"]
    for course in range(courses):
        y = gable_bottom_y - (course + 1) * 24
        for x in (left_x + course * 20, right_x - course * 20):
            lines.append(f"1 {color} {x} {y} {center_z} {rotation} {parts[beam_studs]}.dat")
    return "\n".join(lines)


def _roof_tile_caps_ldr(left_x: int, right_x: int, front_z: int,
                         rear_z: int, gable_bottom_y: int, courses: int,
                         beam_studs: int, color: int) -> str:
    """Tile the top of each stepped beam with non-overlapping lengths."""
    _stepped_roof_beams_ldr(left_x, right_x, front_z, rear_z,
                            gable_bottom_y, courses, beam_studs, color)
    parts = {8: "4162", 4: "2431", 2: "3069b"}
    rotation = "0 0 1 0 1 0 -1 0 0"
    center_z = (front_z + rear_z) // 2
    first_edge_z = center_z - beam_studs * 10
    lines = ["0 Tile caps for matching gable-supported stepped roof beams"]
    for course in range(courses):
        y = gable_bottom_y - (course + 1) * 24 - 8
        for x in (left_x + course * 20, right_x - course * 20):
            used = 0
            while used < beam_studs:
                length = next(size for size in (8, 4, 2) if size <= beam_studs - used)
                z = first_edge_z + used * 20 + length * 10
                lines.append(f"1 {color} {x} {y} {z} {rotation} {parts[length]}.dat")
                used += length
    return "\n".join(lines)


def _support_column_ldr(x: int, z: int, bottom_y: int, bricks: int,
                        color: int, cap_color: int, cap_plate: bool,
                        size_studs: int = 1) -> str:
    if any(type(v) is not int for v in (x, z, bottom_y, bricks, color, cap_color, size_studs)) or type(cap_plate) is not bool:
        raise ValueError("Column coordinates, count, and colors must be integers; cap_plate is boolean")
    if size_studs not in (1, 2) or x % 20 != (10 if size_studs == 1 else 0) or z % 20 != (10 if size_studs == 1 else 0) or bottom_y % 8 or not 1 <= bricks <= 30:
        raise ValueError("Column X/Z must match 1x1 stud centers or 2x2 origins, Y plate-aligned, and bricks 1-30")
    if any(abs(v) > 2000 for v in (x, z, bottom_y)) or not 0 <= color <= 999 or not 0 <= cap_color <= 999:
        raise ValueError("Column coordinates or colors out of range")
    identity = "1 0 0 0 1 0 0 0 1"
    brick_part, plate_part = ("3005", "3024") if size_studs == 1 else ("3003", "3022")
    lines = [f"0 Generated {size_studs}x{size_studs} support column"]
    for row in range(bricks):
        lines.append(f"1 {color} {x} {bottom_y - row * 24} {z} {identity} {brick_part}.dat")
    if cap_plate:
        lines.append(f"1 {cap_color} {x} {bottom_y - (bricks - 1) * 24 - 8} {z} {identity} {plate_part}.dat")
    return "\n".join(lines)


def _roof_seam_column_ldr(x: int, z: int, bottom_y: int, bricks: int,
                          color: int, cap_color: int) -> str:
    if any(type(v) is not int for v in (x, z, bottom_y, bricks, color, cap_color)):
        raise ValueError("Roof seam column coordinates, count, and colors must be integers")
    if x % 20 != 10 or z % 20 or bottom_y % 8 or not 1 <= bricks <= 30:
        raise ValueError("Roof seam column needs stud-center X, stud-edge Z, plate-aligned Y, bricks 1-30")
    if any(abs(v) > 2000 for v in (x, z, bottom_y)) or not 0 <= color <= 999 or not 0 <= cap_color <= 999:
        raise ValueError("Roof seam column coordinates or colors out of range")
    turn = "0 0 1 0 1 0 -1 0 0"
    lines = ["0 Generated 1x2 Z-axis roof-seam support column"]
    for row in range(bricks):
        lines.append(f"1 {color} {x} {bottom_y - row * 24} {z} {turn} 3004.dat")
    lines.append(f"1 {cap_color} {x} {bottom_y - (bricks - 1) * 24 - 8} {z} {turn} 3023.dat")
    return "\n".join(lines)


def _tool(directory: Path, state: dict, name: str, args: dict,
          invocation_context: dict | None = None) -> dict:
    if state.get("schema") == "bricksmith-transaction-state-v1":
        if invocation_context is None:
            raise RuntimeError("Transaction workspaces require explicit offline invocation context; model runner integration is pending M7")
        from .transaction_tools import dispatch
        return dispatch(directory, name, args, invocation_context)
    if invocation_context is not None:
        raise ValueError("Offline transaction invocation context is valid only for an initialized transaction workspace")
    if state.get("schema") == READ_ONLY_V2_SCHEMA:
        raise RuntimeError("bricksmith-agent-session-v2 remains an inert historical snapshot; offline transaction adapters are available separately, while runner integration is pending M7")
    if state.get("schema") != SCHEMA:
        raise ValueError("Refusing to mutate an unsupported BrickSmith session schema")
    if name == "search":
        query = args["query"][:160]
        results = search(load_references(DEFAULT_CORPUS), query, limit=6)
        # Prevent large absolute-path metadata from filling the model context.
        return {"query": query, "results": [{key: r[key] for key in
                ("id", "title", "description", "piece_count", "sha256", "license", "score",
                 "matched_query_terms", "unmatched_query_terms", "query_coverage")}
                for r in results]}
    if name in ("inspect", "study_reference"):
        reference_id = args["reference_id"]
        refs = {r.id: r for r in load_references(DEFAULT_CORPUS)}
        if reference_id not in refs:
            raise ValueError("Unknown reference ID; call search first")
        if name == "study_reference":
            return _compact_study(study_reference(Path(refs[reference_id].path), args["focus"]))
        return inspect_model(Path(refs[reference_id].path),
                             start=int(args["start"]), count=min(max(int(args["count"]), 1), 40))
    if name == "inspect_reference_region":
        refs = {ref.id: ref for ref in load_references(DEFAULT_CORPUS)}
        reference_id = args["reference_id"]
        if reference_id not in refs:
            raise ValueError("Unknown reference ID; call search first")
        return inspect_reference_region(
            Path(refs[reference_id].path), args["x_min"], args["x_max"],
            args["z_min"], args["z_max"], args["h_min"], args["h_max"],
            args["offset"], min(args["count"], 40))
    if name == "inspect_build_region":
        if not state["module_order"]:
            raise ValueError("Save at least one module before inspecting the build")
        build, _ = _assemble(directory, state)
        result = inspect_reference_region(
            build, args["x_min"], args["x_max"], args["z_min"], args["z_max"],
            args["h_min"], args["h_max"], args["offset"], min(args["count"], 40))
        mapping, _ = _module_lines(directory, state)
        for placement in result["placements"]:
            module, local_index = mapping[placement["line"]]
            placement["module"] = module
            placement["module_line"] = local_index + 1
        return {"model_path": str(build), "region": result["region"],
                "total_matches": result["total_matches"], "offset": result["offset"],
                "next_offset": result["next_offset"], "placements": result["placements"],
                "note": "Origins only, not full part bodies; build and module-local line numbers are current until a placement is added or deleted."}
    if name == "render_reference":
        reference_id, view = args["reference_id"], args["view"]
        refs = {r.id: r for r in load_references(DEFAULT_CORPUS)}
        if reference_id not in refs:
            raise ValueError("Unknown reference ID; call search first")
        if view not in VIEWS:
            raise ValueError(f"Unknown render view: {view}")
        if len(state.get("pending_images", [])) >= 4:
            raise ValueError("At most four renders can be queued per step")
        safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", reference_id)
        image_path = directory / "renders" / f"reference-{safe_id}-{view}.png"
        source_path = Path(refs[reference_id].path)
        omitted: Counter[str] = Counter()
        try:
            render_ldr_to_png(source_path, image_path,
                              azimuth=VIEWS[view][0], elevation=VIEWS[view][1], resolution=800)
        except KeyError:
            # The local BrickNet mesh catalog is smaller than the LDraw
            # reference corpus. A preview may omit unsupported parts, but the
            # exact source file remains available through inspect/study.
            stems = load_catalog().stem_to_id
            supported = []
            for line in source_path.read_text(encoding="utf-8", errors="replace").splitlines():
                fields = line.split()
                if len(fields) == 15 and fields[0] == "1":
                    stem = Path(fields[-1]).stem.lower()
                    if stem not in stems:
                        omitted[stem] += 1
                        continue
                supported.append(line)
            if not omitted or not any(line.startswith("1 ") for line in supported):
                raise
            filtered_path = directory / "renders" / f"reference-{safe_id}-supported.ldr"
            filtered_path.parent.mkdir(parents=True, exist_ok=True)
            filtered_path.write_text("\n".join(supported) + "\n", encoding="utf-8")
            render_ldr_to_png(filtered_path, image_path,
                              azimuth=VIEWS[view][0], elevation=VIEWS[view][1], resolution=800)
        state.setdefault("pending_images", []).append(str(image_path))
        return {"reference_id": reference_id, "title": refs[reference_id].title,
                "sha256": refs[reference_id].sha256, "license": refs[reference_id].license,
                "image_path": str(image_path), "omitted_unsupported_parts": dict(omitted),
                "note": "The reference image is included in the next model request for technique and proportion study; if parts were omitted, the preview is incomplete. Do not copy it as the answer."}
    if name == "search_parts":
        return {"results": search_parts(args["query"][:120])}
    if name == "search_omr_sets":
        try:
            results = search_omr(args["query"])
        except (RuntimeError, ValueError) as exc:
            return {"error": str(exc)}
        return {"query": args["query"][:160],
                "results": [{"model_id": r.model_id, "title": r.title,
                             "model_number": r.model_number, "thumbnail_url": r.thumbnail_url}
                            for r in results],
                "note": OMR_LICENSE_NOTE}
    if name == "fetch_omr_set":
        try:
            ldr = fetch_omr_file(args["model_number"])
        except (RuntimeError, ValueError) as exc:
            return {"error": str(exc)}
        return {"model_number": args["model_number"], "ldr": ldr, "note": OMR_LICENSE_NOTE}
    if name == "save_floor":
        ldr = _floor_ldr(args["rectangles"], args["y"], args["color"])
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": ldr})
        result["generated_floor_parts"] = sum(line.startswith("1 ") for line in ldr.splitlines())
        floor_validation = result.get("validation") or result.get("candidate_validation") or {}
        if not floor_validation.get("checks", {}).get("actual_connectivity", True):
            result["floor_support_hint"] = (
                "Edge-touching floor plates do not stud-connect to each other. "
                "Upper floors need walls or beams below each tile, or a second overlapping "
                "bonding layer. Inspect disconnected line samples and add supports next; "
                "do not submit while connectivity fails."
            )
        return result
    if name == "save_wall_runs":
        ldr = _wall_runs_ldr(args["runs"], args["bottom_y"], args["color"])
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": ldr})
        result["generated_wall_parts"] = sum(line.startswith("1 ") for line in ldr.splitlines())
        return result
    if name == "save_gable":
        ldr = _gable_ldr(args["axis"], args["start"], args["end"], args["fixed"],
                         args["bottom_y"], args["courses"], args["inset_studs"], args["color"])
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": ldr})
        result["generated_gable_parts"] = sum(line.startswith("1 ") for line in ldr.splitlines())
        return result
    if name == "save_stepped_roof_beams":
        ldr = _stepped_roof_beams_ldr(args["left_x"], args["right_x"],
                                      args["front_z"], args["rear_z"],
                                      args["gable_bottom_y"], args["courses"],
                                      args["beam_studs"], args["color"])
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": ldr})
        result["generated_roof_parts"] = 2 * args["courses"]
        return result
    if name == "save_roof_tile_caps":
        ldr = _roof_tile_caps_ldr(args["left_x"], args["right_x"],
                                  args["front_z"], args["rear_z"],
                                  args["gable_bottom_y"], args["courses"],
                                  args["beam_studs"], args["color"])
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": ldr})
        result["generated_roof_cap_parts"] = sum(line.startswith("1 ") for line in ldr.splitlines())
        return result
    if name == "save_support_column":
        ldr = _support_column_ldr(args["x"], args["z"], args["bottom_y"], args["bricks"],
                                  args["color"], args["cap_color"], args["cap_plate"],
                                  args.get("size_studs", 1))
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": ldr})
        result["generated_column_parts"] = sum(line.startswith("1 ") for line in ldr.splitlines())
        return result
    if name == "save_roof_seam_column":
        ldr = _roof_seam_column_ldr(args["x"], args["z"], args["bottom_y"],
                                    args["bricks"], args["color"], args["cap_color"])
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": ldr})
        result["generated_column_parts"] = sum(line.startswith("1 ") for line in ldr.splitlines())
        return result
    if name == "inspect_part":
        return inspect_part(args["part_id"])
    if name == "inspect_alignment":
        path, count = _assemble(directory, state)
        if count == 0:
            raise ValueError("Save at least one module before inspecting alignment")
        return analyze_alignment(path, args["lines"])
    if name == "set_plan":
        plan = args["plan"].strip()
        if not 50 <= len(plan) <= 3000:
            raise ValueError("Plan must contain 50-3000 characters")
        state["plan"] = plan
        return {"saved": True, "characters": len(plan)}
    if name == "clone_module":
        source, destination = args["source"], args["name"]
        if source not in state["module_order"]:
            raise ValueError("Unknown source module")
        if source == destination or destination in state["module_order"]:
            raise ValueError("Clone destination must be a new module name")
        offsets = [args["dx"], args["dy"], args["dz"]]
        if any(type(value) is not int or abs(value) > 2000 for value in offsets) or not any(offsets):
            raise ValueError("Translation must use integer LDU offsets within ±2000, at least one nonzero")
        original = (directory / "modules" / f"{source}.ldr").read_text(encoding="utf-8")
        translated = _translate_module(original, offsets)
        result = _tool(directory, state, "save_module", {"name": destination, "ldr": translated})
        result["cloned_from"] = source
        result["translation_ldu"] = offsets
        return result
    if name == "discard_module":
        module = args["name"]
        if module not in state["module_order"]:
            raise ValueError("Unknown module")
        if len(state["module_order"]) <= 1:
            raise ValueError("Cannot discard the only saved module")
        path = directory / "modules" / f"{module}.ldr"
        revision = _revision(directory, state, module, path.read_text(encoding="utf-8"))
        path.unlink()
        state["module_order"].remove(module)
        state.pop("submitted_design", None)
        build, count = _assemble(directory, state)
        return {"discarded_module": module, "saved_revision": str(revision),
                "remaining_parts": count,
                "validation": _check_and_record(directory, state, build, "discard")}
    if name == "save_array":
        expanded = _expand_array(args["template"], args["counts"],
                                 [args["step_x"], args["step_y"], args["step_z"]])
        result = _tool(directory, state, "save_module", {"name": args["name"], "ldr": expanded})
        result["pattern"] = {"counts": args["counts"], "template_parts":
                             sum(line.startswith("1 ") for line in args["template"].splitlines())}
        return result
    if name == "save_module":
        module = args["name"]
        if not re.fullmatch(r"[a-z][a-z0-9_-]{0,35}", module):
            raise ValueError("Module name must be lowercase letters, digits, hyphens, or underscores")
        ldr = args["ldr"]
        piece_count = _validate_ldr(ldr)
        old_count = 0
        previous = None
        if module in state["module_order"]:
            previous = (directory / "modules" / f"{module}.ldr").read_text(encoding="utf-8")
            old_count = _validate_ldr(previous)
        total = sum(_validate_ldr((directory / "modules" / f"{item}.ldr").read_text())
                    for item in state["module_order"] if item != module)
        if total + piece_count > MAX_PARTS:
            raise ValueError(f"Build exceeds the {MAX_PARTS}-part limit")
        before_feedback = state.get("last_feedback")
        before_collisions = next((error.get("count", 0) for error in
                                  (before_feedback or {}).get("errors", [])
                                  if error.get("kind") == "mesh_collision"), 0)
        revision = _revision(directory, state, module, previous) if previous is not None else None
        if module not in state["module_order"]:
            state["module_order"].append(module)
        state.pop("submitted_design", None)
        (directory / "modules" / f"{module}.ldr").write_text(ldr.rstrip() + "\n", encoding="utf-8")
        path, total = _assemble(directory, state)
        validation = _check_and_record(directory, state, path, module)
        candidate_collisions = next((error.get("count", 0) for error in validation["errors"]
                                     if error.get("kind") == "mesh_collision"), 0)
        before_checks = (before_feedback or {}).get("checks", {})
        candidate_checks = validation.get("checks", {})
        ground_regressed = bool(before_feedback) and (
            (before_checks.get("included_base", True) and not candidate_checks.get("included_base", True)) or
            (before_checks.get("no_parts_below_ground", True) and
             not candidate_checks.get("no_parts_below_ground", True))
        )
        if candidate_collisions > before_collisions or ground_regressed:
            module_path = directory / "modules" / f"{module}.ldr"
            if previous is None:
                module_path.unlink()
                state["module_order"].remove(module)
            else:
                module_path.write_text(previous, encoding="utf-8")
            restored_path, _ = _assemble(directory, state)
            if state["module_order"]:
                _check_and_record(directory, state, restored_path, "rollback")
            else:
                state["last_feedback"] = None
                state.pop("checked_digest", None)
            reason = ("mesh collisions increased" if candidate_collisions > before_collisions
                      else "the build lost its ground support or placed parts below ground")
            return {"error": f"Module save rolled back because {reason}",
                    "module": module, "before_collisions": before_collisions,
                    "candidate_collisions": candidate_collisions,
                    "candidate_validation": validation,
                    "previous_revision": str(revision) if revision else None}
        result = {"module": module, "module_parts": piece_count, "total_parts": total,
                "replaced_parts": old_count, "model_path": str(path),
                "previous_revision": str(revision) if revision else None,
                "validation": validation}
        if not validation["passed"]:
            result["provisional"] = True
            result["next_action"] = (
                "This module is saved as an incomplete construction stage. "
                "Inspect the failed checks and add or repair support/connection geometry next. "
                "The final submission gate will reject this state."
            )
        return result
    if name == "edit_lines":
        edits = args["edits"]
        if not isinstance(edits, list) or not 1 <= len(edits) <= 30:
            raise ValueError("Provide 1-30 assembled-line edits")
        deletes = sum(edit.get("action") == "delete" for edit in edits)
        if deletes > 8:
            raise ValueError("Too many deletions: preserve design features and repair their placements instead")
        mapping, modules = _module_lines(directory, state)
        seen = set()
        changes: dict[str, list[tuple[int, str | None]]] = {}
        for edit in edits:
            line_num = int(edit["line"])
            if line_num in seen:
                raise ValueError(f"Line {line_num} was edited more than once in this call")
            if line_num not in mapping:
                raise ValueError(f"Line {line_num} is not a placement in the current assembled build; do not edit comments or module-local numbers")
            seen.add(line_num)
            action = edit["action"]
            if action == "replace":
                replacement = edit["text"].strip()
                if "\n" in replacement or "\r" in replacement:
                    raise ValueError("Replace edits must contain exactly one LDraw placement line")
                _validate_ldr(replacement)
            elif action == "delete":
                replacement = None
                if edit["text"].strip():
                    raise ValueError("Delete edits must have empty text")
            else:
                raise ValueError(f"Unsupported edit action: {action}")
            module, local_index = mapping[line_num]
            changes.setdefault(module, []).append((local_index, replacement))
        proposed = {}
        for module, module_edits in changes.items():
            updated = list(modules[module])
            for local_index, replacement in sorted(module_edits, reverse=True):
                if replacement is None:
                    del updated[local_index]
                else:
                    updated[local_index] = replacement
            text = "\n".join(updated).rstrip() + "\n"
            _validate_ldr(text)
            proposed[module] = text
        revisions = {}
        state.pop("submitted_design", None)
        for module, text in proposed.items():
            old = "\n".join(modules[module]).rstrip() + "\n"
            revisions[module] = str(_revision(directory, state, module, old))
            (directory / "modules" / f"{module}.ldr").write_text(text, encoding="utf-8")
        path, total = _assemble(directory, state)
        return {"edited_build_lines": sorted(seen), "modules": sorted(proposed),
                "parts": total, "previous_revisions": revisions,
                "validation": _check_and_record(directory, state, path, "edit-lines")}
    if name in ("move_lines", "move_groups"):
        groups = [args] if name == "move_lines" else args["groups"]
        if not isinstance(groups, list) or not 1 <= len(groups) <= 8:
            raise ValueError("Provide 1-8 translation groups")
        mapping, modules = _module_lines(directory, state)
        edits = []
        seen = set()
        for group in groups:
            lines = group["lines"]
            offsets = [group["dx"], group["dy"], group["dz"]]
            if not isinstance(lines, list) or not 1 <= len(lines) <= 30:
                raise ValueError("Each group needs 1-30 assembled placement line numbers")
            if any(type(value) is not int or abs(value) > 200 for value in offsets) or not any(offsets):
                raise ValueError("dx, dy, dz must be integer LDU offsets within ±200, at least one nonzero")
            for line_num in lines:
                if type(line_num) is not int or line_num not in mapping:
                    raise ValueError(f"Line {line_num} is not a current assembled placement")
                if line_num in seen:
                    raise ValueError("Provide distinct line numbers across all translation groups")
                seen.add(line_num)
                module, local_index = mapping[line_num]
                fields = modules[module][local_index].split()
                for index, delta in enumerate(offsets, start=2):
                    fields[index] = f"{float(fields[index]) + delta:g}"
                edits.append({"line": line_num, "action": "replace", "text": " ".join(fields)})
        if len(edits) > 30:
            raise ValueError("At most 30 placements may move in one call")
        before_feedback = state.get("last_feedback")
        before_metrics = _repair_metrics(before_feedback)
        result = _tool(directory, state, "edit_lines", {"edits": edits})
        after_metrics = _repair_metrics(result["validation"])
        if after_metrics[0] > before_metrics[0] or after_metrics[1] > before_metrics[1]:
            for module in result["modules"]:
                (directory / "modules" / f"{module}.ldr").write_text(
                    "\n".join(modules[module]).rstrip() + "\n", encoding="utf-8")
            path, _ = _assemble(directory, state)
            restored = _check_and_record(directory, state, path, "move-rollback")
            return {"error": "Move would worsen collision count or disconnected component count; rolled back",
                    "before_metrics": {"collisions": before_metrics[0], "components": before_metrics[1]},
                    "candidate_metrics": {"collisions": after_metrics[0], "components": after_metrics[1]},
                    "restored_validation": restored}
        result["translation_groups"] = [{"lines": group["lines"], "offset_ldu":
                                         [group["dx"], group["dy"], group["dz"]]} for group in groups]
        return result
    if name == "read_module":
        module = args["name"]
        if module not in state["module_order"]:
            raise ValueError("Unknown saved module")
        lines = (directory / "modules" / f"{module}.ldr").read_text(encoding="utf-8").splitlines()
        start, count = int(args["start"]), int(args["count"])
        if start < 1 or count < 1:
            raise ValueError("start and count must be positive")
        if start > len(lines):
            raise ValueError(f"start exceeds this module's {len(lines)} lines")
        return {"module": module, "total_lines": len(lines),
                "excerpt": [{"line": i + 1, "text": lines[i]}
                            for i in range(start - 1, min(len(lines), start - 1 + min(count, 60)))]}
    if name == "recolor_module_lines":
        module = args["name"]
        local_lines = args["lines"]
        color = args["color"]
        if module not in state["module_order"]:
            raise ValueError("Unknown saved module")
        if (not isinstance(local_lines, list) or not 1 <= len(local_lines) <= 30
                or any(type(line) is not int for line in local_lines)
                or len(set(local_lines)) != len(local_lines)):
            raise ValueError("Provide 1-30 distinct module-local placement line numbers")
        if type(color) is not int or not 0 <= color <= 999:
            raise ValueError("LDraw color must be an integer from 0 to 999")
        mapping, modules = _module_lines(directory, state)
        assembled = {(owner, index + 1): line for line, (owner, index) in mapping.items()}
        edits = []
        for local_line in local_lines:
            assembled_line = assembled.get((module, local_line))
            if assembled_line is None:
                raise ValueError(f"Module line {local_line} is not a current placement")
            fields = modules[module][local_line - 1].split()
            fields[1] = str(color)
            edits.append({"line": assembled_line, "action": "replace", "text": " ".join(fields)})
        result = _tool(directory, state, "edit_lines", {"edits": edits})
        result["recolored_module"] = module
        result["module_lines"] = sorted(local_lines)
        result["color"] = color
        return result
    if name == "check":
        path, count = _assemble(directory, state)
        if count == 0:
            raise ValueError("Save at least one module before checking")
        return _check_and_record(directory, state, path, "check")
    if name == "render":
        path, count = _assemble(directory, state)
        if count == 0:
            raise ValueError("Save at least one module before rendering")
        view = args["view"]
        if view not in VIEWS:
            raise ValueError(f"Unknown render view: {view}")
        if len(state.get("pending_images", [])) >= 4:
            raise ValueError("At most four renders can be queued per step")
        image_path = _fresh_render_path(directory, f"step-{state['step']:02d}-{view}")
        render_ldr_to_png(path, image_path, azimuth=VIEWS[view][0],
                          elevation=VIEWS[view][1], resolution=800)
        state["preview_digest"] = hashlib.sha256(path.read_bytes()).hexdigest()
        state.setdefault("pending_images", []).append(str(image_path))
        state.setdefault("pending_render_views", {})[view] = state["preview_digest"]
        state.setdefault("pending_render_images", {})[str(image_path)] = view
        state.setdefault("rendered_views", [])
        if view not in state["rendered_views"]:
            state["rendered_views"].append(view)
        return {"image_path": str(image_path), "parts": count,
                "note": "The rendered image is included in the next model request."}
    if name == "review_renders":
        path, count = _assemble(directory, state)
        if count == 0:
            raise ValueError("Save a model before reviewing renders")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        views = {view for view, seen_digest in state.get("inspected_view_digests", {}).items()
                 if seen_digest == digest}
        if "front_left" not in views or len(views) < 2:
            raise ValueError("Inspect front_left plus another current view before recording a visual review")
        review = {key: args[key].strip() for key in
                  ("visual_strengths", "largest_gap", "revision_plan")}
        if any(len(value) < 30 for value in review.values()):
            raise ValueError("Describe a concrete strength, visible gap, and architectural revision (30+ characters each)")
        state["visual_revision_checkpoint"] = {
            **review, "geometry_digest": _placement_digest(path),
            "views": sorted(views), "step": state["step"]}
        return {"recorded": True, "priority": review["largest_gap"],
                "next_action": "Make the stated visual revision, then inspect fresh front_left and another view."}
    if name == "submit_design":
        path, count = _assemble(directory, state)
        feedback = _check_and_record(directory, state, path, "final")
        if not feedback["passed"]:
            raise ValueError("Final design cannot be accepted while construction checks fail")
        target_numbers = [int(value) for value in re.findall(r"\d+", state["target_pieces"])]
        minimum = target_numbers[0] if target_numbers else 0
        maximum = target_numbers[1] if len(target_numbers) > 1 else None
        if minimum and count < minimum:
            raise ValueError(f"Only {count} parts; below the {minimum}-part target minimum")
        if maximum is not None and count > maximum:
            raise ValueError(f"{count} parts; above the {maximum}-part target maximum")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        views = {view for view, seen_digest in state.get("inspected_view_digests", {}).items()
                 if seen_digest == digest}
        if "front_left" not in views or len(views) < 2:
            raise ValueError("Inspect front_left plus at least one other view of the current geometry before submission")
        review = state.get("visual_revision_checkpoint")
        if not review:
            raise ValueError("Record a two-view architectural critique with review_renders before submission")
        if _placement_digest(path) == review["geometry_digest"]:
            raise ValueError("Revise actual LDraw placements after review_renders, then inspect fresh views")
        features = [feature.strip() for feature in args["signature_features"] if feature.strip()]
        if len(features) < 3 or len(args["visual_review"].strip()) < 120:
            raise ValueError("Describe at least three visible signature features and a substantive visual critique")
        state["submitted_design"] = {"pieces": count, "visual_review": args["visual_review"],
                                     "signature_features": features, "known_limits": args["known_limits"],
                                     "views": sorted(views)}
        return {"accepted": True, "model_path": str(path), **state["submitted_design"]}
    raise ValueError(f"Unsupported tool: {name}")


def step_session(directory: Path, message: str | None = None) -> dict:
    state = load_session(directory)
    if state["module_order"]:
        path, count = _assemble(directory, state)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if state.get("checked_digest") != digest or not state.get("last_feedback"):
            _check_and_record(directory, state, path, "preflight")
        if state.get("preview_digest") != digest:
            # Do not send the model a queued image of superseded geometry.
            build_images = state.get("pending_render_images", {})
            state["pending_images"] = [image for image in state.get("pending_images", [])
                                       if image not in build_images and
                                       not Path(image).name.startswith("step-")]
            state["pending_render_images"] = {}
            state["pending_render_views"] = {}
        if state.get("preview_digest") != digest and not state.get("pending_images"):
            for view in _auto_preview_views(state, count):
                image_path = _fresh_render_path(directory, f"step-{state['step']:02d}-{view}-auto")
                try:
                    render_ldr_to_png(path, image_path, azimuth=VIEWS[view][0],
                                      elevation=VIEWS[view][1], resolution=900)
                    state.setdefault("pending_images", []).append(str(image_path))
                    state.setdefault("rendered_views", [])
                    if view not in state["rendered_views"]:
                        state["rendered_views"].append(view)
                    state["preview_digest"] = digest
                    state.setdefault("pending_render_views", {})[view] = digest
                    state.setdefault("pending_render_images", {})[str(image_path)] = view
                except (RuntimeError, OSError, ValueError) as exc:
                    state["preview_error"] = str(exc)
        _save(directory, state)
    history = list(state["history"])
    history_start = len(history)
    prior_start = (state["events"][-2].get("history_start", 1)
                   if len(state["events"]) >= 2 else
                   state["events"][-1].get("history_start", 1) if state["events"] else 1)
    request_history = [history[0]]
    request_history.append({"role": "user", "content": _session_status(directory, state)})
    request_history.extend(_compact_history_item(item) for item in history[prior_start:])
    if state["step"] == 0:
        starter = state.get("starter_references") or _starter_reference_pack(state["brief"])
        state["starter_references"] = starter
        first = next((example for example in starter["examples"]
                      if example["requested_style_matched"] and example["piece_count"] >= 200), None)
        if first and not state.get("starter_preview_attempted"):
            state["starter_preview_attempted"] = True
            try:
                rendered = _tool(directory, state, "render_reference",
                                 {"reference_id": first["id"], "view": "front_left"})
                starter["preview"] = {key: rendered[key] for key in
                                      ("reference_id", "title", "sha256", "license",
                                       "omitted_unsupported_parts")}
            except (RuntimeError, OSError, ValueError, KeyError) as exc:
                state["starter_preview_error"] = str(exc)
        _save(directory, state)
        starter_item = {"role": "user", "content": "Locally prefetched LDraw construction references:\n" +
                        json.dumps(starter, separators=(",", ":")) +
                        "\nUse these examples to set a plan and start geometry. Do not copy a set."}
        history.append(starter_item)
        request_history.append(starter_item)
    if state.get("pending_images"):
        render_instruction = (
            "These are real-set construction-reference previews, not your current build. "
            "Study proportions and techniques, then make an original plan; do not copy the set."
            if state["step"] == 0 else
            "Inspect these latest renders. Critique proportions, detail, roof, and obvious construction problems before editing.")
        content = [{"type": "input_text", "text": render_instruction}]
        for image_name in state["pending_images"][:4]:
            image_bytes = Path(image_name).read_bytes()
            content.append({"type": "input_text", "text": Path(image_name).stem})
            content.append({"type": "input_image", "image_url": "data:image/png;base64," + base64.b64encode(image_bytes).decode()})
        image_item = {"role": "user", "content": content}
        history.append(image_item)
        request_history.append(image_item)
    if state["step"] == 0 and state.get("reference_image"):
        image_path = Path(state["reference_image"])
        image_bytes = image_path.read_bytes()
        mime = "image/jpeg" if image_path.suffix.lower() in (".jpg", ".jpeg") else f"image/{image_path.suffix.lower().lstrip('.')}"
        image_item = {"role": "user", "content": [
            {"type": "input_text", "text": "This is the user's visual design reference, which takes priority over any real-set construction examples. Preserve its distinctive proportions, silhouette, roof forms, openings, and architectural character while making an original LEGO interpretation."},
            {"type": "input_image", "image_url": f"data:{mime};base64," + base64.b64encode(image_bytes).decode()}
        ]}
        history.append(image_item)
        request_history.append(image_item)
    if message:
        if len(message) > 3000:
            raise ValueError("Operator message may contain at most 3000 characters")
        operator_message = {"role": "user", "content": message}
        history.append(operator_message)
        request_history.append(operator_message)
    response = respond(state["model"], load_system_prompt(), request_history, TOOLS)
    output = response["output"]
    history.extend(output)  # Includes reasoning items required by store:false.
    state.setdefault("inspected_view_digests", {}).update(state.get("pending_render_views", {}))
    state["pending_render_views"] = {}
    state["pending_render_images"] = {}
    state["pending_images"] = []
    state["step"] += 1
    calls = [item for item in output if item.get("type") == "function_call"]
    results = []
    for index, call in enumerate(calls):
        name = call.get("name", "").split(".")[-1]
        try:
            if index >= MAX_TOOLS_PER_STEP:
                raise ValueError("Per-step local tool-call limit reached; continue on the next step")
            args = json.loads(call.get("arguments", "{}"))
            result = _tool(directory, state, name, args)
        except (ValueError, KeyError, FileNotFoundError, RuntimeError, OSError) as exc:
            result = {"error": str(exc)}
        results.append({"tool": name, "result": result})
        history.append({"type": "function_call_output", "call_id": call["call_id"],
                        "output": json.dumps(result)})
    state["history"] = history
    state["events"].append({"step": state["step"], "usage": response.get("usage"),
                            "tools": [r["tool"] for r in results], "history_start": history_start})
    _save(directory, state)
    text = "\n".join(part.get("text", "") for item in output if item.get("type") == "message"
                     for part in item.get("content", []) if part.get("type") == "output_text")
    return {"step": state["step"], "text": text, "tools": results,
            "usage": {k: (response.get("usage") or {}).get(k)
                      for k in ("input_tokens", "output_tokens", "total_tokens")},
            "build_path": str(directory / "build.ldr")}


def run_session(directory: Path, *, max_requests: int = 4,
                max_total_tokens: int = 60000, message: str | None = None) -> dict:
    """Continue a session through bounded model/tool turns, saving each turn.

    The token ceiling is soft: a single request can exceed the remaining
    allowance, but no further request is sent once its reported usage reaches
    the ceiling. This is not an account quota guard.
    """
    if not 1 <= max_requests <= 8:
        raise ValueError("max_requests must be between 1 and 8")
    if not 1000 <= max_total_tokens <= 250000:
        raise ValueError("max_total_tokens must be between 1000 and 250000")
    turns = []
    usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
    reason = "max_requests"
    stopped_error = None
    research_streak = 0
    if directory.exists():
        for event in reversed(load_session(directory).get("events", [])[-2:]):
            previous_tools = event.get("tools") or []
            if previous_tools and all(name in RESEARCH_TOOLS for name in previous_tools):
                research_streak += 1
            else:
                break
    for index in range(max_requests):
        if usage["total_tokens"] >= max_total_tokens:
            reason = "max_total_tokens"
            break
        follow_up = message if index == 0 and message is not None else (
            RESEARCH_NUDGE if research_streak >= 2 else None)
        try:
            turn = step_session(directory, message=follow_up)
        except (ValueError, RuntimeError, FileNotFoundError, OSError) as exc:
            if not turns:
                raise
            reason = "request_error"
            stopped_error = str(exc)
            break
        turns.append(turn)
        for key in usage:
            usage[key] += int((turn.get("usage") or {}).get(key) or 0)
        names = [item.get("tool") for item in turn.get("tools", [])]
        research_streak = research_streak + 1 if names and all(name in RESEARCH_TOOLS for name in names) else 0
        if research_streak >= 3:
            reason = "research_stall"
            break
        if not turn.get("tools"):
            reason = "model_stopped"
            break
        if any(result.get("tool") == "submit_design" and
               result.get("result", {}).get("accepted") for result in turn["tools"]):
            reason = "submitted_design"
            break
    return {"steps": [{"step": turn["step"], "text": turn["text"],
                       "tools": [{"tool": item["tool"],
                                  "error": item["result"].get("error"),
                                  "passed": (item["result"].get("validation") or {}).get("passed"),
                                  "module": item["result"].get("module"),
                                  "module_parts": item["result"].get("module_parts"),
                                  "total_parts": item["result"].get("total_parts")}
                                 for item in turn["tools"]]}
                      for turn in turns],
            "stopped_because": reason, "error": stopped_error,
            "requests": len(turns), "usage": usage,
            "build_path": str(directory / "build.ldr")}


def queue_renders(directory: Path, views: list[str]) -> dict:
    """Queue local views for the next model step without consuming inference."""
    if not 1 <= len(views) <= 4 or len(set(views)) != len(views):
        raise ValueError("Choose 1-4 distinct render views")
    if any(view not in VIEWS for view in views):
        raise ValueError(f"Views must be among: {', '.join(VIEWS)}")
    state = load_session(directory)
    if len(state.get("pending_images", [])) + len(views) > 4:
        raise ValueError("At most four images may be queued")
    images = []
    for view in views:
        result = _tool(directory, state, "render", {"view": view})
        images.append(result["image_path"])
    _save(directory, state)
    return {"queued_images": images, "step": state["step"],
            "next_step_uses_model": True}
