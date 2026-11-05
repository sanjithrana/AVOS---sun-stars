import io

import pytest
from PIL import Image

from studio.explainer import engines, planner, prompts, quality, spec


@pytest.fixture(autouse=True)
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("AVOS_EXPLAINER_PROMPTS", str(tmp_path / "prompts.json"))


def _png(c, w=96, h=96, noise=False):
    im = Image.new("RGB", (w, h), c)
    if noise:
        for x in range(0, w, 3):
            for y in range(0, h, 3):
                im.putpixel((x, y), (255 - c[0], (x * 7) % 256, (y * 5) % 256))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _photo():
    im = Image.new("RGB", (96, 96))
    for x in range(96):
        for y in range(96):
            im.putpixel((x, y), (40 + x * 2, 60 + y, 150 - x if (x // 12 + y // 12) % 2 else 30 + y))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _use(key, v, outcomes, flag="too_dark"):
    for o in outcomes:
        prompts.record(key, v, o, [flag] if o == "flag" else [], "a prompt", "")


def test_library_has_every_prompt_with_a_default():
    lib = prompts.library()
    keys = {i["key"] for i in lib["items"]}
    assert {"director.rules", "picture.base", "picture.recipe.macro_close_up", "motion.keep", "sheet.character", "poster.tail"} <= keys
    text, v = prompts.pick("picture.base", "x1")
    assert v == 1 and text == prompts.default("picture.base")


def test_prompt_faults_are_not_confused_with_network_or_billing():
    assert prompts.is_prompt_fault("flux-schnell: content blocked by safety filter")
    assert prompts.is_prompt_fault("prompt too long: exceeds 2000 characters")
    for infra in ("flux-schnell: [Errno 101] Network is unreachable", "fal: no credit left (Exhausted balance)",
                  "401 Unauthorized: bad api key", "No picture model could draw it (set up Qwen-Image-Edit on a GPU worker)", "429 quota used up"):
        assert not prompts.is_prompt_fault(infra)


def test_rejected_results_count_but_never_beyond_the_uses():
    _use("picture.base", 1, ["ok", "ok", "flag"])
    prompts.record("picture.base", 1, "redo")
    prompts.record("picture.base", 1, "down")
    prompts.record("picture.base", 1, "down")                       # more rejections than uses cannot exceed 100%
    a = next(i for i in prompts.library()["items"] if i["key"] == "picture.base")["active"]
    assert a["uses"] == 3 and a["bad"] == 3 and a["bad_rate"] == 1.0 and a["down"] == 2


def test_a_prompt_that_keeps_failing_gets_an_improved_candidate_that_is_tested_then_promoted():
    _use("picture.recipe.macro_close_up", 1, ["flag"] * 4 + ["ok"] * 4)       # 50% too dark
    msgs = prompts.learn(None)
    assert msgs and "testing v2" in msgs[0]
    item = next(i for i in prompts.library()["items"] if i["key"] == "picture.recipe.macro_close_up")
    cand = item["candidate"]
    assert cand and cand["v"] == 2 and "brightly and evenly lit" in cand["text"] and cand["source"] == "learned"
    pids = [f"x{i}" for i in range(40)]
    got = {prompts.pick("picture.recipe.macro_close_up", p)[1] for p in pids}
    assert got == {1, 2}                                                       # about half of the projects test the new one
    assert prompts.pick("picture.recipe.macro_close_up", "x3") == prompts.pick("picture.recipe.macro_close_up", "x3")
    _use("picture.recipe.macro_close_up", 2, ["ok"] * 6)
    msgs = prompts.learn(None)
    assert any("won" in m for m in msgs)
    assert prompts.pick("picture.recipe.macro_close_up", "x1")[1] == 2         # promoted for everyone


def test_a_candidate_that_is_not_better_is_dropped_and_not_retried_at_once():
    _use("picture.base", 1, ["flag"] * 4 + ["ok"] * 4)
    prompts.learn(None)
    _use("picture.base", 2, ["flag"] * 4 + ["ok"] * 2)
    assert any("not better" in m for m in prompts.learn(None))
    item = next(i for i in prompts.library()["items"] if i["key"] == "picture.base")
    assert item["active"]["v"] == 1 and item["candidate"] is None
    assert prompts.learn(None) == []                                           # cooldown: needs six more uses before another try


def test_nothing_happens_before_enough_results_or_when_results_are_good():
    _use("picture.base", 1, ["flag"] * 3)
    assert prompts.learn(None) == []
    _use("poster.tail", 1, ["ok"] * 10)
    assert prompts.learn(None) == []


def test_ai_writer_improvement_is_validated(monkeypatch):
    from studio.series import writers
    key = "sheet.character"
    cur = prompts.default(key)
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"text": cur + " Keep the face symmetrical and fully visible in every view.", "why": "faces were off-model"})
    _use(key, 1, ["flag"] * 4 + ["ok"] * 2, "flat")
    assert prompts.learn({"id": "x"}) and prompts.library()["items"][-2]["candidate"]["text"].startswith(cur)
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"text": "Draw a character sheet.", "why": "short"})          # drops {name}/{look}/{style}
    out = prompts._ai_improve({"id": "x"}, key, cur, prompts._load()["keys"][key]["versions"][0], None)
    assert out is None


def test_user_notes_become_concrete_fixes_without_an_ai_writer():
    x = {"flags": {}, "examples": [{"outcome": "down", "flags": [], "note": "the hands are wrong and it is blurry", "prompt": "p"}]}
    text, why = prompts.heuristic_fix("extreme close-up, macro lens", x)
    assert "five fingers" in text and "sharp focus" in text and why.startswith("added")


def test_you_can_edit_restore_and_reset_a_prompt():
    prompts.set_text("picture.base", "cinematic, warm light, crisp detail", "my taste")
    assert prompts.pick("picture.base", "p")[0] == "cinematic, warm light, crisp detail"
    prompts.restore("picture.base", 1)
    assert prompts.pick("picture.base", "p")[1] == 1
    with pytest.raises(ValueError):
        prompts.set_text("sheet.character", "A character sheet with no placeholders at all.")
    with pytest.raises(ValueError):
        prompts.set_text("picture.base", "short")
    prompts.reset("picture.base")
    assert prompts.pick("picture.base", "p")[0] == prompts.default("picture.base")


def test_shot_prompt_uses_the_library_recipe_and_reports_what_it_used():
    pl = spec.norm_plan(planner.builtin("a magnet in a copper pipe", 30, "16:9"), 30, "16:9")
    shot = next(s for s in pl["shots"] if s["shot_type"] == "macro_close_up")
    p = {"id": "x9", "plan": pl}
    text, used = engines.shot_prompt_used(p, shot)
    assert prompts.default("picture.recipe.macro_close_up") in text and prompts.default("picture.base") in text
    assert ["picture.recipe.macro_close_up", 1] in used and ["picture.base", 1] in used
    prompts.set_text("picture.recipe.macro_close_up", "macro, glowing copper, crisp")
    assert "glowing copper" in engines.shot_prompt(p, shot)
    assert engines.motion_prompt("a hand moves", "push in", "", "x9").endswith(prompts.default("motion.keep"))


def test_picture_check_flags_dark_flat_duplicate_and_survives_junk():
    assert "too_dark" in quality.check(_png((5, 5, 5), noise=True))["flags"]
    assert "too_bright" in quality.check(_png((252, 252, 252)))["flags"]
    assert "flat" in quality.check(_png((120, 120, 120)))["flags"]
    good = quality.check(_photo())
    assert good["flags"] == []
    assert "duplicate" in quality.check(_photo(), [good["hash"]])["flags"]
    assert quality.check(b"not an image")["flags"] == []
