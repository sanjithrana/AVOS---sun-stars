"""Blender route: shot description -> scene plan -> render service."""

import asyncio
import json
import random

import httpx
import pytest

from agentic_core.models.video import blender_provider
from agentic_core.models.video.blender_provider import BlenderVideoProvider
from agentic_core.models.video.factory import get_video_provider
from agentic_core.pipelines.blender.planner import DEFAULT_CATALOG, keyword_plan, plan_scene, sanitize


def _run(coro):
    return asyncio.run(coro)


def test_keyword_plan_fight_with_giant():
    plan = keyword_plan("A man punches a giant gorilla", DEFAULT_CATALOG, random.Random(1))
    assert [a["variant"] for a in plan["actors"]] == ["man", "giant"]
    assert plan["actors"][0]["action"] == "punch" and plan["actors"][1]["action"] == "fight_idle"
    assert plan["actors"][0]["facing"] > 0 > plan["actors"][1]["facing"]  # facing each other
    assert plan["camera"]["move"] == "orbit"


def test_keyword_plan_environment_crowd_props_and_movement():
    assert keyword_plan("An astronaut jumps on the Moon", DEFAULT_CATALOG, random.Random(1))["environment"] == "space"
    crowd = keyword_plan("100 men run across the desert", DEFAULT_CATALOG, random.Random(1))
    assert crowd["environment"] == "desert" and len(crowd["actors"]) == 5
    assert crowd["actors"][0].get("move_to") and crowd["camera"]["move"] == "track"
    gold = keyword_plan("A gold bar falls from the sky", DEFAULT_CATALOG, random.Random(1))
    assert gold["props"][0]["type"] == "gold_bar" and gold["props"][0]["motion"] == "fall"
    # 'wide shot' / 'storybook' must not turn into bullets or suns
    assert keyword_plan("A woman waves, wide shot, storybook style", DEFAULT_CATALOG,
                        random.Random(1))["props"] == []


def test_sanitize_clamps_unknown_names_and_ranges():
    plan = sanitize({
        "environment": "jungle",
        "actors": [{"asset": "spiderman", "variant": "alien", "action": "Boxing", "position": [99, -50],
                    "facing": 900, "scale": 40, "color": "red", "move_to": [1, 2]}],
        "props": [{"type": "spaceship"}, {"type": "Gold_Bar", "position": [0, 0, 99], "motion": "warp"}],
        "camera": {"shot": "extreme", "move": "dolly_zoom"},
    }, DEFAULT_CATALOG)
    actor = plan["actors"][0]
    assert plan["environment"] == "grid_studio"
    assert actor["asset"] == "mannequin" and actor["variant"] == "man" and actor["action"] == "punch"
    assert actor["position"] == [3, -1] and actor["facing"] == 180 and actor["scale"] == 3.0
    assert "color" not in actor and actor["move_to"] == [1, 2]
    assert [p["type"] for p in plan["props"]] == ["gold_bar"]
    assert plan["props"][0]["position"][2] == 12 and plan["props"][0]["motion"] == "none"
    assert plan["camera"] == {"shot": "wide", "move": "push_in", "target": "a1"}


def test_library_assets_are_allowed_when_the_service_has_them():
    catalog = {**DEFAULT_CATALOG, "library_characters": ["remy"], "library_animations": ["hook_punch"]}
    plan = sanitize({"actors": [{"asset": "remy", "action": "hook_punch"}]}, catalog)
    assert plan["actors"][0]["asset"] == "remy" and plan["actors"][0]["action"] == "hook_punch"


class FakeLLM:
    name = "groq"

    def __init__(self, reply):
        self.reply = reply
        self.prompts = []

    async def complete(self, prompt, *, system=None, **kw):
        self.prompts.append(prompt)
        return self.reply


def test_plan_scene_uses_llm_json_and_falls_back_on_garbage():
    llm = FakeLLM("```json\n" + json.dumps({
        "environment": "desert", "actors": [{"id": "a1", "asset": "mannequin", "variant": "kid", "action": "dance",
                                             "position": [0, 0], "facing": 0}],
        "props": [], "camera": {"shot": "close", "move": "push_in", "target": "a1"}}) + "\n```")
    plan = _run(plan_scene("a kid dances", llm=llm, duration=3.2, seed=4))
    assert plan["planner"] == "groq" and plan["environment"] == "desert" and plan["duration"] == 3.2
    assert "CATALOG" in llm.prompts[0] and "dance" in llm.prompts[0]

    bad = _run(plan_scene("a man punches a giant", llm=FakeLLM("sorry, I can't"), duration=3))
    assert bad["planner"] == "keywords" and len(bad["actors"]) == 2

    hinted = _run(plan_scene("a man waves", llm=None, environment_hint="night_city_floor"))
    assert hinted["environment"] == "night_city_floor"


def test_factory_blender(monkeypatch):
    monkeypatch.setenv("BLENDER_RENDER_URL", "http://bl:8090")
    provider = get_video_provider("blender", llm_provider="mock")
    assert isinstance(provider, BlenderVideoProvider) and provider.base_url == "http://bl:8090"


def test_blender_provider_plans_posts_and_returns_clip(monkeypatch):
    posted = {}
    real = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/catalog":
            return httpx.Response(200, json=DEFAULT_CATALOG)
        posted.update(json.loads(request.content))
        return httpx.Response(200, content=b"\x00\x00\x00\x18ftypmp42blender")

    monkeypatch.setattr(blender_provider.httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))
    provider = BlenderVideoProvider("http://bl:8090", llm=None)
    prompt = ("A man punches a giant gorilla. Setting: main setting. Camera: wide shot, 24mm lens. "
              "Style: 3D. Motion: smooth.")
    clip = _run(provider.generate(prompt, seed=9, duration_seconds=4.4))
    assert clip.endswith(b"blender")
    assert posted["duration"] == 4.4 and len(posted["actors"]) == 2 and posted["props"] == []


def test_blender_provider_explains_service_down(monkeypatch):
    real = httpx.AsyncClient

    def handler(request):
        raise httpx.ConnectError("refused", request=request)

    monkeypatch.setattr(blender_provider.httpx, "AsyncClient",
                        lambda *a, **k: real(*a, **{**k, "transport": httpx.MockTransport(handler)}))
    with pytest.raises(RuntimeError, match="docker compose up -d blender"):
        _run(BlenderVideoProvider("http://bl:8090").generate("a man waves"))


def test_keyword_plan_prefers_library_characters_named_after_variants():
    catalog = {**DEFAULT_CATALOG, "library_characters": ["man", "giant"]}
    plan = keyword_plan("A man punches a giant gorilla", catalog, random.Random(1))
    assert [a["asset"] for a in plan["actors"]] == ["man", "giant"]
