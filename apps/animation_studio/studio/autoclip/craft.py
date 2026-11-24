"""Clip craft: where a clip should start and end, which candidates are repeats, which finalist wins, and how to cut the dead air and 'ums' out of a clip.

Everything here is plain code that runs without an AI helper; the head-to-head rerank and the 'unfinished ending' check use the AI only when one is set.
Times are seconds on whatever clock the words use (the source video's, or a section file's)."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

END = re.compile(r"[.!?…]+[\"'”’)\]]*$")
DANGLE = {"and", "but", "so", "because", "or", "then", "which", "that", "with", "to", "of", "the", "a", "an", "if", "when", "as", "like", "also", "plus", "cause"}
FILLERS = {"um", "umm", "uh", "uhh", "er", "erm", "ah", "hmm", "mm", "mhm", "uhm"}
PAUSE = 0.7                                                # a silence this long between words ends a "sentence" when the text has no punctuation


def _bare(w: str) -> str:
    return re.sub(r"[^\w']", "", str(w or "")).lower()


def sentences(words: list[dict]) -> list[dict]:
    """[{s, e, last}]: each sentence's first-word start, last-word end and last word. Ends at . ! ? or at a long pause."""
    out: list[dict] = []
    cur: dict | None = None
    for i, w in enumerate(words):
        if cur is None:
            cur = {"s": w["s"], "e": w["e"], "last": _bare(w["w"])}
        else:
            cur["e"], cur["last"] = w["e"], _bare(w["w"])
        nxt = words[i + 1] if i + 1 < len(words) else None
        if END.search(str(w["w"]).strip()) or nxt is None or nxt["s"] - w["e"] >= PAUSE:
            out.append(cur)
            cur = None
    return out


def finish(moments: list[dict], words: list[dict], min_s: int, max_s: int, total: float | None = None) -> list[dict]:
    """Move each clip's edges to sentence edges: start where a sentence starts (up to 5 s earlier), end where one ends (up to 10 s later),
    and keep going past a sentence that ends on 'and', 'but', 'because'... because that thought is not finished. Never longer than max_s + 8."""
    if not words:
        return moments
    ss = sentences(words)
    starts = [x["s"] for x in ss]
    out = []
    for m in moments:
        a, b = float(m["start"]), float(m["end"])
        near = [t for t in starts if a - 5 <= t <= a + 2]
        if near:
            a = min(near, key=lambda t: abs(t - a))
        cand = [x for x in ss if b - 2 <= x["e"] <= b + 10]
        if cand:
            pick = min(cand, key=lambda x: abs(x["e"] - b))
            i = cand.index(pick)
            while pick["last"] in DANGLE and i + 1 < len(cand):         # ended on "and"/"but": the thought goes on
                i += 1
                pick = cand[i]
            b = pick["e"] + 0.15
        cap = a + max_s + 8
        if b > cap:
            fit = [x["e"] + 0.15 for x in ss if a + min_s <= x["e"] + 0.15 <= cap]
            b = max(fit) if fit else a + max_s
        if b - a < min_s:                                       # never shorter than asked: run on to the end of a sentence past the minimum
            longer = [x["e"] + 0.15 for x in ss if a + min_s <= x["e"] + 0.15 <= a + max_s + 4]
            b = min(longer) if longer else a + min_s
        if total:
            b = min(b, total)
        n = dict(m)
        n["start"], n["end"] = round(a, 2), round(max(b, a + 1), 2)
        out.append(n)
    return out


def extend(m: dict, words: list[dict], extra: float = 10.0, total: float | None = None) -> dict:
    """The next sentence end after the clip's end (within `extra` s), for a clip the AI says stops before its thought is finished."""
    b = float(m["end"])
    nxt = [x["e"] for x in sentences(words) if b + 0.3 < x["e"] <= b + extra]
    n = dict(m)
    if nxt:
        n["end"] = round(min(nxt[0] + 0.15, total) if total else nxt[0] + 0.15, 2)
    return n


def _toks(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']{4,}", (t or "").lower())}


def dedupe(moments: list[dict], texts: list[str], thr: float = 0.5) -> list[int]:
    """Indexes to keep, original order. A clip is dropped when it overlaps a better one in time or repeats most of its words (the same idea said twice)."""
    order = sorted(range(len(moments)), key=lambda i: -float(moments[i].get("score") or 0))
    kept: list[int] = []
    for i in order:
        ti = _toks(texts[i])
        dup = False
        for j in kept:
            a, b = moments[i], moments[j]
            if a["start"] < b["end"] and b["start"] < a["end"]:
                dup = True
                break
            tj = _toks(texts[j])
            if ti and tj and len(ti & tj) / len(ti | tj) >= thr:
                dup = True
                break
        if not dup:
            kept.append(i)
    return sorted(kept) or ([order[0]] if order else [])


RERANK = ("You are the editor choosing which clips to publish from one long video. You get numbered finalist transcripts. Compare them head-to-head: "
          "the best clip has a hook in the first sentence, builds, and pays off, and makes sense with no other context. Penalise setup with no payoff and clips that repeat each other. "
          'Answer ONE JSON object: {"best":[n, n, ...],"unfinished":[n, ...]} where "best" is exactly {count} numbers, best first, and "unfinished" lists the finalists '
          "whose last sentence stops before the thought is complete (cut off mid-story or a setup with no punchline). No other text.")


def ai_rerank(s: dict, moments: list[dict], texts: list[str], count: int, log: Any = None) -> tuple[list[int], list[int]] | None:
    """(indexes of the winners best first, indexes that are unfinished) or None when there is no AI or its answer is unusable."""
    from ..series import writers
    if len(moments) <= 1 or not writers.uses_ai(s):
        return None
    cand = "\n".join(f"Finalist {i + 1} ({m['end'] - m['start']:.0f}s): {t[:700] or '(no words)'}" for i, (m, t) in enumerate(zip(moments, texts)))
    data = writers.ask(s, "story", RERANK.replace("{count}", str(count)), cand, log, max_tokens=300, temperature=0.2)
    if not isinstance(data, dict) or not isinstance(data.get("best"), list):
        return None
    best: list[int] = []
    for x in data["best"]:
        try:
            i = int(x) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(moments) and i not in best:
            best.append(i)
    if not best:
        return None
    for i in range(len(moments)):                         # anything the AI left out can still fill a short list, in its old order
        if len(best) >= count:
            break
        if i not in best:
            best.append(i)
    unf = []
    for x in data.get("unfinished") or []:
        try:
            i = int(x) - 1
        except (TypeError, ValueError):
            continue
        if 0 <= i < len(moments):
            unf.append(i)
    return best[:count], unf


# ---------- tighten: cut dead air and ums ----------
def tighten_plan(words: list[dict], start: float, end: float, gap: float = 0.55, pad: float = 0.11, min_save: float = 1.0, drop_fillers: bool = True) -> list[tuple[float, float]] | None:
    """The stretches of [start, end] to keep: pauses longer than `gap` shrink to about 2*pad and filler words (um, uh) go. None when it would save under `min_save` seconds."""
    ws = [w for w in words if w["e"] > start and w["s"] < end]
    if len(ws) < 4:
        return None
    spans: list[list[float]] = []
    force_split = False
    for w in ws:
        if drop_fillers and _bare(w["w"]) in FILLERS:
            force_split = True
            continue
        s0, e0 = max(start, w["s"]), min(end, w["e"])
        if e0 <= s0:
            continue
        if spans and not force_split and s0 - spans[-1][1] <= gap:
            spans[-1][1] = max(spans[-1][1], e0)
        else:
            spans.append([s0, e0])
        force_split = False
    if not spans:
        return None
    out: list[tuple[float, float]] = []
    for i, (a, b) in enumerate(spans):
        a2 = start if (i == 0 and a - start < 0.4) else max(start, a - pad)
        b2 = end if (i == len(spans) - 1 and end - b < 0.6) else min(end, b + pad)
        if out and a2 < out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], b2))
        else:
            out.append((a2, b2))
    kept = sum(b - a for a, b in out)
    if (end - start) - kept < min_save or len(out) > 60 or len(out) < 2:
        return None
    return [(round(a, 3), round(b, 3)) for a, b in out]


def map_time(t: float, spans: list[tuple[float, float]]) -> float | None:
    """Where source time `t` lands on the tightened clip's clock, or None when that moment was cut out."""
    off = 0.0
    for a, b in spans:
        if a - 1e-6 <= t <= b + 1e-6:
            return round(off + (t - a), 3)
        off += b - a
    return None


def remap_words(words: list[dict], spans: list[tuple[float, float]]) -> list[dict]:
    out = []
    for w in words:
        mid = (w["s"] + w["e"]) / 2
        a = map_time(mid, spans)
        if a is None or _bare(w["w"]) in FILLERS:
            continue
        d = max(0.05, w["e"] - w["s"])
        out.append({**w, "s": round(max(0.0, a - d / 2), 3), "e": round(a + d / 2, 3)})
    return out


def tight_render(src: str, out: Path, spans: list[tuple[float, float]], ffmpeg: str, has_audio: bool = True) -> float:
    """Write the kept stretches of `src` as one video and return its length. Raises RuntimeError when ffmpeg fails (the caller then cuts normally)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    base = max(0.0, spans[0][0] - 1.0)
    rel = [(a - base, b - base) for a, b in spans]
    parts, labels = [], ""
    for i, (a, b) in enumerate(rel):
        parts.append(f"[0:v]trim=start={a:.3f}:end={b:.3f},setpts=PTS-STARTPTS[v{i}]")
        labels += f"[v{i}]"
        if has_audio:
            parts.append(f"[0:a:0]atrim=start={a:.3f}:end={b:.3f},asetpts=PTS-STARTPTS[a{i}]")
            labels += f"[a{i}]"
    n = len(rel)
    parts.append(f"{labels}concat=n={n}:v=1:a={1 if has_audio else 0}[v]" + ("[a]" if has_audio else ""))
    script = out.with_suffix(".graph")
    script.write_text(";".join(parts), "utf-8")
    cmd = [ffmpeg, "-v", "error", "-y", "-nostdin", "-ss", f"{base:.3f}", "-t", f"{rel[-1][1] + 1.0:.3f}", "-i", src, "-filter_complex_script", str(script),
           "-map", "[v]"] + (["-map", "[a]"] if has_audio else []) + ["-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-pix_fmt", "yuv420p"] \
        + (["-c:a", "aac", "-b:a", "160k"] if has_audio else []) + [str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
    script.unlink(missing_ok=True)
    if r.returncode != 0 or not out.is_file():
        raise RuntimeError("tighten failed: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1][:200])
    return round(sum(b - a for a, b in spans), 3)
