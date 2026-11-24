"""Ghibli Recipe Prompt: the recipe is read from a link's published recipe data or pasted text, one 15 s prompt is written, and
nothing private is ever fetched. No network, no real key."""
from __future__ import annotations

import json

import pytest

from studio.series import media, writers
from studio.skilllab import ghibli_recipe as G
from studio.skilllab import pipeline, store

LD = {"@context": "https://schema.org", "@graph": [
    {"@type": "WebSite", "name": "x"},
    {"@type": ["Recipe"], "name": "Tomato  Soup", "recipeYield": "4",
     "recipeIngredient": ["4 ripe tomatoes", "1 onion", "2 cloves garlic", "1 cup stock"],
     "recipeInstructions": [{"@type": "HowToStep", "text": "Roast the tomatoes."},
                            {"@type": "HowToSection", "itemListElement": [{"@type": "HowToStep", "text": "Fry the onion and garlic."}]},
                            "Blend with the stock."]}]}
PAGE = f'<html><script type="application/ld+json">{json.dumps(LD)}</script></html>'


def test_recipe_data_is_read_from_a_page():
    r = G.parse_recipe(PAGE)
    assert r["title"] == "Tomato Soup" and len(r["ingredients"]) == 4
    assert r["steps"] == ["Roast the tomatoes.", "Fry the onion and garlic.", "Blend with the stock."]
    assert G.parse_recipe("<html>no data</html>") is None


def test_pasted_text_and_subject():
    r = G.read_recipe("Masala chai: ginger, cardamom, tea, milk, jaggery")
    assert r["title"] == "Masala chai" and r["ingredients"] == ["ginger", "cardamom", "tea", "milk", "jaggery"] and r["source"] == "pasted"
    assert G.subject_of("https://www.example.com/recipes/paneer-butter-masala/?utm=1") == "Paneer butter masala"


def test_a_link_with_no_recipe_says_so_and_private_addresses_are_refused(monkeypatch):
    monkeypatch.setattr(G, "fetch", lambda url: "<html></html>")
    with pytest.raises(RuntimeError, match="Paste the recipe text"):
        G.read_recipe("https://example.com/x")
    monkeypatch.undo()
    for bad in ("http://127.0.0.1/x", "http://localhost/x", "http://169.254.169.254/latest", "http://192.168.1.1/", "file:///etc/passwd", "ftp://example.com/x"):
        with pytest.raises(RuntimeError, match="public web page"):
            G.fetch(bad)


def test_the_built_in_prompt_is_one_timed_continuous_scene():
    rec = G.parse_recipe(PAGE)
    t = G.template_prompt(rec, 15)
    assert G.usable(t, 15) and "Studio Ghibli" in t and "no cuts" in t and "0-4s" in t and "11-15s" in t
    assert "tomatoes" in t and "steam" in t and "No text" in t


def test_a_bad_ai_answer_falls_back_to_the_template(monkeypatch):
    rec = G.parse_recipe(PAGE)
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    calls = []
    monkeypatch.setattr(writers, "ask", lambda *a, **k: calls.append(1) or {"prompt": "Cut to scene 2. Short."})
    out = G.write_prompt({"crew": "groq"}, rec, 15)
    assert len(calls) == 2 and out == G.template_prompt(rec, 15)
    good = G.template_prompt(rec, 15)
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"prompt": f'"{good}"'})
    assert G.write_prompt({"crew": "groq"}, rec, 15) == good


def test_prompts_only_run_gives_the_prompt_and_nothing_else(monkeypatch):
    monkeypatch.setattr(G, "fetch", lambda url: PAGE)
    pid = store.new_id()
    store.save({"id": pid, "skill": G.ID, "subject": "Tomato soup", "request": "https://example.com/tomato-soup", "aspect": "16:9", "seconds": 15,
                "media": "prompts", "status": "working", "stage": "recipe", "steps": {}, "log": []})
    pipeline._run(pid, "recipe")
    p = store.load(pid)
    assert p["status"] == "done", p.get("error")
    assert p["title"] == "Tomato Soup" and "Studio Ghibli" in p["prompts"]["video"] and not p.get("video")
    pipeline.spec_of(p)["reset"](p, "prompt")
    assert "prompts" not in p and "recipe" in p


def test_media_run_makes_a_clip_even_with_no_video_model(monkeypatch):
    from studio.explainer import engines
    from studio.stickman import video
    monkeypatch.setattr(media, "picture", lambda *a, **k: (b"PNG", {"model": "stand-in"}))
    monkeypatch.setattr(video, "ready", lambda s: False)
    monkeypatch.setattr(engines, "keypose", lambda s, a, b, secs, kind: b"MP4")
    pid = store.new_id()
    store.save({"id": pid, "skill": G.ID, "subject": "Chai", "request": "Masala chai: ginger, cardamom, tea, milk", "aspect": "16:9", "seconds": 10,
                "media": "media", "status": "working", "stage": "recipe", "steps": {}, "log": []})
    pipeline._run(pid, "recipe")
    p = store.load(pid)
    assert p["status"] == "done", p.get("error")
    assert p["video"] == "scene.mp4" and p["engine"] == "camera move on the key frame" and "10-second" in p["prompts"]["video"]
    assert G.outputs_of(p)[0]["file"] == "scene.mp4"
