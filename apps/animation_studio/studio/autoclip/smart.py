"""Long videos without downloading them.

A 6 or 23 hour video is gigabytes, but the clips are a minute each. So instead of fetching the whole video this module
  1. reads the video's details (length, chapters, YouTube's "Most replayed" graph): a few KB,
  2. reads its captions (about 100 KB), which give the words with times,
  3. only when there is no replay graph, downloads the AUDIO at low quality (tens of MB) and measures loudness,
  4. later, downloads just the chosen windows (about a minute each) at full video quality.
Nothing here reads cookies or logins beyond the optional cookies.txt that intake already honours.
"""
from __future__ import annotations

import json
import statistics
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from . import intake, pick

PAD = 4.0                    # seconds kept before and after each window, so the cut can start exactly where it should
SMART_SITES = ("youtube", "twitch")


def _exec(cmd: list[str], cancel: Callable[[], None] | None, timeout: float) -> tuple[int, str, str]:
    import tempfile
    with tempfile.NamedTemporaryFile("w+") as so, tempfile.NamedTemporaryFile("w+") as se:
        proc = subprocess.Popen(cmd, stdout=so, stderr=se, text=True)
        t0 = time.time()
        try:
            while proc.poll() is None:
                if cancel:
                    cancel()
                if time.time() - t0 > timeout:
                    proc.kill()
                    raise RuntimeError("That download took too long.")
                time.sleep(0.5)
        except BaseException:
            proc.kill()
            proc.wait()
            raise
        so.seek(0)
        se.seek(0)
        return proc.returncode, so.read(), se.read()


def _blocked(err: str, url: str) -> RuntimeError:
    who = "YouTube" if intake.is_youtube(url) else "That site"
    why = (err.strip().splitlines() or [""])[-1][:160]
    return RuntimeError(f"{who} isn't letting Auto Clip read this right now. Update the downloader (pip install -U \"yt-dlp[default]\"), try later, or upload the file. Reason: {why}")


# ---------- 1. details ----------
def probe(url: str, cancel: Callable[[], None] | None = None) -> dict:
    """Length, title, live state, chapters and the replay graph, without downloading anything."""
    url = intake.public_url(url)
    rc, out, err = _exec(intake.ytdlp_base() + ["--no-playlist", "--skip-download", "--dump-single-json", "--no-warnings", url], cancel, 300)
    if rc != 0 or not out.strip():
        raise _blocked(err, url)
    j = json.loads(out)
    return {"duration": float(j.get("duration") or 0), "title": j.get("title") or "", "live": j.get("live_status") in ("is_live", "is_upcoming"),
            "heatmap": j.get("heatmap") or [], "chapters": j.get("chapters") or [], "has_subs": bool(j.get("subtitles") or j.get("automatic_captions")),
            "has_chat": "live_chat" in (j.get("subtitles") or {}) or bool(j.get("was_live"))}


def heat_curve(heat: list[dict], duration: float) -> list[float]:
    """YouTube's replay graph as one number per second, 0 = ordinary, 1 = what viewers replay most. A flat graph gives all zeros (nothing stands out)."""
    n = int(duration)
    if not heat or n < 10:
        return []
    h = [0.0] * n
    for b in heat:
        for s in range(max(0, int(b["start_time"])), min(n, int(b["end_time"]) + 1)):
            h[s] = max(h[s], float(b["value"]))
    med, top = statistics.median(h), max(h)
    if top - med < 0.08:                                          # even the most replayed part is no different from the rest
        return [0.0] * n
    return [min(1.0, max(0.0, (v - med) / (top - med))) for v in h]


# ---------- 2. captions ----------
def captions(url: str, dest: Path, cancel: Callable[[], None] | None = None) -> list[dict] | None:
    """Cues with word times from the video's own captions (json3), or None when there are none."""
    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob("scout.*.json3"):
        f.unlink(missing_ok=True)
    cmd = intake.ytdlp_base() + ["--no-playlist", "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en.*,en,hi.*,hi,.*-orig", "--sub-format", "json3",
                                 "--no-warnings", "-o", str(dest / "scout.%(ext)s"), intake.public_url(url)]
    rc, _, _ = _exec(cmd, cancel, 300)
    files = sorted(dest.glob("scout.*.json3"), key=lambda f: (0 if ".en" in f.name else 1 if ".hi" in f.name else 2, f.name))
    if files:
        try:
            got = parse_json3(json.loads(files[0].read_text("utf-8")))     # json3 has real word times: best
            if got:
                return got
        except Exception:  # noqa: BLE001
            pass
    from . import yttranscript                                 # refused or none: YouTube's transcript endpoint, any language
    cues, _ = yttranscript.fetch(url)
    return cues


def parse_json3(j: dict) -> list[dict]:
    cues: list[dict] = []
    for ev in j.get("events") or []:
        segs = [s for s in (ev.get("segs") or []) if (s.get("utf8") or "").strip()]
        if not segs or ev.get("tStartMs") is None:
            continue
        t0 = ev["tStartMs"] / 1000.0
        end = t0 + (ev.get("dDurationMs") or 2000) / 1000.0
        words = []
        for i, s in enumerate(segs):
            ws = t0 + (s.get("tOffsetMs") or 0) / 1000.0
            we = t0 + (segs[i + 1].get("tOffsetMs") or 0) / 1000.0 if i + 1 < len(segs) else end
            words.append({"w": s["utf8"].strip(), "s": round(ws, 3), "e": round(max(we, ws + 0.12), 3)})
        text = " ".join(w["w"] for w in words)
        if cues and cues[-1]["text"] == text:
            continue
        cues.append({"start": t0, "end": end, "text": text, "words": words})
    return cues


# ---------- 3. audio only, when there is no replay graph ----------
def audio(url: str, dest: Path, cancel: Callable[[], None] | None = None) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob("scout-audio.*"):
        f.unlink(missing_ok=True)
    cmd = intake.ytdlp_base() + ["--no-playlist", "-f", "worstaudio[abr>=32]/worstaudio/worst", "-o", str(dest / "scout-audio.%(ext)s"), "--print", "after_move:filepath",
                                 "--no-warnings", intake.public_url(url)]
    rc, out, err = _exec(cmd, cancel, 4 * 3600)
    lines = [ln for ln in out.strip().splitlines() if ln.strip()]
    if rc != 0 or not lines or not Path(lines[-1]).is_file():
        raise _blocked(err, url)
    return Path(lines[-1])


# ---------- 4. only the chosen windows ----------
def section(url: str, out_file: Path, t0: float, t1: float, cancel: Callable[[], None] | None = None) -> Path:
    """The video between t0 and t1 seconds as one small mp4 with sound. Tries three ways (exact cut, keyframe cut, one-file format)
    and checks each result is long enough and has audio before using it: a broken download never becomes a 0-second or silent clip."""
    from . import cut
    out_file.parent.mkdir(parents=True, exist_ok=True)
    want = t1 - t0
    tries = [
        ["--download-sections", f"*{int(t0)}-{int(t1) + 1}", "--force-keyframes-at-cuts", "-f", "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b/best"],
        ["--download-sections", f"*{max(0, int(t0) - 2)}-{int(t1) + 3}", "-f", "bv*[height<=1080]+ba/b[height<=1080]/bv*+ba/b/best"],   # keyframe cut (no re-encode)
        ["--download-sections", f"*{max(0, int(t0) - 2)}-{int(t1) + 3}", "-f", "18/b[acodec!=none][vcodec!=none]/best"],                # one file that has both picture and sound
    ]
    last = ""
    best: tuple[float, Path] | None = None
    for k, extra in enumerate(tries):
        for f in out_file.parent.glob(out_file.stem + ".*"):
            f.unlink(missing_ok=True)
        cmd = intake.ytdlp_base() + ["--no-playlist", *extra, "--merge-output-format", "mp4", "-o", str(out_file.with_suffix(".%(ext)s")),
                                     "--print", "after_move:filepath", "--no-warnings", intake.public_url(url)]
        rc, out, err = _exec(cmd, cancel, 1800)
        lines = [ln for ln in out.strip().splitlines() if ln.strip()]
        f = Path(lines[-1]) if lines else None
        if rc == 0 and f and f.is_file():
            dur, aud = cut.media_info(str(f))
            if dur >= 0.92 * want and aud:            # the whole part: done
                if k:
                    intake.note(f"Downloaded that part the {'second' if k == 1 else 'third'} way after the first failed.")
                return f
            if aud and dur >= max(3.0, 0.6 * want) and (best is None or dur > best[0]):
                keep = f.with_name(f.stem + f".try{k}" + f.suffix)  # short but usable: keep it in case the other ways do worse
                f.replace(keep)
                best = (dur, keep)
            last = f"came out {dur:.0f} s long{'' if aud else ' with no sound'}"
        else:
            last = (err.strip().splitlines() or ["unknown error"])[-1][:160]
    if best:
        final = out_file.with_suffix(best[1].suffix)
        best[1].replace(final)
        intake.note(f"YouTube only gave {best[0]:.0f} of the {want:.0f} seconds asked for, so this clip is shorter.")
        return final
    raise _blocked(last, url)


# ---------- the plan ----------
def wanted(url: str, o: dict) -> bool:
    from . import rights
    return o.get("smart") != "off" and rights.platform(url) in SMART_SITES


def parse_chat(path: Path) -> dict[int, int]:
    """Messages per second of the video from a YouTube live-chat replay file (one JSON object per line). Millions of lines are fine: only counts are kept."""
    counts: dict[int, int] = {}
    with open(path, encoding="utf-8", errors="ignore") as fh:
        for line in fh:
            try:
                r = json.loads(line).get("replayChatItemAction") or {}
                off = float(r.get("videoOffsetTimeMsec"))
            except (ValueError, TypeError, AttributeError):
                continue
            if off < 0:
                continue
            acts = r.get("actions") or []
            n = sum(1 for a in acts if isinstance(a, dict) and "addChatItemAction" in a) or (1 if acts else 0)
            if n:
                counts[int(off // 1000)] = counts.get(int(off // 1000), 0) + n
    return counts


def chat(url: str, dest: Path, cancel: Callable[[], None] | None = None) -> dict[int, int] | None:
    """Chat speed of a stream's replay: a few MB of text. None when the video has no chat replay."""
    dest.mkdir(parents=True, exist_ok=True)
    for f in dest.glob("chat*.live_chat.json"):
        f.unlink(missing_ok=True)
    cmd = intake.ytdlp_base() + ["--no-playlist", "--skip-download", "--write-subs", "--sub-langs", "live_chat", "--no-warnings", "-o", str(dest / "chat.%(ext)s"), intake.public_url(url)]
    _exec(cmd, cancel, 1800)
    files = sorted(dest.glob("chat*.live_chat.json"))
    if not files:
        return None
    try:
        counts = parse_chat(files[0])
    except Exception:  # noqa: BLE001
        counts = {}
    finally:
        for f in files:
            f.unlink(missing_ok=True)
    return counts if sum(counts.values()) >= 50 else None


def chat_curve(counts: dict[int, int], duration: float) -> list[float]:
    """0..1 per second: chat speed against this video's usual (median to 95th percentile) and against the previous five minutes, so a surge stands out either way."""
    n = int(duration)
    if n < 2 or not counts:
        return []
    per = [counts.get(i, 0) for i in range(n)]
    cs = [0]
    for x in per:
        cs.append(cs[-1] + x)
    rate = [(cs[min(n, i + 6)] - cs[max(0, i - 4)]) for i in range(n)]            # messages in an 10-second window around each second
    rs = sorted(rate)
    med, p95 = rs[n // 2], rs[min(n - 1, int(n * 0.95))]
    span = max(p95 - med, 3.0)
    rc = [0]
    for x in rate:
        rc.append(rc[-1] + x)
    out = []
    for i in range(n):
        lo, hi = max(0, i - 305), max(0, i - 5)
        base = (rc[hi] - rc[lo]) / (hi - lo) if hi > lo else med
        g = max(0.0, min(1.0, (rate[i] - med) / span))
        loc = max(0.0, min(1.0, (rate[i] - base) / (base + 6.0)))
        out.append(0.5 * g + 0.5 * loc)
    return out


def lex_curve(words: list[dict], n: int, excited: set[str]) -> list[float]:
    """0..1 per second from excited words in the captions ("no way", "insane", "let's go"), smoothed over a few seconds."""
    raw = [0.0] * n
    for w in words:
        i = int(w["s"])
        tok = "".join(ch for ch in w["w"].lower() if ch.isalpha() or ch == "'")
        if 0 <= i < n and (tok in excited or w["w"].endswith("!")):
            raw[i] += 1
    out = []
    for i in range(n):
        seg = raw[max(0, i - 2): i + 3]
        out.append(min(1.0, 0.5 * sum(seg)))
    return out


def fuse(heat: list[float], aud: list[float], cht: list[float], lex: list[float], n: int) -> tuple[list[float], list[str]]:
    """One hype curve from every signal there is. Signals that agree (the crowd, the sound and the replay graph all peaking) rank higher than any one alone."""
    g = lambda a, i: a[i] if i < len(a) else 0.0  # noqa: E731
    used = [name for name, a in (("the replay graph", heat), ("the audio loudness", aud), ("the live chat", cht), ("excited words in the captions", lex)) if a and max(a) > 0]
    out = []
    for i in range(n):
        base = max(g(heat, i), 0.9 * g(aud, i))
        c, x = g(cht, i), g(lex, i)
        if cht and base:
            v = 0.5 * base + 0.35 * c + 0.25 * min(base, c) + 0.12 * x
        elif cht:
            v = 0.85 * c + 0.15 * x
        else:
            v = base + 0.12 * x
        out.append(max(0.0, min(1.0, v)))
    return out, used


def scout(url: str, d: Path, o: dict, hype_mod: Any, log: Callable[[str], None], cb: Callable[[float | None, str], None], cancel: Callable[[], None]) -> dict | None:
    """Returns {"duration", "cues", "curve", "how", "smart": True}, or None when the video is short enough to simply download (or smart mode is off)."""
    if not wanted(url, o):
        return None
    cb(None, "Reading the video's details (length, replay graph). Nothing is downloaded yet.")
    info = probe(url, cancel)
    cancel()
    if info["live"]:
        return None
    minutes = info["duration"] / 60
    limit = float(o.get("smart_min") or 45)
    if o.get("smart") != "on" and minutes < limit:
        return None
    log(f"This video is {minutes:.0f} minutes long, so the studio will not download all of it. It reads the replay graph and captions, then fetches only the clips.")
    from concurrent.futures import ThreadPoolExecutor
    cb(None, "Reading the captions" + (" and the live-chat replay" if info.get("has_chat") else "") + " (small text downloads).")
    from . import signals
    with ThreadPoolExecutor(max_workers=3) as ex:                          # independent text downloads, so they run side by side
        f_cap = ex.submit(captions, url, d, cancel)
        f_chat = ex.submit(chat, url, d, cancel) if info.get("has_chat") else None
        f_com = ex.submit(signals.comments, url, d, cancel)
        cues = f_cap.result()
        counts = f_chat.result() if f_chat else None
        try:
            com = signals.comments_curve(f_com.result(), info["duration"])
        except Exception:  # noqa: BLE001
            com = []
    cancel()
    words = []
    if cues:
        from . import transcript
        words = transcript.words_of(cues)
    n = int(info["duration"])
    heat = heat_curve(info["heatmap"], info["duration"])
    cht = chat_curve(counts, info["duration"]) if counts else []
    levels_curve: list[float] = []
    if not heat and not cht or o.get("smart_audio"):                       # chat or the replay graph is enough; the audio scan is the slow one
        cb(None, "No replay graph or chat for this video, so reading the audio at low quality (much smaller than the video).")
        ap = audio(url, d, cancel)
        cancel()
        levels = pick.loudness(str(ap), 0, info["duration"])
        levels_curve = hype_mod.curve(levels, words, 0.0, None)
        for f in d.glob("scout-audio.*"):
            f.unlink(missing_ok=True)                        # measured; the clips come from their own windows, not from this
    lex = lex_curve(words, n, getattr(hype_mod, "EXCITED", set())) if words else []
    sig = {"replay": heat, "audio": levels_curve, "chat": cht, "words": lex, "comments": com}
    curve, used = signals.combine(sig, n)
    signals.save(d, sig, 0.0)
    if com:
        log("Viewers wrote timestamps in the comments; those moments count too.")
    how = (["captions"] if cues else []) + [signals.NAMES[k].lower() for k in used]
    return {"duration": info["duration"], "cues": cues, "curve": curve, "how": " and ".join(how) or "nothing", "title": info["title"], "smart": True}


def shifted(words: list[dict], shift: float, a: float, b: float) -> list[dict]:
    """The words that fall in [a, b] (whole-video seconds), with their times moved to count from the start of the downloaded window."""
    return [{**w, "s": round(w["s"] - shift, 3), "e": round(w["e"] - shift, 3)} for w in words if w["e"] > a and w["s"] < b]


def clip_source(d: Path, c: dict) -> tuple[Path | None, float]:
    """The file a clip is cut from and how many seconds that file starts after the start of the video: the clip's own window in long-video mode, else the downloaded source."""
    if c.get("sec") and (d / c["sec"]).is_file():
        return d / c["sec"], float(c.get("sec_t0") or 0.0)
    return intake.find_source(d), 0.0
