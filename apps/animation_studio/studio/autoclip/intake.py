"""Getting the source video: your own file, or a link. Links go through yt-dlp when it is installed (pip install yt-dlp).

YouTube often refuses downloads from servers and home PCs ("Sign in to confirm you're not a bot"). This does not try to get around that
(no cookie copying, no tricks): it says so and suggests an upload, or a Twitch / Kick / direct link. Clip videos you own or may use."""
from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import sys
import urllib.parse
from pathlib import Path

BLOCKED = re.compile(r"sign in to confirm|not a bot|http error 403|http error 429|too many requests|unable to extract|po token|login required|private video", re.I)


def public_url(url: str) -> str:
    u = urllib.parse.urlparse(url.strip())
    if u.scheme not in ("http", "https") or not u.hostname:
        raise RuntimeError("Paste a full link that starts with https://")
    try:
        infos = socket.getaddrinfo(u.hostname, None)
    except OSError as e:
        raise RuntimeError("That link's address could not be found.") from e
    for i in infos:
        ip = ipaddress.ip_address(i[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise RuntimeError("That link points inside your own network, so it was not opened.")
    return url.strip()


def is_youtube(url: str) -> bool:
    return bool(re.search(r"(^|//)(www\.|m\.)?(youtube\.com|youtu\.be)/", url, re.I))


def have_ytdlp() -> bool:
    try:
        import yt_dlp  # noqa: F401
        return True
    except Exception:  # noqa: BLE001
        return False


_PCT = re.compile(r"PCT\s+([\d.]+)%\s*\|\s*(.*)")


def _report(fh, progress) -> None:
    """The newest yt-dlp progress line -> (percent, 'x MiB of y MiB | speed | ETA')."""
    try:
        fh.flush()
        with open(fh.name, "r", errors="replace") as f:
            f.seek(max(0, os.path.getsize(fh.name) - 600))
            lines = f.read().splitlines()
    except OSError:
        return
    for ln in reversed(lines):
        m = _PCT.search(ln)
        if m:
            progress(float(m.group(1)), "Downloading: " + " | ".join(x.strip() for x in m.group(2).split("|") if "NA" not in x and x.strip()))
            return


def ytdlp_base() -> list[str]:
    """The yt-dlp command every call starts with: your cookies.txt when you added one, and a JavaScript runtime for YouTube when only Node is installed."""
    import shutil
    cmd = [sys.executable, "-m", "yt_dlp"]
    ck = _cookies()
    if ck:
        cmd += ["--cookies", ck]
    try:
        import yt_dlp.version as v
        new = tuple(int(x) for x in v.__version__.split(".")[:3]) >= (2025, 11, 12)
    except Exception:  # noqa: BLE001
        new = False
    if new and shutil.which("node") and not shutil.which("deno"):
        cmd += ["--js-runtimes", "node"]
    if new and (shutil.which("deno") or shutil.which("node")):
        cmd += ["--remote-components", "ejs:github"]          # fetches YouTube's challenge-solver script when the pip package for it is missing or out of date
    return cmd


def _cookies() -> str:
    from . import store
    f = store.ROOT / "cookies.txt"
    return str(f) if f.is_file() else ""


FRAGMENT = re.compile(r"^source\.f[\w-]+\.")                 # source.f251.webm: one half (audio or video) of a download that was never merged


def find_source(d: Path) -> Path | None:
    """The job's real video file: never a .srt, a .part, or a leftover half such as source.f251.webm (that one is audio only)."""
    ok = [p for p in d.glob("source.*") if p.suffix.lower() not in (".srt", ".part", ".ytdl", ".json", ".vtt") and not FRAGMENT.match(p.name)]
    return max(ok, key=lambda p: p.stat().st_size) if ok else None


def download(url: str, dest: Path, log=None, cancel=None, progress=None, section: tuple[float, float] | None = None) -> Path:
    url = public_url(url)
    if not have_ytdlp():
        raise RuntimeError("Links need yt-dlp. Run: docker compose exec animation-studio pip install yt-dlp   (or upload the video file instead).")
    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob("source.*"):                  # leftovers of an earlier, unfinished download would be mistaken for the video
        if FRAGMENT.match(f.name) or f.suffix.lower() == ".part":
            f.unlink(missing_ok=True)
    cmd = ytdlp_base() + ["--no-playlist", "--newline", "--progress-template", "download:PCT %(progress._percent_str)s | %(progress._downloaded_bytes_str)s of %(progress._total_bytes_estimate_str)s | %(progress._speed_str)s | ETA %(progress._eta_str)s", "--max-filesize", "4G", "-f", "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b/best",
           "--merge-output-format", "mp4", "-o", str(dest / "source.%(ext)s"), "--print", "after_move:filepath", url]
    if section:                      # a long stream: fetch only the minutes asked for
        cmd[cmd.index("--max-filesize"):cmd.index("--max-filesize")] = ["--download-sections", f"*{int(section[0])}-{int(section[1])}"]
    if log:
        log("Downloading the video…")
    # Run it as a child we can stop: the Stop button used to wait for the whole download to finish.
    import tempfile
    import time
    with tempfile.NamedTemporaryFile("w+") as so, tempfile.NamedTemporaryFile("w+") as se:
        proc = subprocess.Popen(cmd, stdout=so, stderr=se, text=True)
        t0 = time.time()
        try:
            while proc.poll() is None:
                if cancel:
                    cancel()                      # raises Stopped
                if progress:
                    _report(so, progress)
                if time.time() - t0 > 7200:
                    proc.kill()
                    raise RuntimeError("The download took longer than 2 hours.")
                time.sleep(0.5)
        except BaseException:
            proc.kill()
            proc.wait()
            for f in dest.glob("source.*"):       # half-downloaded pieces
                f.unlink(missing_ok=True)
            raise
        so.seek(0)
        se.seek(0)
        stdout, stderr = so.read(), se.read()
    out = [ln for ln in stdout.strip().splitlines() if ln.strip()]
    if proc.returncode != 0 or not out or not Path(out[-1]).is_file():
        text = stderr[-600:]
        if BLOCKED.search(text):
            who = "YouTube" if is_youtube(url) else "That site"
            why = (text.strip().splitlines() or [""])[-1][:160]
            hint = (" It wants a signed-in browser: put a cookies.txt in the studio's autoclip folder." if re.search(r"not a bot|sign in|login required", text, re.I) else
                    " Update the downloader (pip install -U yt-dlp) or try again later." )
            raise RuntimeError(f"{who} isn't letting Auto Clip download this right now.{hint} Or upload the file, or use a Twitch or Kick link. Reason: {why}")
        raise RuntimeError("The download failed: " + (text.strip().splitlines() or ["unknown error"])[-1][:200])
    return Path(out[-1])


def live_urls(url: str) -> list[str]:
    """The direct stream address(es) of a live video (one muxed stream, or a video and an audio one)."""
    r = subprocess.run(ytdlp_base() + ["--no-playlist", "-g", "-f", "best[height<=720]/best/bv*[height<=720]+ba", "--no-warnings", url],
                       capture_output=True, text=True, timeout=90)
    urls = [ln.strip() for ln in r.stdout.splitlines() if ln.strip().startswith("http")][:2]
    if r.returncode != 0 or not urls:
        text = (r.stderr or "").strip().splitlines()
        if BLOCKED.search(r.stderr or ""):
            raise RuntimeError("The site isn't letting Auto Clip open this live stream right now. Try again in a few minutes.")
        raise RuntimeError("Could not open the live stream: " + (text[-1][:160] if text else "no address found"))
    return urls


def record_live(url: str, seconds: int, dest: Path, log=None, cancel=None, progress=None) -> Path:
    """Record the next `seconds` of a live stream to dest/source.mp4 (stream copy: no quality loss, little CPU). Stop works at any time; a stream that ends early keeps what it got."""
    import tempfile
    import time
    from .. import config
    url = public_url(url)
    if not have_ytdlp():
        raise RuntimeError("Links need yt-dlp. Run: docker compose exec animation-studio pip install yt-dlp")
    dest.mkdir(parents=True, exist_ok=True)
    seconds = int(max(30, min(seconds, 4 * 3600)))
    if log:
        log(f"Recording the live stream for {seconds // 60} minute{'s' if seconds >= 120 else ''}…")
    urls = live_urls(url)
    out = dest / "source.mp4"
    ins: list[str] = []
    for u in urls:
        ins += (["-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5"] if u.startswith("http") else []) + ["-i", u]       # ride out a brief network drop
    maps = ["-map", "0:v:0?", "-map", "0:a:0?"] if len(urls) == 1 else ["-map", "0:v:0", "-map", "1:a:0"]
    cmd = [config.ffmpeg(), "-hide_banner", "-nostdin", "-y", "-loglevel", "error", "-progress", "pipe:1", *ins, "-t", str(seconds), *maps, "-c", "copy", "-movflags", "+faststart", str(out)]
    got = 0.0
    with tempfile.NamedTemporaryFile("w+") as so, tempfile.NamedTemporaryFile("w+") as se:
        proc = subprocess.Popen(cmd, stdout=so, stderr=se, text=True)
        t0 = time.time()
        try:
            while proc.poll() is None:
                if cancel:
                    cancel()
                try:
                    so.flush()
                    with open(so.name, "r", errors="replace") as f:
                        f.seek(max(0, os.path.getsize(so.name) - 400))
                        ms = re.findall(r"out_time_(?:us|ms)=(\d+)", f.read())
                    got = int(ms[-1]) / 1e6 if ms else got
                except (OSError, ValueError):
                    pass
                if progress:
                    progress(min(99.0, 100.0 * got / seconds), f"Recording the live stream: {int(got) // 60}:{int(got) % 60:02d} of {seconds // 60}:{seconds % 60:02d}")
                if time.time() - t0 > seconds + 180:
                    proc.kill()
                    break
                time.sleep(0.5)
        except BaseException:
            proc.kill()
            proc.wait()
            out.unlink(missing_ok=True)
            raise
        se.seek(0)
        err = se.read()[-400:]
    if not out.is_file() or out.stat().st_size < 50_000 or got < 5 and proc.returncode != 0:
        out.unlink(missing_ok=True)
        raise RuntimeError("The live recording failed: " + ((err.strip().splitlines() or ["no video was received"])[-1][:200]))
    return out


def note(msg: str) -> None:
    """A message for the job log when there is no job at hand (printed; harmless)."""
    print(msg, flush=True)
