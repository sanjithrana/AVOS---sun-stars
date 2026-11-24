"""The editing polish that makes a clip feel edited by a person: smooth punch-ins on the beats of speech, designed callouts on keywords, a colour look,
a flash / shake / glitch on the hype peaks with matching sounds, voice clean-up, and optional music that ducks under the voice.

Everything is decided up front into a small `edit` dict (zooms, callouts, peaks, music) that is saved with the clip, so a clip can be re-rendered with one
switch changed without guessing again. ffmpeg does the drawing: the zoom and the shake are time expressions, each callout an extra image input."""
from __future__ import annotations

import re
from typing import Any

from . import music, stickers

STYLES = {
    "classic": {"label": "Classic: gentle zooms, a few callouts", "amp": (0.045, 0.085), "every": 3.8, "stickers": 4, "sticker_gap": 5.0},
    "punchy": {"label": "Punchy: bigger, faster zooms, more callouts", "amp": (0.07, 0.14), "every": 2.4, "stickers": 6, "sticker_gap": 3.2},
    "clean": {"label": "Clean: slow push, no callouts", "amp": (0.03, 0.05), "every": 5.5, "stickers": 0, "sticker_gap": 99.0},
}
# colour looks, applied after the zoom. Plain ffmpeg filters, nothing that needs a licence.
LOOKS = {
    "none": ("No filter", ""),
    "clean": ("Clean: a little contrast and sharpness", "eq=contrast=1.06:saturation=1.08:gamma=0.99,unsharp=5:5:0.45:5:5:0.0"),
    "cinematic": ("Cinematic: teal shadows, warm highlights", "colorbalance=rs=-0.06:bs=0.08:rm=0.02:bm=0.02:rh=0.07:bh=-0.07,eq=contrast=1.12:saturation=1.06:gamma=0.97,unsharp=5:5:0.5:5:5:0.0,vignette=PI/5"),
    "vivid": ("Vivid: punchy colour for gaming and sport", "eq=contrast=1.1:saturation=1.38:gamma=0.98,unsharp=5:5:0.7:5:5:0.0"),
    "warm": ("Warm: golden and friendly", "colorbalance=rs=0.05:rm=0.06:bm=-0.06:bh=-0.05,eq=contrast=1.05:saturation=1.12,unsharp=5:5:0.4:5:5:0.0"),
    "cool": ("Cool: crisp and modern", "colorbalance=rs=-0.04:bs=0.06:bm=0.06:bh=0.04,eq=contrast=1.08:saturation=1.05,unsharp=5:5:0.5:5:5:0.0"),
    "mono": ("Black and white: high contrast", "hue=s=0,eq=contrast=1.25:gamma=0.95,vignette=PI/4.5"),
    "film": ("Film: faded blacks, grain, soft edges", "curves=all='0/0.05 0.5/0.5 1/0.95',eq=saturation=0.95:contrast=1.04,noise=alls=9:allf=t,vignette=PI/4.5"),
}
DEFAULTS = {"edit": "classic", "zoom": True, "stickers": True, "look": "clean", "fx": True, "sfx": True, "progress": False, "loudness": True, "music": "auto", "music_volume": 0.14, "riser": False}
PAL = ["sun", "hot", "ice", "lime", "snow"]
KINDS = ["pill", "tag", "outline", "pill", "tag"]


def _clean(w: str) -> str:
    return re.sub(r"[^a-z0-9'$#]", "", w.lower())


def resolve(o: dict | None) -> dict:
    """The edit settings for a clip from job options (strings from forms are fine)."""
    o = o or {}
    out = dict(DEFAULTS)
    st = str(o.get("edit") or out["edit"]).lower()
    out["edit"] = st if st in STYLES or st == "off" else "classic"
    for k in ("zoom", "stickers", "fx", "sfx", "progress", "loudness", "riser"):
        if k in o and o[k] not in (None, ""):
            out[k] = str(o[k]).lower() in ("1", "true", "yes", "on")
    lk = str(o.get("look") or out["look"]).lower()
    out["look"] = lk if lk in LOOKS else "clean"
    out["music"] = str(o.get("music") or "none")
    try:
        out["music_volume"] = max(0.04, min(0.5, float(o.get("music_volume") or out["music_volume"])))
    except (TypeError, ValueError):
        pass
    return out


# ---------- deciding what happens when ----------
def phrases(words: list[dict], start: float, end: float) -> list[float]:
    """Seconds (from the clip start) where a new phrase begins: after a pause or sentence end."""
    ws = [w for w in words if w["e"] > start and w["s"] < end]
    out = []
    for i, w in enumerate(ws):
        if i == 0 or w["s"] - ws[i - 1]["e"] >= 0.3 or re.search(r"[.!?]$", ws[i - 1]["w"].strip()):
            out.append(max(0.0, w["s"] - start))
    return out


def zoom_events(words: list[dict], start: float, end: float, style: str, peaks: list[float] | None = None) -> list[list[float]]:
    """[[t0, t1, amplitude]]: smooth punch-ins on phrase starts (alternating small and bigger), plus a hard punch-in on every hype peak."""
    sp = STYLES.get(style) or STYLES["classic"]
    dur = end - start
    starts = phrases(words, start, end) or [i * sp["every"] for i in range(int(dur // sp["every"]) + 1)]
    ev: list[list[float]] = []
    last = -99.0
    for t in starts:
        if t < 0.5 or t > dur - 1.2 or t - last < sp["every"]:
            continue
        if any(abs(t - p) < 1.6 for p in peaks or []):
            continue                                            # the peak gets its own bigger punch
        ev.append([round(t - 0.05, 2), round(min(dur - 0.3, t + 1.5 + 0.5 * (len(ev) % 2)), 2), sp["amp"][len(ev) % 2]])
        last = t
    for p in peaks or []:
        ev.append([round(max(0.0, p - 0.1), 2), round(min(dur - 0.2, p + 1.3), 2), 0.12 if style == "punchy" else 0.09])
    return sorted(ev)


def sticker_events(words: list[dict], start: float, end: float, style: str, peaks: list[float] | None = None) -> list[dict]:
    """Callouts on keywords ("$$$" on money, "WAIT FOR IT" on wait) and a burst on a hype peak that no keyword covers."""
    sp = STYLES.get(style) or STYLES["classic"]
    out: list[dict] = []
    last = -99.0
    for w in words:
        if w["e"] <= start or w["s"] >= end:
            continue
        lab = stickers.label_for(_clean(w["w"]))
        t = w["s"] - start
        if not lab or t < 0.6 or t - last < sp["sticker_gap"] or len(out) >= sp["stickers"] or end - w["s"] < 1.6 or any(s["text"] == lab for s in out[-3:]):
            continue
        k = len(out)
        kind = "burst" if lab.endswith("!") and len(lab) <= 6 else KINDS[k % len(KINDS)]
        out.append({"t0": round(t, 2), "t1": round(t + 1.6, 2), "kind": kind, "text": lab, "color": PAL[k % len(PAL)], "x": 0.74 if k % 2 == 0 else 0.26, "y": 0.3, "word": _clean(w["w"])})
        last = t
    if sp["stickers"] and len(out) < sp["stickers"]:
        for p in peaks or []:
            if all(abs(p - s["t0"]) > 2.0 for s in out):
                out.append({"t0": round(p, 2), "t1": round(p + 1.4, 2), "kind": "burst", "text": "WOW!", "color": "sun", "x": 0.72, "y": 0.3, "word": ""})
    return sorted(out, key=lambda s: s["t0"])


def plan_edit(words: list[dict], start: float, end: float, o: dict | None, label: str = "", rng_seed: int = 0, peaks: list[float] | None = None) -> dict | None:
    """The saved description of the polish for one clip. None when editing is off. `peaks` are hype-peak times (seconds from the clip start)."""
    r = resolve(o)
    if r["edit"] == "off":
        return None
    st = r["edit"]
    pk = [p for p in (peaks or []) if 0.8 < p < end - start - 0.8] if (r["fx"] or r["zoom"]) and st != "clean" else []
    ed: dict[str, Any] = {"v": 2, "style": st, "dur": round(end - start, 2), "look": r["look"], "loudness": r["loudness"], "progress": r["progress"], "sfx": r["sfx"],
                          "peaks": pk if r["fx"] else [], "tint": pk[-1:] if (r["fx"] and st in ("punchy", "classic")) else [], "zooms": zoom_events(words, start, end, st, pk) if r["zoom"] else [],
                          "stickers": sticker_events(words, start, end, st, pk) if r["stickers"] else [], "music": None,
                          "opts": {k: r[k] for k in ("edit", "zoom", "stickers", "look", "fx", "sfx", "progress", "loudness", "music", "music_volume", "riser")}}
    if r["music"] != "none":
        tr = music.pick(r["music"], label, rng_seed)
        if tr:
            ed["music"] = {"id": tr["id"], "name": tr["name"], "mood": tr["mood"], "volume": r["music_volume"], "riser": bool(r.get("riser")), "file": music.file_for(tr["id"]),
                           "offset": music.offset_for(tr, end - start, rng_seed)}
    return ed


# ---------- the ffmpeg side ----------
def _rise(a: float, d: float) -> str:
    return f"(1-cos(PI*min(max((t-{a:.3f})/{d:.3f},0),1)))/2"


def zoom_expr(zooms: list[list[float]], base: float = 1.0) -> str:
    """zoom factor as an expression of t: each event eases in, holds and eases out (cosine ramps), so there is never a jump."""
    terms = [f"{amp:.4f}*(({_rise(t0, 0.28)})-({_rise(t1, 0.5)}))" for t0, t1, amp in zooms]
    return f"({base:.3f}" + ("+" + "+".join(terms) if terms else "") + ")"


def shake_expr(peaks: list[float], px: float, phase: str) -> str:
    """A 0.35 s shake after each peak that dies away (sin of time, so x and y move differently)."""
    terms = [f"if(between(t,{p:.3f},{p + 0.35:.3f}),{px:.1f}*(1-(t-{p:.3f})/0.35)*sin(t*{70 if phase == 'x' else 91}),0)" for p in peaks]
    return "+".join(terms) if terms else "0"


def sfx_events(ed: dict) -> list[tuple[str, float, float]]:
    """[(kind, time, volume)]: a pop under each callout and a hit on each hype peak."""
    if not ed.get("sfx"):
        return []
    ev = [("pop", float(s["t0"]), 0.5) for s in ed.get("stickers") or []] + [("hit", float(p), 0.7) for p in ed.get("peaks") or []]
    return sorted(ev, key=lambda x: x[1])[:10]


def build(ed: dict, w: int, h: int, has_audio: bool, dur: float, label_in: str, label_out: str) -> tuple[str, list[str], str | None]:
    """(filtergraph text from label_in to label_out plus the audio chain, the extra ffmpeg input args, the audio label or None).
    Inputs are numbered from 1 (0 is the video): music, then the sound effects, then the callout pictures, then the progress bar."""
    inputs: list[str] = []
    idx = 1
    music_idx = None
    mus = ed.get("music")
    if mus and mus.get("file"):
        inputs += ["-stream_loop", "-1", "-ss", f"{float(mus.get('offset') or 0):.2f}", "-i", str(mus["file"])]
        music_idx = idx
        idx += 1
    sfx = []
    for kind, t, vol in sfx_events(ed):
        inputs += ["-i", music.sfx_file(kind)]
        sfx.append((idx, t, vol))
        idx += 1
    parts: list[str] = []
    cur = label_in
    peaks = ed.get("peaks") or []
    fx = bool(peaks)
    zooms = ed.get("zooms") or []
    if zooms or fx:
        base = 1.045 if fx else 1.0
        z = zoom_expr(zooms, base)
        cx = f"(iw-{w})/2+{shake_expr(peaks, 9, 'x')}" if fx else f"(iw-{w})/2"
        cy = f"(ih-{h})/2+{shake_expr(peaks, 9, 'y')}" if fx else f"(ih-{h})/2"
        parts.append(f"{cur}scale=w='trunc({w}*{z}/2)*2':h='trunc({h}*{z}/2)*2':eval=frame:flags=bicubic,crop={w}:{h}:x='{cx}':y='{cy}'[z]")
        cur = "[z]"
    look = LOOKS.get(ed.get("look") or "none", LOOKS["none"])[1]
    if look:
        parts.append(f"{cur}{look}[g]")
        cur = "[g]"
    if fx:
        flash = "+".join(f"0.28*max(0,1-abs(t-{p:.3f})/0.12)" for p in peaks)
        glitch = "+".join(f"between(t,{p:.3f},{p + 0.2:.3f})" for p in peaks)
        parts.append(f"{cur}eq=brightness='{flash}':eval=frame,rgbashift=rh=-9:bh=9:gv=3:enable='{glitch}'[f]")
        cur = "[f]"
    tint = ed.get("tint") or []
    if tint:                                                  # the big moment goes red for a moment, like the big gaming channels
        on = "+".join(f"between(t,{max(0.0, p - 0.1):.3f},{p + 0.9:.3f})" for p in tint)
        parts.append(f"{cur}colorbalance=rs=0.5:gs=-0.25:bs=-0.35:rm=0.3:rh=0.15:enable='{on}'[rt]")
        cur = "[rt]"
    for k, st in enumerate(ed.get("stickers") or []):
        png = stickers.ensure(st, w)
        inputs += ["-loop", "1", "-framerate", "25", "-t", f"{st['t1'] - st['t0'] + 0.4:.2f}", "-i", str(png)]
        p = f"min(max((t-{st['t0']:.3f})/0.22,0),1)"
        grow = f"(1+2.70158*pow({p}-1,3)+1.70158*pow({p}-1,2))"                      # ease-out-back: pops past full size and settles
        out = f"(1-min(max((t-({st['t1']:.3f}-0.15))/0.15,0),1))"                  # and shrinks away at the end
        parts.append(f"[{idx}:v]format=rgba,setpts=PTS+{st['t0']:.3f}/TB,scale=w='max(2,trunc(iw*{grow}*{out}/2)*2)':h='max(2,trunc(ih*{grow}*{out}/2)*2)':eval=frame[s{k}]")
        nxt = f"[o{k}]"
        parts.append(f"{cur}[s{k}]overlay=x='{st['x'] * w:.1f}-w/2':y='{st['y'] * h:.1f}-h/2':enable='between(t,{st['t0']:.3f},{st['t1']:.3f})':eof_action=pass{nxt}")
        cur = nxt
        idx += 1
    if ed.get("progress"):
        inputs += ["-f", "lavfi", "-i", f"color=c=0xFFD60A:s={w}x{max(6, h // 190)}:r=25:d={dur + 1:.2f}"]
        parts.append(f"{cur}[{idx}:v]overlay=x='-W+W*t/{dur:.2f}':y=H-h:shortest=0{'[pb]'}")
        cur = "[pb]"
        idx += 1
    parts.append(f"{cur}null{label_out}")
    af = audio_chain(ed, has_audio, music_idx, sfx, dur)
    return ";".join(parts + ([af] if af else [])), inputs, ("[a]" if af else None)


def audio_chain(ed: dict | None, has_audio: bool, music_idx: int | None, sfx: list[tuple[int, float, float]], dur: float) -> str:
    """Clean and level the voice, put the music under it (ducked while someone speaks) and the sound effects on top. "" when there is nothing to do."""
    mus = ed.get("music") if ed else None
    use_music = bool(mus) and music_idx is not None
    if not has_audio and not use_music and not sfx:
        return ""
    chain: list[str] = []
    if has_audio and (not ed or ed.get("loudness")):
        chain = ["highpass=f=70", "acompressor=threshold=0.125:ratio=3:attack=5:release=120:makeup=2", "loudnorm=I=-14:TP=-1.5:LRA=11"]
    if has_audio:
        voice = "[0:a]" + ",".join(chain + ["aresample=44100,aformat=channel_layouts=stereo"])
    else:
        voice = f"anullsrc=r=44100:cl=stereo,atrim=0:{dur:.2f}"
    if not use_music and not sfx:
        return voice + "[a]"
    fl = [voice + "[vc]"]
    mix = ["[vc]"]
    if use_music:
        vol = float(mus.get("volume") or 0.14)
        fl.append("[vc]asplit=2[v1][v2]")
        if mus.get("riser"):                           # low under the talking, then it climbs to a peak over the last seconds (the payoff)
            rl = min(6.0, max(2.0, dur * 0.25))
            r0 = max(0.0, dur - rl)
            gain = f"volume='{vol:.3f}*if(gt(t,{r0:.2f}),1+3.5*(t-{r0:.2f})/{rl:.2f},1)':eval=frame"
            fade = f"afade=t=out:st={max(0.0, dur - 0.35):.2f}:d=0.35"
        else:
            gain = f"volume={vol:.3f}"
            fade = f"afade=t=out:st={max(0.0, dur - 1.4):.2f}:d=1.4"
        fl.append(f"[{music_idx}:a]aresample=44100,aformat=channel_layouts=stereo,{gain},afade=t=in:st=0:d=0.8,{fade},"
                  f"atrim=0:{dur:.2f},asetpts=PTS-STARTPTS[mu]")
        fl.append("[mu][v1]sidechaincompress=threshold=0.04:ratio=" + ("4" if mus.get("riser") else "10") + ":attack=15:release=350[du]")
        mix = ["[v2]", "[du]"]
    for n, (i, t, vol) in enumerate(sfx):
        fl.append(f"[{i}:a]aresample=44100,aformat=channel_layouts=stereo,volume={vol:.2f},adelay=delays={int(t * 1000)}:all=1[x{n}]")
        mix.append(f"[x{n}]")
    fl.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0,alimiter=limit=0.95[a]")
    return ";".join(fl)
