"""Company Story skill: name a company or an industry, get a narrated 16:9 cartoon business story in the "founder caricatures and
company empires" look (one big-head cartoon founder on the left, a toy-town of company buildings, paper cards with exact numbers).

  research   Wikipedia articles on the subject (each kept with its link) PLUS Wikidata's structured facts (founding date, founders,
             headquarters, parent, employees and revenue with the year they refer to). The AI writer pulls milestones, numbers and how
             it works from the source text only; Wikidata settles the founding year when the two disagree, and the clash is shown.
  script     one 10-second scene per beat, narration from the research only. Every number on a card, in the narration or in the
             title must be one of the RESEARCHED facts (not just any number somewhere in an article): cards that fail are dropped,
             narration that fails is rewritten once by the writer, then the unchecked sentence is cut.
  cast       ONE ready-made 2D character per video (cut out of your model sheets into transparent poses). Nothing is drawn: the
             character is exactly the one you picked
  scenes     per scene: the backdrop is drawn WITHOUT people (the place from the research, props that tell the moment, the left third kept
             open), then the character is stood on it in code (compose.py) in three poses that follow the narration (pointing, thinking,
             arms open, cheering…), the first pose is the scene picture
  animate    AI video (Seedance 2.0 through fal.ai) from the scene picture; if that isn't set up the run stops and says so. Drawn-poses motion
             is the free choice: cut and crossfade between the three poses every ~3 s with a slow push-in. Then the cards are composited frame
             by frame without covering the character or each other
  voice      one narrator (a silent result stops the run with the reason)
  finish     joins the scenes with the voice and a light underscore (never shorter than the length asked for)"""
from __future__ import annotations

import io
import json
import os
import re
import urllib.parse
import urllib.request
import wave
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from .. import paper
from ..series import media, writers
from . import base, cards, compose, store

ID = "company-story"
INFO = {
    "id": ID, "name": "Company Story", "group": "Business stories", "kind": "story",
    "made_for": "Give a company or an industry: it researches how it started, grew, competes and works, then makes a narrated cartoon story",
    "about": "Research first (Wikipedia and Wikidata, every source kept), then a script that may only use those facts, one ready-made 2D character you pick "
             "in front of a toy-town backdrop (AI video for each scene), and paper cards drawn by code so every number is exact: the "
             "company card with its years, counting numbers, a caption strip and a VS banner for the rival company. One narrator, a light underscore, "
             "landscape for YouTube or portrait for reels, from 30 seconds to 10 minutes.",
    "input": "A company or an industry, e.g. Toyota, Nvidia, Zomato, the airline industry",
    "outputs": ["Research with sources", "Script and scene cards", "Narrated video (16:9 or 9:16 reel)"],
    "aspect": "16:9", "aspects": ["16:9", "9:16"], "seconds": [30, 60, 90, 180, 300, 600], "default_seconds": 60, "native_audio": False,
    "examples": ["Toyota", "Nvidia", "Zomato", "Tata Group", "Netflix", "The airline industry"],
    "credit": "Look modelled on the 'Founder Story' style: founder caricatures and company empires.",
    "make": [["media", "Research, script and video"], ["prompts", "Research and script only"]],
    "styles": [["2d", "2D paper-cut"]],
    "motions": [["video", "AI video for every scene (Seedance, needs fal.ai credit)"], ["poses", "Paper puppet: swaying character + paper effects (free)"]],
}
# The ready-made characters (2D, cut out of your model sheets into transparent poses in characters/<id>/): ONE character per video. The scene
# backdrop is drawn without people and the chosen character is placed on it in code (compose.py), so he is always exactly the one you picked.
CHAR_DIR = Path(__file__).with_name("characters")
CHARACTERS = {
    "director": {"name": "Corporate director", "about": "Stout, wavy dark hair, big mustache, grey suit with brown leather lapels"},
    "young": {"name": "Young businessman", "about": "Slim, short curly brown hair, cheerful, black suit and black tie"},
    "executive": {"name": "Middle-aged executive", "about": "Friendly build, greyish-brown hair, glasses, dark grey suit"},
}
INFO["characters"] = [{"id": k, "name": v["name"], "about": v["about"]} for k, v in CHARACTERS.items()]
INFO["default_cast"] = {"founder": "executive"}
STAGES = ("research", "script", "cast", "scenes", "animate", "voice", "finish")
LABELS = {"research": "Research with sources", "script": "Script and cards", "cast": "Founder characters", "scenes": "Scene pictures and poses",
          "animate": "Motion and cards", "voice": "Narration", "finish": "Final video"}
SCENE_SECONDS = 10                          # a scene of a short video; a longer video uses longer scenes (PACING)
POSES = 3                                   # pictures per scene when there is no Seedance: the founder changes gesture every ~3 s
# A ten-minute story cannot be 60 ten-second scenes: the research does not hold 60 distinct moments, and it would be 60 pictures and
# 60 clips. Longer videos therefore use longer scenes, with more narration in each.
PACING = ((90, 10), (300, 12), (10 ** 6, 15))
WORDS_PER_SECOND = 2.6                      # measured against the narration voices


def scene_seconds(total: float) -> int:
    """How long one scene runs in a video of this length."""
    return next(sec for cap, sec in PACING if float(total) <= cap)


def scenes_for(total: float) -> int:
    """How many scenes a video of this length has."""
    return max(3, round(float(total) / scene_seconds(total)))


def words_for(secs: float) -> tuple[int, int]:
    """The spoken-word range for one scene of `secs` seconds."""
    mid = secs * WORDS_PER_SECOND
    return round(mid * 0.85), round(mid * 1.15)


INFO["lengths"] = [{"seconds": n, "scenes": scenes_for(n), "each": scene_seconds(n)} for n in INFO["seconds"]]
UA = "AVOS-animation-studio/1.1 (company-story skill; local app)"

LOOK = (paper.LOOK_SHORT + ", built as a toy-town of paper buildings, factories and towers on a tabletop, every building, hill, cloud and river a "
        "separate cut-out sheet with its own drop shadow, simple bold shapes, NOT photographic, NOT 3D, NOT realistic, NOT a painting")
PAPER_TAIL = ("Flat paper colours, visible cut edges and real paper thickness, deep shadow separation between the layers, generous empty space. "
              "No text, no letters, no numbers, no signs, no logos, no watermark anywhere.")
NO_TEXT = ("No text, no letters, no numbers, no signs, no logos, no labels, no watermarks anywhere in the picture (text is added later).")
# Where the character will be standing has to stay empty, and that differs by shape and by which side he is on this scene.
BRIGHTER = ("MUCH BRIGHTER: a pale cream or light blue paper sky filling the top half, light-coloured paper buildings and ground, strong even "
            "daylight, and several clearly visible paper objects in the scene. Not a dark room, not an empty frame.")
BRIGHT = "Bright even daylight, warm cream or soft blue paper sky, every shape clearly lit. Never a dark, gloomy or empty frame, even in a crisis scene."
FRAME = ("COMPOSITION (16:9 landscape): the buildings and props sit in the CENTRE and {far} of the frame. The {near} third is kept almost empty "
         "(flat grass, road or floor, low detail), because a character is placed there afterwards. The top band and a strip along the bottom stay "
         "calm sky or ground (paper cards are placed there later). NO people at all.")
FRAME_VS = ("COMPOSITION (16:9 landscape): this company's buildings in the centre-left and the rival company's taller towers on the right, a river or "
            "road between them with a clear gap; the far {near} third stays almost empty (flat ground, low detail) because a character is placed there "
            "afterwards; the top band stays calm. NO people at all.")
FRAME_TALL = ("COMPOSITION (9:16 vertical reel): build the scene TALL - the sky and the tops of the buildings fill the upper half, the buildings and "
              "props sit across the middle, and the BOTTOM THIRD is kept almost empty (flat ground, road or floor, low detail) because a character is "
              "placed there afterwards. Keep the very top calm (paper cards are placed there later). NO people at all.")
FRAME_VS_TALL = ("COMPOSITION (9:16 vertical reel): this company's buildings on the left and the rival's taller towers on the right, a river or road "
                 "between them, both reaching up into the upper half; the BOTTOM THIRD stays almost empty (flat ground, low detail) because a character "
                 "is placed there afterwards; the very top stays calm. NO people at all.")


def side_of(n: int, aspect: str) -> str:
    """Which side the character stands on. In a reel he is always centred at the bottom; in landscape he changes side every other scene,
    so six scenes do not look like the same photograph six times."""
    return "centre" if (aspect or "16:9") == "9:16" else ("left" if n % 2 else "right")


def frame_for(aspect: str, vs: bool, side: str) -> str:
    if side == "centre":
        return FRAME_VS_TALL if vs else FRAME_TALL
    near, far = ("LEFT", "right-centre") if side == "left" else ("RIGHT", "left-centre")
    return (FRAME_VS if vs else FRAME).format(near=near, far=far)


NEGATIVE = ("people, person, character, face, crowd, silhouette, aerial view of a tiny map, text, letters, numbers, logo, watermark, caption, blurry, "
            "photo-realistic, photograph, realistic, 3D render, painting, oil painting, gradient mesh, lens flare, " + paper.NEGATIVE)
BEATS = ["the HOOK: the most astonishing true fact about the person or company in one sentence, then who they are; the company card",
         "the STRUGGLE and the SPARK: what they did before, what was not working, the gap they noticed",
         "the BET: how they started and with how little (money, team, constraint) and what they did differently",
         "the TROUBLE and the TURN: rejections, rivals or a near-failure, then the partner, launch or event that fixed it",
         "the GROWTH: how it grew, figures and years in order (revenue, users, valuation, employees); one criticism if the research has one",
         "the TAKEAWAY: where it stands today, then the real lesson in two or three crisp principles from what happened",
         "the rivalry: the main competitor and how they compare", "the people: how it hires, builds and sells", "what comes next, from what is known"]
DEFAULT_POSES = {"origin": ["standing proud, hands on hips", "hand on chin, thinking", "fists raised, cheering"],
                 "rivalry": ["pointing toward the right", "hand on chin, thinking", "presenting with one hand out"],
                 "": ["pointing toward the right", "arms open wide, welcoming", "hand on chin, thinking"]}

# The two writer prompts are static (no placeholders), so skills/avos-company-story*/SKILL.md can hold the same text.
RESEARCH = """You are the research desk of a business-history video channel. You get long source texts about a company or an industry (the full
Wikipedia article, its history sections, sometimes a separate history article) and structured facts from Wikidata. Dig out the STORY, not just the
summary: the humble start, the big bet, the near-death moment, the turning point, the breakthrough, the rivals, and where it stands now.
Answer with ONE JSON object only:
{"name":"the short common name, e.g. Nvidia","kind":"company|industry","founded":"year or empty","founder":"the founder(s) or empty",
 "origin":"one or two sentences: where, how and why it began, with the concrete details the sources give (the place, the first idea, the first product)",
 "home":"headquarters or region",
 "story_moments":[{"year":"YYYY or empty","title":"3-6 word name, e.g. The meeting at a diner","what":"2-3 sentences with the concrete details from the source: the place, the people, what was at stake, what they decided, what happened next, exact figures as written","kind":"beginning|bet|crisis|turning point|breakthrough|rivalry|today","source":<n>}],
 "milestones":[{"year":"YYYY","event":"one plain sentence","source":<source number>}],
 "numbers":[{"value":"ONE exact figure as written in the source, e.g. 375,235 or $44 billion","label":"what it counts, e.g. employees","year":"year it refers to or empty","source":<n>}],
 "how_it_works":["how it makes money or operates today, one sentence each"],"rivals":["main competitors named in the sources"],
 "turning_points":["decisions or crises that changed it, one sentence each"],"unknowns":["what the sources leave unclear or where they disagree"]}
Rules:
- Use ONLY the source texts and the Wikidata facts, never outside knowledge or memory. If a famous anecdote is not in the sources, leave it out.
- The founding year is when the business first started, even under an earlier name (a renaming, a new parent company, an IPO or a listing is a milestone, not the founding). If Wikidata gives an inception year, use it.
- Every year and number must be written in the cited source. Give every number the year it refers to ("as of"), when the source says.
- 5-8 story moments, in time order, covering as many of beginning, bet, crisis, turning point, breakthrough, rivalry and today as the sources support. These are what the video is built on, so make them vivid and specific.
- 8-14 milestones in time order, from the start to the latest year in the sources; leave out trivia (awards, single ad campaigns, minor lawsuits).
- Up to 12 numbers. Prefer a GROWTH TRAIL: the same measure (revenue, users, employees, valuation, stores, units sold) at different years, from the start to the latest, so the video can show how it grew. Add the first sale, the money it started with, the crisis and the size today. Each with the year it refers to.
- Leave a field empty rather than guess."""

SCRIPT = """You are the head writer of a viral business-story channel (the kind of 60-second videos people watch to the end and share). You turn researched facts into a PERSON-DRIVEN story, told like a smart friend explaining over coffee, never like an encyclopedia or a press release. You get the research (with its story moments, milestones and numbers), the number of scenes, how long each scene is on screen and the job of each scene.
HOW THE NARRATION SOUNDS (study these openings and this rhythm; they are style examples only, never reuse their facts):
  "This man built a $1.8 billion company without hiring a single person."  /  "How a Flipkart engineer built his own billion-dollar company."  /  "A brand that turned headphones from gadgets into a fashion statement: meet boAt."
  Short punchy sentences. Plain words a 15-year-old understands. Then the turns: "But...", "So instead...", "However, it wasn't that simple.", "Suddenly...", "But the real shift came when...". Ask one question the viewer is wondering ("But how did boAt become so popular?"). Put the person first: name the founder, what he did before, what frustrated him, what he noticed.
THE STORY SHAPE (scene jobs follow it): 1 the HOOK: the most astonishing true fact about the person or company in one sentence (the size, the speed, "without X"), then who they are. 2 the STRUGGLE and the SPARK: what they did before, what was not working, the gap they noticed. 3 the BET: how they started and with how little (the money, the team, the constraint), and what they chose to do differently. 4 the TROUBLE: rejections, rivals, a near-failure, or the world changing around them, then the TURN that fixed it (a partner, a launch, an event). 5 the GROWTH: how it grew, with figures and years in order (first revenue, then the later years, users, valuation, employees); one trouble or criticism if the research has one. 6 the TAKEAWAY: where it stands today, then "the real lesson is..." in two or three crisp principles taken from what actually happened. Never open with "Every empire starts somewhere" or any generic line.
RULES: Use ONLY facts, names, years and numbers from the research. Never invent figures, dates, quotes, places or motives; if a detail is not in the research, leave it out and tell the story with what is known. Say numbers the way people say them ("a hundred million dollars", "₹941 crore"), and always with their year ("by 2025"). Do not use the words "legacy", "empire" or "journey" more than once in the whole video.
Each scene has:
- "narration": English, in the voice above, as many spoken words as the ask gives you for one scene (never more: the scene cuts away). Build each scene on a story moment from the research and use its real details (the place, the people, the money, the stakes).
- "place": the BACKDROP of the scene, from the research, as something we can see (e.g. "a roadside diner with coffee cups and napkin sketches on the tables", "a dark server room glowing blue", "a stormy sky over the company headquarters"). It is drawn WITHOUT any people: the main character is placed in front of it afterwards.
- EVERY SENTENCE IS ONE PICTURE: each sentence of the narration carries exactly ONE complete visual idea, because the scene can only show one thing; never put two ideas in one sentence. Never give two sentences in a row the same rhythm (alternate short and medium), and every second or third scene must land one of: a surprising fact, a reveal, a twist, a contrast, an unexpected comparison, a scale reveal, a consequence or a payoff.
- "visual": the objects and symbols in the backdrop that tell the moment (a red chart crashing on a big screen, a calendar flipping, a glowing chip, a stadium crowd screen, rival towers across the river). No people, no readable text, logos or numbers.
- "poses": three gestures the main character (the founder's stand-in, a cartoon character, never a real person's face) makes in this scene, in order, each chosen ONLY from: "arms open wide, welcoming", "pointing toward the right", "presenting with one hand out", "hand on chin, thinking", "holding a tablet or paper", "on the phone", "fists raised, cheering", "standing proud, hands on hips". Match them to the narration (a crisis is thinking or worry, a win is cheering) and use three different ones.
- "setting": origin|factory|city|rivalry|boardroom|world (the nearest one), "move": slow push in|slow pull out|pan left|pan right, "rival": true only in the rivalry scene.
- "cards": paper cards drawn on screen by code:
  {"type":"title","kicker":"THE LEGACY|THE STORY OF|THE ENTIRE HISTORY OF","text":"short company name"}  scene 1 only (the years are added for you)
  {"type":"stat","value":"ONE figure copied exactly from the research","unit":"2-4 words saying what it counts and the year, e.g. revenue in 2025"}  at most 3 per scene, only figures from the research. Show the GROWTH: across the growth scenes use the same measure at different years so the viewer watches it climb, each stat with its year card
  {"type":"caption","text":"3-6 word hook line","accent":"the one word to colour red"}  most scenes have one
  {"type":"year","value":"YYYY"}  the year of the moment (not in scene 1)
  {"type":"vs","left":"this company","right":"the rival"}  only in the rivalry scene, only for a rival named in the research; its caption becomes the banner, e.g. "THE PRICE WAR"
The title is a YouTube title built only from research facts, e.g. "<Name>: From <the humble start> to <what it is now>". No number in it unless it is in the research.
Answer with ONE JSON object: {"title":str,"scenes":[{"purpose":str,"narration":str,"place":str,"visual":str,"poses":[str,str,str],"setting":str,"move":str,"rival":bool,"cards":[...]}]}"""

NO_VIDEO = ("AI video needs a working video model: add a fal.ai key with credit in Settings, then press Continue. Or switch this run to "
            "drawn poses (free), which cut between three drawn poses per scene with camera moves.")
NO_VIDEO_FELL_BACK = ("No video model is ready (add a fal.ai key with credit in Settings), so this run uses the free paper-puppet motion. "
                      "The video still gets made.")
FIX = """You check a business-story script against its research. Some narration lines use numbers or years that are NOT in the research. Rewrite each
line given so it keeps its meaning and length (20-26 words) but uses only numbers and years that appear in the research, or no numbers at all.
Answer with ONE JSON object: {"lines":{"<scene number>":"rewritten narration"}}"""


# ---------- numbers ----------
def _num_tokens(text: str) -> set[str]:
    return {x.replace(",", "").rstrip(".") for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")}


def checked(text: str, allowed: set[str]) -> bool:
    """Every number in `text` is one of the allowed numbers."""
    return all(t in allowed for t in _num_tokens(text))


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


# ---------- Wikidata ----------
CURRENCY = {"Q4917": "$", "Q80524": "₹", "Q4916": "€", "Q25224": "£", "Q8146": "¥", "Q39099": "CN¥", "Q1104069": "C$", "Q259502": "A$",
            "Q202040": "₩", "Q25344": "CHF ", "Q131473": "R$", "Q41044": "₽", "Q4730": "MX$", "Q4608": "S$", "Q31015": "HK$"}


def _get_json(url: str, timeout: int = 15) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 - fixed https hosts below
        return json.loads(r.read().decode("utf-8"))


def _big(amount: float, sym: str) -> str:
    for div, word in ((1e12, "trillion"), (1e9, "billion"), (1e6, "million")):
        if abs(amount) >= div:
            x = amount / div
            return f"{sym}{x:.1f}".rstrip("0").rstrip(".") + f" {word}"
    return f"{sym}{amount:,.0f}"


def _year(t: str) -> str:
    m = re.match(r"[+-]?(\d{4})-", t or "")
    return m.group(1) if m else ""


def wikidata(title: str) -> dict:
    """Structured facts for a Wikipedia article: {} when there are none or Wikidata can't be reached (the research still works)."""
    try:
        q = _get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "prop": "pageprops", "ppprop": "wikibase_item", "redirects": 1, "titles": title, "format": "json"}))
        qid = next((p.get("pageprops", {}).get("wikibase_item") for p in (q.get("query", {}).get("pages") or {}).values()), None)
        if not qid:
            return {}
        ent = _get_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json")["entities"][qid]
    except Exception:  # noqa: BLE001 - optional
        return {}
    cl = ent.get("claims") or {}

    def vals(pid: str) -> list[dict]:
        out = [c for c in cl.get(pid) or [] if c.get("rank") != "deprecated" and (c.get("mainsnak") or {}).get("datavalue")]
        pref = [c for c in out if c.get("rank") == "preferred"]
        return pref + [c for c in out if c not in pref]

    def ids(pid: str, n: int) -> list[str]:
        return [c["mainsnak"]["datavalue"]["value"].get("id") for c in vals(pid)[:n] if isinstance(c["mainsnak"]["datavalue"]["value"], dict)]

    def when(c: dict) -> str:
        for qp in ("P585", "P580"):
            for x in (c.get("qualifiers") or {}).get(qp) or []:
                y = _year(((x.get("datavalue") or {}).get("value") or {}).get("time", ""))
                if y:
                    return y
        return ""

    def latest(pid: str) -> tuple[dict | None, str]:
        best, by = None, ""
        for c in vals(pid):
            y = when(c)
            if best is None or y > by:
                best, by = c, y
        return best, by

    founded = next((_year(c["mainsnak"]["datavalue"]["value"].get("time", "")) for c in vals("P571")), "")
    refs = {"founders": ids("P112", 4), "hq": ids("P159", 1), "parent": ids("P749", 1), "subs": ids("P355", 6), "industry": ids("P452", 3), "country": ids("P17", 1)}
    emp, emp_y = latest("P1128")
    rev, rev_y = latest("P2139")
    unit = ""
    if rev:
        unit = str(rev["mainsnak"]["datavalue"]["value"].get("unit") or "").rsplit("/", 1)[-1]
    need = sorted({x for v in refs.values() for x in v if x})
    labels: dict[str, str] = {}
    if need:
        try:
            got = _get_json("https://www.wikidata.org/w/api.php?" + urllib.parse.urlencode(
                {"action": "wbgetentities", "ids": "|".join(need[:50]), "props": "labels", "languages": "en", "format": "json"}))
            labels = {k: ((v.get("labels") or {}).get("en") or {}).get("value", "") for k, v in (got.get("entities") or {}).items()}
        except Exception:  # noqa: BLE001
            labels = {}
    lab = lambda xs: [labels[x] for x in xs if labels.get(x)]  # noqa: E731
    out: dict[str, Any] = {"qid": qid, "url": f"https://www.wikidata.org/wiki/{qid}", "label": ((ent.get("labels") or {}).get("en") or {}).get("value", title),
                           "description": ((ent.get("descriptions") or {}).get("en") or {}).get("value", ""), "founded": founded,
                           "founders": lab(refs["founders"]), "hq": ", ".join(lab(refs["hq"])), "parent": ", ".join(lab(refs["parent"])),
                           "subsidiaries": lab(refs["subs"]), "industry": lab(refs["industry"]), "country": ", ".join(lab(refs["country"])), "numbers": []}
    if emp:
        try:
            n = float(emp["mainsnak"]["datavalue"]["value"]["amount"])
            out["numbers"].append({"value": f"{n:,.0f}", "label": "employees", "year": emp_y})
        except (KeyError, TypeError, ValueError):
            pass
    if rev and unit in CURRENCY:
        try:
            n = float(rev["mainsnak"]["datavalue"]["value"]["amount"])
            out["numbers"].append({"value": _big(n, CURRENCY[unit]), "label": "revenue", "year": rev_y})
        except (KeyError, TypeError, ValueError):
            pass
    return out


def _wd_text(wd: dict) -> str:
    lines = [f"Wikidata: {wd.get('label')} - {wd.get('description')}"]
    for k, lab in (("founded", "Inception (founded)"), ("hq", "Headquarters"), ("parent", "Parent organisation"), ("country", "Country")):
        if wd.get(k):
            lines.append(f"{lab}: {wd[k]}")
    for k, lab in (("founders", "Founded by"), ("subsidiaries", "Subsidiaries"), ("industry", "Industry")):
        if wd.get(k):
            lines.append(f"{lab}: {', '.join(wd[k])}")
    lines += [f"{n['label'].capitalize()}: {n['value']}" + (f" (as of {n['year']})" if n.get("year") else "") for n in wd.get("numbers") or []]
    return "\n".join(lines)


# ---------- research ----------
SOURCE_CHARS = int(os.environ.get("COMPANY_STORY_SOURCE_CHARS", "28000"))    # how much article text the research desk reads
STORY_HEAD = re.compile(r"histor|found|origin|early|begin|start|growth|expan|acqui|merger|crisis|bankrupt|turnaround|pivot|launch|product|"
                        r"business|operation|finance|ipo|listing|competit|rival|strategy|decline|recover|technolog|innovation|timeline|era|\d{4}", re.I)
SKIP_HEAD = re.compile(r"see also|reference|notes|further reading|external links|bibliograph|citation|sources|gallery|footnote", re.I)


def wiki_article(title: str) -> tuple[str, str]:
    """The FULL plain text of an English Wikipedia article and its URL (the search only gives the opening); ('', '') if it can't be read."""
    try:
        q = _get_json("https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "prop": "extracts|info", "explaintext": 1, "exsectionformat": "wiki", "inprop": "url", "redirects": 1,
             "titles": title, "format": "json"}), timeout=20)
        page = next(iter((q.get("query", {}).get("pages") or {}).values()), {})
        if "missing" in page:
            return "", ""
        return page.get("extract") or "", page.get("fullurl") or f"https://en.wikipedia.org/wiki/{urllib.parse.quote(title.replace(' ', '_'))}"
    except Exception:  # noqa: BLE001 - the search text is still there
        return "", ""


def story_text(full: str, cap: int = SOURCE_CHARS) -> str:
    """The parts of a long article that tell the story: the opening, then the history-like sections first, in article order, up to `cap`."""
    parts = re.split(r"^(=+ .+? =+)\s*$", full, flags=re.M)
    lead, secs = parts[0].strip(), []
    parent = ""
    for i in range(1, len(parts) - 1, 2):
        head = parts[i].strip("= ").strip()
        if parts[i].startswith("== ") and not parts[i].startswith("=== "):
            parent = head
        body = parts[i + 1].strip()
        if not body or SKIP_HEAD.search(head) or SKIP_HEAD.search(parent):
            continue
        rank = 0 if re.search(r"histor|found|origin|early|timeline", head + " " + parent, re.I) else 1 if STORY_HEAD.search(head + " " + parent) else 2
        secs.append((i, rank, f"[{parent + ' / ' if parent and parent != head else ''}{head}]\n{body}"))
    keep, used = set(), len(lead)
    for i, rank, t in sorted(secs, key=lambda x: (x[1], x[0])):
        if used + len(t) > cap:
            if rank == 0 and cap - used > 1500:              # a long history section is cut, not dropped
                t = t[: cap - used]
            else:
                continue
        keep.add((i, t))
        used += len(t)
    return "\n\n".join([lead] + [t for i, t in sorted(keep)])[:cap]


def _about(subject: str, src: dict) -> bool:
    """A 'History of …' hit is kept only if it is really about the subject (not 'History of India' for 'Zomato')."""
    words = [w for w in re.findall(r"[a-z0-9]+", subject.lower()) if w not in {"the", "of", "and", "industry", "company", "group", "inc", "ltd", "limited"}]
    if not words:
        return True
    title, text = src.get("title", "").lower(), src.get("text", "").lower()
    return any(w in title for w in words) or sum(text.count(w) for w in words) >= 3


def research(s: dict, subject: str, log: Callable[[dict], None] | None = None, scenes: int = 6) -> dict:
    """`scenes` is how many scenes the video will have: a long video needs more moments, milestones and numbers to tell, so it keeps
    more of what the sources gave."""
    from ..explainer import research as R
    srcs: list[dict] = []
    for q in (subject, f"History of {subject}"):
        try:
            for x in R.find(q, 2 if q == subject else 1):
                if x["url"] not in {y["url"] for y in srcs} and (q == subject and not srcs or _about(subject, x)):
                    srcs.append(x)
        except R.ResearchError as e:
            if q == subject and not srcs:
                raise RuntimeError(f"Research found nothing for “{subject}”: {e}. Check the spelling, or try the full company name.") from e
    srcs = [x for x in srcs if not re.match(r"(list|lists|index|outline) of ", x.get("title", ""), re.I)][:3] or srcs[:1]
    # Read the whole article (the search only gives its opening), and a separate "History of …" article when Wikipedia has one.
    if srcs:
        full, url = wiki_article(srcs[0]["title"])
        if len(full) > len(srcs[0].get("text") or ""):
            srcs[0] = {**srcs[0], "text": story_text(full), "url": srcs[0].get("url") or url}
        hist, hurl = wiki_article(f"History of {srcs[0]['title']}")
        if len(hist) > 2000 and hurl not in {x["url"] for x in srcs}:
            srcs.insert(1, {"title": f"History of {srcs[0]['title']}", "url": hurl, "text": story_text(hist, SOURCE_CHARS // 2)})
            srcs[0] = {**srcs[0], "text": srcs[0]["text"][: SOURCE_CHARS // 2]}
    srcs = srcs[:4]
    wd = wikidata(srcs[0]["title"]) if srcs else {}
    out: dict[str, Any] = {"sources": [{"title": x["title"], "url": x["url"]} for x in srcs], "status": "ok"}
    if wd:
        out["sources"].append({"title": f"Wikidata: {wd['label']}", "url": wd["url"]})
        out["about"] = wd.get("description", "")
    wd_txt = _wd_text(wd) if wd else ""
    allowed = set().union(*[_num_tokens(x["text"]) for x in srcs]) if srcs else set()
    allowed |= _num_tokens(wd_txt)
    data = None
    if writers.uses_ai(s):
        body = "\n\n".join(f"[Source {i + 1}] {x['title']}\n{x['text']}" for i, x in enumerate(srcs))
        if wd_txt:
            body += f"\n\n[Source {len(srcs) + 1}] {wd_txt}"
        data = writers.ask(s, "story", writers.system("avos-company-story", RESEARCH), f"Subject: {subject}\n\n{body}\n\nWrite the JSON.", log, max_tokens=4000, temperature=0.1)
    if not isinstance(data, dict):
        found = re.search(r"(?:founded|established|formed|incorporated)\D{0,30}(\d{4})", " ".join(x["text"] for x in srcs), re.I)
        data = {"name": subject.strip().title() if subject.islower() else subject.strip(), "kind": "company", "founded": found.group(1) if found else "",
                "milestones": [], "numbers": [], "origin": "", "how_it_works": [], "rivals": [], "turning_points": []}
    src = lambda i: out["sources"][i - 1] if isinstance(i, int) and 0 < i <= len(out["sources"]) else None  # noqa: E731
    now = datetime.now().year

    def s_(v: Any, n: int = 300) -> str:
        return " ".join(str(v or "").split())[:n]

    ms = []
    for m in data.get("milestones") or []:
        y = s_(m.get("year")) if isinstance(m, dict) else ""
        if re.fullmatch(r"\d{4}", y) and int(y) <= now and y in allowed and checked(s_(m.get("event")), allowed):
            ms.append({"year": y, "event": s_(m.get("event")), "source": src(_int(m.get("source")))})
    moments = []
    for m in data.get("story_moments") or []:
        if not isinstance(m, dict) or not s_(m.get("what")):
            continue
        y = s_(m.get("year"), 4)
        y = y if re.fullmatch(r"\d{4}", y) and int(y) <= now and y in allowed else ""
        if checked(s_(m.get("what"), 600) + " " + s_(m.get("title"), 80), allowed):
            moments.append({"year": y, "title": s_(m.get("title"), 80), "what": s_(m.get("what"), 600), "kind": s_(m.get("kind"), 20),
                            "source": src(_int(m.get("source")))})
    nums = []
    for m in data.get("numbers") or []:
        if isinstance(m, dict) and len(_num_tokens(s_(m.get("value")))) == 1 and checked(s_(m.get("value")) + " " + s_(m.get("year")), allowed):
            nums.append({"value": s_(m.get("value"), 40), "label": s_(m.get("label"), 60), "year": s_(m.get("year"), 10), "source": src(_int(m.get("source")))})
    unknowns = [s_(x) for x in data.get("unknowns") or []][:3]
    ai_founded = s_(data.get("founded"), 4) if re.fullmatch(r"\d{4}", s_(data.get("founded"), 4)) and s_(data.get("founded"), 4) in allowed else ""
    founded = ai_founded
    if wd.get("founded") and wd["founded"].isdigit() and int(wd["founded"]) <= now:
        if ai_founded and ai_founded != wd["founded"]:
            unknowns.insert(0, f"The article text points to {ai_founded}, Wikidata gives {wd['founded']} as the founding year; the video uses {wd['founded']}.")
        founded = wd["founded"]
    for n in wd.get("numbers") or []:                       # Wikidata's latest employees / revenue, with their year
        if not any(n["label"] in x["label"].lower() and x.get("year") == n["year"] for x in nums):
            nums.insert(0, {**n, "source": out["sources"][-1]})
    founder = s_(data.get("founder"), 120) or ", ".join(wd.get("founders") or [])
    hw = [s_(x) for x in data.get("how_it_works") or []][:4]
    if wd.get("subsidiaries") and len(hw) < 4:
        hw.append(f"Its businesses include {', '.join(wd['subsidiaries'][:5])}.")
    out.update(name=s_(data.get("name"), 60) or wd.get("label") or subject, kind="industry" if data.get("kind") == "industry" else "company",
               founded=founded, founder=founder, origin=s_(data.get("origin")), home=s_(data.get("home"), 120) or wd.get("hq", ""),
               parent=wd.get("parent", ""), story_moments=moments[:max(8, scenes)], milestones=sorted(ms, key=lambda m: m["year"])[:max(14, scenes * 2)],
               numbers=nums[:max(12, scenes)], how_it_works=hw,
               rivals=[s_(x, 60) for x in data.get("rivals") or []][:4], turning_points=[s_(x) for x in data.get("turning_points") or []][:4], unknowns=unknowns[:4])
    out["allowed"] = sorted(fact_numbers(out))
    return out


def facts_text(r: dict) -> str:
    lines = [f"Name: {r['name']} ({r['kind']})" + (f" - {r['about']}" if r.get("about") else "")]
    for k, lab in (("founded", "Founded"), ("founder", "Founder"), ("origin", "Origin"), ("home", "Home"), ("parent", "Parent company")):
        if r.get(k):
            lines.append(f"{lab}: {r[k]}")
    lines += [f"Story moment{' (' + m['year'] + ')' if m.get('year') else ''} [{m.get('kind') or 'moment'}] {m['title']}: {m['what']}" for m in r.get("story_moments") or []]
    lines += [f"{m['year']}: {m['event']}" for m in r.get("milestones") or []]
    lines += [f"Number: {n['value']} {n['label']}" + (f" (as of {n['year']})" if n.get("year") else "") for n in r.get("numbers") or []]
    for k, lab in (("how_it_works", "How it works"), ("rivals", "Rivals"), ("turning_points", "Turning points"), ("unknowns", "Unclear")):
        if r.get(k):
            lines.append(f"{lab}: " + " | ".join(r[k]))
    if r.get("founded"):
        lines.append(f"Age: {int(datetime.now().year) - int(r['founded'])} years (from {r['founded']} to {datetime.now().year})")
    return "\n".join(lines)


def fact_numbers(r: dict) -> set[str]:
    """The numbers a script may use: those in the RESEARCHED facts (plus this year and the age), not every number in the articles.
    (An article on Zomato mentions COVID-19, so '19' is in its text; that must not let '$19 billion' through.)"""
    return _num_tokens(facts_text(r)) | {str(datetime.now().year)}


# ---------- script ----------
def _poses(v: Any, setting: str) -> list[str]:
    got = [" ".join(str(x).split())[:120] for x in v if str(x).strip()] if isinstance(v, list) else []
    fb = DEFAULT_POSES.get(setting) or DEFAULT_POSES[""]
    return (got + fb)[:POSES]


def norm_script(d: Any, r: dict, n: int, start: int = 0) -> dict:
    """`start` is how many scenes were written in earlier acts, so a long script's later acts keep numbering on and do not each open
    with the company title card."""
    allowed = fact_numbers(r)
    if not isinstance(d, dict) or not isinstance(d.get("scenes"), list) or not d["scenes"]:
        raise writers.WriterError("The AI writer didn't return a usable script. Try again, or pick another AI crew.")
    years = f"{r['founded']} – {datetime.now().year}" if r.get("founded") else ""
    scenes = []
    for i, sc in enumerate(d["scenes"][:n]):
        idx = start + i                                   # the scene's place in the whole video
        sc = sc if isinstance(sc, dict) else {}
        narr = " ".join(str(sc.get("narration") or "").split())[:400]
        keep, dropped = [], 0
        for c in sc.get("cards") or []:
            if not isinstance(c, dict) or c.get("type") not in ("title", "stat", "caption", "year", "vs"):
                continue
            c = {k: " ".join(str(v).split())[:60] for k, v in c.items() if isinstance(v, (str, int, float))}
            if c["type"] == "title":
                if idx:
                    continue
                c["years"] = years
                c["text"] = (c.get("text") or r["name"])[:40]
            if c["type"] == "stat" and len(_num_tokens(c.get("value", ""))) != 1:   # one figure per card ("4 and 5 trillion" isn't one)
                dropped += 1
                continue
            if c["type"] == "vs" and not r.get("rivals"):
                dropped += 1
                continue
            if not checked(" ".join(str(v) for k, v in c.items() if k not in ("type", "years")), allowed):
                dropped += 1
                continue
            keep.append(c)
        if idx == 0 and not any(c["type"] == "title" for c in keep):
            keep.insert(0, {"type": "title", "kicker": "THE STORY OF", "text": r["name"], "years": years})
        vs = any(c["type"] == "vs" for c in keep)
        stats = [] if vs else [c for c in keep if c["type"] == "stat"][:3]
        keep = [c for c in keep if c["type"] not in ("stat",) and not (c["type"] == "year" and idx == 0)] + stats
        caps = [c for c in keep if c["type"] == "caption"]
        keep = [c for c in keep if c["type"] != "caption"] + caps[:1]
        setting = str(sc.get("setting") or "city")[:20]
        scenes.append({"n": idx + 1, "purpose": " ".join(str(sc.get("purpose") or BEATS[idx % len(BEATS)]).split())[:160], "narration": narr,
                       "visual": " ".join(str(sc.get("visual") or "").split())[:400], "place": " ".join(str(sc.get("place") or "").split())[:240], "setting": setting, "poses": _poses(sc.get("poses"), "rivalry" if vs else setting),
                       "move": str(sc.get("move") or "slow push in")[:20], "rival": vs, "cards": keep, "dropped": dropped,
                       "warning": "" if checked(narr, allowed) else "The narration has a number the research doesn't show."})
    if len(scenes) < n:
        raise writers.WriterError(f"The AI writer wrote {len(scenes)} of {n} scenes. Try again.")
    title = " ".join(str(d.get("title") or "").split())[:100]
    if not title or not checked(title, allowed):
        title = f"{r['name']}: The Story So Far" if not r.get("founded") else f"{r['name']}: The Story from {r['founded']} to {datetime.now().year}"
    return {"title": title, "scenes": scenes}


def _sentences(t: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?])\s+", t.strip()) if x]


def fix_narration(s: dict, r: dict, sc: dict, log: Callable[[dict], None] | None = None) -> dict:
    """Narration with an unchecked number: one rewrite by the writer, then the sentence with the number is cut. Never left silently."""
    allowed = fact_numbers(r)
    bad = [x for x in sc["scenes"] if not checked(x["narration"], allowed)]
    if not bad:
        return sc
    lines: dict = {}
    try:
        got = writers.ask(s, "story", writers.system("avos-company-story-check", FIX),
                          "Research:\n" + facts_text(r) + "\n\nLines to fix:\n" + json.dumps({str(x["n"]): x["narration"] for x in bad}, ensure_ascii=False),
                          log, max_tokens=1200, temperature=0.2)
        lines = (got or {}).get("lines") or {} if isinstance(got, dict) else {}
    except Exception:  # noqa: BLE001 - the cut below still makes it safe
        lines = {}
    for x in bad:
        new = " ".join(str(lines.get(str(x["n"])) or "").split())[:400]
        if new and checked(new, allowed) and len(new.split()) >= 10:
            x["narration"], x["warning"] = new, "Rewritten: the first line used a number the research doesn't show."
            continue
        kept = [t for t in _sentences(x["narration"]) if checked(t, allowed)]
        if len(" ".join(kept).split()) >= 8:
            x["narration"], x["warning"] = " ".join(kept), "A sentence with a number the research doesn't show was cut."
        else:
            x["warning"] = "The narration has a number the research doesn't show: edit it before you share the video."
    return sc


LONG_ARC = ("1. the HOOK: the most astonishing true fact, then who they are; the company card. 2. the STRUGGLE and the SPARK: what they did before and "
            "the gap they noticed. 3. the BET: how they started and with how little. 4. the TROUBLE and the TURN: the near-failure, then what fixed it. "
            "{mid}. walk the history FORWARD IN TIME, one scene per milestone or number in the research, in chronological order: each of these scenes "
            "names its year, the one thing that changed that year, and the figure for it, so the viewer watches the company climb. Never repeat a "
            "milestone, never jump backwards, and spend no more than one scene on any single year. Somewhere in the middle give one scene to the main "
            "rival (the VS scene), one to how the company actually works inside (how it hires, builds and sells), and one to a criticism or controversy "
            "if the research has one. {today}. where it stands today, with the latest figures. {last}. the TAKEAWAY: the real lesson in two or three "
            "crisp principles from what actually happened.")


def beats_for(n: int) -> str:
    """The job of each scene. Short videos get one named beat each; a long video gets the four opening beats, a chronological middle that
    walks the research's own milestones, and the two closing beats - naming forty beats one by one would only pad the prompt."""
    if n == 3:
        return ("1. the HOOK: the astonishing fact and who they are, with the company card; 2. the STRUGGLE, the BET and the TURN: what they did before, "
                "how they started with how little, what changed everything; 3. the GROWTH in figures and years, then the TAKEAWAY: the real lesson")
    if n > 10:
        return LONG_ARC.format(mid=f"5-{n - 2}", today=n - 1, last=n)
    if n >= 6:
        order = BEATS[:5] + [BEATS[5]] if n == 6 else BEATS[:5] + [BEATS[6]] + [BEATS[5]] + BEATS[7:]
        order = order[:n]
    else:
        order = [BEATS[0], BEATS[1], BEATS[2], BEATS[4], BEATS[5]][:n]
    return "; ".join(f"{i + 1}. {b}" for i, b in enumerate(order))


ACT_SCENES = 8                              # scenes per writing pass: one answer cannot hold forty of them


def script(s: dict, r: dict, n: int, log: Callable[[dict], None] | None = None, secs: int = SCENE_SECONDS) -> dict:
    if not writers.uses_ai(s):
        raise writers.WriterError("Company Story needs an AI writer for the script (pick Groq or another AI crew in Models); the research is ready.")
    system = writers.system("avos-company-story-writer", SCRIPT)
    lo, hi = words_for(secs)
    head = (f"Write a {n}-scene story about {r['name']}. Each scene is on screen for about {secs} seconds, so each narration is {lo}-{hi} spoken words.\n"
            f"Scene jobs in order: {beats_for(n)}.\n\nResearch (the only facts you may use):\n{facts_text(r)}\n\n"
            f"Numbers you may use: {', '.join(sorted(fact_numbers(r), key=lambda x: (len(x), x)))}\n")
    if n <= ACT_SCENES + 2:
        d = writers.ask(s, "story", system, head + f"Write the JSON script, with exactly {n} scenes.", log, max_tokens=4000, temperature=0.5)
        return fix_narration(s, r, norm_script(d, r, n), log)
    title, scenes = "", []                  # a long video is written act by act, each act told what the earlier ones already said
    for start in range(0, n, ACT_SCENES):
        take = min(ACT_SCENES, n - start)
        if log:
            log({"text": f"Writing scenes {start + 1}-{start + take} of {n}", "kind": "info"})
        sofar = "\n".join(f"{x['n']}. {x['purpose']} - {x['narration']}" for x in scenes) or "(nothing yet: this is the opening act)"
        d = writers.ask(s, "story", system,
                        head + f"\nScenes already written - carry the story straight on from the last one and never repeat a fact, year or figure "
                        f"they already used:\n{sofar}\n\nNow write ONLY scenes {start + 1} to {start + take}, as a JSON object whose \"scenes\" list "
                        f"holds exactly {take} scenes in that order.", log, max_tokens=4000, temperature=0.5)
        part = norm_script(d, r, take, start=start)
        title = title or part["title"]
        scenes += part["scenes"]
    return fix_narration(s, r, {"title": title, "scenes": scenes}, log)


# ---------- backdrop pictures ----------
SETTINGS = {"origin": "a small humble starting place (a garage, workshop, shop, diner or small office)",
            "factory": "rows of factories and warehouses with a road and chimneys",
            "city": "a company city skyline of office towers with the green hills and river beyond",
            "rivalry": "two clusters of company towers facing each other across a river, one for each company",
            "boardroom": "a cartoon boardroom with a big window over the company city",
            "world": "a stylised globe and map with little company buildings spread across continents"}


def scene_prompt(r: dict, sc: dict, vs: bool = False, aspect: str = "16:9", side: str = "") -> str:
    """The BACKDROP only: no people (the chosen character is placed on it afterwards, in code). The look leads the prompt, because the free
    picture models weigh the opening words the most and cut a long prompt off at the end."""
    place = sc.get("place") or SETTINGS.get(sc.get("setting"), SETTINGS["city"])
    side = side or side_of(int(sc.get("n") or 1), aspect)
    return (f"{LOOK}. SCENE: {place}. In the scene: {sc.get('visual') or sc.get('purpose')}. {BRIGHT} "
            f"{frame_for(aspect, vs, side)} {PAPER_TAIL}")


def motion_prompt(sc: dict, sheet: bool = False, secs: int = SCENE_SECONDS) -> str:
    """The AI-video prompt for one scene: the handcrafted paper rules (locked camera, real cardstock weight, stop-motion jitter),
    then the one thing the character does. Scene 1 builds itself out of its paper layers first."""
    ref = ("The second reference image is the character's full model sheet (all angles, expressions and poses): follow it exactly for his face, hair, "
           "glasses or mustache, suit, tie, shoes and proportions in every frame, including when he turns or changes expression. " if sheet else "")
    poses = ", then ".join(sc.get("poses") or [])
    where = {"left": "in the left third of the frame", "right": "in the right third of the frame"}.get(sc.get("side") or "", "where he is standing now")
    return (ref + f"A {secs}-second paper-craft cartoon shot made from this exact picture (keep the cut-paper look, the white paper-sticker outline round "
            f"the character and the paper texture). Keep the character standing {where} with exactly the same face, hair, "
            "suit and proportions for the whole shot; he never leaves the frame and his face stays visible. He acts with clear, expressive cartoon "
            f"animation: {poses}; his mouth moves as if he is telling the story. {sc.get('visual') or sc.get('purpose')}. Small cars move on the road "
            f"and the river flows in the backdrop; the camera does a {sc.get('move') or 'slow push in'}, very slowly and with no other camera move. "
            f"{PAPER_MOTION} {_assembly(sc)}No text, no new characters, no style change, no cuts.")


PAPER_MOTION = ("Everything keeps the weight of real cardstock: tiny stop-motion jitter, natural paper friction, a slight settle after every movement, "
                "soft paper collisions and the layered paper depth and shadows visible throughout, never perfectly smooth CGI motion. Cut-paper parts "
                "slide, tilt and swap rather than bending, melting or morphing, and no element changes its size, colour or place in the frame.")


def _assembly(sc: dict) -> str:
    """Only the first scene builds itself: the later scenes would waste their seconds assembling instead of telling the beat."""
    if int(sc.get("n") or 0) != 1:
        return ""
    return ("For the first second the paper backdrop finishes assembling itself back to front, each cut sheet dropping into place with a tiny paper "
            "bounce and its own shadow, then everything stays exactly where it landed. ")


# ---------- stages ----------
def do_research(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "research", status="working")
    r = research(base.sdict(p), p["subject"], base.logger(pid), scenes_for(float(p.get("seconds") or 60)))
    base.put(pid, research=r, title=r["name"])
    wd = any(x["url"].startswith("https://www.wikidata.org/") for x in r["sources"])
    base.step(pid, "research", status="done", note=f"{len(r['sources'])} sources{' incl. Wikidata' if wd else ''}, founded {r['founded'] or 'unknown'}, "
              f"{len(r.get('story_moments') or [])} story moments, {len(r['milestones'])} dated milestones, {len(r['numbers'])} checked numbers")
    store.say(pid, f"Research ready: {len(r['sources'])} sources.")


def do_script(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "script", status="working")
    total = float(p.get("seconds") or 60)
    sc = script(base.sdict(p), p["research"], scenes_for(total), base.logger(pid), secs=scene_seconds(total))
    base.put(pid, script=sc, title=sc["title"])
    dropped = sum(x["dropped"] for x in sc["scenes"])
    fixed = sum(1 for x in sc["scenes"] if x["warning"])
    note = "; ".join(t for t in (f"{dropped} card(s) dropped: their numbers weren't in the research" if dropped else "",
                                 f"{fixed} narration line(s) corrected or flagged" if fixed else "") if t)
    base.step(pid, "script", status="done", note=note)


def _w_h(p: dict) -> tuple[int, int]:
    return base.SIZES.get(p.get("aspect") or "16:9", base.SIZES["16:9"])


def _seedance(s: dict) -> bool:
    try:
        from ..stickman import video
        return bool(video.ready(s))
    except Exception:  # noqa: BLE001
        return False


def _cid(p: dict) -> str:
    cid = (p.get("characters") or {}).get("founder")
    return cid if cid in CHARACTERS else INFO["default_cast"]["founder"]


def do_cast(pid: str) -> None:
    """Nothing to draw: the character is one of the ready-made ones. Checks its poses are there."""
    p = store.load(pid)
    base.step(pid, "cast", status="working")
    cid = _cid(p)
    names = compose.sprites(cid)
    if len(names) < 3:
        raise RuntimeError(f"The character “{CHARACTERS[cid]['name']}” is missing its pose pictures: reinstall the skill zip (characters/{cid}/).")
    base.put(pid, cast={"founder": cid})
    base.step(pid, "cast", status="done", note=f"{CHARACTERS[cid]['name']} · {len(names)} poses")


def _backdrop(pid: str, p: dict, sc: dict, s: dict, w: int, h: int, side: str) -> tuple[bytes, str]:
    """The scene's backdrop. A picture model draws it; if every model refuses (no key, no credit, a network blip), the backdrop is drawn
    here in code instead, so one unlucky scene never stops the whole video."""
    seed = media.seed_of(pid, sc["n"], sc.get("version", 1))
    prompt = scene_prompt(p["research"], sc, bool(sc["rival"]), p.get("aspect") or "16:9", side)
    last = ""
    for attempt in range(2):
        try:
            ask = prompt if not attempt else prompt + " " + BRIGHTER
            bg, info = media.picture(ask, [], w, h, seed + attempt, f"{pid}-S{sc['n']}", s=s, negative=NEGATIVE)
            dull = compose.too_dull(bg)
            if dull and attempt == 0:
                store.say(pid, f"Scene {sc['n']}: the backdrop {dull}, drawing it again brighter.", "warn")
                last = dull
                continue
            return bg, str(info.get("model") or "")
        except Exception as e:  # noqa: BLE001 - the drawn fallback below keeps the run going
            last = str(e)[:160]
    store.say(pid, f"Scene {sc['n']}: no usable backdrop from the picture model ({last}). Drew a paper set in code instead.", "warn")
    return compose.paper_scene(w, h, seed, side, bool(sc["rival"])), "drawn in code"


def do_scenes(pid: str) -> None:
    """Per scene: draw the backdrop (no people), then stand the character on it in three poses (the first is the scene picture)."""
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    aspect = p.get("aspect") or "16:9"
    base.step(pid, "scenes", status="working")
    cid = _cid(p)
    for sc in p["script"]["scenes"]:
        base.check(pid)
        if sc.get("picture") and store.file_path(pid, sc["picture"]) and len(sc.get("pose_pics") or []) >= POSES:
            continue
        side = side_of(sc["n"], aspect)
        bg = base.read(pid, sc.get("backdrop")) if sc.get("backdrop") and store.file_path(pid, sc["backdrop"]) else None
        if bg is None:
            bg, model = _backdrop(pid, p, sc, s, w, h, side)
            bgname = base.write(pid, f"S{sc['n']:02d}_bg.png", bg)
            store.update(pid, lambda q, n=sc["n"], bgname=bgname, m=model: q["script"]["scenes"][n - 1].update(backdrop=bgname, picture_model=m))
        names = compose.choose(cid, sc.get("poses") or [], POSES)
        pics = [base.write(pid, f"S{sc['n']:02d}_p{k}.png", compose.place(bg, cid, nm, w, h, side=side)) for k, nm in enumerate(names, start=1)]
        first = base.write(pid, f"S{sc['n']:02d}.png", base.read(pid, pics[0]) or b"")
        store.update(pid, lambda q, n=sc["n"], first=first, pics=pics, names=names, side=side:
                     q["script"]["scenes"][n - 1].update(picture=first, pose_pics=pics, pose_names=names, side=side, video=None))
        if sc["n"] == 1:
            base.put(pid, thumb=first)
    base.step(pid, "scenes", status="done", note=f"{CHARACTERS[cid]['name']} placed on every scene")


PUPPET_NOTE = ("Paper-puppet motion (free): the character sways and flips between poses over a slowly pushing paper backdrop; cards and numbers animate.")


def do_animate(pid: str) -> None:
    from .. import config
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    secs = scene_seconds(float(p.get("seconds") or 60))
    base.step(pid, "animate", status="working")
    d = store.pdir(pid)
    engines: list[str] = []
    want_video = (p.get("motion") or "video") == "video" and _seedance(s)
    if (p.get("motion") or "video") == "video" and not want_video:
        store.say(pid, NO_VIDEO_FELL_BACK, "warn")
    sheet = compose.sheet(_cid(p)) if want_video else None
    for sc in p["script"]["scenes"]:
        base.check(pid)
        if sc.get("video") and store.file_path(pid, sc["video"]):
            continue
        img = base.read(pid, sc.get("picture"))
        if not img:
            raise RuntimeError(f"scene {sc['n']} has no picture yet")
        src: Any = None
        if want_video:
            from ..stickman import video
            try:
                raw = d / f"S{sc['n']:02d}_base.mp4"
                raw.write_bytes(video.clip(motion_prompt(sc, bool(sheet), secs), [img] + ([sheet] if sheet else []), None, secs,
                                           p.get("aspect") or "16:9", audio=False))
                src = raw
                engines.append("Seedance 2.0")
            except Exception as e:  # noqa: BLE001 - a finished video beats a stopped run: the rest of the scenes use the free motion
                want_video, sheet = False, None
                store.say(pid, f"Scene {sc['n']}: the AI video failed ({str(e)[:160]}). Carrying on with the free paper-puppet motion for the rest of "
                               "this run. Top up fal.ai and press Redo on the Motion step to use Seedance instead.", "warn")
        if src is None:
            bgraw = base.read(pid, sc.get("backdrop")) if sc.get("backdrop") else None
            if bgraw and sc.get("pose_names"):
                src = compose.scene_frames(bgraw, _cid(p), sc["pose_names"], w, h, secs + 3, active=secs + 0.5, side=sc.get("side") or "",
                                           move=sc.get("move") or "slow push in")
            else:
                src = [b for b in (base.read(pid, x) for x in (sc.get("pose_pics") or [sc["picture"]])) if b] or [img]
            engines.append("paper puppet")
        out = cards.burn(src, sc["cards"], d / f"S{sc['n']:02d}.mp4", w, h, secs + 3, config.ffmpeg(), active=secs + 0.5)
        store.update(pid, lambda q, n=sc["n"], name=out.name: q["script"]["scenes"][n - 1].update(video=name))
    kinds = sorted(set(engines))
    base.step(pid, "animate", status="done", model=" + ".join(kinds) or None,
              note="" if kinds == ["Seedance 2.0"] else PUPPET_NOTE)


def do_voice(pid: str) -> None:
    from ..explainer import pipeline as xp
    p = store.load(pid)
    s = base.sdict(p)
    base.step(pid, "voice", status="working")
    note = ""
    for sc in p["script"]["scenes"]:
        base.check(pid)
        if sc.get("voice") and store.file_path(pid, sc["voice"]):
            continue
        wav, info = xp._voice(s, sc["narration"], p)
        if is_silent(wav):
            why = (info.get("note") or "").strip()
            raise RuntimeError("The narrator voice failed, so the video would be silent" + (f": {why[:200]}" if why else "") +
                               (". This is Microsoft's Edge voice refusing the request: update it with  docker compose exec animation-studio pip install -U edge-tts"
                                "  then restart animation-studio and press Continue, or pick another voice model in Models." if "403" in why or "bing" in why.lower() else
                                ". Pick another voice model in Models and press Continue."))
        name = base.write(pid, f"S{sc['n']:02d}_voice.wav", wav)
        note = info.get("note") or note
        secs = media.wav_seconds(wav)
        store.update(pid, lambda q, n=sc["n"], name=name, secs=secs: q["script"]["scenes"][n - 1].update(voice=name, voice_seconds=round(secs, 2)))
    base.step(pid, "voice", status="done", note=note)


def is_silent(wav: bytes) -> bool:
    """True when a narration file has no audible speech (empty, or a failed voice that came back as silence)."""
    try:
        w = wave.open(io.BytesIO(wav))
        n, width = w.getnframes(), w.getsampwidth()
        data = w.readframes(n)
    except Exception:  # noqa: BLE001 - not a WAV we can read: don't block on it
        return not wav
    if n == 0 or width != 2:
        return n == 0
    import array
    a = array.array("h", data[: len(data) // 2 * 2])
    return not a or max(abs(x) for x in a[:: max(1, len(a) // 20000)]) < 300


def do_finish(pid: str) -> None:
    from ..series import assemble
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    base.step(pid, "finish", status="working")
    d = store.pdir(pid)
    work = d / "work"
    work.mkdir(exist_ok=True)
    parts, total = [], 0.0
    target = float(p.get("seconds") or 60)
    each = scene_seconds(target)
    scenes = p["script"]["scenes"]
    for sc in scenes:
        clip = d / (sc.get("video") or "")
        if not clip.is_file():
            raise RuntimeError(f"scene {sc['n']} has no video yet")
        sec = float(max(target / len(scenes), each, min(each + 3, (sc.get("voice_seconds") or 0) + 0.8)))
        fit = assemble.fit_shot(clip, work / f"S{sc['n']:02d}_fit.mp4", sec, w, h)
        line = d / (sc.get("voice") or "")
        aud = assemble.shot_audio(work / f"S{sc['n']:02d}_a.wav", sec, line if line.is_file() else None, None, line_at=0.3)
        parts.append({"video": fit, "audio": aud, "seconds": sec})
        total += sec
    mpath = None
    try:
        music, _ = media.music(s, "light curious business-documentary underscore, pizzicato strings, soft piano and brushed percussion, no vocals", total, f"{pid}:music")
        if music:
            mpath = work / "music.wav"
            mpath.write_bytes(media.to_wav(music))
    except Exception as e:  # noqa: BLE001 - music is optional
        store.say(pid, f"No music this time ({str(e)[:120]})", "warn")
    joined = assemble.part(parts, work, work / "joined.mp4", w, h, mpath, [], music_volume=0.16)
    import shutil
    shutil.copyfile(joined, d / "final.mp4")
    base.put(pid, video="final.mp4", finalSeconds=round(total, 1))
    base.step(pid, "finish", status="done", note="" if mpath else "no music model ready: narration only")


RUN = {"research": do_research, "script": do_script, "cast": do_cast, "scenes": do_scenes, "animate": do_animate, "voice": do_voice, "finish": do_finish}


def last_stage(p: dict) -> str:
    return "script" if p.get("media") == "prompts" else "finish"


def reset(p: dict, step: str, n: int | None = None) -> None:
    """Clear what `step` (and every later step) made, so the run makes it again. With n: only that scene."""
    order = STAGES[STAGES.index(step):]
    for st in order:
        p.setdefault("steps", {}).pop(st, None)
    if "research" in order:
        p.pop("research", None)
    if "script" in order:
        p.pop("script", None)
        p.pop("plan_ok", None)                                  # a new script is reviewed again (when the run pauses for review)
    if "cast" in order:
        p.pop("cast", None)
    for sc in (p.get("script") or {}).get("scenes") or []:
        if n and sc["n"] != n:
            continue
        sc["version"] = int(sc.get("version", 1)) + 1
        if "scenes" in order:
            sc["picture"] = None
            sc["pose_pics"] = []
            if n or "script" not in order:                     # a new picture for scene n (or the whole step) draws a new backdrop
                sc["backdrop"] = None
        if "animate" in order or "scenes" in order:
            sc["video"] = None
        if "voice" in order:
            sc["voice"] = None
    p.pop("video", None)


# ---------- the plan the person reviews after the script ----------
def plan_of(p: dict) -> dict:
    """What the run will do, worked out from the script and the choices made (nothing is invented: every line comes from the script,
    the character, the motion and the voice chosen). The review step shows it and lets the person change the character, the motion and the voice."""
    scenes = (p.get("script") or {}).get("scenes") or []
    cid = _cid(p)
    motion = p.get("motion") or "video"
    words = sum(len((sc.get("narration") or "").split()) for sc in scenes)
    each = scene_seconds(float(p.get("seconds") or 60))
    secs = each * len(scenes)
    board = []
    for sc in scenes:
        names = (sc.get("pose_names") or compose.choose(cid, sc.get("poses") or [], POSES)) if compose.sprites(cid) else []
        board.append({"n": sc["n"], "purpose": sc.get("purpose") or "", "place": sc.get("place") or SETTINGS.get(sc.get("setting"), ""), "visual": sc.get("visual") or "",
                      "poses": sc.get("poses") or [], "pose_names": names, "move": sc.get("move") or "", "rival": bool(sc.get("rival")), "cards": sc.get("cards") or [],
                      "narration": sc.get("narration") or "", "picture": sc.get("picture"), "video": sc.get("video")})
    return {
        "characters": [{"id": c["id"], "name": c["name"], "about": c["about"], "chosen": c["id"] == cid, "poses": len(compose.sprites(c["id"])),
                        "role": "On screen in every scene, standing in for the founder (a cartoon, never a real person's face)" if c["id"] == cid else ""}
                       for c in INFO.get("characters") or []],
        "storyboard": board,
        "motion": {"engine": motion, "options": INFO.get("motions") or [], "clips": len(scenes), "seconds_each": each,
                   "note": (f"Seedance makes one {each}-second clip per scene ({len(scenes)} in all) and uses your fal.ai credit; if the credit runs out "
                            "the run carries on with the free paper-puppet motion." if motion == "video"
                            else "Free: the paper-cut character sways and flips between three poses over a slowly pushing backdrop; cards and numbers animate.")},
        "audio": {"voice": p.get("voice") or "male", "words": words, "seconds": secs, "music": "A light underscore under the narration (never louder than the voice)",
                  "narration_note": f"{words} words over about {secs} seconds"},
    }


def change_plan(p: dict, b: dict) -> None:
    """Apply the person's changes from the review step (character, motion, voice) and clear only what they make stale."""
    chars = {c["id"] for c in INFO.get("characters") or []}
    new = b.get("character")
    if new in chars and new != (p.get("characters") or {}).get("founder"):
        p["characters"] = {"founder": new}
        p.pop("cast", None)
        for st in ("cast", "scenes", "animate", "voice", "finish"):
            p.get("steps", {}).pop(st, None)
        for sc in (p.get("script") or {}).get("scenes") or []:
            sc["picture"], sc["pose_pics"], sc["pose_names"], sc["video"] = None, [], [], None            # the backdrops are kept; the character is placed again
        p.pop("video", None)
    if b.get("voice") in ("male", "female") and b["voice"] != p.get("voice"):
        p["voice"] = b["voice"]
        for st in ("voice", "finish"):
            p.get("steps", {}).pop(st, None)
        for sc in (p.get("script") or {}).get("scenes") or []:
            sc["voice"] = None
        p.pop("video", None)
