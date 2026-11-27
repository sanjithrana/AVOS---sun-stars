"""One Auto Clip job: get the video, pick the moments, cut the clips. Posting is autopilot.py's job (or a button), never this module's."""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from pathlib import Path
from typing import Any

from . import boundaries, neonsig, coach, craft, cut, meta, experiments, finder, hype, intake, pick, polish, presets, reframe, rights, signals, smart, store, templates, transcript, visual

_threads: dict[str, threading.Thread] = {}
_cancel: dict[str, threading.Event] = {}
STAGES = ("get", "pick", "cut")
LABELS = {"get": "Get the video", "pick": "Find the moments", "cut": "Cut the clips"}


class Stopped(Exception):
    pass


def _check(jid: str) -> None:
    ev = _cancel.get(jid)
    if ev is not None and ev.is_set():
        raise Stopped()


def _step(jid: str, name: str, **kw: Any) -> None:
    def f(j: dict) -> None:
        stp = j.setdefault("steps", {}).setdefault(name, {})
        stp.update(kw)
        if kw.get("status") == "working":                # how long each stage took, shown on the job
            stp["started"], stp["secs"] = time.time(), None
        elif kw.get("status") in ("done", "error") and stp.get("started"):
            stp["secs"] = round(time.time() - float(stp["started"]), 1)
        if kw.get("status") == "working":
            j["stage"] = name
        j["progress"] = None                  # a new step starts without the last step's bar
    store.update(jid, f)


_last_prog: dict[str, float] = {}


def progress(jid: str, pct: float | None, text: str) -> None:
    """What the page shows as the live bar: a percentage (or None for 'working, no number') and one line. Written at most every 1.2 s."""
    import time
    now = time.time()
    if pct is not None and pct < 99.5 and now - _last_prog.get(jid, 0) < 1.2:
        return
    _last_prog[jid] = now
    store.update(jid, lambda j: j.update(progress={"pct": None if pct is None else round(max(0.0, min(100.0, pct)), 1), "text": text[:140], "t": store.now()}))


def new_job(opts: dict, source: dict, auto: bool = False, permission: str | None = None) -> dict:
    jid = store.new_id()
    d = store.jdir(jid)
    d.mkdir(parents=True, exist_ok=True)
    job = {"id": jid, "title": (source.get("name") or source.get("url") or "New video")[:120], "status": "working", "stage": "get", "source": source,
           "opts": opts, "steps": {}, "log": [], "clips": [], "auto": auto, "createdAt": store.now()}
    if permission:
        job["permission"] = permission
    store.save(job)
    return job


CAP_KEYS = ("font", "size", "x", "y", "upper", "bold", "italic", "outline", "shadow", "glow", "text", "hi", "offset_ms", "anim", "words", "mode")
WHISPER_MODELS = {"base": {"label": "Base", "mb": 145, "ram_gb": 1.0, "speed": 3.0, "note": "fast, rough"},
                  "small": {"label": "Small", "mb": 465, "ram_gb": 2.0, "speed": 1.0, "note": "good for English"},
                  "medium": {"label": "Medium", "mb": 1430, "ram_gb": 4.0, "speed": 0.4, "note": "better for Hindi and noisy audio"},
                  "large-v3-turbo": {"label": "Large v3 Turbo", "mb": 1510, "ram_gb": 6.0, "speed": 0.35, "note": "best, needs RAM"}}


def clean_brand(b: dict | None) -> dict:
    """Only known brand keys, as plain values."""
    b = b if isinstance(b, dict) else {}
    out: dict = {}
    wm = b.get("wm") if isinstance(b.get("wm"), dict) else {}
    if wm.get("kind") in ("text", "logo"):
        out["wm"] = {"kind": wm["kind"], "text": str(wm.get("text") or "")[:40], "pos": str(wm.get("pos") or "br") if str(wm.get("pos") or "br") in ("tl", "tc", "tr", "ml", "mc", "mr", "bl", "bc", "br") else "br",
                     "size": float(wm.get("size") or (18 if wm["kind"] == "logo" else 100)), "opacity": float(wm.get("opacity") or 75)}
    for k, keys in (("end", ("on", "text", "sub", "secs")), ("lower", ("on", "name", "sub", "at", "secs"))):
        v = b.get(k) if isinstance(b.get(k), dict) else {}
        if v.get("on"):
            out[k] = {kk: (bool(v[kk]) if kk == "on" else (str(v[kk])[:50] if kk in ("text", "sub", "name") else float(v[kk] or 0))) for kk in keys if kk in v and v[kk] not in (None, "")}
    return out


def build_opts(o: dict | None) -> dict:
    d = store.settings()["defaults"] | {"start_min": None, "end_min": None, "srt": None, "preset": "", "multi": "speaker", "smart": "auto", "smart_min": 45, "opening_hook": True, "tighten": True, "whole": True, "accurate": True,
                                        "cap": {}, "brand": {}, "cap_lang": "auto", "whisper_model": "small", "mode": "clips", "research": True, "content": "auto", "game_view": "auto",
                                        "template": "none", "canvas": {}, "card": {}, "finder": True, "riser": False}
    for k, v in (o or {}).items():
        if k in d and v not in (None, ""):
            d[k] = v
    for k in ("cap", "brand", "canvas", "card"):       # forms send these as JSON text
        v = d.get(k)
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                v = {}
        d[k] = v if isinstance(v, dict) else {}
    d["brand"] = clean_brand(d["brand"])
    d["cap"] = {k: v for k, v in d["cap"].items() if k in CAP_KEYS}
    d["caption"] = d["caption"] if d.get("caption") in cut.CAPTIONS else "bounce"
    d["cap_lang"] = d["cap_lang"] if d["cap_lang"] in ("auto", "roman", "english") else "auto"
    d["whisper_model"] = d["whisper_model"] if d["whisper_model"] in WHISPER_MODELS else "small"
    d["mode"] = d["mode"] if d["mode"] in ("clips", "captions") else "clips"
    if d["mode"] == "captions":                        # a clip you cut yourself: nothing is picked, tightened or downloaded in parts
        d.update(count=1, smart="off", tighten=False, hype_only=False, min_seconds=5, max_seconds=180)
    for k, lo, hi in (("count", 0, 20), ("min_seconds", 5, 170), ("max_seconds", 10, 180)):     # count 0 = decide from the video's length
        d[k] = max(lo, min(hi, int(d[k])))
    d["max_seconds"] = max(d["max_seconds"], d["min_seconds"])
    d["preset"] = d["preset"] if presets.get(d["preset"]) else ""
    d["layout"] = d["layout"] if d["layout"] in cut.LAYOUTS else "blur"
    d["template"], d["canvas"] = templates.clean(d.get("template"), d.get("canvas"))
    if d["canvas"].get("bg") == "image":               # your own background picture, uploaded once under Brand
        d["canvas"]["image"] = str(store.ROOT / "brand" / "canvas.png")
    d["card"] = templates.clean_card(d.get("card"))
    d["finder"] = str(d.get("finder")).lower() not in ("0", "false", "no", "off")
    d["opening_hook"] = str(d.get("opening_hook")).lower() not in ("0", "false", "no", "off")
    d.update(polish.resolve(d))
    d["coach"] = str(d.get("coach")).lower() in ("1", "true", "yes", "on")
    d["hype_only"] = str(d.get("hype_only")).lower() in ("1", "true", "yes", "on")
    d["hype_level"] = d.get("hype_level") if d.get("hype_level") in hype.LEVELS else "balanced"
    d["tighten"] = str(d.get("tighten")).lower() in ("1", "true", "yes", "on")
    d["whole"] = str(d.get("whole")).lower() not in ("0", "false", "no", "off")
    d["accurate"] = str(d.get("accurate")).lower() not in ("0", "false", "no", "off")
    d["research"] = str(d.get("research")).lower() not in ("0", "false", "no", "off")
    d["content"] = d["content"] if d.get("content") in ("auto", "game", "talk") else "auto"
    d["game_view"] = d["game_view"] if d.get("game_view") in ("auto", "whole", "most", "close") else "auto"
    d["multi"] = d["multi"] if d["multi"] in ("split", "speaker") else "speaker"
    d["smart"] = d["smart"] if d["smart"] in ("auto", "on", "off") else "auto"
    try:
        d["smart_min"] = max(5.0, min(600.0, float(d["smart_min"])))
    except (TypeError, ValueError):
        d["smart_min"] = 45.0
    for k in ("start_min", "end_min"):
        try:
            d[k] = max(0.0, float(d[k])) if d[k] not in (None, "") else None
        except (TypeError, ValueError):
            d[k] = None
    return d


def apply_packs(clips: list[dict]) -> None:
    """Put each clip's pack on the clip: the AI's title (when it wrote one), the description with its hashtags, and the on-screen hook."""
    for c in clips:
        pk = c.get("seo") or {}
        if not pk:
            continue
        if pk.get("title") and pk.get("by") == "ai":
            c["title"] = pk["title"][:95]
        tags = " ".join("#" + t for t in pk.get("hashtags") or [])
        c["description"] = ((pk.get("description") or "") + ("\n\n" + tags if tags else "")).strip()
        if pk.get("hook") and not c.get("hook"):
            c["hook"] = pk["hook"]


GAME_WORDS = re.compile(r"\b(gta|gameplay|game ?play|minecraft|fortnite|valorant|warzone|call of duty|cod|roblox|fifa|ea fc|pubg|bgmi|free ?fire|apex|elden ring|"
                        r"red dead|rdr2|speedrun|let'?s play|playthrough|walkthrough|livestream gaming|twitch|kick\.com|gaming)\b", re.I)


def is_game(o: dict, job: dict, text: str = "") -> bool:
    """Is this gameplay? You said so, the GTA kit is on, or the title, tags, channel or words name a game or a stream."""
    if o.get("content") in ("game", "talk"):
        return o["content"] == "game"
    if o.get("preset") == "gta6" or (job.get("source") or {}).get("kind") == "live":
        return True
    src = job.get("source") or {}
    hay = " ".join([job.get("title") or "", src.get("channel") or "", " ".join(src.get("tags") or []), text[:2000]])
    return bool(GAME_WORDS.search(hay) or meta.detect(hay, ""))


def game_ar(o: dict, cam: bool = False) -> float:
    """How much of the game to keep. "auto": all of it under a streamer cam (the whole picture is visible), most of it on its own."""
    from .reframe import GAME_VIEWS
    v = o.get("game_view") or "auto"
    if v == "auto":
        v = "whole" if cam else "most"
    return GAME_VIEWS.get(v, 4 / 3)


def auto_count(seconds: float) -> int:
    """How many clips a video of this length can give: about one per 5 minutes, at least 3, at most 15."""
    return max(3, min(15, round(seconds / 300)))


def check_clip(path: Path, expect: float, need_audio: bool) -> str | None:
    """Why a finished clip is broken (too short, no picture, no sound), or None when it is fine."""
    if not path.is_file() or path.stat().st_size < 20_000:
        return "the file is empty"
    dur, aud = cut.media_info(str(path))
    if dur < max(2.5, 0.5 * expect):
        return f"it came out {dur:.1f} s long instead of {expect:.0f} s"
    if need_audio and not aud:
        return "it has no sound"
    return None


def logo_of(o: dict) -> dict | None:
    """The brand logo to burn in, when the job asks for one and it was uploaded."""
    wm = (o.get("brand") or {}).get("wm") or {}
    if wm.get("kind") != "logo":
        return None
    p = store.ROOT / "brand" / "logo.png"
    return {**wm, "path": str(p)} if p.is_file() else None


def _run(jid: str) -> None:
    try:
        job = store.load(jid)
        d, o = store.jdir(jid), job["opts"]
        log = lambda t: store.say(jid, t)  # noqa: E731
        # 1. the video
        _step(jid, "get", status="working")
        src = intake.find_source(d)
        scouted = None
        sj = d / "scout.json"
        if src is None and job["source"].get("kind") == "url":
            # A long video is not downloaded: read its replay graph and captions, then fetch only the clips (see smart.py).
            if sj.is_file():
                try:
                    scouted = json.loads(sj.read_text("utf-8"))
                except Exception:  # noqa: BLE001
                    scouted = None
            if scouted is None:
                scouted = smart.scout(job["source"]["url"], d, o, hype, log, lambda pct, text: progress(jid, pct, text), lambda: _check(jid))
                if scouted:
                    sj.write_text(json.dumps({k: ([round(x, 3) for x in v] if k == "curve" else v) for k, v in scouted.items() if k != "cues"}), "utf-8")
                    if scouted.get("cues"):
                        (d / "cues.json").write_text(json.dumps(scouted["cues"]), "utf-8")
        if src is None and scouted is None:
            kind = job["source"].get("kind")
            cb = lambda pct, text: progress(jid, pct, text)  # noqa: E731
            if kind == "live":
                src = intake.record_live(job["source"]["url"], int(job["source"].get("minutes") or 20) * 60, d, log, cancel=lambda: _check(jid), progress=cb)
            elif kind != "url":
                raise RuntimeError("The uploaded video is missing.")
            else:
                s0, e0 = (o.get("start_min") or 0) * 60, (o.get("end_min") or 0) * 60
                sec = (s0, e0) if e0 > s0 and rights.platform(job["source"]["url"]) in ("youtube", "twitch") else None     # a long stream: only fetch the minutes asked for
                src = intake.download(job["source"]["url"], d, log, cancel=lambda: _check(jid), progress=cb, section=sec)
                if sec:
                    store.update(jid, lambda j: j["source"].__setitem__("section", [sec[0], sec[1]]))
        _check(jid)
        total = float(scouted["duration"]) if scouted else pick.duration(str(src))
        a = (o.get("start_min") or 0) * 60
        b = min(total, (o.get("end_min") or 0) * 60 or total)
        if not scouted and (store.load(jid)["source"].get("section") or job["source"].get("kind") == "live"):
            a, b = 0.0, total                                  # the file already is just the part you asked for (or what the live recording caught)
        if b - a < o["min_seconds"] + 1 and o.get("mode") != "captions":
            raise RuntimeError("The part of the video you picked is shorter than the shortest clip.")
        hoff = 0.0 if scouted else a                           # which second of the video the hype curve starts at
        _step(jid, "get", status="done", note=(f"{total / 60:.0f} minutes, not downloaded: reading {scouted['how']}" if scouted else f"{total / 60:.1f} minutes") + (f", using {a / 60:.1f} to {b / 60:.1f}" if (a or b < total) else ""))
        # 2. the moments
        _step(jid, "pick", status="working")
        srt = d / "source.srt"
        cues = transcript.parse_srt(srt.read_text("utf-8", "replace")) if srt.is_file() else None
        how = "your subtitles" if cues else None
        cf = d / "cues.json"
        if not cues and cf.is_file():
            try:
                cues = json.loads(cf.read_text("utf-8")) or None
                how = ("the video's captions" if scouted else "faster-whisper (kept from the last run)") if cues else None
            except Exception:  # noqa: BLE001
                cues = None
        if not cues and not scouted and intake.is_youtube(job["source"].get("url") or ""):
            from . import yttranscript                         # YouTube already has a transcript: read it in a second instead of listening for minutes
            yc, why = yttranscript.fetch(job["source"]["url"], log=log)
            if yc:
                shift = float((store.load(jid)["source"].get("section") or [0.0])[0])   # only part of the video was downloaded
                yc = [dict(c, start=c["start"] - shift, end=c["end"] - shift, words=[dict(w, s=w["s"] - shift, e=w["e"] - shift) for w in c.get("words") or []])
                      for c in yc if c["end"] > shift and c["start"] - shift < total]
                if yc:
                    cues, how = yc, why
                    cf.write_text(json.dumps(cues), "utf-8")
            else:
                log(f"No YouTube transcript ({why}); listening to the audio instead.")
        longsrc = (not scouted) and o.get("smart") != "off" and total >= float(o.get("smart_min") or 45) * 60
        if not cues and longsrc:
            log(f"This video is {total / 60:.0f} minutes long, so it is not transcribed from start to end (that takes hours). Clips are picked by sound first, then only each clip is listened to.")
        if not cues and not scouted and not longsrc:
            log("Listening to the video to write captions (needs faster-whisper; skipped if it isn't installed)…")
            progress(jid, None, "Listening to the video to write captions. The first time it also downloads the speech model, so this can take a few minutes.")
            cues = transcript.whisper(str(src), log, (o.get("whisper_model") or "small") if o.get("mode") == "captions" else "base", None, "translate" if (o.get("mode") == "captions" and o.get("cap_lang") == "english") else "transcribe")
            how = "faster-whisper" if cues else None
            if cues:
                cf.write_text(json.dumps(cues), "utf-8")
        _check(jid)
        preset = presets.get(o.get("preset"))
        from ..series import writers
        crew = o.get("crew") or "builtin"
        s = {"id": jid, "crew": crew, "language": "en", "format": {"width": 720, "height": 1280}, "settings": {"models": {}, "local_only": False}}
        ai = writers.uses_ai(s) and bool(cues) and o.get("mode") != "captions"
        words = transcript.words_of(cues) if cues else []
        key = hashlib.md5(json.dumps([o.get(k) for k in ("count", "min_seconds", "max_seconds", "hype_only", "hype_level", "preset", "crew", "start_min", "end_min")] + [scouted["duration"] if scouted else src.stat().st_size], default=str).encode()).hexdigest()[:12]
        prev = store.load(jid)
        hcurve = None
        hf = d / "hype.json"
        if hf.is_file():
            try:
                hj = json.loads(hf.read_text("utf-8"))
                hcurve = hj["curve"] if abs(float(hj["offset"]) - hoff) < 1 else None
            except Exception:  # noqa: BLE001
                hcurve = None
        metas, titles, reused = None, None, False
        if prev.get("pick_key") == key and prev.get("clips"):
            reused = True
            clips = prev["clips"]                                  # the same video and settings as last time: keep the moments and any clips already cut
            log(f"Reusing the {len(clips)} moments from the last run; clips already cut are kept.")
        else:
            if o.get("mode") == "captions":                 # your own cut: the whole video is the one clip, only captions and styling are added
                moments = [{"start": round(a, 2), "end": round(b, 2), "score": 0.0}]
            else:
                levels = None if scouted else pick.loudness(str(src), a, b)
                moments = []
                if not o["count"]:
                    o["count"] = auto_count(b - a)
                    log(f"Making up to {o['count']} clips for {(b - a) / 60:.0f} minutes of video (fewer if there aren't that many good moments).")
                want = min(24, o["count"] * (3 if (preset or ai) else 1))
                if scouted:
                    hcurve = [x if a <= i < b else 0.0 for i, x in enumerate(scouted["curve"])]
                    (d / "hype.json").write_text(json.dumps({"offset": 0.0, "curve": [round(x, 3) for x in hcurve]}), "utf-8")
                elif o.get("hype_only") or o.get("edit") != "off":
                    try:
                        progress(jid, None, "Measuring every signal: visual action, audio, the streamer's reaction, comment timestamps, excited words.")
                        gamey = is_game(o, job, " ".join(x["w"] for x in (words or [])[:400]))
                        region = signals.cam_region(str(src), a, b, d / "camscan") if (o.get("hype_only") and gamey) else None
                        vis = visual.scan(str(src), a, b, region=region) if o.get("hype_only") else None
                        n_sec = len(levels)
                        sig: dict = {"audio": hype.curve(levels, words, a, None)}
                        if vis:
                            sig["visual"] = [min(1.0, 0.55 * vis["motion"][i] + 0.25 * vis["cut"][i] + 0.2 * vis["shake"][i]) for i in range(len(vis["motion"]))]
                            sig["reaction"] = vis.get("react") or []
                        elif o.get("hype_only"):
                            sig["visual"] = hype.motion(str(src), a, b) or []
                        url = (job.get("source") or {}).get("url") or ""
                        if o.get("hype_only") and url:
                            cc = signals.comments_curve(signals.comments(url, d, lambda: _check(jid)), total)
                            sig["comments"] = cc[int(a):] if cc else []
                        na = neonsig.audio(str(src), a, b)       # NeonClipping's ears: jumps against the last 2 minutes, raised voices, gunfire and booms
                        if na:
                            nac = neonsig.audio_curve(na)
                            sig["audio"] = [max(x, nac[i] if i < len(nac) else 0.0) for i, x in enumerate(sig["audio"])] if sig.get("audio") else nac
                            if gamey:
                                sig["bang"] = na["bang"]
                        if o.get("hype_only"):                     # NeonClipping's eyes: optical flow and hard cuts
                            fl = neonsig.motion(str(src), a, b)
                            if fl:
                                sig["visual"] = [max(x, fl[i] if i < len(fl) else 0.0) for i, x in enumerate(sig.get("visual") or fl)]
                        if words:                                  # what is said: "oh my god", "bhaago", "wasted", "headshot"
                            sig["words"] = neonsig.excite(words, n_sec, a)
                        if gamey and words:                # the streamer going quiet, then talking fast: a reaction to what just happened
                            sig["voice"] = boundaries.voice_return(words, n_sec, a)
                        hcurve, used = signals.combine(sig, n_sec)
                        signals.save(d, sig, a)
                        log("Picked from: " + ", ".join(signals.NAMES[k] for k in used) + (" (the streamer's cam was found and measured on its own)." if region else "."))
                        (d / "hype.json").write_text(json.dumps({"offset": a, "curve": [round(x, 3) for x in hcurve]}), "utf-8")
                    except Exception as e:  # noqa: BLE001 - the loudness picker still works
                        log(f"Hype detection skipped ({str(e)[:120]}).")
                talk = not is_game(o, job, " ".join(x["w"] for x in (words or [])[:400]))
                zones = hype.dead_zones(total, words or cues, talk, a, b)
                if zones:                                      # never the intro, the end credits, or a stretch where nobody talks
                    if hcurve:
                        hcurve = hype.mask(hcurve, hoff, zones)
                    if levels:
                        levels = hype.mask(levels, a, zones, min(levels) if levels else -90.0)
                if (o.get("hype_only") or scouted) and hcurve:
                    moments = hype.moments(hcurve, want, o["min_seconds"], o["max_seconds"], cues, hoff, o["hype_level"], pick._snap, coach.lead_in() if o.get("coach") else 2)
                    if not moments:                            # a long, evenly loud video (a game, a stream) has no moment that clears the bar: take its own best ones
                        moments = hype.moments(hcurve, want, o["min_seconds"], o["max_seconds"], cues, hoff, "relative", pick._snap, coach.lead_in() if o.get("coach") else 2)
                        if moments:
                            log(f"Nothing in this video clears the hype bar, so these are its {len(moments)} strongest moments compared with the rest of it.")
                    if not moments:
                        log("No moment in this video is hype enough for this sensitivity, so no clips were made. Try 'More' under hype, or turn hype-only off.")
                        raise RuntimeError("No hype moments found. Try the 'more' sensitivity or turn off 'only clip the hype'.")
                    if len(moments) < o["count"] and o.get("hype_level") != "relative":     # top up with the video's own best remaining moments
                        more = hype.moments(hcurve, want, o["min_seconds"], o["max_seconds"], cues, hoff, "relative", pick._snap, coach.lead_in() if o.get("coach") else 2) or []
                        add = [m for m in sorted(more, key=lambda m: -float(m.get("score") or 0))
                               if all(min(m["end"], x["end"]) - max(m["start"], x["start"]) <= 0 for x in moments)][: max(0, want - len(moments))]
                        if add:
                            log(f"Only {len(moments)} moment{'s' if len(moments) != 1 else ''} cleared the hype bar; added {len(add)} more of this video's strongest parts.")
                            moments = sorted(moments + add, key=lambda m: m["start"])
                    if len(moments) < o["count"]:
                        log(f"Only {len(moments)} hype moment{'s' if len(moments) != 1 else ''} found; the rest of the video is too quiet to be worth clipping.")
                if not moments and scouted:
                    raise RuntimeError("Nothing in this video stands out (no replay peaks, loud or excited parts), so no clips were made. Try 'More' under hype, or upload the file.")
                if not moments:
                    moments = pick.choose(levels, want, o["min_seconds"], o["max_seconds"], cues, offset=a)
                if not moments:
                    raise RuntimeError("No usable moments were found. Try a shorter minimum length.")
                if words:                                      # edges go to sentence edges, and a sentence that ends on "and"/"but" is not the end
                    moments = craft.finish(moments, words, o["min_seconds"], o["max_seconds"], total)
                if talk and (words or cues) and hype.speech_rate(words or cues, a, b) >= 0.5:
                    spoken = [m for m in moments if hype.speech_rate(words or cues, m["start"], m["end"]) >= 0.8]
                    if len(spoken) < len(moments):
                        log(f"Dropped {len(moments) - len(spoken)} moment{'s' if len(moments) - len(spoken) != 1 else ''} with almost no talking (music, credits or a title card).")
                    if spoken:
                        moments = spoken
                if ai and talk and o.get("finder", True):    # an AI editor reads the whole transcript and returns complete question-and-answer clips
                    progress(jid, None, "The AI editor is reading the whole transcript for complete moments.")
                    try:
                        found = finder.find(finder.rows_of(cues, words), lambda sysm, body: writers.ask(s, "story", writers.system("avos-autoclip-finder", sysm), body, log,
                                            max_tokens=3000, temperature=0.3), o["min_seconds"], o["max_seconds"], o["count"], local=any(k in crew.lower() for k in ("ollama", "local", "lmstudio")), log=log)
                    except Exception as e:  # noqa: BLE001 - the signal picks still work
                        found = []
                        log(f"The AI editor was skipped ({str(e)[:100]}).")
                    found = [f for f in found if f["llm"] >= 0.7 and not any(z[0] <= (f["start"] + f["end"]) / 2 < z[1] for z in zones)]
                    if found:
                        top = max((float(m.get("score") or 0) for m in moments), default=10.0) or 10.0
                        for f in found:                    # what the editor rates, mixed with what the signals saw in the same seconds
                            sv = max(hcurve[max(0, int(f["start"] - hoff)): max(1, int(f["end"] - hoff))] or [0.0]) if hcurve else 0.5
                            f["score"] = round(top * (0.65 * f["llm"] + 0.35 * sv), 2)
                            f["moment"] = f.get("reason") or None
                        rest = [m for m in moments if all(min(m["end"], f["end"]) - max(m["start"], f["start"]) <= 0.5 * (m["end"] - m["start"]) for f in found)]
                        moments = sorted(found + rest, key=lambda m: m["start"])
                        log(f"{len(found)} complete moment{'s' if len(found) != 1 else ''} from the AI editor join {len(rest)} from the signals.")
                if moments and words:                      # promo talk ("like and subscribe", "thanks for watching") is never a moment
                    said = lambda m: " ".join(w["w"] for w in words if m["start"] <= w["s"] < m["end"])  # noqa: E731
                    kept = [m for m in moments if not neonsig.filler(said(m))]
                    moments = neonsig.varied(kept or moments, said, len(kept or moments))   # repeats of a moment already chosen lose
                if moments:                                # never end on the next question, open on the moment, let the reaction land
                    moments = boundaries.refine(moments, words, hcurve, hoff, o["min_seconds"], total)
                    if src and not scouted and Path(str(src)).is_file():     # start and end on a scene cut when one is right there
                        moments = [neonsig.on_scene_cut(str(src), m, words, o["min_seconds"] - 2) for m in moments]
                    short = 0
                    for k, m in enumerate(moments):          # never shorter than the length you asked for: finish the thought instead
                        lack = o["min_seconds"] - (m["end"] - m["start"])
                        if lack > 1:
                            short += 1
                            m2 = dict(m, end=round(min(total, m["end"] + lack), 2))
                            if words:                          # sentence by sentence until it is long enough
                                m2 = m
                                for _ in range(6):
                                    nx = craft.extend(m2, words, 12.0, total)
                                    if nx["end"] == m2["end"]:
                                        break
                                    m2 = nx
                                    if m2["end"] - m2["start"] >= o["min_seconds"]:
                                        break
                            if m2["end"] - m2["start"] < o["min_seconds"] - 1:      # nothing more to say after it: take more before instead
                                m2 = dict(m2, start=round(max(a, m2["end"] - o["min_seconds"]), 2))
                            moments[k] = m2
                    if short:
                        log(f"Lengthened {short} moment{'s' if short != 1 else ''} that came out shorter than {o['min_seconds']} s.")
            texts = [transcript.text_between(cues or [], m["start"], m["end"]) for m in moments]
            if len(moments) > 1:                           # the same idea said twice, or two clips on the same stretch, is one clip
                keep = craft.dedupe(moments, texts)
                if len(keep) < len(moments):
                    log(f"Dropped {len(moments) - len(keep)} near-duplicate moment{'s' if len(moments) - len(keep) != 1 else ''}.")
                    moments, texts = [moments[i] for i in keep], [texts[i] for i in keep]
            metas = None
            if ai:
                progress(jid, None, "The AI is reading the transcript to choose the best moments.")
                try:
                    got = pick.ai_rank(s, moments, texts, min(len(moments), max(o["count"], o["count"] * 2)), log, (scouted or {}).get("title") or job.get("title") or "")
                except Exception as e:  # noqa: BLE001 - the loudness picks still work
                    got = None
                    log(f"The AI could not rank the moments ({str(e)[:100]}); using loudness and the transcript instead.")
                if got:
                    keep, metas = got
                    moments, texts = [moments[i] for i in keep], [texts[i] for i in keep]
                    try:                                   # finalists are compared head-to-head, and clips that stop before the thought ends get a longer ending
                        rr = craft.ai_rerank(s, moments, texts, min(o["count"], len(moments)), log)
                    except Exception as e:  # noqa: BLE001
                        rr = None
                        log(f"The head-to-head comparison was skipped ({str(e)[:100]}).")
                    if rr:
                        best, unf = rr
                        moments, texts, metas = [moments[i] for i in best], [texts[i] for i in best], [metas[i] for i in best]
                        for k, i in enumerate(best):
                            if i in unf and words:
                                moments[k] = craft.extend(moments[k], words, 10.0, total)
                                texts[k] = transcript.text_between(cues or [], moments[k]["start"], moments[k]["end"])
                    elif len(moments) > o["count"]:
                        moments, texts, metas = moments[: o["count"]], texts[: o["count"]], metas[: o["count"]]
            if metas is None:
                if preset and cues:
                    keep = presets.rerank(moments, texts, o["count"])
                else:
                    keep = sorted(range(len(moments)), key=lambda i: -float(moments[i].get("score") or 0))[: o["count"]] if len(moments) > o["count"] else list(range(len(moments)))
                    keep = sorted(keep)
                moments, texts = [moments[i] for i in keep], [texts[i] for i in keep]
            labels = [presets.classify(t)[0] if preset else None for t in texts]
            titles = [m["title"] for m in metas] if metas and all(m["title"] for m in metas) else None
            if titles is None:
                try:
                    titles = pick.ai_titles(s, texts, log)
                except Exception as e:  # noqa: BLE001 - a title is never worth stopping for
                    log(f"The AI titles failed ({str(e)[:100]}); using the first words instead.")
            sig_all, sig_off = signals.load(d)
            jt = (scouted or {}).get("title") or job.get("title") or ""
            clips = [{"n": i + 1, "start": m["start"], "end": m["end"], "score": m["score"], "why": signals.why(sig_all, sig_off, m["start"], m["end"]) if sig_all else {},
                      "title": (titles[i] if titles else m.get("title") or pick.title_for(texts[i], i + 1, jt, (labels[i] if labels else None) or m.get("moment"))), "text": texts[i][:600], "status": "pending", "approved": False,
                      "privacy": None, "schedule_at": None, "youtube_id": None} for i, m in enumerate(moments)]
            jtitle = (scouted or {}).get("title") or job.get("title") or ""
            whole = " ".join(x.get("text", "") for x in cues) if cues else " ".join(texts)
            vid_fr = meta.detect(whole, "")                # across the whole video: a stream titled "GTA 6" whose speaker keeps saying "GTA 5" is GTA 5 footage
            for i, c in enumerate(clips):                  # which game the footage is: the clip's own words, then the whole video's, then the uploader's title. Titles and tags never name a game it is not
                c["franchise"] = meta.detect(texts[i], "") or vid_fr or meta.detect("", jtitle) or ""
            if metas:
                for c, m in zip(clips, metas):
                    m["tags"] = meta.clean_ai_tags(m["tags"], c["franchise"] or None)
                    c["ai_score"] = round(m["ai"], 1)
                    c["description"] = (m["description"] + ("\n\n" if m["description"] else "") + " ".join("#" + t for t in m["tags"])).strip()
            if preset:
                for i, c in enumerate(clips):
                    c["moment"], c["hook"] = labels[i] or "", presets.hook(labels[i])
                    pre, note = meta.franchise_prefix(preset["title_prefix"], c["franchise"] or None)
                    c["title"] = presets.title(preset, labels[i], c["title"], pre)
                    if note:
                        c["notice"] = note
                        log(f"Clip {c['n']}: {note}")
            if o.get("opening_hook", True):                # an opening heading on every clip: the clip's own strongest line (NeonClipping)
                for i, c in enumerate(clips):
                    if not c.get("hook") and texts[i]:
                        h = neonsig.extract_hook(texts[i])
                        if h and (neonsig.hook_supported(h, texts[i]) or len(h.split()) >= 4):
                            c["hook"] = h
            store.update(jid, lambda j: j.update(clips=clips, pick_key=key))
        _step(jid, "pick", status="done", note=(f"{len(clips)} clips (kept from the last run)" if reused else "") or f"{len(clips)} clips by {'loudness and the transcript (' + how + ')' if how else 'loudness only (no transcript: no captions)'}"
              + (", ranked by AI" if metas else "") + (", titles by AI" if titles else ""))
        # 2b. the packaging team: what the top Shorts on this topic use (hashtags, mentions, sound), then a title, description and tags per clip
        if o.get("research", True) and any(not c.get("seo") for c in clips):
            progress(jid, None, "Researching the most-viewed Shorts on this topic for hashtags, mentions and sounds")
            try:
                from . import research
                ask_pack = (lambda sysm, prompt: writers.ask(s, "story", sysm, prompt, None, max_tokens=700, temperature=0.4)) if writers.uses_ai(s) else None  # noqa: E731
                summary = research.run(store.load(jid), [c for c in clips if not c.get("seo")], ask_pack, log)
                apply_packs(clips)
                store.update(jid, lambda j: j.update(clips=clips, research=list(summary.values())))
            except Exception as e:  # noqa: BLE001 - packaging is never worth losing the clips
                log(f"The packaging research was skipped ({str(e)[:160]}).")
        # 3. the clips
        _step(jid, "cut", status="working")
        (d / "clips").mkdir(exist_ok=True)
        from .. import config  # noqa: F401  (ffmpeg lookup happens in cut)
        w, h = cut.SIZES.get(o["quality"], cut.SIZES["720p"])
        warned: list[int] = []
        vision_ok = False
        if o["layout"] == "auto" and writers.uses_ai(s):
            try:
                from .. import avos_settings
                avos_settings.apply()                    # so a vision model saved in the AI settings is seen
                vision_ok = writers.crew(s, "story", None).vision()
            except Exception:  # noqa: BLE001
                vision_ok = False
            if not vision_ok:
                log("This AI can't look at pictures, so unclear scenes use the face and motion rules only. For vision, pick a vision model (for Ollama: set STUDIO_OLLAMA_VISION_MODEL=qwen2.5vl:7b).")
        gaming = is_game(o, store.load(jid), " ".join(x["w"] for x in words[:400]) if words else "")
        if gaming and o["layout"] in ("auto", "game"):
            log("This looks like gameplay, so the game is shown steady and sharp" + (" with the streamer's cam on top when there is one." if o["layout"] == "auto" else "."))
        labeller = (lambda sysm, prompt, imgs: writers.ask(s, "story", sysm, prompt, None, max_tokens=200, temperature=0.2, images=imgs)) if vision_ok else None  # noqa: E731
        for c in clips:
            _check(jid)
            if c.get("status") == "ready" and c.get("file") and (d / c["file"]).is_file():
                log(f"Clip {c['n']} was already cut: kept.")
                continue
            progress(jid, 100.0 * (c["n"] - 1) / len(clips), f"Cutting clip {c['n']} of {len(clips)}")
            oc = dict(o)
            if o.get("coach"):
                try:
                    drawn = coach.draw(o)                  # the coach picks this clip's recipe from what has worked before
                    oc.update(drawn)
                    coach.log_draw(jid, c["n"], o, drawn)
                except Exception:  # noqa: BLE001 - a clip is never lost to the coach
                    pass
            if (c.get("seo") or {}).get("music_id") and str(o.get("music")) == "auto":
                oc["music"] = c["seo"]["music_id"]        # the sound the top Shorts on this topic use, from your music shelf
            csrc, shift, cwords = src, 0.0, words
            task = "translate" if o.get("cap_lang") == "english" else "transcribe"
            if scouted:                                    # only this clip's window is fetched, not the whole video
                t0, t1 = max(0.0, c["start"] - smart.PAD), min(total, c["end"] + smart.PAD)
                secf = d / "sections" / f"sec-{c['n']}.mp4"
                if not secf.is_file():
                    progress(jid, 100.0 * (c["n"] - 1) / len(clips), f"Clip {c['n']} of {len(clips)}: downloading just this part ({(t1 - t0):.0f} s)")
                    try:
                        secf = smart.section(job["source"]["url"], secf, t0, t1, cancel=lambda: _check(jid))
                    except RuntimeError as e:          # one part that won't download costs one clip, never the whole job
                        if "cancel" in str(e).lower():
                            raise
                        log(f"Clip {c['n']}: skipped, its part of the video would not download ({str(e)[:200]}).")
                        c.update(status="failed", error="This part of the video would not download. Press Carry on to try again.")
                        store.update(jid, lambda j: j.update(clips=clips))
                        continue
                csrc, shift = secf, t0
                c["sec"], c["sec_t0"] = f"sections/{secf.name}", t0
                if not cues:                                # no captions on the video: listen to this small part only
                    cc = transcript.whisper(str(secf), log)
                    cwords = [{**x, "s": x["s"] + t0, "e": x["e"] + t0} for x in transcript.words_of(cc)] if cc else []
            if longsrc and not cues and not cwords:        # long video with no captions: listen to this clip's stretch only
                progress(jid, 100.0 * (c["n"] - 1) / len(clips), f"Clip {c['n']} of {len(clips)}: listening to just this part")
                cc = transcript.whisper_window(str(src), max(0.0, c["start"] - 2), min(total, c["end"] + 2), log, o.get("whisper_model") or "small", (job.get("title") or "")[:200], task)
                cwords = transcript.words_of(cc) if cc else []
            if (o.get("accurate", True) or task == "translate") and transcript.available() and (c["end"] - c["start"]) <= 180:
                # captions from YouTube's auto-subs are often wrong on game audio ("I heard. Catching"): listen again to just this stretch with the better model
                progress(jid, 100.0 * (c["n"] - 1) / len(clips), f"Clip {c['n']} of {len(clips)}: writing accurate captions")
                try:
                    a0, a1 = max(0.0, c["start"] - 1.5), min(total, c["end"] + 1.5)
                    if scouted:
                        cc = transcript.whisper(str(csrc), log, o.get("whisper_model") or "small", (job.get("title") or "")[:200], task)
                        fresh = [{**x, "s": x["s"] + shift, "e": x["e"] + shift} for x in transcript.words_of(cc)] if cc else []
                    else:
                        cc = transcript.whisper_window(str(src), a0, a1, log, o.get("whisper_model") or "small", (job.get("title") or "")[:200], task)
                        fresh = transcript.words_of(cc) if cc else []
                    if len([x for x in fresh if c["start"] <= x["s"] <= c["end"]]) >= 3 or (task == "translate" and fresh):
                        cwords = fresh
                except Exception as e:  # noqa: BLE001 - the video's own captions stay in use
                    log(f"Clip {c['n']}: kept the video's own captions ({str(e)[:100]}).")
            if preset and cwords:                          # the clip's own words can show the footage is a different game than the title says
                txt = " ".join(x["w"] for x in cwords if c["start"] - 1 <= x["s"] <= c["end"] + 1)
                fr2 = meta.detect(txt, "")
                if fr2 and fr2 != c.get("franchise"):
                    pre, note = meta.franchise_prefix(preset["title_prefix"], fr2)
                    if note:
                        c["title"] = re.sub("^" + re.escape(preset["title_prefix"]), pre, c["title"])
                        c["notice"], c["franchise"] = note, fr2
                        log(f"Clip {c['n']}: {note}")
            rw = smart.shifted(cwords, shift, c["start"], c["end"]) if shift else cwords
            rs, re_ = c["start"] - shift, c["end"] - shift
            peaks = hype.peaks_in(hcurve, hoff, c["start"], c["end"], o["hype_level"]) if hcurve else None
            for k in ("tight", "tight_dur"):
                c.pop(k, None)
            if o.get("tighten") and rw:                    # dead air and ums out, so the clip moves faster
                try:
                    from .. import config as _cfg
                    spans = craft.tighten_plan(rw, rs, re_)
                    if spans:
                        tf = d / "tight" / f"t-{c['n']}.mp4"
                        had = cut.has_audio(str(csrc))
                        dur = craft.tight_render(str(csrc), tf, spans, _cfg.ffmpeg(), had)
                        bad = check_clip(tf, 0.6 * (re_ - rs), had)
                        if bad:
                            raise RuntimeError(bad)
                        peaks = [x for x in (craft.map_time(rs + p, spans) for p in (peaks or [])) if x is not None] or None
                        log(f"Clip {c['n']}: tightened {re_ - rs:.0f}s to {dur:.0f}s (dead air and ums removed).")
                        rw, csrc, rs, re_ = craft.remap_words(rw, spans), tf, 0.0, dur
                        c["tight"], c["tight_dur"] = f"tight/{tf.name}", dur
                except Exception as e:  # noqa: BLE001 - tightening is a bonus, never a reason to lose a clip
                    log(f"Clip {c['n']}: not tightened ({str(e)[:140]}).")
            out = d / "clips" / f"clip-{c['n']}.mp4"
            plan = None
            if o["layout"] == "auto":
                progress(jid, 100.0 * (c["n"] - 1) / len(clips), f"Clip {c['n']} of {len(clips)}: finding scenes and faces")
                try:
                    plan = reframe.analyse(str(csrc), rs, re_, rw, o.get("multi") or "speaker", labeller=labeller, say=log, whole=bool(o.get("whole", True)) and gaming,
                                           game=gaming, game_ar=game_ar(o), cam_ar=game_ar(o, cam=True))
                    (d / "clips" / f"clip-{c['n']}.plan.json").write_text(json.dumps(plan), "utf-8")
                except Exception as e:  # noqa: BLE001 - fall back to the blurred layout: a clip is never lost to a framing problem
                    if not warned:
                        log(f"AI Reframe could not run ({str(e)[:160]}). Using the blurred layout instead.")
                        warned.append(1)
                progress(jid, 100.0 * (c["n"] - 1) / len(clips), f"Cutting clip {c['n']} of {len(clips)}")
            tpl = o.get("template") or "none"
            ass = cut.ass_for(rw, rs, re_, oc["caption"], w, h, hook=None if tpl != "none" else c.get("hook"),
                              cam_top=(plan.get("cam_h") or reframe.CAM_TOP) if plan and plan.get("cam") else None,
                              cap=o.get("cap"), brand=o.get("brand"), roman=o.get("cap_lang") == "roman")
            frame = None
            if tpl != "none" or o["layout"] in templates.LAYOUTS:
                frame = {"tpl": tpl, "canvas": o.get("canvas") or {"bg": "blur"}}
                if tpl != "none":                      # the headline pinned above the clip for its whole length
                    bx = templates.box(o["layout"] if o["layout"] in ("centered", "wide") else "wide", tpl, frame["canvas"], w, h)
                    handle = ((o.get("brand") or {}).get("wm") or {}).get("text") or ""
                    if templates.TEMPLATES[tpl].get("card"):          # a post card / frame drawn as a picture over the clip
                        from . import cards
                        cf = dict(o.get("card") or {})
                        av = store.ROOT / "brand" / "avatar.png"
                        if av.is_file():
                            cf["avatar"] = str(av)
                        cf.setdefault("name", ((o.get("brand") or {}).get("lower") or {}).get("name") or handle.lstrip("@") or "")
                        cf.setdefault("handle", handle)
                        frame["overlay"] = cards.render(tpl, cf, c.get("hook") or c.get("title") or "", w, h, bx, d / f".card-{c['n']}.png")
                    else:
                        top = 0 if templates.TEMPLATES[tpl].get("pin_top") else bx[1]
                        st_, ev_ = templates.head_events(tpl, c.get("hook") or c.get("title") or "", handle, re_ - rs, w, h, top)
                        ass = templates.add_to_ass(ass, st_, ev_, w, h)
                plan = None if o["layout"] != "auto" or tpl != "none" else plan
            try:
                ed = polish.plan_edit(rw, rs, re_, oc, c.get("moment") or c.get("title") or "", rng_seed=c["n"] + int(time.time()) % 1000,
                                      peaks=peaks)
            except Exception as e:  # noqa: BLE001
                log(f"Editing effects skipped for clip {c['n']} ({str(e)[:120]}).")
                ed = None
            lay = o["layout"] if o["layout"] != "auto" else ("game" if gaming else "blur")
            try:
                cut.cut(str(csrc), str(out), rs, re_, lay, o["quality"], ass, plan, ed, logo_of(o), game_ar(o), frame)
            except RuntimeError as e:                      # a fancy edit must never lose the clip: retry plainer, then plainest
                log(f"Clip {c['n']}: the full edit failed ({str(e)[:160]}). Retrying without effects.")
                plan, ed = None, None
                try:
                    cut.cut(str(csrc), str(out), rs, re_, lay, o["quality"], ass, None, None)
                except RuntimeError as e2:
                    log(f"Clip {c['n']}: retrying with a plain layout and no captions ({str(e2)[:160]}).")
                    cut.cut(str(csrc), str(out), rs, re_, "blur", o["quality"], None, None, None)
            need_audio = cut.has_audio(str(csrc))
            bad = check_clip(out, re_ - rs, need_audio)
            if bad:                                        # never hand over a 0-second or silent clip: cut it again from the untouched source, plainly
                log(f"Clip {c['n']}: {bad}; cutting it again plainly.")
                src0, s0 = smart.clip_source(d, c) if scouted else (src, 0.0)
                try:
                    cut.cut(str(src0), str(out), c["start"] - s0, c["end"] - s0, "blur", o["quality"], None, None, None)
                    bad = check_clip(out, c["end"] - c["start"], cut.has_audio(str(src0)))
                except RuntimeError as e:
                    bad = str(e)[:160]
                if bad:
                    log(f"Clip {c['n']}: still broken ({bad}), so it is left out.")
                    c.update(status="failed", error=f"This clip came out broken ({bad}). Press Carry on to try again.")
                    out.unlink(missing_ok=True)
                    store.update(jid, lambda j: j.update(clips=clips))
                    continue
            c["edit"], c["recipe"] = ed, coach.recipe_of(oc, ed, c)
            if ed:
                (d / "clips" / f"clip-{c['n']}.words.json").write_text(json.dumps(rw if c.get("tight") else [x for x in cwords if x["e"] > c["start"] and x["s"] < c["end"]]), "utf-8")
            if plan:
                c["reframe"] = reframe.summary(plan)

            cov = f"clips/clip-{c['n']}-cover.jpg"
            try:
                has_cover = cut.cover(str(out), str(d / cov), c["title"])
            except Exception:  # noqa: BLE001 - a thumbnail is never worth losing a clip
                has_cover = False

            var = None
            try:
                var = experiments.prepare(s, d, c, out, log)
            except Exception:  # noqa: BLE001
                var = None

            def mark(j: dict, n: int = c["n"], cov: str = cov, has_cover: bool = has_cover, var: dict | None = var) -> None:
                for x in j["clips"]:
                    if x["n"] == n:
                        x.update(file=f"clips/clip-{n}.mp4", thumb=f"clips/clip-{n}.jpg", status="ready", captions=bool(cwords), sec=c.get("sec"), sec_t0=c.get("sec_t0"), tight=c.get("tight"), tight_dur=c.get("tight_dur"), reframe=c.get("reframe"), edit=c.get("edit"), recipe=c.get("recipe"))
                        if has_cover:
                            x["cover"] = cov
                        if var:
                            x["variants"] = var
            store.update(jid, mark)
        auto_ok = store.load(jid).get("auto") and not store.settings()["autopilot"]["review_first"]
        if auto_ok:
            store.update(jid, lambda j: [x.update(approved=True) for x in j["clips"]])
        _step(jid, "cut", status="done", note=("with captions" if (words or any(x.get("captions") for x in store.load(jid)["clips"])) else "without captions (no transcript)"))
        fin = store.load(jid)["clips"]
        good, broken = [x for x in fin if x.get("status") != "failed"], [x for x in fin if x.get("status") == "failed"]
        if fin and not good:
            raise RuntimeError("None of the clips could be made: " + (broken[0].get("error") or "the video would not download") + " Try again later, or upload the file.")
        store.update(jid, lambda j: j.update(status="done", progress=None))
        store.say(jid, f"{len(good)} clip{'s' if len(good) != 1 else ''} ready." + (f" {len(broken)} could not be made (shown with the reason); press Carry on to retry them." if broken else ""))
    except Stopped:
        store.update(jid, lambda j: j.update(status="stopped"))
        store.say(jid, "Stopped.", "warn")
    except Exception as e:  # noqa: BLE001 - kept and shown; nothing was posted
        store.update(jid, lambda j: j.update(status="error", error=str(e)[:500]))
        store.say(jid, str(e)[:300], "error")


def start(jid: str) -> bool:
    t = _threads.get(jid)
    if t and t.is_alive():
        return False
    _cancel[jid] = threading.Event()
    _threads[jid] = threading.Thread(target=_run, args=(jid,), daemon=True, name=f"autoclip-{jid}")
    _threads[jid].start()
    return True


def stop(jid: str) -> None:
    ev = _cancel.get(jid)
    if ev:
        ev.set()


def busy(jid: str) -> bool:
    t = _threads.get(jid)
    return bool(t and t.is_alive())


def recover() -> None:
    """A job still 'working' after a restart was cut off: say so, so it can be run again."""
    for j in store.listing():
        if j["status"] == "working" and not busy(j["id"]):
            store.update(j["id"], lambda x: x.update(status="error", error="The studio restarted while this was running. Press Run again."))


def estimate(minutes: float, o: dict | None = None, cpus: int | None = None) -> dict:
    """A rough time for a job, in minutes (low, high), from the video's length and the options: transcribing, picking, then per clip
    reframe + accurate captions + render. Measured on a 4-core laptop CPU; more cores make it faster."""
    import os
    o = build_opts(o or {})
    cpus = cpus or os.cpu_count() or 4
    speed = max(0.6, min(2.5, cpus / 4))
    m = max(0.1, float(minutes or 0))
    n = 1 if o["mode"] == "captions" else o["count"]
    clip = m if o["mode"] == "captions" else min(o["max_seconds"], max(o["min_seconds"], (o["min_seconds"] + o["max_seconds"]) / 2)) / 60
    wm = WHISPER_MODELS.get(o["whisper_model"], WHISPER_MODELS["small"])
    get = 0.15 * m if m > 30 and o["smart"] != "off" else 0.04 * m          # a long video is read, not downloaded
    listen = (m * 0.12 / wm["speed"]) if o["mode"] == "captions" else (0.0 if m > 30 else m * 0.05)
    pick_t = 0.02 * min(m, 90) if o["hype_only"] else 0.01 * m
    per = clip * (1.2 if o["layout"] == "auto" else 0.5) + (clip * 1.5 / wm["speed"] if o["accurate"] and o["mode"] != "captions" else 0) + clip * (1.0 if o.get("edit") != "off" else 0.4)
    total = (get + listen + pick_t + n * per) / speed
    return {"low": max(1, round(total * 0.7)), "high": max(2, round(total * 1.5 + 0.5)), "clips": n}
