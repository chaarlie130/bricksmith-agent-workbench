#!/usr/bin/env python3
"""Live 3D build viewer — watch an .ldr file and serve it with Three.js LDrawLoader.

Usage:
    python scripts/live_view.py runs/my-build/build.ldr [--port 8111]

Opens a browser page with full 3D LDraw rendering: real studs, edge lines,
PBR environment lighting, and interactive orbit controls. Auto-reloads when
the .ldr file changes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import unquote

LDRAW_DIR = Path(__file__).resolve().parents[1] / "data" / "ldraw"


class BuildState:
    """Thread-safe state tracking for the watched .ldr file."""

    def __init__(self, ldr_path: Path):
        self.ldr_path = ldr_path
        self.lock = threading.Lock()
        self.revision = 0
        self.last_mtime = 0.0
        self.last_hash = ""
        self.part_count = 0

    def check(self) -> bool:
        """Check if the .ldr file changed. Returns True if updated."""
        if not self.ldr_path.exists():
            return False

        mtime = self.ldr_path.stat().st_mtime
        if mtime == self.last_mtime:
            return False

        content = self.ldr_path.read_text(encoding="utf-8", errors="replace")
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        if content_hash == self.last_hash:
            self.last_mtime = mtime
            return False

        part_count = sum(1 for line in content.splitlines()
                         if line.strip().startswith("1 ") and line.strip().endswith(".dat"))

        with self.lock:
            self.last_mtime = mtime
            self.last_hash = content_hash
            self.part_count = part_count
            self.revision += 1
            rev = self.revision

        print(f"  Rev {rev}: {part_count} parts  [{content_hash}]")
        return True

    def status_json(self) -> dict:
        with self.lock:
            return {
                "revision": self.revision,
                "part_count": self.part_count,
                "hash": self.last_hash,
            }


def watch_loop(state: BuildState, interval: float = 0.8):
    state.check()
    while True:
        time.sleep(interval)
        try:
            state.check()
        except Exception as e:
            print(f"  Watch error: {e}")


# ─── HTML + Three.js viewer ─────────────────────────────────────────────────

HTML_PAGE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>🧱 BrickSmith Live 3D View</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #161823; color: #e0e0e0; overflow: hidden;
         font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', monospace; touch-action: none; }
  #canvas-container { width: 100vw; height: 100vh; touch-action: none; }
  canvas { display: block; touch-action: none; }
  #hud {
    position: fixed; top: 0; left: 0; right: 0;
    padding: 12px 20px;
    background: rgba(18, 20, 32, 0.85);
    backdrop-filter: blur(10px);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    display: flex; justify-content: space-between; align-items: center;
    z-index: 10; pointer-events: none;
  }
  #hud h1 { font-size: 1.15em; color: #ff5252; letter-spacing: 0.5px; }
  .stats { display: flex; gap: 24px; font-size: 0.9em; }
  .stat-label { color: #888; }
  .stat-value { color: #4ecca3; font-weight: bold; }
  .dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%;
         margin-right: 6px; background: #4ecca3; animation: pulse 2s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  #loading {
    position: fixed; top: 50%; left: 50%; transform: translate(-50%,-50%);
    font-size: 1.1em; color: #4ecca3; z-index: 20;
    background: rgba(18,20,32,0.9); padding: 14px 28px; border-radius: 10px;
    border: 1px solid rgba(78,204,163,0.3); pointer-events: none;
  }
  #flash {
    position: fixed; top: 60px; right: 20px;
    background: rgba(78, 204, 163, 0.2); color: #4ecca3;
    padding: 6px 16px; border-radius: 20px; font-size: 0.8em;
    border: 1px solid rgba(78,204,163,0.4);
    opacity: 0; transition: opacity 0.3s; z-index: 15;
  }
  #flash.show { opacity: 1; }
  #controls-hint {
    position: fixed; bottom: 16px; left: 20px;
    font-size: 0.8em; color: #666; z-index: 10; pointer-events: none;
  }
</style>
</head>
<body>
<div id="hud">
  <h1>🧱 BrickSmith Live 3D</h1>
  <div class="stats">
    <div><span class="dot"></span><span class="stat-label">Live</span></div>
    <div><span class="stat-label">Revision </span><span class="stat-value" id="rev">0</span></div>
    <div><span class="stat-label">Bricks </span><span class="stat-value" id="parts">0</span></div>
  </div>
</div>
<div id="flash">✓ Updated</div>
<div id="loading">Loading LDraw model…</div>
<div id="controls-hint">Left-drag to rotate · Right-drag to pan · Scroll to zoom</div>
<div id="canvas-container"></div>

<script type="importmap">
{
  "imports": {
    "three": "https://cdn.jsdelivr.net/npm/three@0.174.0/build/three.module.js",
    "three/addons/": "https://cdn.jsdelivr.net/npm/three@0.174.0/examples/jsm/"
  }
}
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { LDrawLoader } from 'three/addons/loaders/LDrawLoader.js';
import { LDrawConditionalLineMaterial } from 'three/addons/materials/LDrawConditionalLineMaterial.js';

const POLL_MS = 1000;
let lastRev = -1;
let scene, camera, renderer, controls, model;
const loading = document.getElementById('loading');

// ── Three.js setup ──
function initThree() {
  const container = document.getElementById('canvas-container');
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x1a1c26);

  camera = new THREE.PerspectiveCamera(40, window.innerWidth / window.innerHeight, 1, 15000);
  camera.position.set(200, 200, 300);

  renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  container.appendChild(renderer.domElement);

  // Environment for realistic plastic reflections
  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  scene.environment = pmremGenerator.fromScene(new RoomEnvironment()).texture;

  // Key and fill lights
  const keyLight = new THREE.DirectionalLight(0xffffff, 2.0);
  keyLight.position.set(200, 400, 250);
  scene.add(keyLight);

  const fillLight = new THREE.DirectionalLight(0xb0c4de, 0.8);
  fillLight.position.set(-200, 200, -200);
  scene.add(fillLight);

  const bounceLight = new THREE.DirectionalLight(0xfff0dd, 0.4);
  bounceLight.position.set(0, -200, 0);
  scene.add(bounceLight);

  // Subtle circular ground shadow ring / grid
  const grid = new THREE.GridHelper(600, 30, 0x333745, 0x242735);
  grid.position.y = 0;
  scene.add(grid);

  // Controls
  controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;
  controls.target.set(0, 0, 0);
  controls.update();

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  animate();
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}

// ── LDraw Loader Setup ──
const ldrawLoader = new LDrawLoader();
ldrawLoader.setConditionalLineMaterial(LDrawConditionalLineMaterial);
ldrawLoader.setPartsLibraryPath('/ldraw/');
ldrawLoader.smoothNormals = true;

let materialsReady = false;

async function ensureMaterials() {
  if (!materialsReady) {
    loading.textContent = 'Loading official LDraw color palette…';
    await ldrawLoader.preloadMaterials('/ldraw/LDConfig.ldr');
    materialsReady = true;
  }
}

async function loadModel() {
  loading.style.display = 'block';
  loading.textContent = 'Loading model…';

  try {
    await ensureMaterials();
    const resp = await fetch('/model.ldr?t=' + Date.now());
    if (!resp.ok) throw new Error('HTTP ' + resp.status);
    const text = await resp.text();

    ldrawLoader.parse(text, (group) => {
      if (model) scene.remove(model);
      model = group;

      // Invert Y: LDraw uses -Y as UP; rotating 180° around X turns it into standard +Y UP
      model.rotation.x = Math.PI;

      // Enhance materials slightly for crispness
      model.traverse(c => {
        if (c.isMesh && c.material) {
          const mats = Array.isArray(c.material) ? c.material : [c.material];
          mats.forEach(m => {
            m.roughness = 0.3;
            m.metalness = 0.05;
          });
        }
      });

      scene.add(model);

      // Auto-frame camera smoothly on model bounds
      const box = new THREE.Box3().setFromObject(model);
      const center = box.getCenter(new THREE.Vector3());
      const size = box.getSize(new THREE.Vector3());
      const maxDim = Math.max(size.x, size.y, size.z, 30);
      const dist = maxDim * 2.2;

      controls.target.copy(center);
      camera.position.set(center.x + dist * 0.7, center.y + dist * 0.6, center.z + dist * 0.7);
      controls.update();

      loading.style.display = 'none';

      const flash = document.getElementById('flash');
      flash.classList.add('show');
      setTimeout(() => flash.classList.remove('show'), 1500);
    }, (error) => {
      console.error('LDraw parse error:', error);
      loading.textContent = 'LDraw Parse Error: ' + error.message;
    });
  } catch(e) {
    console.error('Load error:', e);
    loading.textContent = 'Error: ' + e.message;
  }
}

// ── Polling Loop ──
async function poll() {
  try {
    const resp = await fetch('/status.json?t=' + Date.now());
    if (!resp.ok) return;
    const data = await resp.json();
    document.getElementById('rev').textContent = data.revision;
    document.getElementById('parts').textContent = data.part_count;

    if (data.revision !== lastRev) {
      lastRev = data.revision;
      loadModel();
    }
  } catch(e) { /* server starting */ }
}

initThree();
setInterval(poll, POLL_MS);
poll();
</script>
</body>
</html>
"""


# ─── HTTP Handler ────────────────────────────────────────────────────────────

def make_handler(state: BuildState, ldraw_dir: Path):

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_HEAD(self):
            self._handle_request(send_body=False)

        def do_GET(self):
            self._handle_request(send_body=True)

        def _handle_request(self, send_body: bool = True):
            path = unquote(self.path.split("?")[0])

            if path == "/" or path == "/index.html":
                self._serve_text(HTML_PAGE, "text/html", send_body)

            elif path == "/status.json":
                self._serve_text(json.dumps(state.status_json()), "application/json", send_body)

            elif path == "/model.ldr":
                if state.ldr_path.exists():
                    self._serve_file(state.ldr_path, "text/plain", send_body)
                else:
                    self.send_error(404)

            elif path.startswith("/ldraw/"):
                rel = path[len("/ldraw/"):]
                file_path = ldraw_dir / rel

                # Case-insensitive resolution fallback
                if not file_path.exists():
                    file_path = self._case_insensitive_find(ldraw_dir, rel)

                if file_path and file_path.exists() and file_path.is_file():
                    self._serve_file(file_path, "text/plain", send_body)
                else:
                    self.send_error(404, f"Part not found: {rel}")

            else:
                self.send_error(404)

        def _case_insensitive_find(self, base: Path, rel: str) -> Path | None:
            parts = rel.split("/")
            current = base
            for part in parts:
                if not current.is_dir():
                    return None
                candidate = current / part
                if candidate.exists():
                    current = candidate
                    continue
                found = None
                lower = part.lower()
                for child in current.iterdir():
                    if child.name.lower() == lower:
                        found = child
                        break
                if found:
                    current = found
                else:
                    return None
            return current

        def _serve_text(self, content: str, mime: str, send_body: bool = True):
            data = content.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if send_body:
                self.wfile.write(data)

        def _serve_file(self, filepath: Path, mime: str, send_body: bool = True):
            data = filepath.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", f"{mime}; charset=utf-8")
            if "/ldraw/" in self.path and "/model" not in self.path:
                self.send_header("Cache-Control", "public, max-age=86400")
            else:
                self.send_header("Cache-Control", "no-cache")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            if send_body:
                self.wfile.write(data)

    return Handler


def main():
    parser = argparse.ArgumentParser(description="Live 3D build viewer for BrickSmith .ldr files")
    parser.add_argument("ldr_file", help="Path to the .ldr file to watch")
    parser.add_argument("--port", type=int, default=8111, help="HTTP port (default: 8111)")
    parser.add_argument("--no-browser", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    ldr_path = Path(args.ldr_file).resolve()
    ldraw_dir = LDRAW_DIR.resolve()

    if not ldraw_dir.exists():
        print(f"  ERROR: LDraw library not found at {ldraw_dir}")
        sys.exit(1)

    print(f"\n  🧱 BrickSmith Live 3D Viewer")
    print(f"  {'─'*40}")
    print(f"  Model:    {ldr_path}")
    print(f"  LDraw:    {ldraw_dir}")
    print(f"  Parts:    {sum(1 for _ in (ldraw_dir / 'parts').glob('*.dat'))} .dat files")

    state = BuildState(ldr_path)

    watcher = threading.Thread(target=watch_loop, args=(state,), daemon=True)
    watcher.start()

    server = HTTPServer(("127.0.0.1", args.port), make_handler(state, ldraw_dir))
    url = f"http://127.0.0.1:{args.port}"
    print(f"  Server:   {url}")
    print(f"  {'─'*40}\n")

    if not args.no_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Shutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
