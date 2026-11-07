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
                "By 1984 it was exporting to Europe and fought a price war with Atlas Auto. It employs 210,000 people and had revenue of $44 billion in 2023."}]
RESEARCH_ANSWER = {"name": "Northwind Motors", "kind": "company", "founded": "1937", "founder": "Ada Lane", "origin": "A garage in Ohio.",
                   "milestones": [{"year": "1955", "event": "First factory opens.", "source": 1}, {"year": "1999", "event": "Invented milestone.", "source": 1}],
                   "numbers": [{"value": "210,000", "label": "employees", "source": 1}, {"value": "$44 billion", "label": "revenue", "year": "2023", "source": 1},
                               {"value": "9,999", "label": "invented", "source": 1}],
                   "how_it_works": ["It sells cars."], "rivals": ["Atlas Auto"], "turning_points": ["The 1984 price war."]}


def _script(n):
    sc = [{"purpose": f"beat {i}", "narration": "From one garage in 1937 to a giant with 210,000 people.", "visual": "the founder points at factories",
           "setting": "city", "move": "slow push in", "cards": [{"type": "stat", "value": "210,000", "unit": "employees"}, {"type": "stat", "value": "$77B", "unit": "made up"},
                                                               {"type": "caption", "text": "All from one garage", "accent": "garage"}]} for i in range(n)]
    sc[1]["cards"].append({"type": "vs", "left": "Northwind", "right": "Atlas Auto"})
    sc[2]["narration"] = "In 2011 it sold 5 million cars."            # numbers the research doesn't have
    return {"title": "From a Garage to $44 Billion", "scenes": sc}


def cs_ask(s, who, system, prompt, log=None, **kw):
    if "research desk" in system:
        return dict(RESEARCH_ANSWER)
    return _script(int(re.search(r"exactly (\d+) scenes", system).group(1)))


def test_research_keeps_only_numbers_in_the_sources(monkeypatch):
    from studio.explainer import research as R
    monkeypatch.setattr(R, "find", lambda q, limit=3: SRC if not q.startswith("History") else (_ for _ in ()).throw(R.ResearchError("none")))
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr(writers, "ask", cs_ask)
    r = CS.research({"id": "x", "crew": "groq"}, "Northwind Motors")
    assert r["founded"] == "1937" and [m["year"] for m in r["milestones"]] == ["1955"]          # 1999 isn't in the source
    assert [n["value"] for n in r["numbers"]] == ["210,000", "$44 billion"] and r["sources"][0]["url"].startswith("https://")
    sc = CS.norm_script(_script(6), r, 6)
    s1 = sc["scenes"][0]
    assert s1["cards"][0]["type"] == "title" and s1["cards"][0]["years"].startswith("1937 – ")      # the title card is always there, years computed
    assert all(c.get("value") != "$77B" for x in sc["scenes"] for c in x["cards"]) and s1["dropped"] == 1
    assert any(c["type"] == "vs" for c in sc["scenes"][1]["cards"]) and sc["scenes"][1]["rival"]
    assert sc["scenes"][2]["warning"] and not sc["scenes"][0]["warning"]


def test_cards_count_up_and_draw():
    assert cards.counted("210,000", 0.5) == "105,000" and cards.counted("$44B", 1) == "$44B" and cards.counted("4.5%", 1) == "4.5%"
    layer = cards.overlay([{"type": "title", "text": "Northwind Motors", "years": "1937 – 2026"}, {"type": "stat", "value": "210,000", "unit": "employees"},
                           {"type": "caption", "text": "All from one garage", "accent": "garage"}, {"type": "vs", "left": "A", "right": "B"}], 1280, 720, 3.0)
    assert layer.size == (1280, 720) and layer.getbbox()


def test_scene_prompts_have_no_text_and_no_real_likeness():
    r = {"name": "Northwind Motors", "founded": "1937"}
    p = CS.sheet_prompt(r, "founder")
    assert "Not a portrait or likeness of any real person" in p and "No text" in p and "round wire glasses" in p
    q = CS.scene_prompt(r, {"visual": "points at factories", "purpose": "scale", "setting": "factory"}, True)
    assert "Image 1" in q and "Image 2" in q and "No text, no letters, no numbers" in q


@needs_ffmpeg
def test_company_story_run_makes_the_video(monkeypatch):
    import io
    from PIL import Image
    from studio.explainer import pipeline as xp
    from studio.explainer import research as R
    monkeypatch.setattr(R, "find", lambda q, limit=3: SRC)
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr(writers, "ask", cs_ask)
    pics = []

    def fake_picture(prompt, refs, w, h, seed, tag, priority=5, s=None, negative=None):
        pics.append((tag, len(refs)))
        b = io.BytesIO(); Image.new("RGB", (w // 8, h // 8), (90, 160, 90)).save(b, "PNG"); return b.getvalue(), {"model": "stand-in"}

    monkeypatch.setattr(media, "picture", fake_picture)
    monkeypatch.setattr(xp, "_voice", lambda s, text, p: (media.silence(2.0), {"model": "silence"}))
    monkeypatch.setattr(media, "music", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no music model")))
    pid = store.new_id()
    store.save({"id": pid, "skill": CS.ID, "subject": "Northwind Motors", "aspect": "16:9", "seconds": 30, "media": "media", "status": "working",
                "stage": "research", "steps": {}, "log": [], "crew": "groq"})
    pipeline._run(pid, "research")
    p = store.load(pid)
    assert p["status"] == "done", p.get("error")
    assert len(p["script"]["scenes"]) == 3 and all(sc["video"] for sc in p["script"]["scenes"])
    assert ("%s-founder" % pid, 0) in pics and ("%s-S2" % pid, 2) in pics             # scene 2 has the rival: drawn from both sheets
    assert p["video"] == "final.mp4" and media.probe_seconds(store.pdir(pid) / "final.mp4") >= 29
    store.update(pid, lambda q: CS.reset(q, "scenes", 2))
    q = store.load(pid)
    assert q["script"]["scenes"][1]["picture"] is None and q["script"]["scenes"][0]["picture"] and not q.get("video")
