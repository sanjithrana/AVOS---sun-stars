"""One-pass clip finding from the whole transcript: an AI editor reads every line and returns complete clips.

Ported from AutoClip by zhouxiaoka (github.com/zhouxiaoka/autoclip, backend/pipeline/clip_finder.py, MIT licence,
Copyright (c) 2024 AutoClip Team), rewritten for this studio: any language, our AI crew, our clip lengths.

Why it gives better clips than loudness alone: a clip is one complete thought. It starts at the first sentence of a question
or a point and ends when the answer is really finished, never on a half sentence, never with the host's next question.
Rows go to the model as `id|time|text` (about 40% fewer tokens than SRT). Long videos are read in ~60-minute windows
(~20 minutes for a local model, which has a small context) that overlap by 4 minutes; picks that overlap by more than half
are the same moment and only the best one stays. Every answer is checked: row numbers in range, a title, a sane length."""
from __future__ import annotations

import re
from typing import Any, Callable

WINDOW_SEC, OVERLAP_SEC, WINDOW_CHARS = 60 * 60, 4 * 60, 70_000
LOCAL_WINDOW_SEC, LOCAL_CHARS = 20 * 60, 12_000
DUPLICATE_OVERLAP = 0.5

PROMPT = (
    "You are the editor of a short-video channel. From the full transcript of an interview, podcast, talk, show or stream, pick every part "
    "that would work as a short video on its own.\n"
    "Each row is `row|start time|text`, in time order (captions are often cut mid-sentence).\n"
    "Pick for: a sharp or surprising point, hard information, a strong emotion or laugh, a line people will quote or argue about, a complete little story. "
    "Prefer parts that open on something happening or a strong line (not on 'so, um, as I was saying'), and that contain one line that works with no setup "
    "(a number, a contrast, a one-sentence answer).\n"
    "CUT RULES (most important): each clip is ONE complete question-and-answer or ONE complete point: from the first sentence of the question or point "
    "to where the answer is really finished. Never stop mid-sentence, never stop just as the answer starts, never end on the next question, "
    "and leave out greetings and the bridge into the next topic.\n"
    "Length: each clip {min_sec}-{max_sec} seconds (from the start row's time to the time of the row after the end row). If an answer is over when it is "
    "over, end it; do not pad with the next question. If it is longer, split it where the thought naturally breaks.\n"
    "Count: {count_lo}-{count_hi} clips from these rows, fewer if there are not that many good ones; clips must not overlap.\n"
    "For each clip give start and end (row numbers, end row included), title (in the language the people speak; under 60 characters; who + the concrete "
    "thing they did or said, or the number; true to the words, no invented claims), reason (why it works, under 20 words) and score (0.0-1.0, how likely "
    "strangers watch it to the end; 0.7+ means post it).\n"
    'Answer ONE JSON object: {{"clips":[{{"start":0,"end":0,"title":"...","reason":"...","score":0.0}}]}}'
)


def clock(sec: float) -> str:
    sec = int(sec)
    return f"{sec // 3600}:{sec % 3600 // 60:02d}:{sec % 60:02d}" if sec >= 3600 else f"{sec // 60}:{sec % 60:02d}"


def rows_of(cues: list[dict] | None, words: list[dict] | None) -> list[dict]:
    """Transcript rows {start, end, text}: the caption cues, or (whisper words only) words grouped into lines of up to 8 s."""
    rows = [{"start": float(c["start"]), "end": float(c["end"]), "text": " ".join(str(c.get("text") or "").split())}
            for c in (cues or []) if str(c.get("text") or "").strip() and "start" in c and "end" in c]
    if rows:
        return sorted(rows, key=lambda r: r["start"])
    out: list[dict] = []
    cur: list[dict] = []
    for w in words or []:
        if cur and (w["s"] - cur[0]["s"] > 8 or str(cur[-1]["w"]).endswith((".", "?", "!"))):
            out.append({"start": cur[0]["s"], "end": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
            cur = []
        cur.append(w)
    if cur:
        out.append({"start": cur[0]["s"], "end": cur[-1]["e"], "text": " ".join(x["w"] for x in cur)})
    return out


def windows(rows: list[dict], seconds: float, overlap: float, chars: int) -> list[tuple[int, int]]:
    """[first, last] row ranges: about `seconds` each, `overlap` shared, under `chars` characters."""
    if not rows:
        return []
    out, first = [], 0
    while first < len(rows):
        start, n, last = rows[first]["start"], 0, first
        while last + 1 < len(rows) and rows[last + 1]["end"] - start <= seconds and n + len(rows[last + 1]["text"]) <= chars:
            last += 1
            n += len(rows[last]["text"])
        out.append((first, last))
        if last + 1 >= len(rows):
            break
        back = last
        while back > first and rows[last]["end"] - rows[back]["start"] < overlap:
            back -= 1
        first = max(back, first + 1)
    return out


def parse(raw: Any, first: int, last: int, rows: list[dict], min_s: float, max_s: float) -> list[dict]:
    items = raw.get("clips") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        return []
    out = []
    for it in items:
        if not isinstance(it, dict):
            continue
        a, b = it.get("start"), it.get("end")
        title = re.sub(r"[*_`#]+", "", str(it.get("title") or "")).strip()
        try:
            a, b = int(a), int(b)
        except (TypeError, ValueError):
            continue
        if not first <= a <= b <= last or not title:
            continue
        end_t = rows[b + 1]["start"] if b + 1 < len(rows) and rows[b + 1]["start"] - rows[b]["end"] < 1.5 else rows[b]["end"]
        length = end_t - rows[a]["start"]
        if length < min_s * 0.5 or length > max_s * 1.8:
            continue                                         # far off the asked length: the model misread the rows
        try:
            score = max(0.0, min(1.0, float(it.get("score"))))
        except (TypeError, ValueError):
            score = 0.5
        out.append({"start": round(rows[a]["start"], 2), "end": round(end_t, 2), "title": title[:80],
                    "reason": " ".join(str(it.get("reason") or "").split())[:140], "llm": score})
    return out


def dedupe(clips: list[dict]) -> list[dict]:
    kept: list[dict] = []
    for c in sorted(clips, key=lambda c: -c["llm"]):
        if all(min(c["end"], o["end"]) - max(c["start"], o["start"]) <= DUPLICATE_OVERLAP * min(c["end"] - c["start"], o["end"] - o["start"]) for o in kept):
            kept.append(c)
    return sorted(kept, key=lambda c: c["start"])


def find(rows: list[dict], ask: Callable[[str, str], Any], min_s: float, max_s: float, count: int, local: bool = False,
         log: Callable[[str], None] | None = None) -> list[dict]:
    """Clips {start, end, title, reason, llm} from the whole transcript, best first. Empty when the model gives nothing usable."""
    if not rows:
        return []
    sec, chars = (LOCAL_WINDOW_SEC, LOCAL_CHARS) if local else (WINDOW_SEC, WINDOW_CHARS)
    spans = windows(rows, sec, OVERLAP_SEC * sec / WINDOW_SEC, chars)
    total = max(1.0, rows[-1]["end"] - rows[0]["start"])
    picked: list[dict] = []
    for first, last in spans:
        share = min(1.0, (rows[last]["end"] - rows[first]["start"]) / total)
        lo, hi = max(1, round(count * share)), max(2, round(count * share * 2))
        prompt = PROMPT.format(min_sec=int(min_s), max_sec=int(max_s), count_lo=lo, count_hi=hi)
        body = "\n".join(f"{i}|{clock(rows[i]['start'])}|{rows[i]['text']}" for i in range(first, last + 1))
        got: list[dict] = []
        for attempt in range(2):
            try:
                got = parse(ask(prompt, body if not attempt else body + "\n\n(Your last answer was not valid. Use the row numbers above and the exact JSON format.)"),
                            first, last, rows, min_s, max_s)
            except Exception as e:  # noqa: BLE001 - one window failing never stops the others
                if log:
                    log(f"The transcript editor failed on one part ({str(e)[:100]}).")
                got = []
            if got:
                break
        picked += got
    out = dedupe(picked)
    if log:
        log(f"The AI editor read the whole transcript in {len(spans)} part{'s' if len(spans) != 1 else ''} and found {len(out)} complete moments.")
    return sorted(out, key=lambda c: -c["llm"])
