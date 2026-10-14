# The Reichstag Building - Master Builder Edition
from pathlib import Path

PARTS_INFO = {
    # Bricks (h=3)
    "3001": {"h": 3, "R0": (4, 2), "R90": (2, 4), "R180": (4, 2), "R270": (2, 4)},
    "3003": {"h": 3, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    "3004": {"h": 3, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "3005": {"h": 3, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3010": {"h": 3, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},
    "3622": {"h": 3, "R0": (3, 1), "R90": (1, 3), "R180": (3, 1), "R270": (1, 3)},
    "3009": {"h": 3, "R0": (6, 1), "R90": (1, 6), "R180": (6, 1), "R270": (1, 6)},
    "3008": {"h": 3, "R0": (8, 1), "R90": (1, 8), "R180": (8, 1), "R270": (1, 8)},
    "3062b": {"h": 3, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3941": {"h": 3, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    # Plates (h=1)
    "3024": {"h": 1, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3023": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "3623": {"h": 1, "R0": (3, 1), "R90": (1, 3), "R180": (3, 1), "R270": (1, 3)},
    "3710": {"h": 1, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},
    "3022": {"h": 1, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    "3020": {"h": 1, "R0": (4, 2), "R90": (2, 4), "R180": (4, 2), "R270": (2, 4)},
    "3031": {"h": 1, "R0": (4, 4), "R90": (4, 4), "R180": (4, 4), "R270": (4, 4)},
    "3034": {"h": 1, "R0": (8, 2), "R90": (2, 8), "R180": (8, 2), "R270": (2, 8)},
    "3035": {"h": 1, "R0": (8, 4), "R90": (4, 8), "R180": (8, 4), "R270": (4, 8)},
    "3030": {"h": 1, "R0": (10, 4), "R90": (4, 10), "R180": (10, 4), "R270": (4, 10)},
    "3666": {"h": 1, "R0": (6, 1), "R90": (1, 6), "R180": (6, 1), "R270": (1, 6)},
    "3795": {"h": 1, "R0": (6, 2), "R90": (2, 6), "R180": (6, 2), "R270": (2, 6)},
    # Tiles (h=1)
    "3070b": {"h": 1, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3069b": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "2412b": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
    "2431": {"h": 1, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},
    "6636": {"h": 1, "R0": (6, 1), "R90": (1, 6), "R180": (6, 1), "R270": (1, 6)},
    "4162": {"h": 1, "R0": (8, 1), "R90": (1, 8), "R180": (8, 1), "R270": (1, 8)},
    # Cones & Antennas
    "3942c": {"h": 6, "R0": (2, 2), "R90": (2, 2), "R180": (2, 2), "R270": (2, 2)},
    "59900": {"h": 3, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "3957": {"h": 12, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "90398": {"h": 5, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "15332": {"h": 6, "R0": (4, 1), "R90": (1, 4), "R180": (4, 1), "R270": (1, 4)},
    "50746": {"h": 2, "R0": (1, 1), "R90": (1, 1), "R180": (1, 1), "R270": (1, 1)},
    "15573": {"h": 1, "R0": (2, 1), "R90": (1, 2), "R180": (2, 1), "R270": (1, 2)},
}

LIVE_BUILD_PATH = Path("runs/romanesque-chapel-20261001/build.ldr")
ARCHIVE_BUILD_PATH = Path("the_reichstag.ldr")

class MasterEngine:
    def __init__(self, name="The Reichstag - Master Builder Edition", w_studs=64, d_studs=56):
        self.name = name
        self.w_studs = w_studs
        self.d_studs = d_studs
        self.x_origin = -((w_studs * 20.0) / 2.0)
        self.z_origin = -((d_studs * 20.0) / 2.0)
        self.lines = [
            f"0 {name}",
            "0 Name: build.ldr",
            "0 Author: Antigravity Master Builder"
        ]
        self.occupied = {} 
        self.part_count = 0

    def place(self, part, color, kx, mz, py, rot="R0"):
        if part not in PARTS_INFO:
            raise ValueError(f"Unknown part: {part}")
            
        info = PARTS_INFO[part]
        w, d = info[rot]
        h = info["h"]
        
        # Collision check
        for dy in range(h):
            for dx in range(w):
                for dz in range(d):
                    cx, cz, cy = kx + dx, mz + dz, py + dy
                    if (cx, cz, cy) in self.occupied:
                        raise ValueError(f"COLLISION: {part} at stud ({cx}, {cz}), plate {cy}.")
                        
        # Occupy
        for dy in range(h):
            for dx in range(w):
                for dz in range(d):
                    self.occupied[(kx + dx, mz + dz, py + dy)] = True
                    
        # LDU Coordinates
        x_ldu = self.x_origin + (kx * 20.0) + ((w * 20.0) / 2.0)
        z_ldu = self.z_origin + (mz * 20.0) + ((d * 20.0) / 2.0)
        ytop = 0.0 if py == 0 else -(py + h - 1) * 8.0
        
        rot_matrix = {
            "R0":   "1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 1.0",
            "R90":  "0.0 0.0 1.0 0.0 1.0 0.0 -1.0 0.0 0.0",
            "R180": "-1.0 0.0 0.0 0.0 1.0 0.0 0.0 0.0 -1.0",
            "R270": "0.0 0.0 -1.0 0.0 1.0 0.0 1.0 0.0 0.0"
        }
        
        self.lines.append(f"1 {color} {x_ldu} {ytop} {z_ldu} {rot_matrix[rot]} {part}.dat")
        self.part_count += 1

    def save(self):
        LIVE_BUILD_PATH.parent.mkdir(parents=True, exist_ok=True)
        LIVE_BUILD_PATH.write_text("\n".join(self.lines))
        ARCHIVE_BUILD_PATH.write_text("\n".join(self.lines))

def build_and_broadcast():
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  COMMENCING LIVE BROADCAST: THE REICHSTAG (MASTER BUILDER EDITION)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    
    me = MasterEngine()
    
    # Colors
    DARK_BLUISH_GRAY = 72
    LIGHT_BLUISH_GRAY = 71
    TAN = 19
    DARK_TAN = 2
    TRANS_LIGHT_BLUE = 43
    TRANS_CLEAR = 47
    BLACK = 0
    RED = 4
    YELLOW = 14
    GOLD = 115
    WHITE = 15
    GREEN = 2

    stages = []

    def stage_1_foundation():
        print("▶ Stage 1/8: Massive Foundation Baseplates (py=0)...")
        for mz in range(0, 56, 4):
            for kx in range(0, 64, 8):
                me.place("3035", DARK_BLUISH_GRAY, kx, mz, 0, "R0") 
    stages.append(("Foundation Baseplates", stage_1_foundation))

    def stage_2_plaza_and_steps():
        print("▶ Stage 2/8: Public Plaza & Grand Staircase (py=1..3)...")
        def is_safe(x, z):
            if z < 8: return x < 22 or x >= 42
            if z >= 48: return True
            return x < 4 or x >= 60

        # High detail 2x2 paving
        for mz in range(0, 56, 2):
            for kx in range(0, 64, 2):
                if is_safe(kx, mz) and is_safe(kx+1, mz) and is_safe(kx, mz+1) and is_safe(kx+1, mz+1):
                    me.place("3022", LIGHT_BLUISH_GRAY, kx, mz, 1, "R0")

        # Plaza details (Micro-people and lampposts)
        import random
        random.seed(42)
        people_colors = [RED, 1, GREEN, WHITE, BLACK] # 1 is Blue
        for _ in range(50):
            px = random.randint(0, 63)
            pz = random.randint(0, 7)
            if is_safe(px, pz) and (px, pz, 2) not in me.occupied:
                me.place("3024", random.choice(people_colors), px, pz, 2, "R0") # Micro-person
                
        # Lampposts along the front
        for px in [4, 12, 20, 43, 51, 59]:
            if is_safe(px, 1) and (px, 1, 2) not in me.occupied:
                me.place("3062b", BLACK, px, 1, 2, "R0")
                me.place("59900", TRANS_CLEAR, px, 1, 5, "R0") # Lantern

        # Grand Steps
        step_parts = [("3795", 2), ("3020", 4), ("3022", 6)] # 2x6, 2x4, 2x2
        for step, (part, st_mz) in enumerate(step_parts):
            py = step + 1
            # Step base
            for kx in range(22, 42, 2):
                me.place(part, LIGHT_BLUISH_GRAY, kx, st_mz, py, "R90")
            
            # Lion statues on step edges
            if step == 0:
                me.place("3004", DARK_BLUISH_GRAY, 20, 2, 2, "R90")
                me.place("3004", DARK_BLUISH_GRAY, 42, 2, 2, "R90")
                me.place("90398", GOLD, 20, 3, 5, "R0") # Statuette
                me.place("90398", GOLD, 42, 3, 5, "R0") # Statuette

    stages.append(("Plaza & Steps", stage_2_plaza_and_steps))

    def build_rusticated_wall(py):
        # First, solid walls py=1..6
        for p in [py, py+3]:
            # North left
            me.place("3008", DARK_TAN, 4, 8, p, "R0")
            me.place("3008", DARK_TAN, 12, 8, p, "R0")
            me.place("3010", DARK_TAN, 20, 8, p, "R0")
            # North right
            me.place("3008", DARK_TAN, 40, 8, p, "R0")
            me.place("3010", DARK_TAN, 48, 8, p, "R0")
            me.place("3008", DARK_TAN, 52, 8, p, "R0")
            
            # West
            for mz in range(9, 41, 8):
                me.place("3008", DARK_TAN, 4, mz, p, "R90")
            me.place("3009", DARK_TAN, 4, 41, p, "R90")
            me.place("3005", DARK_TAN, 4, 47, p, "R0")
            
            # East
            for mz in range(9, 41, 8):
                me.place("3008", DARK_TAN, 59, mz, p, "R90")
            me.place("3009", DARK_TAN, 59, 41, p, "R90")
            me.place("3005", DARK_TAN, 59, 47, p, "R0")
            
            # South
            for kx in range(5, 53, 8):
                me.place("3008", DARK_TAN, kx, 47, p, "R0")
            me.place("3009", DARK_TAN, 53, 47, p, "R0")
            
            # Inner Courtyard (solid portico rear)
            me.place("3008", DARK_TAN, 24, 14, p, "R0")
            me.place("3008", DARK_TAN, 32, 14, p, "R0")
            
        # Ledge at py=7..9 (sticking out by 1 stud using 1x2 bricks R90)
        p = py + 6
        for kx in range(4, 24, 2): me.place("3004", DARK_TAN, kx, 7, p, "R90")
        for kx in range(40, 60, 2): me.place("3004", DARK_TAN, kx, 7, p, "R90")
        
        for mz in range(9, 47, 2): me.place("3004", DARK_TAN, 3, mz, p, "R0")
        for mz in range(9, 47, 2): me.place("3004", DARK_TAN, 59, mz, p, "R0")
        
        for kx in range(5, 59, 2): me.place("3004", DARK_TAN, kx, 47, p, "R90")
        
        # Inner courtyard at p doesn't have a ledge, just regular wall
        me.place("3008", DARK_TAN, 24, 14, p, "R0")
        me.place("3008", DARK_TAN, 32, 14, p, "R0")

    def stage_3_rusticated_base():
        print("▶ Stage 3/8: Textured Rusticated Stone Base (py=1..9)...")
        build_rusticated_wall(1)
    stages.append(("Rusticated Base", stage_3_rusticated_base))

    def build_facade_layer(py, is_window):
        color = TRANS_CLEAR if is_window else TAN
        # North Left Wing
        for kx in range(4, 23, 3):
            me.place("3004", TAN, kx, 7, py, "R90") # Pilaster
        for kx in [5, 8, 11, 14, 17, 20]:
            if is_window:
                # 1x2 window built of plates for texture
                me.place("3023", TRANS_CLEAR, kx, 8, py, "R0")
                me.place("50746", DARK_TAN, kx, 7, py, "R180")
                me.place("50746", DARK_TAN, kx+1, 7, py, "R180")
                me.place("3023", TRANS_CLEAR, kx, 8, py+1, "R0")
                me.place("3023", TRANS_CLEAR, kx, 8, py+2, "R0")
            else:
                me.place("3004", TAN, kx, 8, py, "R0")
        me.place("3005", TAN, 23, 8, py, "R0")

        # North Right Wing
        for kx in range(41, 60, 3):
            me.place("3004", TAN, kx, 7, py, "R90") # Pilaster
        for kx in [42, 45, 48, 51, 54, 57]:
            if is_window:
                me.place("3023", TRANS_CLEAR, kx, 8, py, "R0")
                me.place("50746", DARK_TAN, kx, 7, py, "R180")
                me.place("50746", DARK_TAN, kx+1, 7, py, "R180")
                me.place("3023", TRANS_CLEAR, kx, 8, py+1, "R0")
                me.place("3023", TRANS_CLEAR, kx, 8, py+2, "R0")
            else:
                me.place("3004", TAN, kx, 8, py, "R0")
        me.place("3005", TAN, 40, 8, py, "R0")

        # West Wing (kx=4)
        for mz in range(9, 46, 3):
            me.place("3004", TAN, 3, mz, py, "R0") # Pilaster
        for mz in [10, 13, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43]:
            if is_window:
                me.place("3023", TRANS_CLEAR, 4, mz, py, "R90")
                me.place("50746", DARK_TAN, 3, mz, py, "R270")
                me.place("50746", DARK_TAN, 3, mz+1, py, "R270")
                me.place("3023", TRANS_CLEAR, 4, mz, py+1, "R90")
                me.place("3023", TRANS_CLEAR, 4, mz, py+2, "R90")
            else:
                me.place("3004", TAN, 4, mz, py, "R90")
        me.place("3005", TAN, 4, 46, py, "R0")

        # East Wing (kx=59)
        for mz in range(9, 46, 3):
            me.place("3004", TAN, 59, mz, py, "R0") # Pilaster
        for mz in [10, 13, 16, 19, 22, 25, 28, 31, 34, 37, 40, 43]:
            if is_window:
                me.place("3023", TRANS_CLEAR, 59, mz, py, "R90")
                me.place("50746", DARK_TAN, 60, mz, py, "R90")
                me.place("50746", DARK_TAN, 60, mz+1, py, "R90")
                me.place("3023", TRANS_CLEAR, 59, mz, py+1, "R90")
                me.place("3023", TRANS_CLEAR, 59, mz, py+2, "R90")
            else:
                me.place("3004", TAN, 59, mz, py, "R90")
        me.place("3005", TAN, 59, 46, py, "R0")
        
        # South Wing (mz=47)
        for kx in range(5, 59, 3):
            me.place("3004", TAN, kx, 47, py, "R90") # Pilaster sticking out south
        for kx in [6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48, 51, 54, 57]:
            if is_window:
                me.place("3023", TRANS_CLEAR, kx, 47, py, "R0")
                me.place("50746", DARK_TAN, kx, 48, py, "R0")
                me.place("50746", DARK_TAN, kx+1, 48, py, "R0")
                me.place("3023", TRANS_CLEAR, kx, 47, py+1, "R0")
                me.place("3023", TRANS_CLEAR, kx, 47, py+2, "R0")
            else:
                me.place("3004", TAN, kx, 47, py, "R0")

        # Inner Portico wall
        me.place("3008", TAN, 24, 14, py, "R0")
        me.place("3008", TAN, 32, 14, py, "R0")

    def stage_4_main_floor():
        print("▶ Stage 4/8: Architectural Facade, Pilasters, Windows (py=10..21)...")
        for py in [10, 13, 16, 19]:
            is_win = (py == 10 or py == 16)
            build_facade_layer(py, is_window=is_win)
            
        # Portico Columns
        for kx in [24, 27, 30, 32, 35, 38]:
            for py in [10, 13, 16, 19, 22]:
                me.place("3941", TAN, kx, 8, py, "R0")
    stages.append(("Main Facade", stage_4_main_floor))

    def stage_5_cornice_and_ceiling():
        print("▶ Stage 5/8: Upper Cornice & Solid Ceiling Slabs (py=22..24)...")
        # Cap walls
        build_facade_layer(22, is_window=False)
        
        # Solid plates over the rooms (py=25) to bind all walls together!
        # Left Wing (kx=4..23, mz=8..47)
        for z in range(8, 48, 4):
            me.place("3030", LIGHT_BLUISH_GRAY, 4, z, 25, "R0") # 10x4 covering kx=4..13
            me.place("3030", LIGHT_BLUISH_GRAY, 14, z, 25, "R0") # 10x4 covering kx=14..23
            
        # Right Wing (kx=40..59, mz=8..47)
        for z in range(8, 48, 4):
            me.place("3030", LIGHT_BLUISH_GRAY, 40, z, 25, "R0") # 10x4 covering kx=40..49
            me.place("3030", LIGHT_BLUISH_GRAY, 50, z, 25, "R0") # 10x4 covering kx=50..59
            
        # Center Block (kx=24..39, mz=20..35)
        for z in range(20, 36, 4):
            me.place("3035", LIGHT_BLUISH_GRAY, 24, z, 25, "R0") # 8x4 covering kx=24..31
            me.place("3035", LIGHT_BLUISH_GRAY, 32, z, 25, "R0") # 8x4 covering kx=32..39
            
        # Portico roof (kx=24..39, mz=10..13)
        me.place("3035", LIGHT_BLUISH_GRAY, 24, 10, 25, "R0") # 8x4
        me.place("3035", LIGHT_BLUISH_GRAY, 32, 10, 25, "R0") # 8x4
    stages.append(("Cornice & Ceiling Slabs", stage_5_cornice_and_ceiling))

    def stage_6_corner_towers():
        print("▶ Stage 6/8: Corner Towers, Colonnades, Cupolas & German Flags (py=26..42)...")
        towers = [(4, 8), (50, 8), (4, 38), (50, 38)]
        for (tx, tz) in towers:
            for py in [26, 29, 32]:
                me.place("3003", TAN, tx, tz, py, "R0")
                me.place("3003", TAN, tx+8, tz, py, "R0")
                me.place("3003", TAN, tx, tz+8, py, "R0")
                me.place("3003", TAN, tx+8, tz+8, py, "R0")
                if py == 32:
                    me.place("3009", TAN, tx+2, tz, py, "R0")
                    me.place("3009", TAN, tx+2, tz+9, py, "R0")
                    me.place("3009", TAN, tx, tz+2, py, "R90")
                    me.place("3009", TAN, tx+9, tz+2, py, "R90")
                elif py == 26:
                    # North/South walls of tower
                    me.place("3005", TAN, tx+2, tz, py, "R0")
                    me.place("3005", TAN, tx+7, tz, py, "R0")
                    me.place("3005", TAN, tx+2, tz, py+3, "R0")
                    me.place("3005", TAN, tx+7, tz, py+3, "R0")
                    me.place("15332", LIGHT_BLUISH_GRAY, tx+3, tz, py, "R0")
                    me.place("3005", TAN, tx+2, tz+9, py, "R0")
                    me.place("3005", TAN, tx+7, tz+9, py, "R0")
                    me.place("3005", TAN, tx+2, tz+9, py+3, "R0")
                    me.place("3005", TAN, tx+7, tz+9, py+3, "R0")
                    me.place("15332", LIGHT_BLUISH_GRAY, tx+3, tz+9, py, "R0")
                    # West/East walls of tower
                    me.place("3005", TAN, tx, tz+2, py, "R0")
                    me.place("3005", TAN, tx, tz+7, py, "R0")
                    me.place("3005", TAN, tx, tz+2, py+3, "R0")
                    me.place("3005", TAN, tx, tz+7, py+3, "R0")
                    me.place("15332", LIGHT_BLUISH_GRAY, tx, tz+3, py, "R90")
                    me.place("3005", TAN, tx+9, tz+2, py, "R0")
                    me.place("3005", TAN, tx+9, tz+7, py, "R0")
                    me.place("3005", TAN, tx+9, tz+2, py+3, "R0")
                    me.place("3005", TAN, tx+9, tz+7, py+3, "R0")
                    me.place("15332", LIGHT_BLUISH_GRAY, tx+9, tz+3, py, "R90")
            # Tower roof (py=35)
            me.place("3030", DARK_BLUISH_GRAY, tx, tz, 35, "R0")
            me.place("3030", DARK_BLUISH_GRAY, tx, tz+4, 35, "R0")
            me.place("3034", DARK_BLUISH_GRAY, tx, tz+8, 35, "R0")
            me.place("3022", DARK_BLUISH_GRAY, tx+8, tz+8, 35, "R0")
            # Cupola / Flagpole base (py=36)
            me.place("3031", DARK_BLUISH_GRAY, tx+3, tz+3, 36, "R0")
            me.place("3941", LIGHT_BLUISH_GRAY, tx+4, tz+4, 37, "R0")
            # German Flag
            me.place("3024", BLACK, tx+4, tz+4, 40, "R0")
            me.place("3024", RED, tx+4, tz+4, 41, "R0")
            me.place("3024", GOLD, tx+4, tz+4, 42, "R0")
            me.place("3957", LIGHT_BLUISH_GRAY, tx+4, tz+4, 43, "R0")
    stages.append(("Corner Towers", stage_6_corner_towers))

    def stage_7_roof_and_portico():
        print("▶ Stage 7/8: Portico Pediment with Frieze & Statues (py=26..30)...")
        
        # Frieze "DEM DEUTSCHEN VOLKE" represented by 1x2 grilles
        # Placed on the roof edge above columns (py=26)
        for kx in range(24, 40, 2):
            me.place("2412b", TAN, kx, 8, 26, "R0")

        # Portico Pediment (Stepped)
        # Base: py=27 (16 wide)
        me.place("3008", TAN, 24, 8, 27, "R0")
        me.place("3008", TAN, 32, 8, 27, "R0")
        # Step 2: py=30 (12 wide)
        me.place("3008", TAN, 26, 8, 30, "R0")
        me.place("3010", TAN, 34, 8, 30, "R0")
        # Step 3: py=33 (8 wide)
        me.place("3008", TAN, 28, 8, 33, "R0")
        
        # Statues on the pediment points!
        # Left point (py=30)
        me.place("3062b", DARK_BLUISH_GRAY, 24, 8, 30, "R0")
        me.place("90398", DARK_BLUISH_GRAY, 24, 8, 33, "R0")
        # Right point (py=30)
        me.place("3062b", DARK_BLUISH_GRAY, 39, 8, 30, "R0")
        me.place("90398", DARK_BLUISH_GRAY, 39, 8, 33, "R0")
        # Center point (py=36)
        me.place("3062b", DARK_BLUISH_GRAY, 31, 8, 36, "R0")
        me.place("90398", DARK_BLUISH_GRAY, 31, 8, 39, "R0")

        # Glass Skylights on wings (between towers mz=8..17 and mz=38..47)
        for z in [20, 26, 32]:
            me.place("3035", TRANS_LIGHT_BLUE, 6, z, 26, "R0") # 8x4 covering kx=6..13
            me.place("3035", TRANS_LIGHT_BLUE, 46, z, 26, "R0") # 8x4 covering kx=46..53
            # Add ribs to skylights
            me.place("2412b", LIGHT_BLUISH_GRAY, 6, z+1, 27, "R0")
            me.place("2412b", LIGHT_BLUISH_GRAY, 12, z+1, 27, "R0")
            me.place("2412b", LIGHT_BLUISH_GRAY, 46, z+1, 27, "R0")
            me.place("2412b", LIGHT_BLUISH_GRAY, 52, z+1, 27, "R0")
    stages.append(("Main Roof & Skylights", stage_7_roof_and_portico))

    def stage_8_glass_dome():
        print("▶ Stage 8/8: The Norman Foster Glass Dome (py=26..41)...")
        cx, cz = 24, 20
        
        def fill_rect(py, x1, x2, z1, z2, color):
            w, d = x2 - x1 + 1, z2 - z1 + 1
            curr_x = x1
            while curr_x <= x2:
                rem_w = x2 - curr_x + 1
                pw = 4 if rem_w >= 4 else (2 if rem_w >= 2 else 1)
                curr_z = z1
                while curr_z <= z2:
                    rem_d = z2 - curr_z + 1
                    pd = 4 if rem_d >= 4 else (2 if rem_d >= 2 else 1)
                    
                    if pw == 4 and pd == 4: me.place("3031", color, curr_x, curr_z, py, "R0")
                    elif pw == 4 and pd == 2: me.place("3020", color, curr_x, curr_z, py, "R0")
                    elif pw == 2 and pd == 4: me.place("3020", color, curr_x, curr_z, py, "R90")
                    elif pw == 4 and pd == 1: me.place("3710", color, curr_x, curr_z, py, "R0")
                    elif pw == 1 and pd == 4: me.place("3710", color, curr_x, curr_z, py, "R90")
                    elif pw == 2 and pd == 2: me.place("3022", color, curr_x, curr_z, py, "R0")
                    elif pw == 2 and pd == 1: me.place("3023", color, curr_x, curr_z, py, "R0")
                    elif pw == 1 and pd == 2: me.place("3023", color, curr_x, curr_z, py, "R90")
                    else: me.place("3024", color, curr_x, curr_z, py, "R0")
                    curr_z += pd
                curr_x += pw

        # Base ring hole was kx=27..36, mz=24..31
        # Build the solid glass dome
        for dy in range(5):
            py = 27 + dy * 3
            x1 = 26 + dy
            x2 = 37 - dy
            z1 = 23 + dy
            z2 = 32 - dy
            if x1 <= x2 and z1 <= z2:
                fill_rect(py, x1, x2, z1, z2, TRANS_LIGHT_BLUE)
                fill_rect(py+1, x1, x2, z1, z2, TRANS_LIGHT_BLUE)
                fill_rect(py+2, x1, x2, z1, z2, TRANS_LIGHT_BLUE)
                
                # Structural ribs (Steel frame of dome)
                if x1 < x2 and z1 < z2:
                    me.place("3024", LIGHT_BLUISH_GRAY, x1, z1, py+3, "R0")
                    me.place("3024", LIGHT_BLUISH_GRAY, x2, z1, py+3, "R0")
                    me.place("3024", LIGHT_BLUISH_GRAY, x1, z2, py+3, "R0")
                    me.place("3024", LIGHT_BLUISH_GRAY, x2, z2, py+3, "R0")
        
        # Lantern Top
        me.place("3941", LIGHT_BLUISH_GRAY, 31, 27, 42, "R0")
    stages.append(("Glass Dome", stage_8_glass_dome))

    # Run stages
    for name, fn in stages:
        fn()
        print(f"  ✓ Broadcasted Stage (Pieces so far: {me.part_count})")
        
    me.save()
    print(f"\nFinal Part Count: {me.part_count} pieces")

if __name__ == "__main__":
    build_and_broadcast()