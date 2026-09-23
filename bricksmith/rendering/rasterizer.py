"""Software axonometric rasterizer for fast geometry QA renders of LEGO models."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb

from bricksmith.physics.validator import BRICKNET_AVAILABLE

if BRICKNET_AVAILABLE:
    import bricknet
    from bricksmith.physics.validator import local_triangles

COLORS = {
    0: "#202326",    # Black
    15: "#e7e7e3",   # White
    19: "#cbb68a",   # Tan
    28: "#958164",   # Dark Green
    71: "#a0a4a5",   # Light Bluish Gray
    72: "#626567",   # Dark Bluish Gray
    47: "#bed9dd",   # Trans-Light Blue
    70: "#693b2a",   # Reddish Brown
    378: "#7c9082",  # Sand Green
    297: "#b89548",  # Pearl Gold
}


def rasterize(triangles: np.ndarray, colors: np.ndarray, width: int, height: int, background: str = "#f5f4ef") -> np.ndarray:
    """Per-pixel depth rasterization with z-buffering in pure NumPy."""
    pixels = np.full((height, width, 3), to_rgb(background), dtype=np.float32)
    depth = np.full((height, width), -np.inf, dtype=np.float32)

    for triangle, color in zip(triangles, colors):
        a, b, c = triangle
        denominator = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
        if abs(denominator) < 1e-10:
            continue
        x0, y0 = np.maximum(np.floor(triangle[:, :2].min(axis=0)).astype(int), 0)
        x1, y1 = np.minimum(np.ceil(triangle[:, :2].max(axis=0)).astype(int), [width - 1, height - 1])
        if x0 > x1 or y0 > y1:
            continue

        x, y = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        u = ((b[1] - c[1]) * (x - c[0]) + (c[0] - b[0]) * (y - c[1])) / denominator
        v = ((c[1] - a[1]) * (x - c[0]) + (a[0] - c[0]) * (y - c[1])) / denominator
        w = 1.0 - u - v
        d = u * a[2] + v * b[2] + w * c[2]

        current = depth[y0:y1 + 1, x0:x1 + 1]
        visible = (u >= -1e-8) & (v >= -1e-8) & (w >= -1e-8) & (d > current)
        current[visible] = d[visible]
        pixels[y0:y1 + 1, x0:x1 + 1][visible] = color
    return pixels


def project(triangles: np.ndarray, azimuth: float, elevation: float = 24.0, resolution: int = 900) -> np.ndarray:
    """Project 3D world triangles to 2D screen coordinates."""
    az_rad, el_rad = np.deg2rad([azimuth, elevation])
    eye = np.array([np.cos(el_rad) * np.cos(az_rad), np.cos(el_rad) * np.sin(az_rad), np.sin(el_rad)])
    right = np.array([-np.sin(az_rad), np.cos(az_rad), 0.0])
    up = np.cross(eye, right)

    projected = triangles @ np.array([right, -up, eye]).T
    low = projected[:, :, :2].min(axis=(0, 1))
    high = projected[:, :, :2].max(axis=(0, 1))
    scale = resolution / (max(high - low) * 1.15)
    projected[:, :, :2] = (projected[:, :, :2] - (low + high) / 2.0) * scale + resolution / 2.0
    return projected


def render_ldr_to_png(
    ldr_path: Union[str, Path],
    output_png: Union[str, Path],
    azimuth: float = 35.0,
    elevation: float = 28.0,
    resolution: int = 800,
    title: Optional[str] = None,
) -> Path:
    """Render an LDraw model file to a clean presentation PNG image."""
    if not BRICKNET_AVAILABLE:
        raise RuntimeError("bricknet is required for mesh rasterization.")

    path = Path(ldr_path)
    graph = bricknet.parse_ldr(path.read_text(encoding="utf-8", errors="ignore"))

    meshes, facecolors = [], []
    light = np.array([0.35, -0.4, 1.0])
    light /= np.linalg.norm(light)

    for pid, m, c in zip(graph.part_ids, graph.transforms, graph.colors):
        tris = local_triangles(pid) @ m[:3, :3].T + m[:3, 3]
        normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        lens = np.linalg.norm(normals, axis=1, keepdims=True)
        normals = np.divide(normals, lens, out=np.zeros_like(normals), where=lens > 1e-9)

        base_hex = COLORS.get(c, "#a0a4a5")
        base_rgb = np.array(to_rgb(base_hex), dtype=np.float32)

        # Ambient + Lambertian diffuse shading
        shade = np.clip(normals @ light, 0.0, 1.0)[:, None]
        colors = base_rgb * (0.65 + 0.35 * shade)

        meshes.append(tris)
        facecolors.append(colors)

    all_tris = np.concatenate(meshes, axis=0)
    all_colors = np.concatenate(facecolors, axis=0)

    proj = project(all_tris, azimuth=azimuth, elevation=elevation, resolution=resolution)
    img = rasterize(proj, all_colors, resolution, resolution)

    out = Path(output_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(str(out), img)
    return out
