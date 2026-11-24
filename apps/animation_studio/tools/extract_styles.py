"""Turn 66 STYLE.md files into one compact Python table AVOS can use without reading the library at run time."""
import json, re, sys
from pathlib import Path

src, out = Path(sys.argv[1]), Path(sys.argv[2])

NAMEY = re.compile(r"\s*\(([^()]{2,60})\)")


def _is_names(inner: str) -> bool:
    """True for '(Cassandre, Lempicka)' and false for '(a map, a supply chain, a city)'.

    Artists, directors and buildings are named all through these prompts as grammar. They are useful to a human
    writing a style and actively harmful in a prompt sent to a picture model, so every parenthetical that is just a
    list of proper names comes out.
    """
    items = [i.strip() for i in inner.split(",") if i.strip()]
    if not items or len(items) > 4:
        return False
    for it in items:
        words = it.split()
        if not 1 <= len(words) <= 3:
            return False
        if not all(w[:1].isupper() for w in words if w[:1].isalpha()):
            return False
        if not any(w[:1].isalpha() for w in words):
            return False
    return True


def scrub(t: str) -> str:
    return re.sub(r"\s{2,}", " ", NAMEY.sub(lambda m: "" if _is_names(m.group(1)) else m.group(0), t)).strip()


def sections(md: str) -> dict:
    """{normalised heading: body} for '## 1. Heading' blocks."""
    parts = re.split(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$", md, flags=re.M)
    d = {}
    for i in range(1, len(parts) - 1, 2):
        key = re.sub(r"[^a-z]+", " ", parts[i].lower()).strip()
        d[key] = parts[i + 1].strip()
    return d

def pick(d: dict, *words):
    for k, v in d.items():
        if all(w in k for w in words):
            return v
    return ""

# A style prompt is half art direction and half build notes. Only the first half means anything to a picture model,
# and the second half crowds it out of a 900-character budget, so these go.
CODEY = re.compile(r"\b(canvas|ctx|shader|webgl|rgb|rgba|hex|px\b|fps\b|source-over|globalCompositeOperation|"
                   r"function|const |return |\.js\b|json|array|buffer|pipeline|render pass|framebuffer|"
                   r"seeded|prng|uniform|vertex|fragment)\b", re.I)


# A dimension ("320x180 pixels") is visual vocabulary and stays; a formula is not.
MATHY = re.compile(r"(?<!\d)[×x](?!\d)(?<![a-z])|[÷Π∑√≈≤≥^²³αβγδθλμσΔ]|\b\w+_\w+\b"
                   r"|\bmix\(|\bclamp\(|\blerp\(|\.(?:sh|py|mjs|js|json|glsl)\b")


def is_build_note(t: str) -> bool:
    return bool(CODEY.search(t) or MATHY.search(t)) or "→" in t or t.count("=") >= 1 or t.count("(") >= 3


def bullets(text: str, n: int, cap: int, drop_build: bool = True) -> list:
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith(("-", "*")):
            continue
        t = re.sub(r"^[-*]\s*", "", line)
        t = re.sub(r"`([^`]*)`", r"\1", t)
        t = re.sub(r"\*\*([^*]*)\*\*", r"\1", t).replace("*", "")
        t = re.sub(r"\s+", " ", t).strip(" .;")
        t = scrub(t)
        if drop_build and is_build_note(t):
            continue
        if len(t) > cap:
            t = t[:cap].rsplit(" ", 1)[0] + "…"
        if len(t) > 15:
            out.append(t)
        if len(out) >= n:
            break
    return out

def bullets_or(text: str, n: int, cap: int) -> list:
    """Filtered bullets, or unfiltered ones if filtering left nothing. A thin record is worse than a noisy one."""
    return bullets(text, n, cap) or bullets(text, n, cap, drop_build=False)


def para(text: str, cap: int) -> str:
    for block in text.split("\n\n"):
        b = block.strip()
        if b.startswith(("-", "*", "|", ">", "#")) or len(b) < 40:
            continue
        b = re.sub(r"`([^`]*)`", r"\1", b)
        b = re.sub(r"\*\*([^*]*)\*\*", r"\1", b).replace("*", "")
        b = re.sub(r"\s+", " ", b).strip()
        b = scrub(b)
        if is_build_note(b):
            continue
        return b[:cap].rsplit(" ", 1)[0] + "…" if len(b) > cap else b
    return ""

recs = {}
for d in sorted((src / "styles").iterdir()):
    sm, sj = d / "STYLE.md", d / "style.json"
    if not (d.is_dir() and sm.exists()):
        continue
    md = sm.read_text("utf-8")
    meta = json.loads(sj.read_text("utf-8")) if sj.exists() else {}
    # the leading blockquote, WITHOUT the "References" line: those name real artists, films and buildings, and
    # AVOS must not put those names into a picture prompt. The craft description is the useful half anyway.
    quote = ""
    for line in md.splitlines():
        if line.startswith("> "):
            t = line[2:].strip()
            if t.lower().startswith(("references", "reference")):
                continue
            quote = scrub(re.sub(r"\*\*([^*]*)\*\*", r"\1", t).replace("*", ""))
            break
        if quote:
            break
    s = sections(md)
    ess = pick(s, "essence")
    nots = ""
    m = re.search(r"((?:Not |It is not |Never )[^\n]{20,400})", ess)
    if m:
        nots = re.sub(r"\*\*([^*]*)\*\*", r"\1", m.group(1)).replace("*", "")
        nots = scrub(re.sub(r"`([^`]*)`", r"\1", nots))
        nots = re.sub(r"^(?:It is not|Not|Never)\s+", "", nots, flags=re.I)
    recs[d.name] = {
        "name": meta.get("en") or d.name, "cat": meta.get("category_en") or "Other",
        "line": meta.get("line") or "", "uses": (meta.get("uses") or [])[:3],
        "quote": quote[:300],
        "essence": para(ess, 420) or " ".join(bullets_or(ess, 2, 210)),
        "nots": nots[:300],
        "material": bullets_or(pick(s, "material"), 4, 170) or bullets_or(ess, 4, 170)[:3],
        "colour": bullets_or(pick(s, "colour"), 3, 160) or [para(pick(s, "colour"), 240)],
        "motion": bullets_or(pick(s, "motion"), 3, 160) or [para(pick(s, "motion"), 240)],
        "camera": bullets_or(pick(s, "camera"), 2, 150),
        "sound": bullets_or(pick(s, "sound"), 2, 140),
    }

body = ['"""The 66 Lemo-Opuscar film styles, compressed into prompt material AVOS can use.',
        "",
        "Generated from skills/lemo-opuscar/styles/*/STYLE.md by tools/extract_styles.py. Do not hand-edit: regenerate.",
        "",
        "Each record is what a picture model can actually act on -- the look, what the style is NOT, its materials,",
        "colour logic, motion and camera -- compressed from a twelve-page style prompt to a few hundred characters,",
        "because Pollinations cuts a prompt at 900 characters and FLUX at about 256 tokens.",
        "",
        "The upstream 'References' lines are deliberately left out. They name real artists, films and buildings as",
        "grammar, and the upstream itself says never to copy a poster layout, a real building, a character, a typeface",
        "design or a melody. Those names have no place in a prompt sent to a picture model, so they are not here.",
        '"""',
        "from __future__ import annotations",
        "",
        "STYLES: dict[str, dict] = " + json.dumps(recs, indent=1, ensure_ascii=False),
        ""]
out.write_text("\n".join(body), "utf-8")
print(f"{len(recs)} styles -> {out.name}, {out.stat().st_size // 1024} KB")
import statistics
ls = [len(r["essence"]) + len(r["quote"]) + sum(map(len, r["material"])) for r in recs.values()]
print(f"look material per style: median {int(statistics.median(ls))} chars, max {max(ls)}")
missing = [k for k, r in recs.items() if not r["essence"] or not r["material"]]
print("thin records:", missing or "none")
