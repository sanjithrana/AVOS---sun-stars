"""Company Story skill: name a company or an industry, get a narrated cartoon business story in the "founder caricatures and company
empires" look (big-head cartoon founders, a toy-town of company buildings, paper cards with exact numbers).

  research   Wikipedia articles on the subject and its history (each kept with its link); the AI writer pulls out the founding, the
             founder, milestones with years, key numbers, how it makes money, rivals and turning points, using ONLY the source text
  script     one 10-second scene per beat (hook · origin · breakthrough · scale · rivalry or crisis · how it works today), narration
             from the research only; every number on a card or in the narration is checked against the sources (unchecked cards dropped)
  cast       original cartoon founder (and rival) characters, never a likeness of a real person
  scenes     one picture per scene with no text in it (the cards are added by code), drawn from the character sheets
  animate    Seedance 2.0 motion when a fal.ai key is set, else a camera move; then the cards are composited frame by frame
  voice      one narrator; finish joins the scenes with the voice and a light underscore"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Callable

from ..series import media, writers
from . import base, cards, store

ID = "company-story"
INFO = {
    "id": ID, "name": "Company Story", "group": "Business stories", "kind": "story",
    "made_for": "Give a company or an industry: it researches how it started, grew, competes and works, then makes a narrated cartoon story",
    "about": "Research first (Wikipedia, with every source kept), then a script that uses only those facts, original cartoon founders in a toy-town of "
             "company buildings, and paper cards drawn by code so every number is exact: the company card with its years, counting numbers, a caption "
             "strip and a VS badge for the rival. One narrator, a light underscore, one finished video.",
    "input": "A company or an industry, e.g. Toyota, Nvidia, Zomato, the airline industry",
    "outputs": ["Research with sources", "Script and scene cards", "Narrated video"],
    "aspect": "16:9", "seconds": [30, 60, 90], "default_seconds": 60, "native_audio": False,
    "examples": ["Toyota", "Nvidia", "Zomato", "Tata Group", "Netflix", "The airline industry"],
    "credit": "Look modelled on the 'Founder Story' style: founder caricatures and company empires.",
    "make": [["media", "Research, script and video"], ["prompts", "Research and script only"]],
}
STAGES = ("research", "script", "cast", "scenes", "animate", "voice", "finish")
LABELS = {"research": "Research with sources", "script": "Script and cards", "cast": "Founder characters", "scenes": "Scene pictures",
          "animate": "Motion and cards", "voice": "Narration", "finish": "Final video"}
SCENE_SECONDS = 10

LOOK = ("hand-drawn 2D cartoon illustration in a satirical business-documentary style, big-head caricature characters (head about half the body, large "
        "rounded nose, expressive eyes, thick eyebrows, small body in a suit), an isometric toy-town of company buildings, factories and skyscrapers on rolling "
        "green land with winding roads and a blue river, distant blue mountains, a warm orange or soft blue sky with a pale sun, flat colours with soft "
        "shading and a light paper texture, clean dark outlines")
NO_TEXT = ("No text, no letters, no numbers, no signs, no logos, no labels, no watermarks anywhere in the picture (text is added later). Leave the top-right "
           "corner and a band along the bottom calm and uncluttered.")
BEATS = ["hook: the empire today (the company card and its biggest numbers)", "origin: where and how it began, and who started it",
         "breakthrough: the first product or decision that worked", "scale: how it grew, factories, cities, countries",
         "rivalry or crisis: the competitor or the moment it nearly failed", "today: how it works and makes money now, and the lesson",
         "turning point: the decision that changed its direction", "the people: how it hires, builds and sells", "what comes next, from what is known"]

RESEARCH = """You are the research desk of a business-history video channel. You get source texts about a company or an industry. Answer with ONE JSON object only:
{"name":"the company or industry name","kind":"company|industry","founded":"year or empty","founder":"the founder(s) or empty","origin":"one sentence: where and how it began",
 "home":"headquarters or region","milestones":[{"year":"YYYY","event":"one plain sentence","source":<source number>}],
 "numbers":[{"value":"exact figure as written in the source, e.g. 375,235 or $44 billion","label":"what it counts, e.g. employees","year":"year it refers to or empty","source":<n>}],
 "how_it_works":["how it makes money or operates, one sentence each"],"rivals":["main competitors named in the sources"],
 "turning_points":["decisions or crises that changed it"],"unknowns":["what the sources leave unclear"]}
Rules: use ONLY the source texts, never outside knowledge; every year and number must be written in the cited source; 5-10 milestones in time order; leave a field empty rather than guess."""

SCRIPT = """You are the head writer of a faceless business-story channel (founder caricatures and company empires). Write exactly {n} scenes of ten seconds about {name}.
Scene jobs in order: {beats}.
Each scene: English narration of 20-26 spoken words, punchy and concrete, present tense for drama; one dominant visual action for a big-head cartoon founder in a toy-town of company buildings; and 1-4 on-screen cards.
Card types: {{"type":"title","kicker":"THE LEGACY|THE STORY OF|THE ENTIRE HISTORY OF","text":"company name","years":"first year – last year"}} (scene 1 only),
{{"type":"stat","value":"a number copied exactly from the research","unit":"2-3 words"}} (at most 3 per scene),
{{"type":"caption","text":"3-6 word hook line","accent":"the one word to colour red"}}, {{"type":"year","value":"YYYY"}}, {{"type":"vs","left":"this company","right":"the rival"}} (only for a rival named in the research).
Use ONLY facts, years and numbers from the research; never invent figures, quotes or motives. Pictures never contain text.
{{"title":"a YouTube title like 'From a Garage to $19 Billion'","scenes":[{{"purpose":str,"narration":str,"visual":"what we see, no text","setting":"origin|factory|city|rivalry|boardroom|world","move":"slow push in|slow pull out|pan left|pan right","rival":false,"cards":[...]}}]}}"""


# ---------- research ----------
def _num_tokens(text: str) -> set[str]:
    return {x.replace(",", "").rstrip(".") for x in re.findall(r"\d[\d,]*(?:\.\d+)?", text or "")}


def checked(text: str, allowed: set[str]) -> bool:
    """Every number in `text` appears in the research (years, figures) or the source texts."""
    return all(t in allowed for t in _num_tokens(text))


def research(s: dict, subject: str, log: Callable[[dict], None] | None = None) -> dict:
    from ..explainer import research as R
    srcs: list[dict] = []
    for q in (subject, f"History of {subject}"):
        try:
            for x in R.find(q, 2 if q == subject else 1):
                if x["url"] not in {y["url"] for y in srcs}:
                    srcs.append(x)
        except R.ResearchError as e:
            if q == subject and not srcs:
                raise RuntimeError(f"Research found nothing for “{subject}”: {e}. Check the spelling, or try the full company name.") from e
    srcs = srcs[:4]
    out: dict[str, Any] = {"sources": [{"title": x["title"], "url": x["url"]} for x in srcs], "status": "ok"}
    allowed = set().union(*[_num_tokens(x["text"]) for x in srcs]) if srcs else set()
    data = None
    if writers.uses_ai(s):
        body = "\n\n".join(f"[Source {i + 1}] {x['title']}\n{x['text']}" for i, x in enumerate(srcs))
        data = writers.ask(s, "story", writers.system("avos-company-story", RESEARCH), f"Subject: {subject}\n\n{body}\n\nWrite the JSON.", log, max_tokens=2200, temperature=0.2)
    if not isinstance(data, dict):
        found = re.search(r"(?:founded|established|formed|incorporated)\D{0,30}(\d{4})", " ".join(x["text"] for x in srcs), re.I)
        data = {"name": subject.strip().title() if subject.islower() else subject.strip(), "kind": "company", "founded": found.group(1) if found else "",
                "milestones": [], "numbers": [], "origin": "", "how_it_works": [], "rivals": [], "turning_points": []}
    src = lambda i: out["sources"][i - 1] if isinstance(i, int) and 0 < i <= len(out["sources"]) else None  # noqa: E731
    def s_(v: Any, n: int = 300) -> str:
        return " ".join(str(v or "").split())[:n]
    ms = []
    for m in data.get("milestones") or []:
        if isinstance(m, dict) and re.fullmatch(r"\d{4}", s_(m.get("year"))) and s_(m.get("year")) in allowed and checked(s_(m.get("event")), allowed):
            ms.append({"year": s_(m["year"]), "event": s_(m.get("event")), "source": src(_int(m.get("source")))})
    nums = []
    for m in data.get("numbers") or []:
        if isinstance(m, dict) and _num_tokens(s_(m.get("value"))) and checked(s_(m.get("value")) + " " + s_(m.get("year")), allowed):
            nums.append({"value": s_(m.get("value"), 40), "label": s_(m.get("label"), 60), "year": s_(m.get("year"), 10), "source": src(_int(m.get("source")))})
    founded = s_(data.get("founded"), 4) if re.fullmatch(r"\d{4}", s_(data.get("founded"), 4)) and s_(data.get("founded"), 4) in allowed else ""
    out.update(name=s_(data.get("name"), 80) or subject, kind="industry" if data.get("kind") == "industry" else "company", founded=founded,
               founder=s_(data.get("founder"), 120), origin=s_(data.get("origin")), home=s_(data.get("home"), 120), milestones=sorted(ms, key=lambda m: m["year"])[:10],
               numbers=nums[:8], how_it_works=[s_(x) for x in data.get("how_it_works") or []][:4], rivals=[s_(x, 60) for x in data.get("rivals") or []][:4],
               turning_points=[s_(x) for x in data.get("turning_points") or []][:4], unknowns=[s_(x) for x in data.get("unknowns") or []][:3])
    now = str(datetime.now().year)
    extra = {now, *([str(int(now) - int(founded))] if founded else [])}
    out["allowed"] = sorted(allowed | extra | {m["year"] for m in ms})
    return out


def _int(v: Any) -> int | None:
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def facts_text(r: dict) -> str:
    lines = [f"Name: {r['name']} ({r['kind']})"]
    for k, lab in (("founded", "Founded"), ("founder", "Founder"), ("origin", "Origin"), ("home", "Home")):
        if r.get(k):
            lines.append(f"{lab}: {r[k]}")
    lines += [f"{m['year']}: {m['event']}" for m in r.get("milestones") or []]
    lines += [f"Number: {n['value']} {n['label']}" + (f" ({n['year']})" if n.get("year") else "") for n in r.get("numbers") or []]
    for k, lab in (("how_it_works", "How it works"), ("rivals", "Rivals"), ("turning_points", "Turning points"), ("unknowns", "Unclear")):
        if r.get(k):
            lines.append(f"{lab}: " + " | ".join(r[k]))
    if r.get("founded"):
        lines.append(f"Age: {int(datetime.now().year) - int(r['founded'])} years (from {r['founded']} to {datetime.now().year})")
    return "\n".join(lines)


# ---------- script ----------
def norm_script(d: Any, r: dict, n: int) -> dict:
    allowed = set(r.get("allowed") or [])
    if not isinstance(d, dict) or not isinstance(d.get("scenes"), list) or not d["scenes"]:
        raise writers.WriterError("The AI writer didn't return a usable script. Try again, or pick another AI crew.")
    years = f"{r['founded']} – {datetime.now().year}" if r.get("founded") else ""
    scenes = []
    for i, sc in enumerate(d["scenes"][:n]):
        sc = sc if isinstance(sc, dict) else {}
        narr = " ".join(str(sc.get("narration") or "").split())[:400]
        keep, dropped = [], 0
        for c in sc.get("cards") or []:
            if not isinstance(c, dict) or c.get("type") not in ("title", "stat", "caption", "year", "vs"):
                continue
            c = {k: " ".join(str(v).split())[:60] for k, v in c.items() if isinstance(v, (str, int, float))}
            if c["type"] == "title":
                c["years"] = years or c.get("years", "")
                c["text"] = c.get("text") or r["name"]
            if c["type"] == "vs" and not r.get("rivals"):
                dropped += 1
                continue
            if not checked(" ".join(str(v) for k, v in c.items() if k not in ("type",)), allowed):
                dropped += 1
                continue
            keep.append(c)
        if i == 0 and not any(c["type"] == "title" for c in keep):
            keep.insert(0, {"type": "title", "kicker": "THE STORY OF", "text": r["name"], "years": years})
        stats = [c for c in keep if c["type"] == "stat"][:3]
        keep = [c for c in keep if c["type"] != "stat"] + stats
        warn = "" if checked(narr, allowed) else "The narration has a number the research doesn't show: check it before you share the video."
        scenes.append({"n": i + 1, "purpose": " ".join(str(sc.get("purpose") or BEATS[i % len(BEATS)]).split())[:160], "narration": narr,
                       "visual": " ".join(str(sc.get("visual") or "").split())[:400], "setting": str(sc.get("setting") or "city")[:20],
                       "move": str(sc.get("move") or "slow push in")[:20], "rival": bool(sc.get("rival")) or any(c["type"] == "vs" for c in keep),
                       "cards": keep, "dropped": dropped, "warning": warn})
    if len(scenes) < n:
        raise writers.WriterError(f"The AI writer wrote {len(scenes)} of {n} scenes. Try again.")
    return {"title": " ".join(str(d.get("title") or r["name"]).split())[:100], "scenes": scenes}


def script(s: dict, r: dict, n: int, log: Callable[[dict], None] | None = None) -> dict:
    if not writers.uses_ai(s):
        raise writers.WriterError("Company Story needs an AI writer for the script (pick Groq or another AI crew in Models); the research is ready.")
    beats = "; ".join(f"{i + 1}. {b}" for i, b in enumerate((BEATS[:5] + [BEATS[5]])[:n] if n <= 6 else BEATS[:n]))
    if n == 3:
        beats = "1. hook: the empire today; 2. origin and breakthrough; 3. how it works today, and the lesson"
    system = writers.system("avos-company-story-writer", SCRIPT.format(n=n, name=r["name"], beats=beats))
    return norm_script(writers.ask(s, "story", system, "Research:\n" + facts_text(r) + "\nWrite the JSON script.", log, max_tokens=3600, temperature=0.6), r, n)


# ---------- characters and pictures ----------
def founder_look(founded: str) -> str:
    y = int(founded) if founded.isdigit() else 1990
    if y < 1950:
        return "side-parted brown hair, round wire glasses, navy three-piece suit, white shirt, red tie"
    if y < 1990:
        return "neat dark hair with grey temples, square glasses, navy suit, light blue shirt, red tie"
    return "short tousled dark hair, thin-framed glasses, navy blazer over a grey t-shirt, sneakers"


RIVAL_LOOK = "grey swept-back hair, heavy grey eyebrows, a smug grin, charcoal pinstripe suit, gold tie"


def sheet_prompt(r: dict, who: str) -> str:
    look = founder_look(r.get("founded") or "") if who == "founder" else RIVAL_LOOK
    role = f"the founder figure of {r['name']}" if who == "founder" else "the head of a rival company"
    return (f"Character model sheet of one ORIGINAL cartoon business character, {role}: {look}. Not a portrait or likeness of any real person. Style: {LOOK}. "
            "Front view and three-quarter view side by side on a plain warm-grey background, full body, same proportions in both views, neutral confident "
            f"pose. {NO_TEXT}")


SETTINGS = {"origin": "a small humble starting place (a garage, workshop, shop or office) at the edge of the toy-town",
            "factory": "rows of factories and warehouses with roads and a test track spreading over the green land",
            "city": "a sprawling company city of grey office towers and factories seen from above at an angle",
            "rivalry": "two clusters of company towers facing each other across a river, one for each company",
            "boardroom": "a cartoon boardroom with a big window over the company city",
            "world": "a stylised globe or map with little company buildings spread across continents"}


def scene_prompt(r: dict, sc: dict, has_rival: bool) -> str:
    who = "The founder character from Image 1 (same face, hair, glasses and suit)" + (" and the rival from Image 2 (same face and suit)" if has_rival else "")
    return (f"Wide 2D cartoon scene, {LOOK}. {who}, large in the foreground on one side, acting: {sc['visual'] or sc['purpose']}. Setting: "
            f"{SETTINGS.get(sc['setting'], SETTINGS['city'])}. Story: {r['name']}, {sc['purpose']}. {NO_TEXT}")


def motion_prompt(sc: dict) -> str:
    return (f"2D cartoon animation of this exact picture, same characters and drawing style. {sc['visual'] or sc['purpose']}. The founder gestures and reacts "
            f"with expressive cartoon acting, small vehicles move along the roads, smoke drifts from chimneys, the river flows; camera {sc['move']}. "
            "No text, no new characters, no style change.")


# ---------- stages ----------
def do_research(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "research", status="working")
    r = research(base.sdict(p), p["subject"], base.logger(pid))
    base.put(pid, research=r, title=r["name"])
    base.step(pid, "research", status="done", note=f"{len(r['sources'])} sources, {len(r['milestones'])} dated milestones, {len(r['numbers'])} checked numbers")
    store.say(pid, f"Research ready: {len(r['sources'])} sources.")


def do_script(pid: str) -> None:
    p = store.load(pid)
    base.step(pid, "script", status="working")
    sc = script(base.sdict(p), p["research"], max(3, int(p.get("seconds") or 60) // SCENE_SECONDS), base.logger(pid))
    base.put(pid, script=sc, title=sc["title"])
    dropped = sum(x["dropped"] for x in sc["scenes"])
    base.step(pid, "script", status="done", note=f"{dropped} card(s) dropped: their numbers weren't in the research" if dropped else "")


def _w_h(p: dict) -> tuple[int, int]:
    return base.SIZES.get(p.get("aspect") or "16:9", base.SIZES["16:9"])


def do_cast(pid: str) -> None:
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    base.step(pid, "cast", status="working")
    need = ["founder"] + (["rival"] if any(x["rival"] for x in p["script"]["scenes"]) else [])
    got = dict(p.get("cast") or {})
    for who in need:
        if got.get(who) and store.file_path(pid, got[who]):
            continue
        img, info = media.picture(sheet_prompt(p["research"], who), [], max(w, h), min(w, h), media.seed_of(pid, who, p.get("version", 1)), f"{pid}-{who}", s=s)
        got[who] = base.write(pid, f"{who}.png", img)
        base.put(pid, cast=got)
    base.step(pid, "cast", status="done")


def do_scenes(pid: str) -> None:
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    base.step(pid, "scenes", status="working")
    f, rv = base.read(pid, (p.get("cast") or {}).get("founder")), base.read(pid, (p.get("cast") or {}).get("rival"))
    for sc in p["script"]["scenes"]:
        base.check(pid)
        if sc.get("picture") and store.file_path(pid, sc["picture"]):
            continue
        refs = [x for x in (f, rv if sc["rival"] else None) if x]
        img, info = media.picture(scene_prompt(p["research"], sc, bool(sc["rival"] and rv)), refs, w, h, media.seed_of(pid, sc["n"], sc.get("version", 1)), f"{pid}-S{sc['n']}", s=s)
        name = base.write(pid, f"S{sc['n']:02d}.png", img)
        store.update(pid, lambda q, n=sc["n"], name=name, m=info.get("model"): q["script"]["scenes"][n - 1].update(picture=name, picture_model=m, video=None))
        if sc["n"] == 1:
            base.put(pid, thumb=name)
    base.step(pid, "scenes", status="done")


def do_animate(pid: str) -> None:
    from ..explainer import engines
    from ..stickman import video
    from .. import config
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    base.step(pid, "animate", status="working")
    d = store.pdir(pid)
    engine = ""
    for sc in p["script"]["scenes"]:
        base.check(pid)
        if sc.get("video") and store.file_path(pid, sc["video"]):
            continue
        img = base.read(pid, sc.get("picture"))
        if not img:
            raise RuntimeError(f"scene {sc['n']} has no picture yet")
        raw = d / f"S{sc['n']:02d}_base.mp4"
        clip = None
        if video.ready(s):
            try:
                clip = video.clip(motion_prompt(sc), [img], None, SCENE_SECONDS, p.get("aspect") or "16:9", audio=False)
                engine = "Seedance 2.0"
            except Exception as e:  # noqa: BLE001 - a failed clip falls back to a camera move (said on the scene)
                store.say(pid, f"Scene {sc['n']}: Seedance failed ({str(e)[:120]}); using a camera move.", "warn")
        if clip is None:
            kind = {"slow push in": "push", "slow pull out": "pull", "pan left": "panl", "pan right": "pan"}.get(sc["move"], "push")
            clip = media.still_motion(s, img, SCENE_SECONDS, kind)
            engine = engine or "camera move"
        raw.write_bytes(clip)
        out = cards.burn(raw, sc["cards"], d / f"S{sc['n']:02d}.mp4", w, h, SCENE_SECONDS, config.ffmpeg())
        store.update(pid, lambda q, n=sc["n"], name=out.name: q["script"]["scenes"][n - 1].update(video=name))
    base.step(pid, "animate", status="done", model=engine or None,
              note="" if engine == "Seedance 2.0" else "No fal.ai key with credit (Settings): scenes move with camera moves; cards and numbers still animate.")


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
        name = base.write(pid, f"S{sc['n']:02d}_voice.wav", wav)
        note = info.get("note") or note
        secs = media.wav_seconds(wav)
        store.update(pid, lambda q, n=sc["n"], name=name, secs=secs: q["script"]["scenes"][n - 1].update(voice=name, voice_seconds=round(secs, 2)))
    base.step(pid, "voice", status="done", note=note)


def do_finish(pid: str) -> None:
    from ..series import assemble
    p = store.load(pid)
    s, (w, h) = base.sdict(p), _w_h(p)
    base.step(pid, "finish", status="working")
    d = store.pdir(pid)
    work = d / "work"
    work.mkdir(exist_ok=True)
    parts, total = [], 0.0
    for sc in p["script"]["scenes"]:
        clip = d / (sc.get("video") or "")
        if not clip.is_file():
            raise RuntimeError(f"scene {sc['n']} has no video yet")
        sec = float(max(SCENE_SECONDS, min(SCENE_SECONDS + 3, (sc.get("voice_seconds") or 0) + 0.8)))
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
    if "cast" in order:
        p.pop("cast", None)
    for sc in (p.get("script") or {}).get("scenes") or []:
        if n and sc["n"] != n:
            continue
        sc["version"] = int(sc.get("version", 1)) + 1
        if "scenes" in order:
            sc["picture"] = None
        if "animate" in order or "scenes" in order:
            sc["video"] = None
        if "voice" in order:
            sc["voice"] = None
    p.pop("video", None)
