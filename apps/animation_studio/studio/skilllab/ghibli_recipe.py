"""Ghibli Recipe Prompt: paste a recipe link (or the recipe), get ONE video prompt for a warm, dreamy Studio Ghibli style anime kitchen.

The prompt is one continuous 15-second scene: the dish being made step by step, with the ingredients, the hands and their motion, the
steam and the light, and the camera moves. With media on it also draws a key frame from the prompt and makes the clip.

  recipe   read the link (the recipe data most food sites publish for search engines) or take the pasted text
  prompt   your writer crew writes the one prompt; with no crew, a built-in template builds it from the same recipe
  video    a key frame from the prompt, then the clip (Seedance, or an open model on your GPU, as the Cost setting allows)

"Studio Ghibli style" names a look, not a franchise to copy: the prompt asks for that kind of soft hand-painted anime kitchen and never
a character, logo or scene from any film.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ..series import writers
from . import base, store

ID = "ghibli-recipe-prompt"
INFO = {
    "id": ID, "name": "Ghibli Recipe Prompt", "group": "Food and ASMR", "kind": "recipe",
    "made_for": "Turn any recipe link into one video prompt: the dish being made in a warm, dreamy Ghibli-style anime kitchen",
    "about": "Reads the recipe, then writes ONE prompt for a single continuous scene: ingredients, hands and motion, steam and light, camera moves, "
             "timed to the length you pick. Prompt only, or it draws a key frame and makes the clip too.",
    "input": "Paste a recipe link (or the recipe itself), e.g. https://example.com/paneer-butter-masala",
    "outputs": ["The prompt", "The cooking scene"],
    "aspect": "16:9", "seconds": [10, 15], "default_seconds": 15, "native_audio": True,
    "examples": ["https://example.com/recipes/tomato-soup", "Masala chai: ginger, cardamom, tea, milk, jaggery", "Pancakes: flour, egg, milk, butter, maple syrup"],
    "credit": "Prompt brief from the 'Ghibli cooking video prompt writer' template.",
}

MAX_PAGE = 1_500_000
UA = "Mozilla/5.0 (compatible; AVOS-Studio recipe reader)"
STYLE = ("warm, dreamy Studio Ghibli style anime kitchen: soft hand-painted backgrounds, gentle watercolour light, a cosy wooden kitchen, "
         "dust motes in a sunbeam, lovingly detailed food")

WRITER = f"""You are a prompt writer for an anime-style cooking video. You are given a recipe (title, ingredients, steps). Write ONE detailed video prompt that
animates the dish being made step by step in a {STYLE}.
Describe the ingredients, the hands and their motion, the steam and the lighting, and the camera moves. It is a single continuous scene of exactly
the requested length: no cuts, no scene changes, no on-screen text. Spread the recipe's key steps across the seconds, in order, with a time range
for each (for example "0-3s", "3-7s"). End on the finished dish, plated, with steam rising.
Rules: describe a look in the Ghibli tradition, but never name a film, a character, or copy a known scene. No logos, no text, no watermarks.
Hands only; no face. Use the real ingredients from the recipe; invent none.
Answer with ONE JSON object: {{"prompt":"the single paragraph prompt, plain text, no markdown"}}"""


# ---------- reading the recipe ----------
def subject_of(text: str) -> str:
    t = " ".join(str(text or "").split())
    m = re.search(r"https?://\S+", t)
    if m:
        u = urllib.parse.urlparse(m.group(0).rstrip(").,"))
        slug = [x for x in u.path.split("/") if x][-1:] or [u.netloc]
        name = re.sub(r"[-_]+", " ", re.sub(r"\.\w{2,5}$", "", slug[0])).strip()
        return (name[:120] or u.netloc[:120]).capitalize()
    return re.split(r"[:\n]", t)[0].strip(" .,'\"")[:120] or "A home-cooked dish"


def _public(host: str) -> bool:
    """Only fetch from the open internet: never your own PC, router, cloud metadata or any private address."""
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return False
    for i in infos:
        ip = ipaddress.ip_address(i[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            return False
    return bool(infos)


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a: Any, **k: Any) -> None:
        return None


def fetch(url: str, hops: int = 3) -> str:
    """The page's text, up to 1.5 MB, over http(s) only, checking every redirect hop against the same public-address rule."""
    opener = urllib.request.build_opener(_NoRedirect)
    for _ in range(hops + 1):
        u = urllib.parse.urlparse(url)
        if u.scheme not in ("http", "https") or not u.hostname or not _public(u.hostname):
            raise RuntimeError("That link can't be read (it must be a public web page).")
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml"})
        try:
            with opener.open(req, timeout=15) as r:  # noqa: S310 - scheme and address checked above
                return r.read(MAX_PAGE).decode(r.headers.get_content_charset() or "utf-8", "replace")
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                url = urllib.parse.urljoin(url, e.headers["Location"])
                continue
            raise RuntimeError(f"The site answered {e.code}. Paste the recipe text instead.") from e
        except OSError as e:
            raise RuntimeError(f"Could not reach that link ({str(e)[:80]}). Paste the recipe text instead.") from e
    raise RuntimeError("Too many redirects. Paste the recipe text instead.")


def _steps(v: Any) -> list[str]:
    out: list[str] = []
    if isinstance(v, str):
        return [x.strip() for x in re.split(r"\n+|(?<=[.!?])\s+(?=[A-Z])", v) if x.strip()]
    for x in v if isinstance(v, list) else [v]:
        if isinstance(x, str):
            out += _steps(x)
        elif isinstance(x, dict):
            if x.get("itemListElement"):
                out += _steps(x["itemListElement"])
            elif x.get("text") or x.get("name"):
                out.append(str(x.get("text") or x.get("name")).strip())
    return out


def _nodes(d: Any) -> list[dict]:
    if isinstance(d, list):
        return [n for x in d for n in _nodes(x)]
    if isinstance(d, dict):
        return [d] + _nodes(d.get("@graph") or [])
    return []


def parse_recipe(page: str) -> dict | None:
    """The Recipe record a site publishes as JSON-LD (name, recipeIngredient, recipeInstructions), or None."""
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', page, re.S | re.I):
        try:
            data = json.loads(html.unescape(m.group(1)).strip())
        except ValueError:
            continue
        for n in _nodes(data):
            t = n.get("@type")
            if "Recipe" in (t if isinstance(t, list) else [t]):
                ing = [" ".join(html.unescape(str(x)).split()) for x in n.get("recipeIngredient") or []]
                steps = [" ".join(html.unescape(s).split()) for s in _steps(n.get("recipeInstructions"))]
                if ing or steps:
                    return {"title": " ".join(html.unescape(str(n.get("name") or "")).split())[:120] or "The dish", "ingredients": ing[:30],
                            "steps": steps[:20], "yield": str(n.get("recipeYield") or "")[:40]}
    return None


def read_recipe(text: str) -> dict:
    t = str(text or "").strip()
    m = re.search(r"https?://\S+", t)
    if m:
        rec = parse_recipe(fetch(m.group(0).rstrip(").,")))
        if not rec:
            raise RuntimeError("No recipe data was found at that link. Paste the recipe text instead.")
        rec["source"] = m.group(0)[:300]
        return rec
    lines = [x.strip(" -*•\t") for x in re.split(r"\n", t) if x.strip()]
    title = subject_of(t)
    rest = t.split(":", 1)[1] if lines and ":" in lines[0] and len(lines) == 1 else "\n".join(lines[1:] if len(lines) > 1 else lines)
    parts = [x.strip() for x in re.split(r",|\n|;", rest) if x.strip()]
    return {"title": title, "ingredients": parts[:30], "steps": [], "yield": "", "source": "pasted", "raw": t[:4000]}


# ---------- the prompt ----------
def _brief(rec: dict, seconds: int) -> str:
    steps = " ".join(f"{i + 1}. {s}" for i, s in enumerate(rec.get("steps") or [])) or "(none given: use the ordinary way this dish is made)"
    return (f"Length: exactly {seconds} seconds, one continuous scene.\nDish: {rec['title']}\n"
            f"Ingredients: {'; '.join(rec.get('ingredients') or []) or '(see the text)'}\nSteps: {steps}\n"
            + (f"Recipe text: {rec['raw']}\n" if rec.get("raw") else ""))[:5000]


def _windows(seconds: int, n: int) -> list[str]:
    edges = [round(seconds * i / n) for i in range(n + 1)]
    return [f"{a}-{b}s" for a, b in zip(edges, edges[1:])]


def template_prompt(rec: dict, seconds: int = 15) -> str:
    """The built-in writer: the same brief filled from the recipe itself, so a run with no AI crew still gives a usable prompt."""
    unit = r"^[\d\s/½¼¾.,-]+(?:cups?|tbsp|tsp|g|kg|ml|l|oz|lb|pinch|cloves?|large|small|medium)?\s*"
    ing = [re.sub(unit, "", i, flags=re.I).strip() or i for i in rec.get("ingredients") or []]
    ing = [i for i in ing if i][:6] or [rec["title"].lower()]
    steps = [s.rstrip(".") for s in (rec.get("steps") or [])][:4] or [f"the ingredients come together into {rec['title'].lower()}"]
    spans = _windows(seconds, len(steps) + 1)
    beats = "; ".join(f"{spans[i]}: {s[0].lower() + s[1:]}, shown by a pair of hands in gentle, unhurried motion" for i, s in enumerate(steps))
    names = ", ".join(ing[:-1]) + " and " + ing[-1] if len(ing) > 1 else ing[0]
    return (f"A single continuous {seconds}-second shot, no cuts, in a {STYLE}. On a worn wooden counter by a sunlit window sit {names}, "
            f"each drawn with soft painted outlines and glowing, appetising colour. A pair of hands, only the hands, makes {rec['title']} step by step. {beats}; "
            f"{spans[-1]}: the finished {rec['title'].lower()} is set down on a handmade plate, steam curling up in the golden light. "
            "Lighting: warm morning sun through the window, dust motes drifting, soft shadows. Camera: starts in a wide, slightly high view of the counter, "
            "drifts in slowly over the hands as they work, dips close to the pan or bowl for the key moment, then eases back out to a tender, still, close "
            "view of the plated dish. Soft ambient sound of the kitchen, gentle sizzling and a wooden spoon on ceramic, no music. No text, no logos, no faces.")


def _clean(text: Any) -> str:
    t = re.sub(r"\s+", " ", str(text or "").strip().strip("\"'`"))
    return re.sub(r"^(here(?:'s| is)[^:]{0,60}:|prompt:)\s*", "", t, flags=re.I)


def usable(text: str, seconds: int) -> bool:
    low = text.lower()
    return (350 <= len(text) <= 3500 and "```" not in text and not text.startswith(("#", "*", "-"))
            and ("ghibli" in low or "anime" in low) and str(seconds) in low
            and not re.search(r"\b(?:cut to|scene 2|shot 2|next scene)\b", low))


def write_prompt(s: dict, rec: dict, seconds: int, log: Any = None) -> str:
    if not writers.uses_ai(s):
        return template_prompt(rec, seconds)
    for attempt in range(2):
        data = writers.ask(s, "story", writers.system("avos-ghibli-recipe", WRITER), _brief(rec, seconds) + ("\nAnswer ONLY the JSON object." if attempt else ""),
                           log, max_tokens=1600, temperature=0.7)
        text = _clean(data.get("prompt") if isinstance(data, dict) else "")
        if usable(text, seconds):
            return text
    if log:
        log({"type": "warn", "text": "The writer's answer did not fit the brief twice, so the built-in template wrote the prompt from the recipe."})
    return template_prompt(rec, seconds)


# ---------- the skill ----------
STAGES = ("recipe", "prompt", "video")
LABELS = {"recipe": "Read the recipe", "prompt": "Write the prompt", "video": "The cooking scene"}


def last_stage(p: dict) -> str:
    return "prompt" if p.get("media") == "prompts" else "video"


def outputs_of(p: dict) -> list[dict]:
    return [{"key": "video", "step": "video", "title": "The cooking scene", "kind": "video", "file": p.get("video"), "prompt": "video"}]


def reset(p: dict, step: str, n: int | None = None) -> None:
    for st in STAGES[STAGES.index(step):]:
        p.setdefault("steps", {}).pop(st, None)
    if step == "recipe":
        p.pop("recipe", None)
    if step in ("recipe", "prompt"):
        p.pop("prompts", None)
    for k in ("video", "picture"):
        p.pop(k, None)
    p["version"] = int(p.get("version", 1)) + 1


def do_recipe(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "recipe", status="working")
    rec = read_recipe(p.get("request") or p["subject"])
    base.put(pid, recipe=rec, title=rec["title"])
    where = "pasted text" if rec.get("source") == "pasted" else rec["source"]
    base.step(pid, "recipe", status="done", note=f"{rec['title']}: {len(rec.get('ingredients') or [])} ingredients, {len(rec.get('steps') or [])} steps ({where[:80]})")


def do_prompt(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "prompt", status="working")
    secs = int(p.get("seconds") or INFO["default_seconds"])
    text = write_prompt(base.sdict(p), p["recipe"], secs, base.logger(pid))
    base.put(pid, prompts={"video": text})
    base.step(pid, "prompt", status="done", note=f"{len(text)} characters for {secs} seconds")


def why_no_video(s: dict) -> str:
    from ..stickman import video
    return f"No video model ran ({video.why_not(s)}), so this is the picture with a slow camera move and no sound."


def do_video(pid: str) -> None:
    from ..explainer import engines
    from ..series import media
    from ..stickman import video
    p = store.load(pid)
    s = base.sdict(p)
    w, h = base.SIZES.get(p.get("aspect") or "16:9", base.SIZES["16:9"])
    secs = int(p.get("seconds") or INFO["default_seconds"])
    prompt = (p.get("prompts") or {}).get("video") or ""
    base.step(pid, "video", status="working")
    img, _info = media.picture(prompt, [], w, h, media.seed_of(pid, "ghibli", p.get("version", 1)), f"{pid}-frame", s=s)
    base.put(pid, picture=base.write(pid, "frame.png", img), thumb="frame.png")
    clip = engine = note = None
    if video.ready(s):
        try:
            clip = video.clip(prompt, [img], None, secs, p.get("aspect") or "16:9", audio=True)
            engine, note = video.engine(s), "made from the key frame"
        except Exception as e:  # noqa: BLE001 - a finished clip beats a stopped run
            store.say(pid, f"The video model could not make the clip ({str(e)[:160]}). Using a camera move on the key frame instead.", "warn")
    if clip is None:
        clip = engines.keypose(s, img, img, secs, "push")
        engine, note = "camera move on the key frame", why_no_video(s)
    base.put(pid, video=base.write(pid, "scene.mp4", clip), engine=engine)
    base.step(pid, "video", status="done", model=engine, note=note)


RUN = {"recipe": do_recipe, "prompt": do_prompt, "video": do_video}
