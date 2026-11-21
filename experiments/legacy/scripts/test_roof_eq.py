#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bricksmith.workbench.feedback import check_model
import scripts.test_mansion_with_partitions as mp

def test_roof():
    # Let's inspect what happens when we replace Stage 8 in test_mansion_with_partitions
    me = mp.build_mansion()
    
    # Let's see the validation of me as is
    p = Path("test_mansion_partitions.ldr")
    res = check_model(p)
    print("Initial check:", res.get("passed"), res.get("checks"))

if __name__ == "__main__":
    test_roof()
