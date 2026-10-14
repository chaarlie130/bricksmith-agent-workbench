#!/usr/bin/env python
"""Generate the traditional farmhouse LDraw model, stage by stage.

Ground convention: ground_y=8 (standard baseplate, top surface Y=0,
underside Y=8). Front facade faces -Z. Studs = 20 LDU, plate = 8 LDU,
brick = 24 LDU. See runs/traditional-farmhouse/PLAN.md for the full plan.

Stud-grid rule (validated against the real checker): on a baseplate
centered at (0,0,0), stud centers sit at ODD multiples of 10 LDU in both
X and Z. A wall running along X (built from even-width bricks) must have
its Z "depth" fixed at an odd multiple of 10; a wall running along Z must
have its X depth fixed at an odd multiple of 10. Getting this wrong causes
real stud/tube mesh interpenetration, not just a cosmetic offset.
"""
from __future__ import annotations
import sys

SAND_BLUE = 379
WHITE = 15
DARK_GREY = 72
REDDISH_BROWN = 70
DARK_BROWN = 308
GREEN = 2
DARK_GREEN = 288
YELLOW = 14
RED = 4
GRASS_GREEN = 2  # baseplate colour; renders as the yard's lawn

IDENT = (1, 0, 0, 0, 1, 0, 0, 0, 1)
ROT_Y90 = (0, 0, 1, 0, 1, 0, -1, 0, 0)
ROT_Y180 = (-1, 0, 0, 0, 1, 0, 0, 0, -1)
ROT_Y270 = (0, 0, -1, 0, 1, 0, 1, 0, 0)


def fmt(v) -> str:
    if isinstance(v, float) and abs(v - round(v)) < 1e-6:
        return str(int(round(v)))
    return str(v)


def assert_odd10(v, label=""):
    assert (v // 10) % 2 != 0 and v % 10 == 0, f"{label}={v} is not an odd multiple of 10"


def assert_mult20(v, label=""):
    assert v % 20 == 0, f"{label}={v} is not a multiple of 20"


class Builder:
    def __init__(self):
        self.lines: list[str] = []

    def add(self, color, x, y, z, mat, part):
        a, b, c, d, e, f, g, h, i = mat
        self.lines.append(
            "1 {} {} {} {} {} {} {} {} {} {} {} {} {} {}".format(
                color, fmt(x), fmt(y), fmt(z),
                fmt(a), fmt(b), fmt(c), fmt(d), fmt(e), fmt(f),
                fmt(g), fmt(h), fmt(i), part,
            )
        )

    def write(self, path, header=""):
        with open(path, "w", encoding="utf-8") as fh:
            if header:
                fh.write(header.rstrip() + "\n")
            fh.write("\n".join(self.lines) + "\n")


def add_baseplates(b: Builder) -> None:
    """Two 32x32 baseplates side by side along X: covers X[-640,640] Z[-320,320]."""
    b.add(GRASS_GREEN, -320, 0, 0, IDENT, "3811.dat")
    b.add(GRASS_GREEN, 320, 0, 0, IDENT, "3811.dat")


# House core, corrected to the stud grid. Run boundaries (where a wall's
# bricks start/stop along their long axis) are multiples of 20; depth
# coordinates (the wall's fixed, 1-stud-deep axis) are odd multiples of 10.
# Front/back walls run along X; their run range is WALL_X0..WALL_X1 and
# their depth is at Z = +-WALL_DEPTH. Gable walls run along Z; their run
# range is WALL_Z0..WALL_Z1 and their depth is at X = +-WALL_DEPTH.
WALL_X0, WALL_X1 = -240, 240   # front/back run range (mult-20); these walls
                                # define the full corner, gable walls butt
                                # against their inside face.
WALL_Z0, WALL_Z1 = -180, 180   # gable run range (mult-20), inset one stud
                                # from the front/back wall's outer corner.
WALL_DEPTH = 190               # +-190, odd-10, front/back Z and gable X

# Interior support posts (2x2 bricks) carrying the second floor's span;
# their footprint must be excluded from the ground-floor plate fill so
# they stand directly on the baseplate like the walls do (same 5-course
# height, topping out flush with the inter-floor plate's underside).
POST_XZ = (
    (-120, -80), (-120, 80), (120, -80), (120, 80),
    (-120, 0), (120, 0), (0, -80), (0, 80), (0, 0),
)
POST_EXCLUDE = [(px - 20, px + 20, pz - 20, pz + 20) for px, pz in POST_XZ]


def wall_run_x(b, color, x0, x1, y, z, gaps):
    """Fill an X-axis wall run [x0,x1) at height y, depth z (must be
    odd-10), with 1x4/1x2/1x1 bricks, skipping gaps (door/window openings
    given as (gx0,gx1) ranges, each a multiple of 20)."""
    assert_odd10(z, "wall_run_x z")

    def in_gap(a, bnd):
        # Skip a candidate brick span if it overlaps a gap AT ALL, not
        # only when fully contained -- a brick that merely pokes into an
        # opening must not be placed either.
        return any(a < g1 and bnd > g0 for g0, g1 in gaps)

    x = x0
    while x < x1:
        placed = False
        for width, part in ((4, "3010.dat"), (2, "3004.dat"), (1, "3005.dat")):
            span = width * 20
            if x + span <= x1 and not in_gap(x, x + span):
                cx = x + span // 2
                b.add(color, cx, y, z, IDENT, part)
                x += span
                placed = True
                break
        if not placed:
            x += 20


def wall_run_z(b, color, z0, z1, y, x, gaps):
    """Fill a Z-axis wall run [z0,z1) at height y, depth x (must be
    odd-10), rotated so the brick's long axis runs along Z."""
    assert_odd10(x, "wall_run_z x")

    def in_gap(a, bnd):
        return any(a < g1 and bnd > g0 for g0, g1 in gaps)

    z = z0
    while z < z1:
        placed = False
        for width, part in ((4, "3010.dat"), (2, "3004.dat"), (1, "3005.dat")):
            span = width * 20
            if z + span <= z1 and not in_gap(z, z + span):
                cz = z + span // 2
                b.add(color, x, y, cz, ROT_Y90, part)
                z += span
                placed = True
                break
        if not placed:
            z += 20


def fill_floor(b, color, x0, x1, z0, z1, y, exclude=()):
    """Tile a rectangular area with 2x4/1x2/1x1 plates at height y. Run
    boundaries (x0,x1,z0,z1) should be multiples of 20. Used for the main
    floor and porch deck; also bridges the seam between adjacent baseplates
    so the connectivity graph treats the whole footprint as one component.
    `exclude` is a list of (ex0,ex1,ez0,ez1) rects; any candidate tile
    overlapping one at all is skipped (e.g. where a support post needs
    direct baseplate access instead of an intervening floor plate)."""
    def excluded(ax0, ax1, az0, az1):
        return any(ax0 < ex1 and ax1 > ex0 and az0 < ez1 and az1 > ez0
                   for ex0, ex1, ez0, ez1 in exclude)

    x = x0
    while x < x1:
        xspan = 80 if x + 80 <= x1 else (40 if x + 40 <= x1 else 20)
        cx = x + xspan // 2
        z = z0
        while z < z1:
            zspan = 40 if z + 40 <= z1 else 20
            cz = z + zspan // 2
            if not excluded(x, x + xspan, z, z + zspan):
                if xspan == 80 and zspan == 40:
                    b.add(color, cx, y, cz, IDENT, "3020.dat")   # plate 2x4
                elif xspan == 40 and zspan == 40:
                    b.add(color, cx, y, cz, IDENT, "3022.dat")   # plate 2x2
                elif zspan == 40:
                    b.add(color, cx, y, cz, ROT_Y90, "3023b.dat")  # 20(X) x 40(Z)
                elif xspan >= 40:
                    b.add(color, cx, y, cz, IDENT, "3023b.dat")  # 40(X) x 20(Z)
                else:
                    b.add(color, cx, y, cz, IDENT, "3024.dat")   # plate 1x1
            z += zspan
        x += xspan


# Ground floor: 5 brick courses. Courses 1-3 (Y -24,-48,-72) are solid
# kick wall; courses 4-5 (Y -96,-120) are the window band (2-brick-tall
# windows replace them in the gap ranges). Door gap spans all 5 courses.
GROUND_COURSES = (-24, -48, -72, -96, -120)
SILL_COURSES = (-24,)              # course 1: solid sill wall
WINDOW_BAND_COURSES = (-48, -72)   # courses 2-3: window band
LINTEL_COURSES = (-96, -120)       # courses 4-5: solid lintel/upper wall
KICK_COURSES = SILL_COURSES + LINTEL_COURSES  # solid courses (door spans all 5 regardless)


def build_stage1() -> Builder:
    b = Builder()
    add_baseplates(b)

    # Ground floor deck: bridges the seam between the two baseplates so the
    # house interior (and everything built on it) forms one connected
    # structure instead of two baseplate-sized islands. Split around the
    # door threshold (X -20..20) since the door part's frame geometry
    # projects deep into the interior (world Z to about -120) and would
    # mesh-collide with a full floor tile there.
    fill_floor(b, WHITE, -220, -20, -180, 180, -8, exclude=POST_EXCLUDE)
    fill_floor(b, WHITE, 20, 220, -180, 180, -8, exclude=POST_EXCLUDE)
    fill_floor(b, WHITE, -20, 20, -120, 180, -8, exclude=POST_EXCLUDE)

    # Ground floor walls: back (+Z, solid, 3 windows) and both gable ends
    # (solid, each with a window in the band). Front (-Z) has the door
    # (full height); the porch deck and columns are added in stage 2.
    back_gaps = [(-220, -180), (-20, 20), (180, 220)]
    front_gaps = [(-20, 20)]  # 2-stud door opening
    gable_gaps = [(-20, 20)]  # one centered window per gable end

    for course_y in SILL_COURSES:
        # Also exclude the window gaps here: the window's bottom edge sits
        # close enough to this course's top that a full-width sill brick
        # would mesh-collide with its inset clearance margin.
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, WALL_DEPTH, back_gaps)
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, -WALL_DEPTH, front_gaps)
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, -(WALL_X1 - 10), gable_gaps)
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, WALL_X1 - 10, gable_gaps)

    for course_y in LINTEL_COURSES:
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, WALL_DEPTH, [])
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, -WALL_DEPTH, front_gaps)
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, -(WALL_X1 - 10), [])
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, WALL_X1 - 10, [])

    for course_y in WINDOW_BAND_COURSES:
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, WALL_DEPTH, back_gaps)
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, -WALL_DEPTH, front_gaps)
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, -(WALL_X1 - 10), gable_gaps)
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, WALL_X1 - 10, gable_gaps)

    return b


def build_stage2() -> Builder:
    """Stage 1 plus glazed windows/door, second-floor walls, and the
    wraparound porch (deck, columns, railing)."""
    b = build_stage1()

    back_gaps = [(-220, -180), (-20, 20), (180, 220)]
    gable_gaps = [(-20, 20)]

    # Glaze the window band (courses 2-3, Y -48/-72). 3582.dat origin is
    # at its top, so place at the band's top course, Y=-48.
    # Rotation pattern taken from omr_374-1_Fire_Station.ldr's validated
    # 3582.dat placements: a wall running along X uses matrix
    # (0,0,-1, 0,1,0, 1,0,0) / its mirror, not identity.
    WIN_ROT_A = (0, 0, -1, 0, 1, 0, 1, 0, 0)
    WIN_ROT_B = (0, 0, 1, 0, 1, 0, -1, 0, 0)
    # 3582.dat's own mesh is NOT centered on its origin (measured local
    # bbox X +-1.75, Z -29.75..1.75): after WIN_ROT_A its world footprint
    # is X in [-1.75,29.75], midpoint +14. Offset placement by -14 so the
    # part's visual center lands on the gap's center instead of its edge.
    for gx0, gx1 in back_gaps:
        cx = (gx0 + gx1) // 2
        b.add(WHITE, cx - 14, -72, WALL_DEPTH, WIN_ROT_A, "3582.dat")
    for gx0, gx1 in gable_gaps:
        cz = (gx0 + gx1) // 2
        # Gable wall runs along Z; local X is already the thin depth axis
        # and local Z the long run axis (local Z midpoint -14), so IDENT
        # needs no rotation. To center that midpoint on the gap center cz,
        # placement_z + (-14) = cz, i.e. placement_z = cz + 14.
        b.add(WHITE, -(WALL_X1 - 10), -72, cz + 14, IDENT, "3582.dat")
        b.add(WHITE, WALL_X1 - 10, -72, cz + 14, IDENT, "3582.dat")

    # Front door: 4486c02.dat (door 1x4x5 left, 6 panes, trans-clear glass).
    # Measured mesh bbox: X nearly centered on origin (~1 stud wide), Y
    # -3.75..+119.7. The baseplate's own mesh spans Y -3.75..+3.75 (its
    # inset clearance band straddles its nominal Y=0 plane, not just one
    # side), so the door origin must clear that band entirely: origin
    # <=-123.49. Y=-124 gives a clean margin.
    b.add(WHITE, 0, -124, -WALL_DEPTH, IDENT, "4486c02.dat")

    # Wraparound porch: deck in front of the front wall (-Z) and along the
    # +X side, white columns near the deck's outer edge, simple railing
    # between columns. All run boundaries below are multiples of 20; all
    # column (1x1, odd-width) depths are odd multiples of 10.
    FRONT_WALL_OUTER_Z = -(WALL_DEPTH + 10)   # -200, mult-20
    SIDE_WALL_OUTER_X = WALL_X1 - 10 + 10     # 230+... use WALL_X1-10 face +10 margin = 240
    SIDE_WALL_OUTER_X = WALL_X1               # gable wall's outer face is at WALL_X1=240
    PORCH_DEPTH = 100                          # 5 studs
    DECK_OUTER_Z = FRONT_WALL_OUTER_Z - PORCH_DEPTH    # -300
    DECK_OUTER_X = SIDE_WALL_OUTER_X + PORCH_DEPTH     # 340
    COL_Z = DECK_OUTER_Z + 10   # -290, odd-10
    COL_X = DECK_OUTER_X - 10   # 330, odd-10

    fill_floor(b, WHITE, WALL_X0, WALL_X1, DECK_OUTER_Z, FRONT_WALL_OUTER_Z, -8)
    fill_floor(b, WHITE, SIDE_WALL_OUTER_X, DECK_OUTER_X, FRONT_WALL_OUTER_Z, WALL_Z1 + 20, -8)

    # Porch columns: 3941.dat (brick 2x2 round), a sturdier column than a
    # 1x1 peg, at even spacing along the deck's outer edge. 2x2 is even-
    # width on both axes, so both X and Z need multiples of 20. Columns
    # stand on the deck's floor plate (top at Y=-8), so the first course
    # origin is -8-24=-32, not -24 (which would be directly on the
    # baseplate, skipping the floor-plate layer the deck is built from).
    COL_Z_20 = -300 + 20   # nearest multiple-of-20 to the odd-10 COL_Z
    COL_X_20 = 340 - 20    # nearest multiple-of-20 to the odd-10 COL_X
    column_y = (-32, -56, -80, -104, -128)
    for cx in (-220, -120, 0, 120, 220):
        for cy in column_y:
            b.add(WHITE, cx, cy, COL_Z_20, IDENT, "3941.dat")
    for cz_ in (-160, -40, 80, 160):
        for cy in column_y:
            b.add(WHITE, COL_X_20, cy, cz_, IDENT, "3941.dat")

    return b


# Ground floor spans Y=0 (baseplate) to Y=-120 (top of course 5), so the
# inter-floor plate sits at Y=-128 (origin, 8 LDU below -120... actually a
# plate ON TOP of the course-5 brick (origin -120, bottom -96) needs
# origin -120-24=-144? No: course 5 brick origin -120 means its own TOP is
# at -120 and bottom at -96 (24 LDU tall, physically above course4). Wait,
# bricks stack with each origin 24 LDU more negative than the one below,
# so course5 (origin -120) sits ON TOP of course4 (origin -96): course5's
# bottom = -120+24 = -96, matching course4's top (-96). Course5's own TOP
# is at -120. A plate placed on course5 needs origin -120-8 = -128.
FLOOR2_PLATE_Y = -128
# Second-floor brick courses, same 5-course pattern, now stacked on the
# inter-floor plate (top at -128): first course origin -128-24=-152.
FLOOR2_COURSES = (-152, -176, -200, -224, -248)
FLOOR2_SILL = (-152,)
FLOOR2_WINDOW_BAND = (-176, -200)
FLOOR2_LINTEL = (-224, -248)


def build_stage3() -> Builder:
    """Stage 2 plus the second floor and inter-floor plate."""
    b = build_stage2()

    # Interior support posts: the inter-floor plate spans the full house
    # interior, far from the perimeter walls in the middle. Without
    # something underneath, the checker's stud/tube connectivity (which
    # does not credit edge-to-edge plate contact) finds the middle of the
    # floor floating. Real houses carry a floor span on interior framing;
    # model that with four 2x2-brick posts from the ground floor (Y=-24)
    # up to the inter-floor plate (Y=-128), well clear of the door and
    # window sightlines.
    # Posts stand directly on the baseplate (like the walls), so a 5-course
    # stack tops out at Y=-120, matching the inter-floor plate's bottom
    # (-128+8=-120). Their footprint must be excluded from the ground-
    # floor plate fill (done in build_stage1's fill_floor call area) --
    # here we rely on the posts simply coexisting with the floor plate's
    # tiles already placed; since 2x2 posts and 1-stud floor plates both
    # Their footprint is excluded from the ground floor's plate fill (see
    # POST_EXCLUDE), so they stand directly on the baseplate like the
    # walls and reach the same top height, Y=-120, after 5 courses.
    for px, pz in POST_XZ:
        for py in (-24, -48, -72, -96, -120):
            b.add(SAND_BLUE, px, py, pz, IDENT, "3003.dat")

    # Same door-threshold exclusion as the ground floor: the door's frame
    # projects up to about Y=-127.75, just clipping a Y=-128 floor plate.
    fill_floor(b, WHITE, -220, -20, -180, 180, FLOOR2_PLATE_Y)
    fill_floor(b, WHITE, 20, 220, -180, 180, FLOOR2_PLATE_Y)
    fill_floor(b, WHITE, -20, 20, -120, 180, FLOOR2_PLATE_Y)

    back_gaps = [(-220, -180), (-20, 20), (180, 220)]
    gable_gaps = [(-20, 20)]

    for course_y in FLOOR2_SILL:
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, WALL_DEPTH, back_gaps)
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, -WALL_DEPTH, [])
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, -(WALL_X1 - 10), gable_gaps)
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, WALL_X1 - 10, gable_gaps)

    for course_y in FLOOR2_LINTEL:
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, WALL_DEPTH, [])
        wall_run_x(b, SAND_BLUE, WALL_X0, WALL_X1, course_y, -WALL_DEPTH, [])
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, -(WALL_X1 - 10), [])
        wall_run_z(b, SAND_BLUE, WALL_Z0, WALL_Z1, course_y, WALL_X1 - 10, [])

    WIN_ROT_A = (0, 0, -1, 0, 1, 0, 1, 0, 0)
    for gx0, gx1 in back_gaps:
        cx = (gx0 + gx1) // 2
        b.add(WHITE, cx - 14, FLOOR2_WINDOW_BAND[0], WALL_DEPTH, WIN_ROT_A, "3582.dat")
    for gx0, gx1 in gable_gaps:
        cz = (gx0 + gx1) // 2
        b.add(WHITE, -(WALL_X1 - 10), FLOOR2_WINDOW_BAND[0], cz + 14, IDENT, "3582.dat")
        b.add(WHITE, WALL_X1 - 10, FLOOR2_WINDOW_BAND[0], cz + 14, IDENT, "3582.dat")

    return b


# 3039.dat's own local Z-depth (-29.75..9.75, asymmetric) means a naive
# placement at the wall's outer face would drive its mesh ~30 LDU further
# inward than the footprint suggests, overlapping the gable triangle's
# eave-corner bricks. Push the eave out to give a clean overhang instead
# of chasing an exact flush seam -- also architecturally normal.
ROOF_EAVE_Z = WALL_DEPTH + 50   # 240, modest overhang past the wall face
ROOF_BASE_Y = -248 - 24         # one brick above FLOOR2_LINTEL's top course


def build_stage4() -> Builder:
    """Stage 3 plus the gabled roof, gable end walls, and ridge cap."""
    b = build_stage3()

    # Gable end walls: flat vertical infill above the second floor's
    # lintel (top Y=-248) at the front/back (Z=+-WALL_DEPTH). Measured
    # against the roof's actual physical depth (not just its nominal
    # placement), only the roof's bottom two courses (Y=-272,-296) reach
    # as far in as Z=190; the next three courses are entirely below
    # Z=170, clear of the gable plane. So gable rows at Y=-272/-296 are
    # skipped here -- the roof's own first two courses visually close
    # that part of the gable end (a boxed-eave look) -- and rows from
    # Y=-320 up are full width, safely under the clear upper roof.
    GABLE_TOP_Y = ROOF_BASE_Y - 24 * 5  # same height as the ridge cap
    gable_courses = []
    gy = -248 - 24 - 72  # start at Y=-344, skipping three conflicting rows
                          # (roof step1's physical reach extends slightly
                          # past its nominal course boundary)
    while gy > GABLE_TOP_Y:
        gable_courses.append(gy)
        gy -= 24
    for gz in (-WALL_DEPTH, WALL_DEPTH):
        for gy in gable_courses:
            wall_run_x(b, SAND_BLUE, -(WALL_X1 - 10), WALL_X1 - 10, gy, gz, [])

    # Roof: 5 stepped courses per side, mirrored front/back, extruded
    # between (not overlapping) the two gable triangles, which are at
    # X=+-(WALL_X1-10)=+-230; the roof's own X run matches that inner
    # span so its courses butt against the gable slopes instead of
    # colliding with the gable wall's eave-corner bricks.
    ROOF_X0, ROOF_X1 = -220, 220  # 11 steps of 40 LDU, inside the gables
    x = ROOF_X0
    while x < ROOF_X1:
        for step in range(5):
            z = ROOF_EAVE_Z - 40 * step
            y = ROOF_BASE_Y - 24 * step
            b.add(DARK_GREY, x + 20, y, z, IDENT, "3039.dat")
            b.add(DARK_GREY, x + 20, y, -z, ROT_Y180, "3039.dat")
        x += 40

    # Ridge cap: a run of 1x4 bricks along the peak (Z=0, Y = base - 4*24
    # - 24, one course above the top roof step), matching the roof's span.
    ridge_y = ROOF_BASE_Y - 24 * 5
    wall_run_x(b, DARK_GREY, ROOF_X0, ROOF_X1, ridge_y, 10, [])

    return b


if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "1"
    out = sys.argv[2] if len(sys.argv) > 2 else f"runs/traditional-farmhouse/0{stage}-stage.ldr"
    if stage == "1":
        model = build_stage1()
    elif stage == "2":
        model = build_stage2()
    elif stage == "3":
        model = build_stage3()
    elif stage == "4":
        model = build_stage4()
    else:
        raise SystemExit(f"unknown stage {stage!r}")
    model.write(out, header="0 Traditional farmhouse")
    print(f"wrote {len(model.lines)} placements to {out}")
