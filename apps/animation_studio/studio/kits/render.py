"""A Python Playwright port of the kits' render.mjs: serve a folder, open the page with ?render=1, step the frames, pipe them to ffmpeg.

One protocol is shared by every kit: the page sets window.ready, window.CONFIG {width,height,fps,duration}, window.renderFrame(n)
(or window.frameJPEG(n) for the 3D styles) and window.renderAudio() (a base64 WAV of the whole sound mix)."""
from __future__ import annotations

import base64
import re
import http.server
import subprocess
import threading
from pathlib import Path
from typing import Callable
from urllib.parse import quote, unquote, urlparse

from .. import config

MIME = {".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript", ".css": "text/css", ".json": "application/json",
        ".png": "image/png", ".jpg": "image/jpeg", ".mp3": "audio/mpeg", ".wav": "audio/wav", ".ttf": "font/ttf", ".woff2": "font/woff2"}
CHROME_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-webgl",
               "--force-color-profile=srgb", "--autoplay-policy=no-user-gesture-required", "--no-sandbox"]


class RenderError(RuntimeError):
    pass


class _Handler(http.server.BaseHTTPRequestHandler):
    root: Path
    overlay: dict[str, Path]

    def log_message(self, *a) -> None:  # silence
        pass

    def do_GET(self) -> None:  # noqa: N802
        rel = unquote(urlparse(self.path).path).lstrip("/")
        p = self.overlay.get(rel) or (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents and rel not in self.overlay:
            return self._send(403, b"")
        try:
            self._send(200, p.read_bytes(), MIME.get(p.suffix.lower(), "application/octet-stream"))
        except OSError:
            self._send(404, b"")

    def _send(self, code: int, data: bytes, ctype: str = "text/plain") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Session:
    """One browser page on one served folder. Use as a context manager."""

    def __init__(self, root: Path, page: str, query: str = "render=1", overlay: dict[str, Path] | None = None, size: tuple[int, int] | None = None):
        self.root, self.page, self.query, self.overlay, self.size = root.resolve(), page, query, overlay or {}, size
        self.errors: list[str] = []
        self.cfg: dict = {}

    def __enter__(self) -> "Session":
        from playwright.sync_api import sync_playwright
        h = type("H", (_Handler,), {"root": self.root, "overlay": self.overlay})
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=True, args=CHROME_ARGS)
        self.pg = self.browser.new_page()
        three = self.overlay.get("__three__")
        if three is None:
            from .paths import THREE as three
        # three.js r160 is shipped: serve it for the kits' CDN tag (cdnjs .../0.160.0/...) and for relative three.min.js, so no internet is needed
        self.pg.route(re.compile(r"(0\.160\.0/three\.min\.js|^http://127\.0\.0\.1:\d+/three\.min\.js)"),
                      lambda r: r.fulfill(status=200, content_type="text/javascript", body=Path(three).read_bytes()))
        self.pg.on("pageerror", lambda e: self.errors.append(str(e)))
        self.pg.on("console", lambda m: self.errors.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        url = f"http://127.0.0.1:{self.srv.server_address[1]}/{quote(self.page)}?{self.query}"
        try:
            self.pg.goto(url, wait_until="load", timeout=120000)
            import time
            t0 = time.time()
            while True:                       # poll in short waits so a page error ends it at once instead of after the 5-minute timeout
                try:
                    self.pg.wait_for_function("window.ready === true || window.__err", timeout=1500)
                    break
                except Exception:  # noqa: BLE001 - not ready yet
                    if self.errors or time.time() - t0 > 300:
                        raise
        except Exception as e:  # noqa: BLE001
            self.close()
            raise RenderError(self.errors[0] if self.errors else f"the page did not become ready: {str(e)[:200]}") from e
        err = self.pg.evaluate("window.__err || null")
        if err or self.errors:
            e0 = err or self.errors[0]
            self.close()
            raise RenderError(str(e0)[:600])
        self.cfg = self.pg.evaluate("window.CONFIG")
        if not self.cfg or not self.cfg.get("width"):
            self.close()
            raise RenderError("the page has no window.CONFIG")
        self.pg.set_viewport_size({"width": int(self.cfg["width"]), "height": int(self.cfg["height"])})
        return self

    def close(self) -> None:
        for fn in (lambda: self.browser.close(), lambda: self.pw.stop(), lambda: self.srv.shutdown()):
            try:
                fn()
            except Exception:  # noqa: BLE001
                pass

    def __exit__(self, *a) -> None:
        self.close()

    # ----- frames -----
    def frame(self, n: int, kind: str = "jpeg") -> bytes:
        """kind 'jpeg'/'png' = screenshot after renderFrame(n); 'canvas' = the page's own frameJPEG(n) (the 3D styles)."""
        if kind == "canvas":
            b = base64.b64decode(self.pg.evaluate("n => window.frameJPEG(n)", n))
        else:
            self.pg.evaluate("n => window.renderFrame(n)", n)
            w, h = int(self.cfg["width"]), int(self.cfg["height"])
            b = self.pg.screenshot(type=kind, clip={"x": 0, "y": 0, "width": w, "height": h}, **({"quality": 92} if kind == "jpeg" else {}))
        if self.errors:
            raise RenderError(self.errors[0][:600])
        return b

    def audio_wav(self) -> bytes:
        return base64.b64decode(self.pg.evaluate("window.renderAudio()"))


def stills(sess: Session, seconds: list[float], kind: str = "png") -> list[bytes]:
    fps, dur = float(sess.cfg["fps"]), float(sess.cfg["duration"])
    last = max(0, round(dur * fps) - 1)
    return [sess.frame(min(round(s * fps), last), "canvas" if kind == "canvas" else kind) for s in seconds]


def video(sess: Session, out: Path, work: Path, progress: Callable[[int, int, float], None] | None = None,
          frame_kind: str = "jpeg", vo: Path | None = None, cancel: Callable[[], None] | None = None,
          limit: int | None = None) -> dict:
    """Render every frame and the sound mix, mux with ffmpeg. `vo` (3D styles) is mixed under/over the effects."""
    import time
    fps, dur = int(sess.cfg["fps"]), float(sess.cfg["duration"])
    n = round(dur * fps)
    if limit:
        n, dur = min(n, limit), min(n, limit) / fps
    wav = work / "mix.wav"
    has_mix = bool(sess.pg.evaluate("typeof window.renderAudio === 'function'"))
    if has_mix:
        wav.write_bytes(sess.audio_wav())
    elif not vo:
        raise RenderError("the page makes no sound and no voice file was given")
    ff = [config.ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg" if frame_kind != "png" else "png", "-i", "-"]
    if has_mix and vo:
        ff += ["-i", str(wav), "-i", str(vo), "-filter_complex", "[1:a][2:a]amix=inputs=2:normalize=0,loudnorm=I=-15:TP=-1.5:LRA=11[a]", "-map", "0:v", "-map", "[a]"]
    elif has_mix:
        ff += ["-i", str(wav), "-map", "0:v", "-map", "1:a"]
    else:
        ff += ["-i", str(vo), "-map", "0:v", "-map", "1:a"]
    ff += ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{dur:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
           "-pix_fmt", "yuv420p", "-r", str(fps), "-movflags", "+faststart", str(out)]
    enc = subprocess.Popen(ff, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    t0 = time.time()
    try:
        for f in range(n):
            if cancel:
                cancel()
            enc.stdin.write(sess.frame(f, frame_kind))
            if progress and (f % 10 == 0 or f == n - 1):
                progress(f + 1, n, (time.time() - t0) / (f + 1))
        enc.stdin.close()
        err = enc.stderr.read().decode("utf-8", "replace")
        if enc.wait() != 0:
            raise RenderError("ffmpeg failed: " + err[-300:])
    except BaseException:
        try:
            enc.kill()
        except Exception:  # noqa: BLE001
            pass
        raise
    finally:
        wav.unlink(missing_ok=True)
    if not out.is_file() or out.stat().st_size < 1500:
        raise RenderError("the MP4 failed its check")
    return {"frames": n, "fps": fps, "seconds": dur, "width": sess.cfg["width"], "height": sess.cfg["height"]}
