"""Pick a model and only that model runs: no silent fallback to other models, the free picture chain or a still stand-in."""
from __future__ import annotations

import pytest

from studio import models
from studio.explainer import engines
from studio.series import media


def S(motion="auto", pictures="auto", local=False, backend=None):
    m = {"motion": {"model": motion}, "pictures": {"model": pictures}}
    if backend:
        m["motion"]["backend"] = backend
    return {"id": "x", "settings": {"models": m, "local_only": local}, "format": {"width": 720, "height": 1280}}


def test_strict_order_is_only_your_model():
    assert media.ordered(S(motion="ltx-2.3"), "motion", ["wan-2.2", "ltx-2.3"]) == ["ltx-2.3"]
    assert media.ordered(S(), "motion", ["wan-2.2", "ltx-2.3"]) == ["wan-2.2", "ltx-2.3"]


def test_picture_choice_never_reaches_other_providers(monkeypatch):
    tried = []
    monkeypatch.setattr(models, "image", lambda mid, *a, **k: tried.append(mid) or (_ for _ in ()).throw(RuntimeError("fal.ai: no credit")))
    monkeypatch.setattr(media, "_ready", lambda mid: True)
    monkeypatch.setattr(media, "where", lambda s, st, mid: None)
    with pytest.raises(media.Fallback) as e:
        media._t2i("a potato", 64, 64, 1, s=S(pictures="z-image"))
    assert tried == ["z-image"] and "not tried" in str(e.value).lower()


def test_local_only_refuses_cloud(monkeypatch):
    monkeypatch.setattr(models, "available", lambda mid: {"gpu": "No GPU worker is online", "fal": None, "cloudflare": None})
    with pytest.raises(models.ModelUnavailable) as e:
        media.where(S(motion="ltx-2.3", local=True), "motion", "ltx-2.3")
    assert "NOT tried" in str(e.value) and "GPU worker" in str(e.value)
    monkeypatch.setattr(models, "available", lambda mid: {"gpu": None, "fal": None})
    assert media.where(S(motion="ltx-2.3", local=True), "motion", "ltx-2.3") == "gpu"


def test_chosen_video_model_failing_does_not_become_a_still(monkeypatch):
    monkeypatch.setattr(models, "available", lambda mid: {"gpu": "No GPU worker is online", "fal": None})
    shot = {"camera": {"movement": "static"}, "sfx": ""}
    with pytest.raises(media.Fallback) as e:
        engines.ai_video(S(motion="ltx-2.3", local=True), shot, b"x", 4.0, 1, "p", "t")
    assert "Nothing else was tried" in str(e.value)
    assert engines.capabilities(S(motion="ltx-2.3", local=True))["ai_video"] is True


def test_animation_prompt_is_image_first():
    p = {"plan": {"characters": [{"id": "c1", "name": "Dr Magnetics"}], "props": [{"id": "p1", "name": "magnet"}]}}
    shot = {"action": "The magnet falls slowly down the pipe.", "characters": ["c1"], "props": ["p1"], "visualization": {"force_arrows": True}}
    t = engines.motion_prompt(engines.animation_prompt(p, shot), "push in", "")
    assert t.startswith("Starting from the attached image.") and "Camera: push in" in t and "no morphing" in t and "magnet" in t


def test_contact_sheet_is_numbered_and_sized():
    import io
    from PIL import Image
    from studio.explainer import contactsheet
    png = io.BytesIO(); Image.new("RGB", (90, 160), (200, 80, 40)).save(png, "PNG")
    out = contactsheet.build([(f"S{i:02d}", png.getvalue() if i != 4 else None) for i in range(1, 7)], "Test")
    im = Image.open(io.BytesIO(out))
    assert im.width > 3 * 300 and im.height > 300
    assert "0-" in engines.beats(4) and "hold" in engines.beats(4)


def test_article_extract_and_private_addresses_refused():
    import pytest as _pt
    from studio.explainer import article
    html = ("<html><head><title>T</title></head><body><nav><p>Menu menu menu menu menu menu menu menu menu</p></nav><h1>How magnets work</h1>"
            + "".join(f"<p>{'Magnets pull on iron because of aligned atomic spins and fields number ' + str(i)}.</p>" for i in range(12))
            + "<script>var x=1</script></body></html>")
    a = article.extract(html, "http://example.com/x")
    assert a["title"] == "How magnets work" and "Menu menu" not in a["text"] and a["words"] > 60
    assert article.excerpt(a, 300).startswith("Title: How magnets work")
    for bad in ("http://127.0.0.1/", "http://localhost:8001/x", "file:///etc/passwd", "ftp://example.com/", "http://10.0.0.5/", "http://169.254.169.254/latest"):
        with _pt.raises(article.ArticleError):
            article.check_url(bad)


def test_no_video_clips_and_estimate():
    from studio.explainer import cost
    assert engines.capabilities(S(motion="off"))["ai_video"] is False
    free = cost.estimate(30, S(local=True))
    assert free["usd_high"] == 0
    paid = cost.estimate(30, S(motion="ltx-2.3"))
    assert paid["usd_high"] > paid["usd_low"] > 0


def test_voice_catalog_filters_and_ids():
    from studio.explainer import voices
    voices._cache.update(t=__import__("time").time(), voices=[
        voices._parse({"ShortName": "hi-IN-SwaraNeural", "Gender": "Female", "Locale": "hi-IN", "FriendlyName": "Microsoft Swara Online (Natural) - Hindi (India)"}),
        voices._parse({"ShortName": "en-US-GuyNeural", "Gender": "Male", "Locale": "en-US", "FriendlyName": "Microsoft Guy Online (Natural) - English (United States)"})])
    assert [v["name"] for v in voices.search(language="hi")] == ["Swara"]
    assert [v["name"] for v in voices.search(language="English")] == ["Guy"]
    assert voices.search(gender="male")[0]["dialect"] == "United States"
    assert voices.valid_id("hi-IN-SwaraNeural") and not voices.valid_id("x; rm -rf /") and not voices.valid_id("../../etc")


def test_direct_look_resets_pictures_but_keeps_voice_and_music(tmp_path, monkeypatch):
    from studio.explainer import pipeline, planner, store
    monkeypatch.setattr(store, "ROOT", tmp_path)
    plan = planner.plan({"brief": "Why straw potato", "seconds": 20, "aspect": "9:16", "language": "en", "id": "d1", "crew": "builtin"})
    p = {"id": store.new_id(), "brief": "x", "title": "x", "seconds": 20, "aspect": "9:16", "language": "en", "crew": "builtin", "auto": True, "style": "",
         "voice": "male", "models": {}, "status": "done", "stage": "finish", "plan": plan, "assets": {"world": "assets/world.png"}, "log": [],
         "final": "final.mp4", "createdAt": store.now(), "updatedAt": store.now()}
    for sh in p["plan"]["shots"]:
        sh["frame"], sh["clip"] = "f.png", "c.mp4"
    store.save(p)
    d = store.pdir(p["id"])
    (d / "music_keep.wav").write_bytes(b"x")
    (d / "shots" / p["plan"]["shots"][0]["id"]).mkdir(parents=True)
    (d / "shots" / p["plan"]["shots"][0]["id"] / "line.wav").write_bytes(b"x")
    pipeline.reset_look(p["id"], "vivid magenta and sky blue palette")
    q = store.load(p["id"])
    assert q["style"].startswith("vivid magenta") and q["assets"] == {} and q["final"] is None
    assert all(s["frame"] is None and s["clip"] is None and s["version"] == 2 for s in q["plan"]["shots"])
    assert (d / "music_keep.wav").is_file() and (d / "shots" / q["plan"]["shots"][0]["id"] / "line.wav").is_file()
    assert engines.look(q).startswith("vivid magenta") and engines.look({"plan": {"style": "BBC documentary"}}) == "BBC documentary"


def test_director_fields_and_prompts():
    from studio.explainer import planner, spec
    data = {"characters": [{"name": "Nini", "look": "baby emperor penguin plush, grey fur, tilted birthday hat"}, {"name": "Koro", "look": "adult emperor penguin plush"}],
            "props": [], "shots": [
                {"scene": 1, "scene_title": "The cake", "mood": "warm golden afternoon light", "emotion": "joy", "narration": "Today is the day.",
                 "action": "Nini bursts out of the ice house door in her tilted hat.", "characters": ["nini"]},
                {"scene": 2, "scene_title": "The crack", "mood": "cold blue", "emotion": "loss", "narration": "It is gone.", "action": "The cake slides into the crack.", "characters": ["nini", "koro"]}]}
    plan = spec.norm_plan(data, 20, "16:9")
    a, b = plan["shots"][0], plan["shots"][1]
    assert (a["scene"], b["scene"], b["scene_title"]) == (1, 2, "The crack")
    p = {"plan": plan, "style": ""}
    t = engines.shot_prompt(p, a)
    assert "warm golden" in t and "only these characters are in the picture: Nini" in t and "tilted birthday hat" in t
    assert "cold blue" in engines.animation_prompt(p, b)
    assert "scene_title" in planner.DIRECTOR_RULES and "Never add characters" in planner.DIRECTOR_RULES
