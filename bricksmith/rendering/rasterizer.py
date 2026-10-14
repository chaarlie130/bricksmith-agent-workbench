"""Software axonometric rasterizer for fast geometry QA renders of LEGO models."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
from functools import lru_cache
import re
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
    28: "#897d62",   # Dark Tan
    288: "#00451a",  # Dark Green
    71: "#a0a4a5",   # Light Bluish Gray
    72: "#626567",   # Dark Bluish Gray
    41: "#559ab7",   # Trans-Medium Blue
    47: "#fcfcfc",   # Trans-Clear
    70: "#693b2a",   # Reddish Brown
    378: "#7c9082",  # Sand Green
    297: "#b89548",  # Pearl Gold
}


@lru_cache(maxsize=1)
def ldraw_colors() -> dict[int, str]:
    """Use actual LDraw palette values so design previews preserve colour choices."""
    palette = dict(COLORS)
    config = Path(__file__).resolve().parents[2] / "data/ldraw/LDConfig.ldr"
    if config.is_file():
        for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.startswith("0 !COLOUR "):
                continue
            match = re.search(r"\bCODE\s+(\d+)\s+VALUE\s+(#[0-9A-Fa-f]{6})\b", line)
            if match:
                palette[int(match.group(1))] = match.group(2)
    return palette


@lru_cache(maxsize=1)
def ldraw_opacity() -> dict[int, float]:
    """Read LDraw ALPHA values; missing ALPHA means an opaque material."""
    config = Path(__file__).resolve().parents[2] / "data/ldraw/LDConfig.ldr"
    opacity = {}
    if config.is_file():
        for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.search(r"\bCODE\s+(\d+)\b.*?\bALPHA\s+(\d+)\b", line)
            if match:
                opacity[int(match.group(1))] = min(1.0, max(0.0, int(match.group(2)) / 255.0))
    return opacity


def preview_face_opacity(material_opacity: float) -> float:
    """Convert a transparent part's target opacity to each mesh skin.

    LDraw's ALPHA describes the material, whereas the software rasterizer
    blends both the front and rear triangles of a solid clear brick. Applying
    ALPHA to each skin makes a two-sided pane substantially more opaque than
    intended and hides the interior that agents need to inspect. Choose the
    per-face opacity whose two-layer composition equals the material value.
    """
    if not 0.0 < material_opacity < 1.0:
        return material_opacity
    return 1.0 - (1.0 - material_opacity) ** 0.5


def rasterize(triangles: np.ndarray, colors: np.ndarray, width: int, height: int,
              background: str = "#f5f4ef", opacity: np.ndarray | None = None) -> np.ndarray:
    """Depth rasterize opaque geometry, then composite translucent faces."""
    pixels = np.full((height, width, 3), to_rgb(background), dtype=np.float32)
    depth = np.full((height, width), -np.inf, dtype=np.float32)
    if opacity is None:
        opacity = np.ones(len(triangles), dtype=np.float32)
    if len(opacity) != len(triangles):
        raise ValueError("One opacity value is required per triangle")

    opaque = np.flatnonzero(opacity >= 0.999)
    translucent = np.flatnonzero((opacity > 0) & (opacity < 0.999))
    # Projected depth increases toward the camera. Back-to-front blending is
    # approximate for intersecting translucent meshes but preserves the
    # important see-through view of studs and interiors behind glazing.
    translucent = translucent[np.argsort(triangles[translucent, :, 2].mean(axis=1))]
    for index in np.concatenate((opaque, translucent)):
        triangle, color, alpha = triangles[index], colors[index], float(opacity[index])
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
        region = pixels[y0:y1 + 1, x0:x1 + 1]
        if alpha >= 0.999:
            current[visible] = d[visible]
            region[visible] = color
        else:
            region[visible] = alpha * color + (1.0 - alpha) * region[visible]
    return pixels


def project(triangles: np.ndarray, azimuth: float, elevation: float = 24.0, resolution: int = 900) -> np.ndarray:
    """Project LDraw triangles (negative Y up) to 2D screen coordinates."""
    az_rad, el_rad = np.deg2rad([azimuth, elevation])
    eye = np.array([np.cos(el_rad) * np.cos(az_rad), -np.sin(el_rad),
                    np.cos(el_rad) * np.sin(az_rad)])
    right = np.array([-np.sin(az_rad), 0.0, np.cos(az_rad)])
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

    meshes, facecolors, faceopacity = [], [], []
    light = np.array([0.35, -1.0, 0.4])
    light /= np.linalg.norm(light)

    for pid, m, c in zip(graph.part_ids, graph.transforms, graph.colors):
        tris = local_triangles(pid) @ m[:3, :3].T + m[:3, 3]
        normals = np.cross(tris[:, 1] - tris[:, 0], tris[:, 2] - tris[:, 0])
        lens = np.linalg.norm(normals, axis=1, keepdims=True)
        normals = np.divide(normals, lens, out=np.zeros_like(normals), where=lens > 1e-9)

        base_hex = ldraw_colors().get(c, "#a0a4a5")
        base_rgb = np.array(to_rgb(base_hex), dtype=np.float32)

        # Ambient + Lambertian diffuse shading
        shade = np.clip(normals @ light, 0.0, 1.0)[:, None]
        colors = base_rgb * (0.65 + 0.35 * shade)

        meshes.append(tris)
        facecolors.append(colors)
        faceopacity.append(np.full(
            len(tris), preview_face_opacity(ldraw_opacity().get(c, 1.0)),
            dtype=np.float32))

    all_tris = np.concatenate(meshes, axis=0)
    all_colors = np.concatenate(facecolors, axis=0)
    all_opacity = np.concatenate(faceopacity, axis=0)

    proj = project(all_tris, azimuth=azimuth, elevation=elevation, resolution=resolution)
    img = rasterize(proj, all_colors, resolution, resolution, opacity=all_opacity)

    out = Path(output_png)
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.imsave(str(out), img)
    return out
