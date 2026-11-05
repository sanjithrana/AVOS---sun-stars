"""
AVOS Blender render service - a tiny HTTP server that runs INSIDE Blender.

    Docker (CPU, Cycles):   docker compose up -d blender      (see apps/docker-compose.yml)
    Windows with a GPU:     "C:\\Program Files\\Blender Foundation\\Blender 5.0\\blender.exe" -b ^
                                --python D:\\star\\apps\\blender_service\\server.py
                            (then BLENDER_RENDER_URL=http://host.docker.internal:8090 in apps/.env)

Endpoints
    GET  /health            {"status": "ok", "blender": "5.0.1"}
    GET  /catalog           what the planner may use (environments, actions, props, library assets)
    POST /render            scene JSON (see avos_scene.py) -> video/mp4 bytes

Settings (env vars): AVOS_ASSETS_DIR (default ../blender_assets next to this file),
BLENDER_PORT (8090), BLENDER_ENGINE (cycles | eevee | workbench; eevee needs a GPU),
BLENDER_SAMPLES, BLENDER_GPU=1 (Cycles on the GPU), BLENDER_FPS, BLENDER_WIDTH/HEIGHT.
One render at a time; requests queue.
"""

import json
import os
import queue
import sys
import tempfile
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import bpy  # noqa: E402

import avos_scene  # noqa: E402

ASSETS = os.environ.get("AVOS_ASSETS_DIR") or str(HERE.parent / "blender_assets")
PORT = int(os.environ.get("BLENDER_PORT") or 8090)
# Blender's Python API must only be used from the main thread: HTTP
# requests are served on worker threads, and renders are handed to the
# main thread through this queue (one at a time).
JOBS: "queue.Queue[dict]" = queue.Queue()


def _defaults(spec: dict) -> dict:
    """Server-side quality settings win unless the request sets them."""
    env = os.environ
    spec.setdefault("engine", env.get("BLENDER_ENGINE") or "cycles")
    spec.setdefault("samples", int(env.get("BLENDER_SAMPLES") or 16))
    spec.setdefault("fps", int(env.get("BLENDER_FPS") or 24))
    spec.setdefault("width", int(env.get("BLENDER_WIDTH") or 540))
    spec.setdefault("height", int(env.get("BLENDER_HEIGHT") or 960))
    if env.get("BLENDER_GPU") in ("1", "true", "yes"):
        spec.setdefault("gpu", True)
    return spec


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # one concise line per request
        sys.stderr.write("[avos-blender] " + (fmt % args) + "\n")

    def _json(self, code: int, obj) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            return self._json(200, {"status": "ok", "blender": bpy.app.version_string, "assets": ASSETS})
        if self.path.startswith("/catalog"):
            return self._json(200, avos_scene.catalog(ASSETS))
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/render"):
            return self._json(404, {"error": "not found"})
        try:
            spec = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except json.JSONDecodeError as exc:
            return self._json(400, {"error": f"invalid JSON: {exc}"})
        spec = _defaults(spec)
        job = {"spec": spec, "done": threading.Event()}
        started = time.time()
        JOBS.put(job)
        job["done"].wait()
        if "error" in job:
            return self._json(500, {"error": job["error"]})
        data, info = job["data"], job["info"]
        self.send_response(200)
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("X-Avos-Render-Seconds", f"{time.time() - started:.1f}")
        self.send_header("X-Avos-Frames", str(info.get("frames")))
        self.end_headers()
        self.wfile.write(data)


def main():
    Path(ASSETS).mkdir(parents=True, exist_ok=True)
    for sub in ("characters", "animations", "props"):
        (Path(ASSETS) / sub).mkdir(exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"AVOS Blender service {bpy.app.version_string} on :{PORT} (assets: {ASSETS})", flush=True)
    while True:  # render loop on Blender's main thread
        job = JOBS.get()
        with tempfile.TemporaryDirectory(prefix="avos-bl-") as tmp:
            out = str(Path(tmp) / "shot.mp4")
            try:
                job["info"] = avos_scene.build_and_render(job["spec"], out, ASSETS)
                job["data"] = Path(out).read_bytes()
            except Exception as exc:  # noqa: BLE001
                traceback.print_exc()
                job["error"] = f"{type(exc).__name__}: {exc}"
        job["done"].set()


if __name__ == "__main__":
    main()
