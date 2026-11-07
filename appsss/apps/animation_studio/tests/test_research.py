import json

import pytest

from studio.explainer import planner, research

PAGES = [{"title": "Eddy current", "url": "https://en.wikipedia.org/wiki/Eddy_current",
          "text": "An eddy current is a loop of electric current induced within conductors by a changing magnetic field in the conductor. "
                  "Eddy currents flow in closed loops within conductors, in planes perpendicular to the magnetic field. "
                  "They can be induced within nearby stationary conductors by a time-varying magnetic field. " * 2},
         {"title": "Lenz's law", "url": "https://en.wikipedia.org/wiki/Lenz%27s_law",
          "text": "Lenz's law states that the direction of the electric current induced in a conductor by a changing magnetic field is such that the magnetic field created by the induced current opposes the initial changing magnetic field. " * 2}]


def _s(crew="builtin"):
    return {"id": "x", "crew": crew, "language": "en", "brief": "how a magnet falls in a copper pipe", "seconds": 30, "aspect": "9:16"}


def test_clean_topic_and_wikipedia_reply_parsing(monkeypatch):
    assert research._clean("How does a magnet fall in a copper pipe?") == "a magnet fall in a copper pipe"
    reply = {"query": {"pages": [{"title": "B", "index": 2, "fullurl": "https://en.wikipedia.org/wiki/B", "extract": "x" * 300},
                                 {"title": "A", "index": 1, "fullurl": "https://en.wikipedia.org/wiki/A", "extract": "y" * 300},
                                 {"title": "short", "index": 3, "fullurl": "https://en.wikipedia.org/wiki/S", "extract": "tiny"},
                                 {"title": "bad", "index": 4, "fullurl": "http://evil.example/x", "extract": "z" * 300}]}}
    monkeypatch.setattr(research, "_get", lambda params: reply)
    got = research.find("magnet copper pipe")
    assert [p["title"] for p in got] == ["A", "B"]                       # ordered by search rank; short and non-https dropped


def test_no_ai_writer_uses_sourced_opening_sentences(monkeypatch):
    monkeypatch.setattr(research, "find", lambda t, limit=3: PAGES)
    r = research.run(_s(), "magnets and copper")
    assert r["status"] == "ok" and len(r["facts"]) >= 3
    assert all(f["source"]["url"].startswith("https://en.wikipedia.org/") for f in r["facts"])


def test_ai_facts_are_checked_against_the_sources(monkeypatch):
    monkeypatch.setattr(research, "find", lambda t, limit=3: PAGES)
    answer = {"research_questions": ["Why is it slow?"], "misconceptions": ["Copper is magnetic"],
              "verified_facts": [{"fact": "A moving magnet induces circulating currents in copper.", "source": 1},
                                 {"fact": "The induced field opposes the magnet's motion.", "source": 2},
                                 {"fact": "Energy is lost mostly as heat in the pipe.", "source": 1},
                                 {"fact": "A made up fact from a source that does not exist.", "source": 9}]}
    monkeypatch.setattr(research.writers, "ask", lambda *a, **k: answer)
    r = research.run(_s("ollama"), "magnets and copper")
    assert r["status"] == "ok" and len(r["facts"]) == 3                  # the fact citing source 9 is dropped
    assert r["misconceptions"] == ["Copper is magnetic"]


def test_unusable_ai_answer_falls_back_and_web_failure_is_a_soft_skip(monkeypatch):
    monkeypatch.setattr(research, "find", lambda t, limit=3: PAGES)
    monkeypatch.setattr(research.writers, "ask", lambda *a, **k: {"verified_facts": []})
    assert research.run(_s("ollama"), "magnets")["status"] == "ok"      # opening sentences
    def boom(t, limit=3):
        raise research.ResearchError("couldn't reach Wikipedia (Network is unreachable)")
    monkeypatch.setattr(research, "find", boom)
    r = research.run(_s(), "magnets")
    assert r["status"] == "skipped" and "Network is unreachable" in r["reason"] and research.facts_block(r) == ""


def test_the_script_prompt_carries_the_facts(monkeypatch):
    seen = {}
    monkeypatch.setattr(research, "find", lambda t, limit=3: PAGES)
    r = research.run(_s(), "magnets")
    def fake(s, who, system, prompt, *a, **k):
        seen["prompt"] = prompt
        return None
    monkeypatch.setattr(planner.writers, "ask", fake)
    planner.plan({**_s(), "research": r})
    assert "Verified facts" in seen["prompt"] and "eddy current" in seen["prompt"].lower()
