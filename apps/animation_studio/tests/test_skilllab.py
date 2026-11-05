"""Skill Lab: the Mechanical Toy skill's design lock, its three prompts (same look words in all three), and the run
(design → compact picture → transformed picture drawn FROM the compact one → clip from both) with stand-in media."""
from __future__ import annotations

import re
import time

from studio.series import media, writers
from studio.skilllab import mechanical_toy as MT
from studio.skilllab import pipeline, store

from .conftest import needs_ffmpeg

HYDRA = {"subject": "a seven-headed hydra", "form": "flattened-sphere pod", "finish": "satin-blackened titanium with micro-brushed surfaces",
         "palette": "deep marsh green, oxidized bronze, and muted bone", "shell": "restrained concentric seam lines and one small recessed button",
         "hidden": ["heads", "necks", "scales"], "anatomy": "A low, sturdy quadrupedal chassis supports seven individually articulated serpentine necks.",
         "torso": "curved shell panels rotated outward around a dense central gear cage",
         "sequence": ["concentric shell seams separate", "four leg assemblies telescope from underbody rails", "seven neck cores rise in a readable fan"],
         "reveal": "the finished articulated necks and engineered jaws"}


def test_subject_from_a_full_request():
    assert MT.subject_of("Turn a seven-headed hydra into a mechanical transformation toy. In this same run…") == "a seven-headed hydra"
    assert MT.subject_of("snow leopard") == "snow leopard"


def test_three_prompts_share_the_locked_look():
    pr = MT.prompts(MT.norm_lock(HYDRA, "a seven-headed hydra"), 15)
    for k in ("compact", "transformed", "video"):
        assert "satin-blackened titanium with micro-brushed surfaces" in pr[k] and "deep marsh green, oxidized bronze, and muted bone" in pr[k]
    assert "held in one human hand only" in pr["compact"] and "no heads" in pr["compact"] and "hydra parts" in pr["compact"]
    assert "Use the supplied compact-device image" in pr["transformed"] and "No hands visible" in pr["transformed"] and "1.5 to 2 times" in pr["transformed"]
    v = pr["video"]
    assert v.startswith("[Style:") and "reference image 1" in v and "reference image 2" in v and "no music" in v
    assert v.index("thumb presses the recessed button") < v.index("hand withdraws") < v.index("seams separate") < v.index("final heavy locking clunk")
    assert "#" not in "".join(pr.values())


def test_builtin_lock_without_ai_is_stable():
    a, b = MT.default_lock("a phoenix"), MT.default_lock("a phoenix")
    assert a == b and a["form"] in MT.FORMS and a["palette"] in MT.PALETTES


@needs_ffmpeg
def test_run_draws_transformed_from_compact_then_clip(monkeypatch):
    from PIL import Image
    import io
    calls = []

    def png(color):
        b = io.BytesIO(); Image.new("RGB", (72, 128), color).save(b, "PNG"); return b.getvalue()

    def fake_picture(prompt, refs, w, h, seed, tag, priority=5, s=None, negative=None):
        calls.append((tag, len(refs)))
        return png("grey" if "compact" in tag else "black"), {"model": "stand-in"}

    monkeypatch.setattr(media, "picture", fake_picture)
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr(writers, "ask", lambda *a, **k: dict(HYDRA))
    pid = store.new_id()
    store.save({"id": pid, "skill": MT.ID, "subject": "a seven-headed hydra", "aspect": "9:16", "seconds": 8, "media": "media", "status": "working",
                "stage": "design", "steps": {}, "log": [], "crew": "groq"})
    pipeline._run(pid, "design")
    p = store.load(pid)
    assert p["status"] == "done", p.get("error")
    assert p["lock"]["form"] == "flattened-sphere pod" and set(p["prompts"]) == {"compact", "transformed", "video"}
    assert [c[1] for c in calls] == [0, 1]                       # the transformed picture is drawn FROM the compact one
    assert p["video"] == "transformation.mp4" and p["engine"] == "key-pose animatic" and store.file_path(pid, p["video"])


def test_prompts_only_run_stops_after_design(monkeypatch):
    pid = store.new_id()
    store.save({"id": pid, "skill": MT.ID, "subject": "a vintage steam locomotive", "aspect": "9:16", "seconds": 15, "media": "prompts", "status": "working",
                "stage": "design", "steps": {}, "log": []})
    pipeline._run(pid, "design")
    p = store.load(pid)
    assert p["status"] == "done" and p["prompts"]["compact"] and not p.get("compact")


# ---------- Company Story ----------
from studio.skilllab import cards, company_story as CS  # noqa: E402

SRC = [{"title": "Northwind Motors", "url": "https://en.wikipedia.org/wiki/Northwind_Motors",
        "text": "Northwind Motors is a carmaker founded in 1937 in a garage in Ohio by Ada Lane. In 1955 it opened its first factory. "
                "By 1984 it was exporting to Europe and fought a price war with Atlas Auto. It employs 210,000 people and had revenue of $44 billion in 2023. "
                "During COVID-19 its 19 plants closed for a while."},
       {"title": "History of Ohio", "url": "https://en.wikipedia.org/wiki/History_of_Ohio", "text": "Ohio became a state in 1803."}]
WIKIDATA = {"qid": "Q1", "url": "https://www.wikidata.org/wiki/Q1", "label": "Northwind Motors", "description": "American carmaker", "founded": "1937",
            "founders": ["Ada Lane"], "hq": "Columbus", "parent": "", "subsidiaries": ["Northwind Trucks"], "industry": ["automotive"], "country": "United States",
            "numbers": [{"value": "212,000", "label": "employees", "year": "2024"}]}
RESEARCH_ANSWER = {"name": "Northwind Motors", "kind": "company", "founded": "1955", "founder": "Ada Lane", "origin": "A garage in Ohio.",
                   "milestones": [{"year": "1955", "event": "First factory opens.", "source": 1}, {"year": "1999", "event": "Invented milestone.", "source": 1}],
                   "numbers": [{"value": "210,000", "label": "employees", "source": 1}, {"value": "$44 billion", "label": "revenue", "year": "2023", "source": 1},
                               {"value": "9,999", "label": "invented", "source": 1}],
                   "story_moments": [{"year": "1937", "title": "A garage in Ohio", "what": "Ada Lane starts building cars in a garage in Ohio.", "kind": "beginning", "source": 1},
                                     {"year": "1984", "title": "The price war", "what": "Northwind fights a price war with Atlas Auto and loses 77 dealers.", "kind": "crisis", "source": 1}],
                   "how_it_works": ["It sells cars."], "rivals": ["Atlas Auto"], "turning_points": ["The 1984 price war."]}


def _script(n):
    sc = [{"purpose": f"beat {i}", "narration": "From one garage in 1937 to a giant with 210,000 people building cars across the land today.",
           "visual": "the founder points at factories", "poses": ["pointing right", "arms wide"],
           "setting": "city", "move": "slow push in", "cards": [{"type": "stat", "value": "210,000", "unit": "employees"}, {"type": "stat", "value": "$77B", "unit": "made up"},
                                                               {"type": "caption", "text": "All from one garage", "accent": "garage"}]} for i in range(n)]
    sc[1]["cards"].append({"type": "vs", "left": "Northwind", "right": "Atlas Auto"})
    sc[2]["narration"] = "In 2011 it sold 5 million cars. The garage became a giant that builds cars for families everywhere in the world."
    sc[0]["narration"] = "Northwind is worth $19 billion. It started in a garage in 1937 and now employs 210,000 people across many busy factories."
    return {"title": "From a Garage to $19 Billion", "scenes": sc}


FIXED = {}


def cs_ask(s, who, system, prompt, log=None, **kw):
    if "research desk" in system:
        assert "Wikidata" in prompt                                     # the structured facts reach the writer
        return dict(RESEARCH_ANSWER)
    if "You check a business-story script" in system:
        return {"lines": FIXED}
    return _script(int(re.search(r"exactly (\d+) scenes", prompt).group(1)))


def _patch(monkeypatch):
    from studio.explainer import research as R
    monkeypatch.setattr(R, "find", lambda q, limit=3: SRC[:1] if not q.startswith("History") else SRC[1:])
    monkeypatch.setattr(CS, "wikidata", lambda title: dict(WIKIDATA))
    monkeypatch.setattr(CS, "wiki_article", lambda title: ("", ""))
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr(writers, "ask", cs_ask)


def test_research_keeps_only_researched_numbers(monkeypatch):
    _patch(monkeypatch)
    r = CS.research({"id": "x", "crew": "groq"}, "Northwind Motors")
    assert [x["title"] for x in r["sources"]] == ["Northwind Motors", "Wikidata: Northwind Motors"]     # 'History of Ohio' isn't about it
    assert r["founded"] == "1937" and "Wikidata gives 1937" in r["unknowns"][0]                        # Wikidata settles the founding year
    assert [m["year"] for m in r["milestones"]] == ["1955"]                                              # 1999 isn't in the source
    assert [n["value"] for n in r["numbers"]] == ["212,000", "210,000", "$44 billion"] and r["numbers"][0]["year"] == "2024"
    assert [m["title"] for m in r["story_moments"]] == ["A garage in Ohio"]       # '77 dealers' isn't in the source: that moment is dropped
    assert "Story moment (1937) [beginning] A garage in Ohio" in CS.facts_text(r)
    assert "19" not in CS.fact_numbers(r)                                   # in the article (COVID-19) but not a researched fact
    sc = CS.norm_script(_script(6), r, 6)
    assert sc["title"].startswith("Northwind Motors: The Story from 1937")  # '$19 Billion' isn't researched: the title is rebuilt
    s1 = sc["scenes"][0]
    assert s1["cards"][0]["type"] == "title" and s1["cards"][0]["years"].startswith("1937 – ")
    assert all(c.get("value") != "$77B" for x in sc["scenes"] for c in x["cards"]) and s1["dropped"] == 1
    s2 = sc["scenes"][1]
    assert s2["rival"] and not any(c["type"] == "stat" for c in s2["cards"]) and s2["poses"][0] == "pointing right" and len(s2["poses"]) == 3
    assert sc["scenes"][0]["warning"] and sc["scenes"][2]["warning"] and not sc["scenes"][3]["warning"]


def test_research_reads_the_whole_article_story_first(monkeypatch):
    full = ("Northwind Motors is a carmaker.\n\n== History ==\n\n=== Founding ===\nIn 1937 Ada Lane met two engineers at a diner and sketched the first car "
            "on a napkin.\n\n=== Near collapse ===\nIn 1962 it was 30 days from running out of money.\n\n== Products ==\nCars and trucks.\n\n"
            "== Sponsorships ==\n" + "Football. " * 3000 + "\n\n== References ==\nRef list.")
    t = CS.story_text(full, 2000)
    assert "napkin" in t and "30 days" in t and "Ref list" not in t and t.index("napkin") < t.index("30 days") and len(t) <= 2000
    _patch(monkeypatch)
    seen = []
    monkeypatch.setattr(CS, "wiki_article", lambda title: (full, "https://en.wikipedia.org/wiki/X") if not title.startswith("History") else ("", ""))
    orig = writers.ask
    monkeypatch.setattr(writers, "ask", lambda s, who, system, prompt, log=None, **k: (seen.append(prompt), orig(s, who, system, prompt, log, **k))[1])
    CS.research({"id": "x", "crew": "groq"}, "Northwind Motors")
    assert "napkin" in seen[0] and "30 days" in seen[0]                       # the writer reads the history sections, not only the opening


def test_unchecked_narration_is_rewritten_or_cut(monkeypatch):
    _patch(monkeypatch)
    r = CS.research({"id": "x", "crew": "groq"}, "Northwind Motors")
    FIXED.clear()
    FIXED["1"] = "Northwind starts in a small Ohio garage in 1937 and grows into a carmaker that employs 210,000 people today."
    sc = CS.script({"id": "x", "crew": "groq"}, r, 6)
    assert sc["scenes"][0]["narration"].startswith("Northwind starts") and "Rewritten" in sc["scenes"][0]["warning"]
    assert sc["scenes"][2]["narration"].startswith("The garage became a giant") and "cut" in sc["scenes"][2]["warning"]
    assert all(CS.checked(x["narration"], CS.fact_numbers(r)) for x in sc["scenes"])


def test_cards_count_up_and_never_overlap():
    assert cards.counted("210,000", 0.5) == "105,000" and cards.counted("$44B", 1) == "$44B" and cards.counted("4.5%", 1) == "4.5%"
    sets = [[{"type": "title", "text": "Northwind Motors Corporation International Holdings", "years": "1937 – 2026"}, {"type": "year", "value": "1937"},
             {"type": "stat", "value": "210,000", "unit": "employees"}, {"type": "stat", "value": "$44 billion", "unit": "revenue in 2023"},
             {"type": "stat", "value": "1,000", "unit": "cities"}, {"type": "caption", "text": "All from one small garage in Ohio", "accent": "garage"}],
            [{"type": "vs", "left": "Northwind", "right": "Atlas Auto"}, {"type": "caption", "text": "The price war", "accent": "war"}]]
    for W, H in ((1280, 720), (720, 1280)):
        for cs in sets:
            pl = cards.plan(cs, W, H)
            boxes = []
            for it in pl:
                im = cards._render(it, it["u"])
                boxes.append((it["cx"] - im.width / 2, it["cy"] - im.height / 2, it["cx"] + im.width / 2, it["cy"] + im.height / 2))
            assert all(0 <= b[0] and 0 <= b[1] and b[2] <= W and b[3] <= H for b in boxes)            # inside the frame
            assert not any(cards._hits(a, b) for i, a in enumerate(boxes) for b in boxes[i + 1:])      # no two cards overlap
            if W > H and cs is sets[0]:
                assert all(b[0] >= W * 0.03 - 1 for b in boxes) and all(it["cx"] > W * 0.5 for it in pl if it["kind"] in ("title", "stat"))  # beside the founder
        assert cards.overlay(sets[0], W, H, 6.0).getbbox()


def test_scene_backdrop_has_no_people_and_cards_leave_the_character_alone():
    sc = {"visual": "a red chart crashing on a big screen", "purpose": "the crisis", "setting": "city", "place": "a dark office", "poses": ["thinking"]}
    q = CS.scene_prompt({"name": "Northwind"}, sc)
    assert "NO people" in q and "LEFT third" in q and "No text, no letters, no numbers" in q and "dark office" in q
    assert "rival company's taller towers" in CS.scene_prompt({"name": "N"}, sc, True)
    assert "people" in CS.NEGATIVE and "$19" not in CS.SCRIPT and "Billion" not in CS.SCRIPT and CS.INFO["aspects"] == ["16:9"]
    assert "face stays visible" in CS.motion_prompt(sc)
    pl = cards.plan([{"type": "caption", "text": "All from one garage", "accent": "garage"}, {"type": "stat", "value": "210,000", "unit": "employees"}], 1280, 720)
    cap = next(i for i in pl if i["kind"] == "caption")
    assert cap["cx"] - cards._render(cap, cap["u"]).width / 2 >= 1280 * 0.36 - 2              # the caption starts right of the character's third


def test_ready_made_characters_are_placed_in_code():
    import io
    from PIL import Image
    from studio.skilllab import compose, routes
    assert {c["id"] for c in CS.INFO["characters"]} == {"director", "young", "executive"} and CS.INFO["default_cast"] == {"founder": "executive"}
    for cid in CS.CHARACTERS:
        assert len(compose.sprites(cid)) >= 4 and (CS.CHAR_DIR / f"{cid}_2d.jpg").is_file()
    assert routes._story_options(CS, {"characters": {"founder": "director", "rival": "young"}, "style": "3d", "motion": "poses"}) == \
        {"style": "2d", "motion": "poses", "characters": {"founder": "director"}}                      # 2D only, one character, no rival picker
    assert routes._story_options(CS, {})["characters"] == {"founder": "executive"}
    # the gestures in the script pick different poses, in the order written
    assert compose.choose("young", ["hand on chin, thinking", "on the phone", "fists raised, cheering"]) == ["think", "call", "celebrate"]
    assert len(set(compose.choose("director", ["pointing", "thinking", "thinking", "cheering"], 3))) == 3 and compose.choose("executive", ["holding a tablet"])[0] == "tablet"
    bg = io.BytesIO(); Image.new("RGB", (640, 360), (90, 170, 90)).save(bg, "PNG")
    out = Image.open(io.BytesIO(compose.place(bg.getvalue(), "young", "welcome", 1280, 720)))
    assert out.size == (1280, 720)
    left = out.crop((0, 0, 640, 720)).getcolors(10**6)
    assert len(left) > 200 and out.crop((700, 0, 1280, 720)).getcolors(10**6) == [(580 * 720, (90, 170, 90))]   # the character is in the left half only; the right half is untouched


def _tone(sec):
    import io, math, wave
    b = io.BytesIO()
    w = wave.open(b, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
    w.writeframes(b"".join(int(6000 * math.sin(i / 8)).to_bytes(2, "little", signed=True) for i in range(int(24000 * sec)))); w.close()
    return b.getvalue()


def test_silent_narration_and_missing_video_model_stop_the_run(monkeypatch):
    from studio.explainer import pipeline as xp
    assert CS.is_silent(media.silence(1.0)) and not CS.is_silent(_tone(1.0))
    pid = store.new_id()
    store.save({"id": pid, "skill": CS.ID, "subject": "N", "aspect": "16:9", "seconds": 30, "media": "media", "status": "working", "stage": "voice",
                "steps": {}, "log": [], "crew": "groq", "motion": "video", "script": {"title": "t", "scenes": [{"n": 1, "narration": "Hello there.", "picture": "x.png"}]}})
    monkeypatch.setattr(xp, "_voice", lambda s, text, p: (media.silence(2.0), {"note": "403, message='Invalid response status', url='wss://speech.platform.bing.com/…'"}))
    try:
        CS.do_voice(pid)
        raise AssertionError("a silent narration must stop the run")
    except RuntimeError as e:
        assert "edge-tts" in str(e)
    monkeypatch.setattr(CS, "_seedance", lambda s: False)
    try:
        CS.do_animate(pid)
        raise AssertionError("AI video without a video model must stop the run")
    except RuntimeError as e:
        assert str(e) == CS.NO_VIDEO


@needs_ffmpeg
def test_company_story_run_makes_the_video(monkeypatch):
    import io
    from PIL import Image
    from studio.explainer import pipeline as xp
    _patch(monkeypatch)
    monkeypatch.setattr(CS, "_seedance", lambda s: False)
    pics = []

    def fake_picture(prompt, refs, w, h, seed, tag, priority=5, s=None, negative=None):
        pics.append((tag, len(refs)))
        assert refs == [] and negative == CS.NEGATIVE and "NO people" in prompt               # backdrops only: the character is placed in code
        b = io.BytesIO(); Image.new("RGB", (w // 8, h // 8), (90, 160 + len(pics) % 60, 90)).save(b, "PNG"); return b.getvalue(), {"model": "stand-in"}

    monkeypatch.setattr(media, "picture", fake_picture)
    monkeypatch.setattr(xp, "_voice", lambda s, text, p: (_tone(2.0), {"model": "tone"}))
    monkeypatch.setattr(media, "music", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no music model")))
    pid = store.new_id()
    store.save({"id": pid, "skill": CS.ID, "subject": "Northwind Motors", "aspect": "16:9", "seconds": 30, "media": "media", "status": "working",
                "stage": "research", "steps": {}, "log": [], "crew": "groq", "motion": "poses", "style": "2d", "characters": {"founder": "young"}})
    pipeline._run(pid, "research")
    p = store.load(pid)
    assert p["status"] == "done", p.get("error")
    assert len(p["script"]["scenes"]) == 3 and all(sc["video"] for sc in p["script"]["scenes"])
    assert len(pics) == 3 and all(len(sc["pose_pics"]) == 3 and len(set(sc["pose_names"])) == 3 for sc in p["script"]["scenes"])   # one backdrop per scene, 3 poses on it
    assert p["cast"] == {"founder": "young"} and all(sc["backdrop"] for sc in p["script"]["scenes"])
    assert p["video"] == "final.mp4" and media.probe_seconds(store.pdir(pid) / "final.mp4") >= 29
    store.update(pid, lambda q: CS.reset(q, "scenes", 2))
    q = store.load(pid)
    assert q["script"]["scenes"][1]["picture"] is None and q["script"]["scenes"][1]["backdrop"] is None and q["script"]["scenes"][0]["backdrop"] and q["script"]["scenes"][1]["pose_pics"] == [] and q["script"]["scenes"][0]["picture"] and not q.get("video")


def test_video_gets_full_model_sheet():
    from studio.skilllab import company_story as cs, compose
    assert compose.sheet("executive") and compose.sheet("director") and compose.sheet("young")
    assert "model sheet" in cs.motion_prompt({"poses": ["a"]}, True)
    assert "model sheet" not in cs.motion_prompt({"poses": ["a"]}, False)
