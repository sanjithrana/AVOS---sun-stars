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


def _scene_png(w: int, h: int, salt: int) -> bytes:
    """A stand-in backdrop with real light and shape in it: the run throws away a frame that comes back black or empty."""
    import io
    from PIL import Image, ImageDraw
    im = Image.new("RGB", (max(16, w), max(16, h)), (196, 214 - salt % 30, 176))
    d = ImageDraw.Draw(im)
    d.rectangle([0, im.height * 0.6, im.width, im.height], fill=(150, 140, 110))
    for i in range(4):
        x = im.width * (0.15 + i * 0.2)
        d.rectangle([x, im.height * (0.25 + (i % 2) * 0.1), x + im.width * 0.12, im.height * 0.62], fill=(90 + i * 24, 80 + i * 20, 70))
    b = io.BytesIO(); im.save(b, "PNG"); return b.getvalue()


def _script(n):
    sc = [{"purpose": f"beat {i}", "narration": "From one garage in 1937 to a giant with 210,000 people building cars across the land today.",
           "visual": "the founder points at factories", "poses": ["pointing right", "arms wide"],
           "setting": "city", "move": "slow push in", "cards": [{"type": "stat", "value": "210,000", "unit": "employees"}, {"type": "stat", "value": "$77B", "unit": "made up"},
                                                               {"type": "caption", "text": "All from one garage", "accent": "garage"}]} for i in range(n)]
    if len(sc) > 1:                                       # a short act (the tail of a long script) has neither
        sc[1]["cards"].append({"type": "vs", "left": "Northwind", "right": "Atlas Auto"})
    if len(sc) > 2:
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
    m = re.search(r"exactly (\d+) scenes", prompt) or re.search(r"(\d+)-scene story", prompt)
    return _script(int(m.group(1)))


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
    assert "people" in CS.NEGATIVE and "$19" not in CS.SCRIPT and "Billion" not in CS.SCRIPT and CS.INFO["aspects"] == ["16:9", "9:16"]
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
    import numpy as np
    left = out.crop((0, 0, 640, 720)).getcolors(10**6)
    right = np.asarray(out.crop((700, 0, 1280, 720)), dtype=float)
    assert len(left) > 200 and right.std(axis=(0, 1)).max() < 25      # the character is in the left half only; the right half is just paper-textured backdrop
    assert (np.asarray(out.crop((0, 0, 640, 720))).min(axis=2) > 245).sum() > 500          # the white paper-sticker outline round the cut-out
    # paper effects: the border is cream with a torn edge, the puppet moves between frames, the sticker has an outline
    fr = list(compose.scene_frames(bg.getvalue(), "young", ["welcome", "think", "point"], 1280, 720, 1.5, active=1.5))
    assert len(fr) == 36 and fr[0].size == (1280, 720) and np.abs(np.asarray(fr[10], dtype=float) - np.asarray(fr[30], dtype=float)).mean() > 0.5
    assert compose.torn_frame(1280, 720).getpixel((2, 360))[3] > 200 and compose.torn_frame(1280, 720).getpixel((640, 360))[3] < 30


def _tone(sec):
    import io, math, wave
    b = io.BytesIO()
    w = wave.open(b, "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000)
    w.writeframes(b"".join(int(6000 * math.sin(i / 8)).to_bytes(2, "little", signed=True) for i in range(int(24000 * sec)))); w.close()
    return b.getvalue()


def test_silent_narration_stops_the_run_but_a_missing_video_model_does_not(monkeypatch):
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
    # a missing video model is not a reason to stop: the run says so and carries on with the free paper-puppet motion
    monkeypatch.setattr(CS, "_seedance", lambda s: False)
    try:
        CS.do_animate(pid)
    except RuntimeError as e:
        assert "no picture yet" in str(e)                 # this fixture has no scene picture; the point is it is not NO_VIDEO
    assert any(CS.NO_VIDEO_FELL_BACK in x["text"] for x in store.load(pid)["log"])


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
        return _scene_png(w // 8, h // 8, len(pics)), {"model": "stand-in"}

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


def test_review_pause_plan_changes_and_activity_feed(monkeypatch):
    import io
    from PIL import Image
    from studio import activity
    from studio.explainer import pipeline as xp
    _patch(monkeypatch)
    monkeypatch.setattr(CS, "_seedance", lambda s: False)

    def fake_picture(prompt, refs, w, h, seed, tag, priority=5, s=None, negative=None):
        return _scene_png(w // 8, h // 8, 1), {"model": "stand-in"}

    monkeypatch.setattr(media, "picture", fake_picture)
    monkeypatch.setattr(xp, "_voice", lambda s, text, p: (_tone(2.0), {"model": "tone"}))
    monkeypatch.setattr(media, "music", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no music model")))
    pid = store.new_id()
    store.save({"id": pid, "skill": CS.ID, "subject": "Northwind Motors", "aspect": "16:9", "seconds": 30, "media": "media", "status": "working", "review": True,
                "stage": "research", "steps": {}, "log": [], "crew": "groq", "motion": "poses", "style": "2d", "voice": "male", "characters": {"founder": "young"}})
    pipeline._run(pid, "research")
    p = store.load(pid)
    assert p["status"] == "waiting" and p["stage"] == "script" and "cast" not in p["steps"]            # paused after the script, nothing drawn yet
    plan = CS.plan_of(p)
    assert [c["id"] for c in plan["characters"] if c["chosen"]] == ["young"] and len(plan["storyboard"]) == 3
    assert plan["motion"]["engine"] == "poses" and plan["audio"]["words"] > 0 and all(sc["pose_names"] for sc in plan["storyboard"])
    # the feed shows it as waiting for the person
    feed = activity.collect()
    row = next(x for x in feed["jobs"] if x["id"] == pid)
    assert row["state"] == "waiting" and row["needs"] == 1 and row["href"] == f"/skills/{pid}" and feed["counts"]["waiting"] >= 1
    # changes from the review: another character and the female voice
    store.update(pid, lambda q: CS.change_plan(q, {"character": "director", "voice": "female"}))
    q = store.load(pid)
    assert q["characters"] == {"founder": "director"} and q["voice"] == "female" and "cast" not in q
    # approve (what POST /continue does) and the run finishes with the new character
    store.update(pid, lambda q: q.update(plan_ok=True))
    pipeline._run(pid, pipeline.resume_stage(store.load(pid)))
    p = store.load(pid)
    assert p["status"] == "done", p.get("error")
    assert p["cast"] == {"founder": "director"} and all(len(sc["pose_pics"]) >= 3 for sc in p["script"]["scenes"])
    assert not any(x["id"] == pid for x in activity.collect()["jobs"]) and any(x["id"] == pid and x["state"] == "done" for x in activity.collect()["recent"])
    # a new script is reviewed again
    store.update(pid, lambda q: CS.reset(q, "script"))
    assert "plan_ok" not in store.load(pid)


def test_reels_and_long_videos():
    """A company story can be a 9:16 reel, and a five- or ten-minute video uses longer scenes written act by act."""
    import io
    import numpy as np
    from PIL import Image
    from studio.skilllab import cards, compose
    assert CS.INFO["aspects"] == ["16:9", "9:16"] and 600 in CS.INFO["seconds"]
    # longer videos use longer scenes, so the research is not cut into sixty ten-second slices
    assert (CS.scenes_for(30), CS.scene_seconds(30)) == (3, 10)
    assert (CS.scenes_for(600), CS.scene_seconds(600)) == (40, 15)
    assert [x["seconds"] for x in CS.INFO["lengths"]] == CS.INFO["seconds"]
    lo, hi = CS.words_for(15)
    assert lo < hi and 30 < lo and hi < 55                      # more words for a longer scene, still speakable
    # the backdrop is asked for in the shape it will be used in
    sc = {"n": 1, "visual": "a loom", "purpose": "the start", "setting": "origin", "place": "a small shed", "poses": ["thinking"]}
    tall = CS.scene_prompt({"name": "N"}, sc, False, "9:16")
    assert "9:16 vertical reel" in tall and "BOTTOM THIRD" in tall and "NO people" in tall
    assert "LEFT third" in CS.scene_prompt({"name": "N"}, sc, False, "16:9")          # he changes side scene by scene
    assert "RIGHT third" in CS.scene_prompt({"name": "N"}, {**sc, "n": 2}, False, "16:9")
    assert CS.side_of(1, "9:16") == "centre" and CS.side_of(1, "16:9") != CS.side_of(2, "16:9")
    # in a reel he stands centred at the bottom, and the cards keep out of his way
    assert compose.layout("centre", 720, 1280).cx == 0.5 and compose.layout("right", 1280, 720).mirror
    bg = io.BytesIO(); Image.new("RGB", (360, 640), (90, 150, 190)).save(bg, "PNG")
    out = Image.open(io.BytesIO(compose.place(bg.getvalue(), "young", "welcome", 720, 1280, side="centre")))
    assert out.size == (720, 1280)
    top = np.asarray(out.crop((0, 0, 720, 440)), dtype=float)
    assert top.std(axis=(0, 1)).max() < 25                      # the top of the reel is backdrop only
    stat = next(i for i in cards.plan([{"type": "stat", "value": "21,000", "unit": "rupees"}], 720, 1280) if i["kind"] == "stat")
    assert stat["cy"] < 1280 * 0.45                             # above his head


def test_a_scene_is_still_made_when_the_models_fail(monkeypatch):
    """No picture model and no video credit must not stop the run: the backdrop is drawn in code and the motion falls back to the puppet."""
    from studio.skilllab import compose, store
    pid = "k-fallback"
    scene = {"n": 1, "purpose": "the start", "narration": "A small shed in 1868.", "place": "a small shed", "visual": "a loom",
             "setting": "origin", "move": "slow push in", "rival": False, "poses": ["hand on chin, thinking"], "cards": [], "dropped": 0, "warning": ""}
    store.save({"id": pid, "skill": CS.ID, "subject": "N", "aspect": "16:9", "seconds": 30, "media": "media", "status": "working", "stage": "scenes",
                "motion": "video", "characters": {"founder": "young"}, "steps": {}, "log": [], "createdAt": "x", "updatedAt": "x",
                "research": {"name": "N", "kind": "company"}, "script": {"title": "N", "scenes": [scene]}})
    from studio.series import media
    def no_model(*a, **k):
        raise RuntimeError("no picture model is ready")
    monkeypatch.setattr(media, "picture", no_model)
    CS.do_scenes(pid)
    p = store.load(pid)
    done = p["script"]["scenes"][0]
    assert done["picture"] and done["picture_model"] == "drawn in code" and done["side"] == "left"
    assert any("drew a paper set in code" in x["text"].lower() for x in p["log"])
    # a backdrop that comes back black or empty is thrown away and drawn again brighter, not pasted into the video
    import io as _io
    from PIL import Image as _Image
    def _png(c):
        b = _io.BytesIO(); _Image.new("RGB", (640, 360), c).save(b, "PNG"); return b.getvalue()
    assert "black" in compose.too_dull(_png((12, 10, 14))) and "empty" in compose.too_dull(_png((180, 170, 150)))
    assert compose.too_dull(compose.paper_scene(1280, 720, 5, "left")) == ""
    assert "MUCH BRIGHTER" in CS.BRIGHTER
    # the paper set is a real picture, not a blank sheet
    assert len(compose.paper_scene(1280, 720, 3, "left", False)) > 5000
    monkeypatch.setattr(CS, "_seedance", lambda s: True)
    from studio.stickman import video
    monkeypatch.setattr(video, "clip", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("fal.ai: no credit left")))
    CS.do_animate(pid)
    p = store.load(pid)
    assert p["script"]["scenes"][0]["video"] and p["steps"]["animate"]["status"] == "done"
    assert "paper puppet" in (p["steps"]["animate"].get("model") or "")
    assert any("Carrying on with the free paper-puppet motion" in x["text"] for x in p["log"])
    store.delete(pid)


def test_a_long_video_is_written_act_by_act(monkeypatch):
    """Twenty-five scenes cannot come from one answer: they are written in passes, each told what the earlier ones said."""
    _patch(monkeypatch)
    seen: list[str] = []
    def ask(s, who, system, prompt, log=None, **kw):
        if "research desk" in system:
            return dict(RESEARCH_ANSWER)
        if "You check a business-story script" in system:
            return {"lines": FIXED}
        seen.append(prompt)
        m = re.search(r"scenes (\d+) to (\d+)", prompt)
        return _script(int(m.group(2)) - int(m.group(1)) + 1 if m else 25)
    monkeypatch.setattr(writers, "ask", ask)
    FIXED.clear()
    r = CS.research({"id": "x", "crew": "groq"}, "Northwind Motors", None, 25)
    sc = CS.script({"id": "x", "crew": "groq"}, r, 25, secs=12)
    assert len(seen) == 4 and len(sc["scenes"]) == 25                      # 8 + 8 + 8 + 1
    assert [x["n"] for x in sc["scenes"]] == list(range(1, 26))            # numbered straight through
    titles = [c for x in sc["scenes"] for c in x["cards"] if c["type"] == "title"]
    assert len(titles) == 1 and sc["scenes"][0]["cards"][0]["type"] == "title"   # only the opening scene gets the company card
    assert "27-36 spoken words" in seen[0] and "walk the history FORWARD IN TIME" in seen[0]
    assert "Scenes already written" in seen[1] and "beat 0" in seen[1]      # each act is handed what came before
    # a long video raises the caps, so nothing the sources gave is thrown away for want of room to tell it
    short = CS.research({"id": "x", "crew": "groq"}, "Northwind Motors", None, 6)
    assert len(r["numbers"]) >= len(short["numbers"]) and len(r["milestones"]) >= len(short["milestones"])


# ---------------------------------------------------------------- ASMR Cooking
AC_RECIPE = {
    "title": "Cheese Corn Nuggets", "ingredients": ["1 cup sweet corn", "100 g mozzarella", "2 tbsp butter"], "tools": ["chef knife", "black bowl"],
    "shots": [{"title": "Raw spread", "stage": "teaser", "state": "nothing cut yet", "subject": "sweet corn and a block of mozzarella on the board",
               "action": "the gloved hands set the block down", "physics": "the block settles with a soft give",
               "asmr": "soft knock as the block lands", "camera": "top-down"},
              {"title": "Grating cheese", "stage": "prep", "state": "the corn still in its bowl behind", "subject": "a grater and the mozzarella",
               "action": "the hands draw the block down the grater", "physics": "shreds fall in a loose pile",
               "asmr": "crisp dry grating", "camera": "45-degree"},
              {"title": "Frying", "stage": "climax", "state": "the nuggets breaded and resting on the board",
               "subject": "nuggets lowered into hot oil", "action": "the hands lower a nugget into the oil",
               "physics": "oil erupts around it and the crust darkens", "asmr": "loud oil sizzle tsssss", "camera": "side"}]}


def test_asmr_cooking_locks_the_look_and_the_sound():
    from studio.skilllab import asmr_cooking as AC, foley, pipeline
    assert pipeline.SKILLS[AC.ID] is AC and pipeline.spec_of({"skill": AC.ID})["stages"] == AC.STAGES
    assert AC.INFO["aspects"] == ["9:16", "16:9"] and AC.INFO["native_audio"]
    assert (AC.shots_for(30), AC.shots_for(180)) == (7, 40) and 3.0 <= AC.seconds_each(45, AC.shots_for(45)) <= 6.0
    r = AC.norm_recipe(AC_RECIPE, "cheese corn nuggets", 3)
    assert [s["n"] for s in r["shots"]] == [1, 2, 3] and r["title"] == "Cheese Corn Nuggets"
    for sh in r["shots"]:                                    # the look is in every picture prompt, word for word
        q = AC.image_prompt(r, sh)
        assert AC.HANDS in q and AC.SURFACE in q and AC.LIGHT in q and AC.NEVER in q
        assert sh["state"] in q and sh["subject"] in q       # continuity and what is in frame are named
        assert len(q) < 1500                                 # the free picture models cut long prompts
    m = AC.motion_prompt(r["shots"][2], 4)
    assert "loud oil sizzle tsssss" in m and "No music, no voice" in m and "no face" in m.lower()
    assert "face" in AC.NEGATIVE and "watermark" in AC.NEGATIVE
    # the sound is chosen from the shot's own ASMR line
    assert [foley.cue_for(s["asmr"]) for s in r["shots"]] == ["knock", "crunch", "sizzle"]
    w = foley.wav("loud oil sizzle tsssss", 1.0)
    assert w[:4] == b"RIFF" and len(w) > 40000               # a real second of 48 kHz mono, not silence
    import numpy as np
    x = np.frombuffer(w[44:], dtype="<i2").astype(float) / 32768
    assert 0.02 < float(np.sqrt((x ** 2).mean())) < 0.6 and float(np.abs(x).max()) > 0.5


@needs_ffmpeg
def test_asmr_cooking_run_makes_the_video_without_any_paid_model(monkeypatch):
    """No fal.ai and no picture model: the run still finishes, with drawn stills, macro moves and sound made in code."""
    import io
    from PIL import Image
    from studio.skilllab import asmr_cooking as AC, store
    from studio.series import media as M
    from studio.stickman import video
    def ask(s, who, system, prompt, log=None, **kw):
        assert "ASMR cooking channel" in system and "exactly 3 shots" in prompt
        return dict(AC_RECIPE)
    monkeypatch.setattr(writers, "ask", ask)
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr(AC, "shots_for", lambda total: 3)
    def fake_picture(prompt, refs, w, h, seed, tag, s=None, negative=None, priority=5):
        assert AC.HANDS in prompt
        return _scene_png(w, h, seed), {"model": "test"}
    monkeypatch.setattr(M, "picture", fake_picture)
    monkeypatch.setattr(video, "ready", lambda s: False)
    pid = store.new_id()
    store.save({"id": pid, "skill": AC.ID, "subject": "cheese corn nuggets", "aspect": "9:16", "seconds": 30, "media": "media",
                "motion": "video", "status": "working", "stage": "recipe", "steps": {}, "log": [], "crew": "groq",
                "createdAt": store.now(), "updatedAt": store.now()})
    try:
        for st in AC.STAGES:
            AC.RUN[st](pid)
        p = store.load(pid)
        assert p["title"] == "Cheese Corn Nuggets" and len(p["recipe"]["shots"]) == 3
        assert all(sh["picture"] and sh["video"] for sh in p["recipe"]["shots"])
        assert p["video"] == "final.mp4" and (store.pdir(pid) / "final.mp4").stat().st_size > 10_000
        assert "macro move" in (p["steps"]["motion"].get("model") or "")
        assert any("macro camera move" in x["text"] for x in p["log"])      # it says what it did instead of stopping
        # the finished file has a sound track, built from the shots' ASMR lines
        import subprocess
        out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=codec_type",
                              "-of", "csv=p=0", str(store.pdir(pid) / "final.mp4")], capture_output=True, text=True).stdout
        assert "audio" in out
    finally:
        store.delete(pid)
