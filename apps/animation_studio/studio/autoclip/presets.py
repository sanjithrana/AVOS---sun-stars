"""Auto Clip presets. GTA 6 Clip Kit (Anylancer): one long stream in, up to 15 vertical clips out, picked for the moments people watch,
with a hook line on screen for the first seconds and a title that carries the search words ("GTA 6 cop chase ...").

The kit's own tool (OpenShorts) is only linked: this preset does the same job inside AVOS with the clip engine that is already here."""
from __future__ import annotations

import re

LINKS = [
    {"label": "OpenShorts on GitHub (MIT, self-hosted, no watermark)", "url": "https://github.com/mutonby/openshorts"},
    {"label": "OpenShorts hosted (no setup, free plan has a watermark)", "url": "https://www.openshorts.app/"},
    {"label": "Free Gemini API key (for picking moments in OpenShorts)", "url": "https://aistudio.google.com/app/apikey"},
]

# label -> (words that show up when it happens, hook line when none is written)
MOMENTS: dict[str, tuple[list[str], str]] = {
    "cop chase": (["chase", "cops", "cop", "police", "wanted", "pursuit", "helicopter", "stars"], "The cops did NOT expect this"),
    "crash": (["crash", "crashed", "wreck", "flip", "flipped", "explode", "exploded", "boom", "smash"], "Wait for the crash"),
    "epic fail": (["fail", "oops", "wasted", "died", "dead", "busted", "missed", "whoops"], "He did NOT see that coming"),
    "glitch": (["glitch", "bug", "broken", "fell through", "clipping", "stuck", "frozen", "floating"], "This should not be possible"),
    "funny moment": (["haha", "lol", "funny", "laughing", "dying", "no way", "bro", "what is that"], "I can't stop laughing at this"),
    "first-time discovery": (["first time", "look at this", "did you see", "secret", "found", "discovered", "wow", "check this"], "Nobody told me about this"),
    "rage moment": (["rage", "unbelievable", "are you kidding", "what the", "come on", "seriously", "stop"], "He completely lost it"),
    "impossible stunt": (["jump", "stunt", "ramp", "insane", "impossible", "clutch", "perfect", "landed"], "Impossible stunt. Watch this"),
}

PRESETS = {
    "gta6": {
        "id": "gta6", "name": "GTA 6 clips", "tag": "Game moments",
        "about": "Built from Anylancer's GTA 6 Clip Kit: picks the moments people search for (cop chases, crashes, fails, glitches, funny reactions, "
                 "first-time discoveries, rage, stunts), burns a hook line over the first seconds and titles each clip with the search words.",
        "title_prefix": "GTA 6",
        "moments": list(MOMENTS),
        "plan": [
            ["Day 1", "Set the tool up. Pick 2 or 3 streamers whose clipping rules you have read."],
            ["Day 2-3", "Clip every launch stream. Post 3 to 5 clips a day on each platform."],
            ["Day 4-5", "See which moments got the most views and clip more of those."],
            ["Day 6-7", "Keep the daily rhythm and collect your best clips as a portfolio."],
        ],
        "rules": [
            "Clip streamers who allow it. Many run clipping programs and pay per view: find their rules and campaign links and follow them. "
            "Posting someone's stream without permission can get your clips removed.",
            "Feed it the VOD. One long stream in, up to 15 clips out: keep the best 3 to 5.",
            "Hook in the first second. Keep the hook line or write your own: \"He did NOT see that coming\".",
            "Title with the search words: \"GTA 6\" plus the moment. Post every day at the same time.",
        ],
        "links": LINKS,
        "defaults": {"count": 12, "min_seconds": 30, "max_seconds": 45, "caption": "hype", "layout": "blur"},
        "credit": "GTA 6 Clip Kit, free from Anylancer.com. Not affiliated with Rockstar Games or OpenShorts (MIT, by mutonby).",
    },
}


def public() -> list[dict]:
    return list(PRESETS.values())


def get(pid: str | None) -> dict | None:
    return PRESETS.get(str(pid or ""))


def classify(text: str) -> tuple[str | None, float]:
    """The moment a transcript most looks like, and how strongly (number of hits). (None, 0) when nothing matches."""
    t = " " + re.sub(r"[^a-z' ]+", " ", (text or "").lower()) + " "
    best, score = None, 0.0
    for label, (words, _hook) in MOMENTS.items():
        n = sum(t.count(f" {w} ") for w in words)
        if n > score:
            best, score = label, float(n)
    return best, score


def rerank(moments: list[dict], texts: list[str], count: int) -> list[int]:
    """Indexes of the `count` best moments: loudness score plus what is said (each hit is worth a quarter of the average loudness)."""
    avg = sum(m["score"] for m in moments) / max(1, len(moments))
    scored = []
    for i, (m, t) in enumerate(zip(moments, texts)):
        _, hits = classify(t)
        scored.append((m["score"] + min(hits, 4) * 0.25 * avg, i))
    scored.sort(reverse=True)
    return sorted(i for _, i in scored[:count])


def title(preset: dict, label: str | None, base: str, prefix: str | None = None) -> str:
    pre = prefix or preset["title_prefix"]
    head = f"{pre} {label}" if label else pre
    return f"{head}: {base}"[:90] if base else head


def hook(label: str | None) -> str:
    return MOMENTS[label][1] if label in MOMENTS else "Watch this until the end"
