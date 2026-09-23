#!/usr/bin/env python3
"""Render an LDraw model file to an axonometric PNG."""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bricksmith.rendering.rasterizer import render_ldr_to_png


def main():
    parser = argparse.ArgumentParser(description="Render an LDraw model file to an axonometric PNG.")
    parser.add_argument("ldr_file", type=Path, help="Path to input .ldr file")
    parser.add_argument("--output", "-o", type=Path, default=None, help="Output PNG path (defaults to <ldr_file>.png)")
    parser.add_argument("--azimuth", type=float, default=35.0, help="Camera azimuth angle in degrees")
    parser.add_argument("--elevation", type=float, default=28.0, help="Camera elevation angle in degrees")
    parser.add_argument("--resolution", "-r", type=int, default=800, help="Image resolution in pixels")
    args = parser.parse_args()

    if not args.ldr_file.exists():
        print(f"Error: {args.ldr_file} does not exist.", file=sys.stderr)
        sys.exit(1)

    out_path = args.output or args.ldr_file.with_suffix(".png")
    print(f"Rendering {args.ldr_file.name} -> {out_path.name}...")
    render_ldr_to_png(
        ldr_path=args.ldr_file,
        output_png=out_path,
        azimuth=args.azimuth,
        elevation=args.elevation,
        resolution=args.resolution,
    )
    print(f"Done! Render saved to: {out_path}")


if __name__ == "__main__":
    main()
