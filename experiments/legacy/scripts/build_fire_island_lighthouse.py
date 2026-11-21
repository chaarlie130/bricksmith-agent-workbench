#!/usr/bin/env python3
"""Builds "Fire Island Light" -- a banded round lighthouse tower beside a
gabled keeper's cottage, on a single connected baseplate -- using the
harness's validated wall/gable/stepped-roof generators plus hand-placed
round-brick tower and landscaping geometry. Saves build.ldr and a checker
report under runs/fire-island-lighthouse-<date>/.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.workbench.agent_session import (
    _floor_ldr, _wall_runs_ldr, _gable_ldr, _stepped_roof_beams_ldr,
    _roof_tile_caps_ldr, _support_column_ldr,
)
from bricksmith.workbench.feedback import check_model

RUN_DIR = ROOT / "runs" / "fire-island-lighthouse-20261002"
BUILD_PATH = RUN_DIR / "build.ldr"

IDENTITY = "1 0 0 0 1 0 0 0 1"
QUARTER = "0 0 1 0 1 0 -1 0 0"

BLACK = 0
WHITE = 15
TAN = 19
DARK_TAN = 28
RED = 4
REDDISH_BROWN = 70
LIGHT_GRAY = 71
DARK_GRAY = 72
DARK_GREEN = 288
TRANS_BLUE = 41
PEARL_GOLD = 297

lines: list[str] = []
occupied_round: set[tuple[int, int, int]] = set()


def add(block: str) -> None:
    lines.extend(l for l in block.splitlines() if l.strip())


def place(color: int, x: int, y: int, z: int, rot: str, part: str) -> None:
    lines.append(f"1 {color} {x} {y} {z} {rot} {part}.dat")


def round_cell(color: int, cx: int, cz: int, y: int, part: str) -> None:
    """Place a round brick at a 2x2-stud cell center, guarding against reuse."""
    key = (cx, cz, y)
    if key in occupied_round:
        raise ValueError(f"round cell reused at {key}")
    occupied_round.add(key)
    place(color, cx, y, cz, IDENTITY, part)


def header(title: str) -> None:
    lines.append(f"0 // {title}")


# ---------------------------------------------------------------------------
# Baseplate -- a single 32x32 part so the whole site shares one connected
# ground layer with no tile seams to worry about.
# ---------------------------------------------------------------------------
header("Site baseplate")
place(DARK_TAN, 0, 0, 0, IDENTITY, "3811")

# ---------------------------------------------------------------------------
# Keeper's cottage -- double-thick brick walls, two stepped gable ends,
# a full stepped roof with tile caps, a covered porch, and two chimneys.
# ---------------------------------------------------------------------------
COTTAGE_X0, COTTAGE_X1 = -160, 160
COTTAGE_Z0, COTTAGE_Z1 = -140, 60
WALL_BOTTOM_Y = -24
WALL_COURSES = 9
GABLE_BOTTOM_Y = WALL_BOTTOM_Y - WALL_COURSES * 24
GABLE_COURSES = 8
ROOF_BEAM_STUDS = 12
FRONT_Z = COTTAGE_Z0 + 10          # -130, outer wall stud-center row (front)
REAR_Z = COTTAGE_Z1 - 10           # 50, outer wall stud-center row (rear)
LEFT_X = COTTAGE_X0 + 10           # -150
RIGHT_X = COTTAGE_X1 - 10          # 150

header("Cottage walls (outer course)")
add(_wall_runs_ldr(
    runs=[
        {"axis": "x", "start": COTTAGE_X0, "end": COTTAGE_X1, "fixed": FRONT_Z,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -20, "end": 20, "from_course": 0, "to_course": 4},
             {"start": -140, "end": -100, "from_course": 2, "to_course": 5},
             {"start": 60, "end": 100, "from_course": 2, "to_course": 5},
         ]},
        {"axis": "x", "start": COTTAGE_X0, "end": COTTAGE_X1, "fixed": REAR_Z,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -140, "end": -100, "from_course": 2, "to_course": 5},
             {"start": -20, "end": 20, "from_course": 2, "to_course": 5},
             {"start": 100, "end": 140, "from_course": 2, "to_course": 5},
         ]},
        {"axis": "z", "start": COTTAGE_Z0 + 20, "end": COTTAGE_Z1 - 20, "fixed": LEFT_X,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -100, "end": -60, "from_course": 2, "to_course": 5},
             {"start": 0, "end": 40, "from_course": 2, "to_course": 5},
         ]},
        {"axis": "z", "start": COTTAGE_Z0 + 20, "end": COTTAGE_Z1 - 20, "fixed": RIGHT_X,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -100, "end": -60, "from_course": 2, "to_course": 5},
             {"start": -20, "end": 20, "from_course": 2, "to_course": 5},
         ]},
    ],
    bottom_y=WALL_BOTTOM_Y, color=TAN,
))

header("Cottage walls (inner course, doubled thickness)")
add(_wall_runs_ldr(
    runs=[
        {"axis": "x", "start": COTTAGE_X0, "end": COTTAGE_X1, "fixed": FRONT_Z + 20,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -20, "end": 20, "from_course": 0, "to_course": 4},
             {"start": -140, "end": -100, "from_course": 2, "to_course": 5},
             {"start": 60, "end": 100, "from_course": 2, "to_course": 5},
         ]},
        {"axis": "x", "start": COTTAGE_X0, "end": COTTAGE_X1, "fixed": REAR_Z - 20,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -140, "end": -100, "from_course": 2, "to_course": 5},
             {"start": -20, "end": 20, "from_course": 2, "to_course": 5},
             {"start": 100, "end": 140, "from_course": 2, "to_course": 5},
         ]},
        {"axis": "z", "start": COTTAGE_Z0 + 40, "end": COTTAGE_Z1 - 40, "fixed": LEFT_X + 20,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -100, "end": -60, "from_course": 2, "to_course": 5},
             {"start": 0, "end": 20, "from_course": 2, "to_course": 5},
         ]},
        {"axis": "z", "start": COTTAGE_Z0 + 40, "end": COTTAGE_Z1 - 40, "fixed": RIGHT_X - 20,
         "courses": WALL_COURSES,
         "openings": [
             {"start": -100, "end": -60, "from_course": 2, "to_course": 5},
             {"start": -20, "end": 20, "from_course": 2, "to_course": 5},
         ]},
    ],
    bottom_y=WALL_BOTTOM_Y, color=DARK_TAN,
))

header("Attic ceiling deck")
add(_floor_ldr(
    rectangles=[{"x_min": COTTAGE_X0, "x_max": COTTAGE_X1,
                 "z_min": COTTAGE_Z0, "z_max": COTTAGE_Z1}],
    y=GABLE_BOTTOM_Y + 24, color=LIGHT_GRAY,
))

header("Front and rear gable ends")
add(_gable_ldr(axis="x", start=COTTAGE_X0, end=COTTAGE_X1, fixed=FRONT_Z,
               bottom_y=GABLE_BOTTOM_Y, courses=GABLE_COURSES, inset_studs=1,
               color=TAN))
add(_gable_ldr(axis="x", start=COTTAGE_X0, end=COTTAGE_X1, fixed=REAR_Z,
               bottom_y=GABLE_BOTTOM_Y, courses=GABLE_COURSES, inset_studs=1,
               color=TAN))

header("Main stepped roof")
add(_stepped_roof_beams_ldr(left_x=LEFT_X, right_x=RIGHT_X, front_z=FRONT_Z,
                             rear_z=REAR_Z, gable_bottom_y=GABLE_BOTTOM_Y,
                             courses=GABLE_COURSES, beam_studs=ROOF_BEAM_STUDS,
                             color=RED))
add(_roof_tile_caps_ldr(left_x=LEFT_X, right_x=RIGHT_X, front_z=FRONT_Z,
                         rear_z=REAR_Z, gable_bottom_y=GABLE_BOTTOM_Y,
                         courses=GABLE_COURSES, beam_studs=ROOF_BEAM_STUDS,
                         color=RED))

header("Chimneys flanking the front gable")
add(_support_column_ldr(x=-140, z=-120, bottom_y=WALL_BOTTOM_Y, bricks=14,
                         color=REDDISH_BROWN, cap_color=BLACK, cap_plate=True,
                         size_studs=2))
add(_support_column_ldr(x=120, z=-120, bottom_y=WALL_BOTTOM_Y, bricks=14,
                         color=REDDISH_BROWN, cap_color=BLACK, cap_plate=True,
                         size_studs=2))

header("Porch columns and canopy")
for px, pz in ((-30, -170), (30, -170)):
    add(_support_column_ldr(x=px, z=pz, bottom_y=-24, bricks=4,
                             color=WHITE, cap_color=WHITE, cap_plate=False,
                             size_studs=1))
add(_floor_ldr(rectangles=[{"x_min": -60, "x_max": 60, "z_min": -200, "z_max": -140}],
               y=-104, color=RED))
for x in range(-50, 51, 20):
    place(RED, x, -112, -196, QUARTER, "3069b")
    place(RED, x, -112, -144, QUARTER, "3069b")

# ---------------------------------------------------------------------------
# Lighthouse tower -- a wide shaft built from a 3x3 grid of 2x2 round
# bricks per course (9 parts/course, each cell on a 40 LDU / 2-stud pitch so
# adjacent round bricks never overlap), banded black/white, with a dark
# gallery deck, a black lantern room, a cone dome, and an antenna finial.
# ---------------------------------------------------------------------------
TOWER_CX, TOWER_CZ = 240, -40
SHAFT_COURSES = 30
SHAFT_BOTTOM_Y = -24
QUAD_OFFSETS = (-40, 0, 40)

header("Lighthouse tower shaft")
for course in range(SHAFT_COURSES):
    y = SHAFT_BOTTOM_Y - course * 24
    band_color = BLACK if (course // 3) % 2 == 0 else WHITE
    for dx in QUAD_OFFSETS:
        for dz in QUAD_OFFSETS:
            round_cell(band_color, TOWER_CX + dx, TOWER_CZ + dz, y, "6143")

GALLERY_Y = SHAFT_BOTTOM_Y - SHAFT_COURSES * 24
header("Gallery deck")
for course in range(2):
    y = GALLERY_Y - course * 24
    for dx in QUAD_OFFSETS:
        for dz in QUAD_OFFSETS:
            round_cell(DARK_GRAY, TOWER_CX + dx, TOWER_CZ + dz, y, "6143")

header("Gallery railing")
GALLERY_TOP_Y = GALLERY_Y - 2 * 24  # top surface after both deck courses
RAIL_Y = GALLERY_TOP_Y - 48  # fence (3185) body height is 48 LDU
DECK_EDGE_Z0 = TOWER_CZ + min(QUAD_OFFSETS) - 20
DECK_EDGE_Z1 = TOWER_CZ + max(QUAD_OFFSETS) + 20
DECK_EDGE_X0 = TOWER_CX + min(QUAD_OFFSETS) - 20
DECK_EDGE_X1 = TOWER_CX + max(QUAD_OFFSETS) + 20
place(DARK_GRAY, TOWER_CX, RAIL_Y, DECK_EDGE_Z0, IDENTITY, "3185")
place(DARK_GRAY, TOWER_CX, RAIL_Y, DECK_EDGE_Z1, IDENTITY, "3185")
place(DARK_GRAY, DECK_EDGE_X0, RAIL_Y, TOWER_CZ, QUARTER, "3185")
place(DARK_GRAY, DECK_EDGE_X1, RAIL_Y, TOWER_CZ, QUARTER, "3185")

header("Lantern room, dome, and finial")
LANTERN_BOTTOM_Y = GALLERY_TOP_Y
for row in range(4):
    place(BLACK, TOWER_CX, LANTERN_BOTTOM_Y - row * 24, TOWER_CZ, IDENTITY, "3003")
LANTERN_TOP_Y = LANTERN_BOTTOM_Y - 3 * 24  # top surface of the 4th lantern course
DOME_Y = LANTERN_TOP_Y - 48  # cone (3942c) body height is 48 LDU
place(BLACK, TOWER_CX, DOME_Y, TOWER_CZ, IDENTITY, "3942c")
place(BLACK, TOWER_CX, DOME_Y, TOWER_CZ, IDENTITY, "3957a")

# ---------------------------------------------------------------------------
# Connecting walkway -- a validated floor slab bridging the cottage porch
# and the tower base, plus a low garden wall built with the proven wall-run
# generator (guarantees correct stud phase and no self-collision).
# ---------------------------------------------------------------------------
header("Walkway between cottage and tower")
add(_floor_ldr(
    rectangles=[{"x_min": 160, "x_max": 180, "z_min": -80, "z_max": 0}],
    y=-8, color=LIGHT_GRAY,
))

header("Yard lamp posts")
for lx, lz in ((-250, -250), (290, -250), (-250, 250), (290, 250), (-250, 10), (290, 10),
               (-270, -130), (-270, 130), (310, -130), (310, 130)):
    add(_support_column_ldr(x=lx, z=lz, bottom_y=-24, bricks=8, color=BLACK,
                             cap_color=TRANS_BLUE, cap_plate=True, size_studs=1))

header("Garden wall -- property boundary")
BOUND_X0, BOUND_X1 = -280, 320
BOUND_Z0, BOUND_Z1 = -280, 280
GARDEN_WALL_COURSES = 4
add(_wall_runs_ldr(
    runs=[
        {"axis": "x", "start": BOUND_X0, "end": BOUND_X1, "fixed": BOUND_Z0 + 10,
         "courses": GARDEN_WALL_COURSES, "openings": []},
        {"axis": "x", "start": BOUND_X0, "end": BOUND_X1, "fixed": BOUND_Z1 - 10,
         "courses": GARDEN_WALL_COURSES, "openings": []},
        {"axis": "z", "start": BOUND_Z0 + 20, "end": BOUND_Z1 - 20, "fixed": BOUND_X0 + 10,
         "courses": GARDEN_WALL_COURSES, "openings": []},
        {"axis": "z", "start": BOUND_Z0 + 20, "end": BOUND_Z1 - 20, "fixed": BOUND_X1 - 10,
         "courses": GARDEN_WALL_COURSES, "openings": []},
    ],
    bottom_y=-24, color=DARK_GREEN,
))

# ---------------------------------------------------------------------------
# Keeper's equipment shed -- a second, smaller single-thickness-wall building
# in the garden's south-west corner, built with the same validated wall/
# gable/roof generators as the cottage, to add genuine architectural volume
# (not just filler parts) toward the 900+ piece requirement.
# ---------------------------------------------------------------------------
header("Shed walls")
SHED_X0, SHED_X1 = -220, -100
SHED_Z0, SHED_Z1 = 100, 220
SHED_WALL_BOTTOM_Y = -24
SHED_WALL_COURSES = 9
SHED_FRONT_Z = SHED_Z0 + 10
SHED_REAR_Z = SHED_Z1 - 10
SHED_LEFT_X = SHED_X0 + 10
SHED_RIGHT_X = SHED_X1 - 10
add(_wall_runs_ldr(
    runs=[
        {"axis": "x", "start": SHED_X0, "end": SHED_X1, "fixed": SHED_FRONT_Z,
         "courses": SHED_WALL_COURSES,
         "openings": [{"start": -180, "end": -140, "from_course": 0, "to_course": 4}]},
        {"axis": "x", "start": SHED_X0, "end": SHED_X1, "fixed": SHED_REAR_Z,
         "courses": SHED_WALL_COURSES,
         "openings": [{"start": -180, "end": -140, "from_course": 2, "to_course": 5}]},
        {"axis": "z", "start": SHED_Z0 + 20, "end": SHED_Z1 - 20, "fixed": SHED_LEFT_X,
         "courses": SHED_WALL_COURSES,
         "openings": [{"start": 120, "end": 160, "from_course": 2, "to_course": 5}]},
        {"axis": "z", "start": SHED_Z0 + 20, "end": SHED_Z1 - 20, "fixed": SHED_RIGHT_X,
         "courses": SHED_WALL_COURSES,
         "openings": [{"start": 120, "end": 160, "from_course": 2, "to_course": 5}]},
    ],
    bottom_y=SHED_WALL_BOTTOM_Y, color=WHITE,
))

header("Shed ceiling deck")
SHED_GABLE_BOTTOM_Y = SHED_WALL_BOTTOM_Y - SHED_WALL_COURSES * 24
SHED_GABLE_COURSES = 3
add(_floor_ldr(
    rectangles=[{"x_min": SHED_X0, "x_max": SHED_X1, "z_min": SHED_Z0, "z_max": SHED_Z1}],
    y=SHED_GABLE_BOTTOM_Y + 24, color=LIGHT_GRAY,
))

header("Shed gable ends and roof")
add(_gable_ldr(axis="x", start=SHED_X0, end=SHED_X1, fixed=SHED_FRONT_Z,
               bottom_y=SHED_GABLE_BOTTOM_Y, courses=SHED_GABLE_COURSES,
               inset_studs=1, color=WHITE))
add(_gable_ldr(axis="x", start=SHED_X0, end=SHED_X1, fixed=SHED_REAR_Z,
               bottom_y=SHED_GABLE_BOTTOM_Y, courses=SHED_GABLE_COURSES,
               inset_studs=1, color=WHITE))
add(_stepped_roof_beams_ldr(left_x=SHED_LEFT_X, right_x=SHED_RIGHT_X,
                             front_z=SHED_FRONT_Z, rear_z=SHED_REAR_Z,
                             gable_bottom_y=SHED_GABLE_BOTTOM_Y,
                             courses=SHED_GABLE_COURSES, beam_studs=6,
                             color=DARK_GRAY))
add(_roof_tile_caps_ldr(left_x=SHED_LEFT_X, right_x=SHED_RIGHT_X,
                         front_z=SHED_FRONT_Z, rear_z=SHED_REAR_Z,
                         gable_bottom_y=SHED_GABLE_BOTTOM_Y,
                         courses=SHED_GABLE_COURSES, beam_studs=6,
                         color=DARK_GRAY))


RUN_DIR.mkdir(parents=True, exist_ok=True)
part_count = sum(1 for l in lines if l.startswith("1 "))
print(f"total part lines: {part_count}")

BUILD_PATH.write_text("\n".join(lines) + "\n")
print(f"wrote {BUILD_PATH}")

report = check_model(BUILD_PATH)
print(report)
