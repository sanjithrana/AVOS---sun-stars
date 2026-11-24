"""The house director (studio/house.py): one set of film rules shared by the Explainer, Stickman and every skill."""
from __future__ import annotations

import inspect

from studio import house
from studio.explainer import planner as ex_planner, prompts as ex_prompts, spec as ex_spec
from studio.series import film, writers
from studio.skilllab import asmr_cooking, company_story, film_style
from studio.stickman import planner as st_planner, spec as st_spec


def test_every_sections_camera_words_become_one_vocabulary():
    assert {house.size_of(x) for x in ("close_up", "CU", "tight close-up on the hands", "close")} == {"close"}
    assert house.size_of("macro_close_up") == house.size_of("extreme-close") == "extreme_close"
    assert house.size_of("top_down") == house.size_of("overhead") == "overhead"
    assert house.size_of("medium wide shot") == "medium" and house.size_of("wide") == "wide"
    assert house.move_of("slow push in") == house.move_of("push_in") == "push_in"
    assert house.move_of("pan left") == house.move_of("pan_right") == "pan"
    assert house.move_of("") == "static"


def test_the_review_finds_what_a_director_would_send_back():
    cards = [house.card(1, "a kitchen", "held still", "wide", "static"),
             house.card(2, "hands", "she realises the dough is ready, then folds it over twice", "close", "push in"),
             house.card(3, "a knife", "the knife drops through the onion", "close_up", "push_in")]
    kinds = [(n, k) for n, k, _ in house.review(cards)]
    assert (1, "flat_opening") in kinds and (2, "two_actions") in kinds and (2, "not_visible") in kinds and (3, "same_framing") in kinds


def test_a_sound_plan_passes_clean():
    cards = [house.card(1, "a kitchen", "steam bursts from the pot lid", "wide", "push_in"),
             house.card(2, "hands", "a knife drops through the onion", "close", "static"),
             house.card(3, "the plate", "sauce pours over the rice", "overhead", "static")]
    assert house.review(cards) == []
    assert "passes" in house.note_of([])


def test_unrepeat_changes_as_little_as_possible_and_never_makes_a_new_repeat():
    vals, n = house.unrepeat(["a", "a", "b", "b", "b"], ["a", "b", "c"])
    assert n and all(x != y for x, y in zip(vals, vals[1:]))
    assert house.unrepeat(["a", "b", "a"], ["a", "b"]) == (["a", "b", "a"], 0)


def test_same_distance_and_same_move_in_a_row_gets_a_new_move_only():
    moves, n = house.unrepeat_framing(["close", "close_up", "wide", "wide"], ["push_in", "push_in", "static", "pan_left"], ex_spec.CAMERA_MOVES)
    assert n == 1 and moves[0] == "push_in" and house.move_of(moves[1]) != "push_in" and moves[2:] == ["static", "pan_left"]


def test_fit_keeps_the_shot_whatever_the_look_costs():
    out = house.fit("LOOK " * 200, "In frame: a brass dial closing to zero.", "extra " * 300, "No text.", 900)
    assert len(out) <= 900 and "a brass dial closing to zero" in out and out.endswith("No text.")
    assert film_style._fit is house.fit and film_style._trim is house.trim      # Film Style uses the shared one now


def test_the_rules_are_safe_inside_format_strings_and_short():
    assert "{" not in house.HOUSE and "}" not in house.HOUSE       # several planners build prompts with str.format
    assert len(house.rules()) < 1200                               # sent with every plan: about 200 tokens, not more


def test_only_planners_get_the_house_rules():
    plain, planned = writers.system("avos-nobody", "ROLE"), writers.directed("avos-nobody", "ROLE")
    assert "HOUSE RULES" not in plain and planned.startswith(plain) and "HOUSE RULES" in planned
    for fn in (ex_planner.plan, film_style.plan_for, asmr_cooking.recipe, company_story.script):
        assert "writers.directed(" in inspect.getsource(fn), fn.__name__
    src = inspect.getsource(st_planner)
    assert "directed=True" in inspect.getsource(st_planner.story) and "directed=True" in inspect.getsource(st_planner.clip_plan)
    for stage in ("topics", "brief", "bible", "roster"):          # research and design stages are not shot plans
        assert "directed=True" not in inspect.getsource(getattr(st_planner, stage)), stage
    assert src.count("directed=True") == 2


def test_the_explainer_plan_is_checked_and_its_repeats_fixed():
    plan = ex_spec.norm_plan(ex_planner.builtin("why ice floats", 30, "9:16"), 30, "9:16")
    for sh in plan["shots"]:                                       # force the worst case: six identical set-ups
        sh["camera"]["type"], sh["camera"]["movement"] = "medium", "push_in"
    said = []
    out = ex_planner.directed(plan, said.append)
    pairs = [(sh["camera"]["type"], sh["camera"]["movement"]) for sh in out["shots"]]
    assert all(a != b for a, b in zip(pairs, pairs[1:]))
    assert out["house"]["fixed"] >= 2 and said and "House director" in said[0]["text"]
    assert all(sh["camera"]["movement"] in ex_spec.CAMERA_MOVES for sh in out["shots"])


def test_the_prompt_library_knows_a_fix_for_each_house_finding():
    for kind in ("two_actions", "not_visible", "flat_opening"):
        assert f"house_{kind}" in ex_prompts.FIX


def test_a_stickman_clip_framed_like_the_last_gets_a_new_camera_move():
    before = {"n": 1, "framing": "medium wide shot", "camera_move": "slow push in"}
    clip = st_planner.unrepeat_clip({"n": 2, "framing": "medium shot", "camera_move": "slow push in"}, before)
    assert clip["camera_move"] in st_spec.CAMERA_MOVES and clip["camera_move"] != "slow push in" and clip["house"]
    same = st_planner.unrepeat_clip({"n": 2, "framing": "close-up", "camera_move": "slow push in"}, before)
    assert same["camera_move"] == "slow push in" and "house" not in same
    assert st_planner.unrepeat_clip({"n": 1, "framing": "wide", "camera_move": "static"}, None)["camera_move"] == "static"


def test_company_story_scenes_in_one_setting_do_not_all_push_in():
    sc = {"scenes": [{"n": i + 1, "setting": "city", "move": "slow push in", "place": "a paper city", "visual": "paper towers rise from the table"} for i in range(4)]}
    note = company_story.directed(sc)
    moves = [x["move"] for x in sc["scenes"]]
    assert all(a != b for a, b in zip(moves, moves[1:])) and set(moves) <= set(company_story.MOVES)
    assert sc["house"]["fixed"] == 2 and "House director" in note
    clean = {"scenes": [{"n": 1, "setting": "origin", "move": "slow push in", "place": "a garage", "visual": "a paper garage door rolls up"},
                        {"n": 2, "setting": "city", "move": "slow push in", "place": "a city", "visual": "paper towers rise"}]}
    assert company_story.directed(clean) == ""


def test_a_film_breakdown_is_reviewed_but_never_changed():
    bd = {"shots": [{"location": "street", "action": "the fox thinks about home, then runs", "framing": "wide", "camera": "static"}]}
    before = [dict(x) for x in bd["shots"]]
    said = []
    out = film.directed(bd, said.append)
    assert out["shots"] == before and out["house"]["found"] and "kept as written" in said[0]["text"]
