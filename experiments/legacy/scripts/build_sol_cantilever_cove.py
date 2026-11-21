#!/usr/bin/env python3
"""Build an original, Sol-authored modern hillside display house in LDraw.

This is a deterministic local design pass, not a model-API invocation. The
Claude modern-house file is a held-out visual benchmark, not source geometry.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.rendering.rasterizer import render_ldr_to_png
from bricksmith.workbench.feedback import check_model


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "runs" / "sol-cantilever-cove"
WHITE, BLACK, GLASS = 15, 0, 43
STONE, CHARCOAL = 71, 72
TAN, EARTH, GREEN, BROWN, WATER = 19, 28, 288, 70, 322
LAWN = 378
R0 = "1 0 0 0 1 0 0 0 1"
R90 = "0 0 1 0 1 0 -1 0 0"
PARTS = {
    "3005": (1, 1, 3), "3004": (2, 1, 3), "3622": (3, 1, 3),
    "3010": (4, 1, 3), "3009": (6, 1, 3), "3008": (8, 1, 3),
    "3003": (2, 2, 3), "3001": (4, 2, 3), "3941": (2, 2, 3),
    "3024": (1, 1, 1), "3023": (2, 1, 1), "3022": (2, 2, 1),
    "3039": (2, 2, 3),
    "3020": (4, 2, 1), "3031": (4, 4, 1), "3032": (6, 4, 1),
    "3035": (8, 4, 1), "3795": (6, 2, 1), "3034": (8, 2, 1),
    "3710": (4, 1, 1), "3666": (6, 1, 1), "4162": (8, 1, 1),
    "3069b": (2, 1, 1),
    "3068b": (2, 2, 1),
    "30055": (4, 1, 6),
    "90398": (1, 1, 5),
    "3942c": (2, 2, 6),
}


class Build:
    def __init__(self):
        self.lines = [
            "0 Cantilever Cove - original modern hillside house",
            "0 Name: cantilever_cove.ldr",
            "0 Author: Sol / BrickSmith local design pass",
            "0 !LDRAW_ORG Unofficial_Model",
        ]
        self.occupied: dict[tuple[int, int, int], str] = {}
        self.stages: Counter[str] = Counter()
        self.stage = "ground"
        self.lines.append(f"1 {BLACK} 0 0 0 {R0} 3811.dat")
        self.stages[self.stage] += 1

    def section(self, title: str):
        self.stage = title
        self.lines.append(f"0 // {title}")

    def put(self, part: str, color: int, x: int, z: int, bottom: int,
            *, turn: bool = False, base_origin: bool = False,
            offset_z_ldu: float = 0.0):
        """Place by southwest stud cell and occupied plate layer above base."""
        w, d, h = PARTS[part]
        if turn:
            w, d = d, w
        if not (0 <= x < 32 and 0 <= z < 32 and x + w <= 32 and z + d <= 32):
            raise ValueError(f"Out of base: {part} ({x},{z}) {w}x{d}")
        for xx in range(x, x+w):
            for zz in range(z, z+d):
                for yy in range(bottom, bottom+h):
                    key = (xx, zz, yy)
                    if key in self.occupied:
                        raise ValueError(f"Overlap {part} at {key} with {self.occupied[key]}")
        for xx in range(x, x+w):
            for zz in range(z, z+d):
                for yy in range(bottom, bottom+h):
                    self.occupied[(xx, zz, yy)] = self.stage
        cx = -320 + (x + w/2) * 20
        cz = -320 + (z + d/2) * 20 + offset_z_ldu
        y = -8 * (bottom if base_origin else bottom+h)
        self.lines.append(f"1 {color} {cx:g} {y:g} {cz:g} {R90 if turn else R0} {part}.dat")
        self.stages[self.stage] += 1

    def tile(self, x0: int, x1: int, z0: int, z1: int, bottom: int,
             color: int, *, color_at=None):
        """Tile a rectangular plate plane without same-course overlap."""
        shapes = [(8, 4, "3035", False), (4, 8, "3035", True),
                  (6, 4, "3032", False), (4, 6, "3032", True),
                  (4, 4, "3031", False), (8, 2, "3034", False),
                  (2, 8, "3034", True), (6, 2, "3795", False),
                  (2, 6, "3795", True), (4, 2, "3020", False),
                  (2, 4, "3020", True), (2, 2, "3022", False),
                  (2, 1, "3023", False), (1, 2, "3023", True),
                  (1, 1, "3024", False)]
        used = set()
        for z in range(z0, z1):
            for x in range(x0, x1):
                if (x, z) in used:
                    continue
                for w, d, part, turned in shapes:
                    cells = {(xx, zz) for xx in range(x, x+w)
                             for zz in range(z, z+d)}
                    if x+w <= x1 and z+d <= z1 and not cells & used:
                        chosen = color_at(x, z, w, d) if color_at else color
                        self.put(part, chosen, x, z, bottom, turn=turned)
                        used.update(cells)
                        break
                else:
                    raise RuntimeError("Tiling failed")

    def wall_x(self, z: int, x0: int, x1: int, bottom: int, material,
               *, max_length: int = 8):
        """Material returns a colour or None (open) for each stud cell."""
        x = x0
        candidates = [(8, "3008"), (6, "3009"), (4, "3010"),
                      (3, "3622"), (2, "3004"), (1, "3005")]
        while x < x1:
            color = material(x)
            if color is None:
                x += 1
                continue
            run_end = x + 1
            while run_end < x1 and material(run_end) == color:
                run_end += 1
            while x < run_end:
                length, part = next((length, part) for length, part in candidates
                                    if length <= max_length and length <= run_end-x)
                self.put(part, color, x, z, bottom)
                x += length

    def wall_z(self, x: int, z0: int, z1: int, bottom: int, material,
               *, max_length: int = 8):
        z = z0
        candidates = [(8, "3008"), (6, "3009"), (4, "3010"),
                      (3, "3622"), (2, "3004"), (1, "3005")]
        while z < z1:
            color = material(z)
            if color is None:
                z += 1
                continue
            run_end = z + 1
            while run_end < z1 and material(run_end) == color:
                run_end += 1
            while z < run_end:
                length, part = next((length, part) for length, part in candidates
                                    if length <= max_length and length <= run_end-z)
                self.put(part, color, x, z, bottom, turn=True)
                z += length

    def save(self, name: str) -> Path:
        OUT.mkdir(parents=True, exist_ok=True)
        path = OUT / name
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")
        return path


def build() -> Build:
    b = Build()

    b.section("garden courts and arrival ribbons")
    # Planting and paving are composed as distinct horizontal courts, not a
    # uniform grass carpet. Every plate is rooted directly on the baseplate.
    for x in (1, 5, 9):
        for z in (1, 5):
            b.put("3031", LAWN, x, z, 0)
    for x in (4, 8, 12, 16, 20, 24):
        b.put("3031", STONE if x in (12, 16) else LAWN,
              x, 26, 0)
        b.put("3710", TAN, x, 30, 0)
    for x in (20, 24, 28):
        for z in (1, 5):
            b.put("3031", STONE, x, z, 0)
    for z in (1, 3, 5, 7):
        b.put("3020", TAN, 14, z, 0)
    for x in (1, 5, 9, 13, 17, 21, 25):
        b.put("3710", TAN, x, 0, 0)
    b.put("3023", TAN, 29, 0, 0)
    # Azure pool inset in a light-stone apron, with a narrow dark rim.
    for x in (21, 25):
        for z in (2, 4):
            b.put("3020", WATER, x, z, 1)
    for x in (20, 24, 28):
        b.put("3710", WHITE, x, 1, 1)
        b.put("3710", WHITE, x, 8, 1)

    b.section("rear garden court")
    for x in (6, 22):
        b.put("3022", EARTH, x, 27, 1)
        b.put("3941", GREEN, x, 27, 2)
    for x, z, colour in ((10, 28, 14), (25, 27, 4)):
        b.put("3024", colour, x, z, 1)

    b.section("stepped hillside against the east wall")
    for z, level in ((10, 1), (14, 4), (18, 7), (22, 10), (26, 13)):
        for bottom in range(0, level-1, 3):
            for x in (28, 30):
                for zz in (z, z+2):
                    b.put("3003", EARTH if bottom < 6 else TAN,
                          x, zz, bottom)
        for x in (28, 30):
            for zz in (z, z+2):
                b.put("3022", LAWN if x == 30 or z >= 22 else STONE,
                      x, zz, level-1)
        if z < 26:
            # 3039's origin is half a stud toward its tall edge. The 10-LDU
            # shift aligns the real sloped mesh with these 2x2 stud cells.
            for x in (28, 30):
                b.put("3039", STONE if x == 28 else 378,
                      x, z+2, level, offset_z_ldu=10)
        if z in (10, 18, 22):
            b.put("3024", 4 if z == 18 else 14,
                  30 if z == 18 else 31, z+1, level)
    # The west flank becomes a rising sequence of stone landings. Each tread
    # is carried by its own earth-coloured masonry, not a floating staircase.
    for z, level in ((10, 1), (12, 4), (14, 4), (16, 7),
                     (18, 7), (20, 10), (22, 10), (24, 13)):
        for bottom in range(0, level-1, 3):
            b.put("3001", EARTH, 0, z, bottom)
        b.put("3022", STONE, 0, z, level-1)
        b.put("3022", LAWN, 2, z, level-1)
        if z in (16, 22):
            b.put("3941", GREEN, 2, z, level)

    b.section("recessed lower ground floor")
    b.tile(4, 27, 9, 26, 0, STONE)
    # The front garden ribbon meets the now-forward ground-floor threshold.

    b.section("lower stone and glass facade")
    for course, bottom in enumerate((1, 4, 7, 10)):
        def front(x, c=course):
            if 14 <= x < 17 and c < 3:
                return None  # recessed entrance
            if c in (0, 1, 2) and (6 <= x < 12 or 19 <= x < 25):
                return GLASS
            return CHARCOAL if c == 0 else (EARTH if x < 13 else STONE)
        def back(x, c=course):
            if c in (1, 2) and (8 <= x < 13 or 18 <= x < 24):
                return GLASS
            return CHARCOAL if c == 0 else STONE
        b.wall_x(9, 4, 27, bottom, front,
                 max_length=6 if course % 2 else 8)
        b.wall_x(25, 4, 27, bottom, back,
                 max_length=6 if course % 2 else 8)
        for x in (4, 26):
            def side(z, c=course):
                if (x == 26 and c in (0, 1, 2) and 11 <= z < 23
                        and z not in (16, 22)):
                    return GLASS
                if x == 4 and c in (1, 2) and 11 <= z < 21:
                    return EARTH if z in (15, 19) else GLASS
                return CHARCOAL if c == 0 else (EARTH if x == 4 else STONE)
            b.wall_z(x, 10, 25, bottom, side,
                     max_length=6 if course % 2 else 8)
        # Two internal bearing lines carry the projecting upper living level.
        for x in (10, 21):
            b.put("3003", STONE, x, 18, bottom)
    # Recess the contrasting dark-red door one stud behind the facade.
    for bottom in (1, 4, 7):
        b.put("3004", BROWN, 14, 10, bottom)
        b.put("3005", GLASS, 16, 10, bottom)
    b.put("3023", TAN, 14, 9, 1)

    b.section("framed arrival portal")
    for x in (13, 18):
        b.put("3024", WHITE, x, 8, 0)
        for bottom in (1, 4, 7):
            b.put("3005", WHITE, x, 8, bottom)
    b.put("3009", WHITE, 13, 8, 10)

    b.section("concealed lower bearing grid")
    # A small interior post-and-beam grid gives the gallery a credible load
    # path; front posts are tucked behind the deep balcony, not on its edge.
    b.put("3022", STONE, 18, 6, 0)
    for x, z in ((5, 7), (17, 6), (8, 11), (23, 11)) + tuple(
            (x, z) for z in (16, 19, 22) for x in (8, 15, 23)) + ((17, 11),):
        for bottom in (1, 4, 7, 10):
            b.put("3003" if z <= 7 or (x, z) == (17, 11) else "3005",
                  STONE, x, z, bottom)

    b.section("warm lower rooms behind the panoramic windows")
    for x in (6, 19):
        b.put("3022", TAN, x, 10, 1)
        b.put("3004", EARTH, x, 11, 2)
    b.put("3020", TAN, 7, 13, 1)
    b.put("3020", EARTH, 19, 13, 1)
    b.put("3001", WHITE, 7, 13, 2)
    for bottom in (1, 4):
        b.put("3010", EARTH, 7, 15, bottom)
    b.put("3003", BROWN, 20, 13, 2)
    b.put("3022", TAN, 20, 13, 5)
    b.put("3004", WHITE, 18, 16, 1)

    b.section("cantilever slab and sheltered entry canopy")
    b.tile(4, 28, 9, 25, 13, WHITE)
    # The sheltered balcony is four studs deep on the left, but the glazed
    # right-hand wing remains a separate projecting volume.
    b.tile(4, 20, 5, 9, 13, WHITE)
    b.tile(20, 28, 7, 9, 13, WHITE)
    # Offset second layer bridges the edge-touching lower plates, including
    # the balcony-to-gallery seam, rather than merely thickening each tile.
    b.tile(4, 28, 7, 25, 14, WHITE)
    b.tile(4, 20, 5, 7, 14, WHITE)
    # These three piers carry the projecting front plate course; moving all
    # of them behind its edge fails the load-path equilibrium check.
    for x in (4, 20, 26):
        for bottom in (1, 4, 7, 10):
            b.put("3003" if x in (20, 26) else "3005",
                  WHITE, x, 6, bottom)

    b.section("upper panoramic glass gallery")
    for course, bottom in enumerate((15, 18, 21, 24)):
        def front(x, c=course):
            if x == 20:
                return CHARCOAL
            # A recessed dark service core interrupts the otherwise continuous
            # cyan ribbon. Its narrow lit slot gives the balcony a focal point
            # and makes the two glazed living bays read as separate rooms.
            if 11 <= x < 15:
                return GLASS if x == 12 and c in (1, 2) else CHARCOAL
            if x in (4, 5, 10, 15, 26, 27):
                return TAN if x >= 26 else WHITE
            return GLASS
        def rear(x, c=course):
            if c in (0, 3):
                return TAN if x >= 20 else WHITE
            if x in (4, 7, 13, 19, 24, 27):
                return TAN if x >= 24 else WHITE
            return GLASS
        b.wall_x(9, 4, 20, bottom, front, max_length=6)
        b.put("3004", WHITE, 20, 9, bottom, turn=True)
        b.wall_x(8, 20, 28, bottom, front, max_length=6)
        b.wall_x(24, 4, 28, bottom, rear, max_length=6)
        for x in (4, 27):
            def side(z, c=course):
                if z in (10, 12, 17, 22, 23):
                    return TAN if x == 27 else WHITE
                return GLASS
            b.wall_z(x, 9 if x == 27 else 10, 24, bottom,
                     side, max_length=6)
        for x in (11, 21):
            b.put("3003", WHITE, x, 17, bottom)

    b.section("upper roof bearing grid")
    for x, z in ((x, z) for z in (12, 15, 18, 22) for x in (8, 15, 23)):
        for bottom in (15, 18, 21, 24):
            b.put("3005", WHITE, x, z, bottom)

    b.section("upper living room furnishings")
    b.put("3020", EARTH, 11, 11, 15)
    b.put("3001", TAN, 11, 11, 16)
    for bottom in (15, 18):
        b.put("3010", TAN, 11, 13, bottom)
    b.put("3024", 4, 12, 11, 19)
    b.put("3024", WHITE, 14, 11, 19)
    b.put("3022", BLACK, 17, 14, 15)
    b.put("3003", EARTH, 17, 14, 16)
    b.put("3022", WHITE, 17, 14, 19)

    b.section("warm upper-level interior floor")
    for z in range(11, 23, 2):
        for x in range(6, 26, 2):
            cells = ((xx, zz) for xx in (x, x+1) for zz in (z, z+1))
            if all((xx, zz, 14) in b.occupied and
                   (xx, zz, 15) not in b.occupied for xx, zz in cells):
                b.put("3022", TAN, x, z, 15)

    b.section("visible upper room vignettes")
    for x in (6, 20):
        b.put("3020", TAN, x, 13, 16)
        b.put("3010", EARTH, x, 14, 17)
        b.put("3023", WHITE, x+1, 13, 17)
    b.put("3003", EARTH, 18, 17, 16)
    b.put("3022", WHITE, 18, 17, 19)
    b.put("3003", EARTH, 24, 17, 16)
    b.put("3941", GREEN, 24, 17, 19)

    b.section("balcony rail and planters")
    for x in (4, 8, 12, 16):
        b.put("30055", BLACK, x, 5, 15)
    for x in (5,):
        b.put("3023", EARTH, x, 8, 15)
        b.put("3004", GREEN, x, 8, 16)
    # A low sofa and coffee table establish the extended deck as occupied
    # space; all three elements attach to exposed studs on the balcony slab.
    b.put("3020", TAN, 8, 7, 15)
    b.put("3010", EARTH, 8, 8, 16)
    b.put("3022", EARTH, 14, 7, 15)
    b.put("3068b", WHITE, 14, 7, 16)

    b.section("thin black main roof with light skylight")
    b.tile(4, 28, 9, 25, 27, CHARCOAL,
           color_at=lambda x, z, w, d: GLASS if (x, z, w, d) in
           ((4, 9, 8, 4), (12, 13, 8, 4)) else CHARCOAL)
    b.tile(20, 28, 8, 9, 27, CHARCOAL)
    b.tile(5, 27, 10, 24, 28, CHARCOAL,
           color_at=lambda x, z, w, d: GLASS if (x, z, w, d) in
           ((5, 10, 8, 4), (13, 14, 8, 4)) else CHARCOAL)
    b.tile(20, 28, 8, 10, 28, CHARCOAL)
    # White cap strip provides the fine horizontal edge missing from the slab.
    for x in (4, 8):
        b.put("3710", WHITE, x, 9, 28)
    for x in (12,):
        b.put("4162", WHITE, x, 9, 28)
    b.put("4162", WHITE, 20, 8, 29)
    for x in (4, 27):
        b.put("3666", WHITE, x, 10, 28, turn=True)
        b.put("4162", WHITE, x, 16, 28, turn=True)
        b.put("3024", WHITE, x, 24, 28)
    for x in (5, 13):
        b.put("4162", WHITE, x, 24, 28)
    b.put("3666", WHITE, 21, 24, 28)

    b.section("framed roof skylight")
    for x in (5, 7, 9):
        b.put("3068b", GLASS, x, 10, 29)
    b.put("3666", WHITE, 5, 9, 29)
    b.put("3666", WHITE, 5, 12, 29)
    b.put("3023", WHITE, 4, 10, 29, turn=True)
    b.put("3023", WHITE, 11, 10, 29, turn=True)
    for x in (13, 15, 17):
        b.put("3068b", GLASS, x, 14, 29)
    b.put("3666", WHITE, 13, 13, 29)
    b.put("3666", WHITE, 13, 16, 29)
    b.put("3023", WHITE, 12, 14, 29, turn=True)
    b.put("3023", WHITE, 19, 14, 29, turn=True)

    b.section("offset rooftop lantern")
    for x in (6, 10):
        b.put("3010", GLASS, x, 19, 29)
        b.put("3010", GLASS, x, 23, 29)
    b.put("3004", GLASS, 6, 20, 29, turn=True)
    b.put("3005", WHITE, 13, 22, 29)
    b.tile(6, 14, 19, 24, 32, CHARCOAL)
    # Finish the lantern cap with smooth tiles; the roof plates below still
    # provide the overlapping structural layer.
    for z in (19, 21):
        for x in (6, 8, 10, 12):
            b.put("3068b", CHARCOAL, x, z, 33)
    for x in (6, 8, 10, 12):
        b.put("3069b", CHARCOAL, x, 23, 33)

    b.section("rooftop terrace")
    b.tile(16, 26, 19, 23, 29, TAN)
    b.put("3022", TAN, 14, 20, 29)
    for x in (17, 23):
        b.put("3022", EARTH, x, 20, 30)
        b.put("3003", GREEN, x, 20, 31)
    b.put("3020", WHITE, 19, 20, 30)
    b.put("3020", TAN, 19, 20, 31)
    # This official statuette has its LDraw origin at the foot, unlike bricks.
    b.put("90398", 4, 22, 19, 30, base_origin=True)
    for x in (16, 20, 24, 25):
        b.put("3005", BLACK, x, 22, 30)
    b.put("4162", BLACK, 16, 22, 33)
    b.put("3069b", BLACK, 24, 22, 33)

    b.section("dark masonry chimney")
    for bottom in (29, 32, 35, 38):
        b.put("3003", CHARCOAL, 14, 18, bottom)
    b.put("3022", BLACK, 14, 18, 41)

    b.section("smooth roof field")
    for z in range(10, 24, 2):
        for x in range(6, 26, 2):
            cells = ((xx, zz) for xx in (x, x+1) for zz in (z, z+1))
            if all((xx, zz, 28) in b.occupied and
                   (xx, zz, 29) not in b.occupied for xx, zz in cells):
                b.put("3068b", CHARCOAL, x, z, 29)

    b.section("trees and planted accents")
    # Two low clipped shrubs soften the otherwise bare stone hillside treads.
    # Their plate-and-brick roots follow each landing's actual top course.
    for z, top in ((14, 4), (18, 7)):
        b.put("3022", EARTH, 28, z, top)
        b.put("3941", GREEN, 28, z, top+1)
    b.put("3022", LAWN, 1, 27, 0)
    for x, z in ((2, 3), (8, 3), (1, 27), (29, 27)):
        ground = 13 if (x, z) == (29, 27) else 1
        b.put("3003", BROWN, x, z, ground)
        if (x, z) == (8, 3):
            # Keep the entrance tree beneath the upper cantilever.
            b.put("3941", GREEN, x, z, ground+3)
            b.put("3942c", GREEN, x, z, ground+6)
        else:
            b.put("3003", BROWN, x, z, ground+3)
            b.put("3941", GREEN, x, z, ground+6)
            b.put("3942c", GREEN, x, z, ground+9)

    b.section("poolside furniture and garden texture")
    # Two pared-back loungers make the right-hand stone terrace read as a
    # usable exterior space. They sit on its existing ground plates.
    for z in (2, 7):
        b.put("3023", WHITE, 29, z, 1)
        b.put("3023", TAN, 29, z, 2)
    for x, z in ((3, 7), (11, 2)):
        b.put("3022", EARTH, x, z, 1)
        b.put("3003", GREEN, x, z, 2)
    for x, z, color in ((2, 2, 4), (7, 7, 14), (10, 7, WHITE),
                        (11, 4, 14), (2, 6, WHITE)):
        b.put("3024", color, x, z, 1)
    for x in (12, 19):
        b.put("3005", BLACK, x, 6, 1)
        b.put("3024", WHITE, x, 6, 4)
        b.put("3024", BLACK, x, 6, 5)

    return b


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args()
    model = build()
    path = model.save("build.ldr")
    print(json.dumps({"file": str(path), "parts": sum(model.stages.values()),
                      "stages": model.stages}, indent=2))
    check = check_model(path, ground_y=8)
    (OUT / "check.json").write_text(json.dumps(check, indent=2) + "\n")
    print(json.dumps({"passed": check["passed"], "checks": check["checks"],
                      "errors": check["errors"][:3]}, indent=2)[:5000])
    if not check["passed"]:
        raise SystemExit("Construction checks failed; see check.json")
    if not args.no_render:
        render_ldr_to_png(path, OUT / "front-right.png", azimuth=325,
                          elevation=28, resolution=1000)
        render_ldr_to_png(path, OUT / "front-left.png", azimuth=215,
                          elevation=28, resolution=1000)
        render_ldr_to_png(path, OUT / "front.png", azimuth=270,
                          elevation=18, resolution=1000)


if __name__ == "__main__":
    main()
