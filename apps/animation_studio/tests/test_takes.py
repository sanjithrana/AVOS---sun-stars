"""Takes: a redo must never be the only copy. Borrowed from Maestro's Director."""
from __future__ import annotations

import pytest

from studio.skilllab import takes


def shot() -> dict:
    return {"n": 3, "title": "Slicing the onion"}


def test_the_shot_still_points_at_a_plain_file_name():
    sh = shot()
    takes.add(sh, "picture", "S03.png", model="flux")
    assert sh["picture"] == "S03.png"                       # everything that reads a shot keeps working
    takes.add(sh, "picture", "S03-b.png", model="flux")
    assert sh["picture"] == "S03-b.png"


def test_a_redo_keeps_the_one_it_replaced():
    sh = shot()
    first = takes.add(sh, "picture", "S03.png")
    takes.add(sh, "picture", "S03-b.png")
    assert [t["file"] for t in takes.listing(sh, "picture")] == ["S03-b.png", "S03.png"]
    assert takes.pick(sh, "picture", first["id"])
    assert sh["picture"] == "S03.png" and takes.chosen(sh, "picture")["id"] == first["id"]


def test_a_stale_id_cannot_blank_the_shot():
    sh = shot()
    takes.add(sh, "picture", "S03.png")
    assert not takes.pick(sh, "picture", "nope")
    assert sh["picture"] == "S03.png"


def test_pictures_and_clips_are_kept_apart():
    sh = shot()
    takes.add(sh, "picture", "S03.png")
    takes.add(sh, "video", "S03.mp4")
    assert sh["picture"] == "S03.png" and sh["video"] == "S03.mp4"
    assert len(takes.listing(sh, "picture")) == 1 and len(takes.listing(sh, "video")) == 1
    takes.add(sh, "video", "S03-b.mp4")
    assert sh["picture"] == "S03.png"                       # redoing the clip leaves the picture alone


def test_a_reset_readies_the_shot_without_destroying_it():
    sh = shot()
    takes.add(sh, "picture", "S03.png")
    takes.clear_pointer(sh, "picture")
    assert sh["picture"] is None and takes.chosen(sh, "picture") is None
    assert len(takes.listing(sh, "picture")) == 1          # still there to go back to
    takes.add(sh, "picture", "S03-b.png")
    assert len(takes.listing(sh, "picture")) == 2


def test_old_takes_fall_off_the_end():
    sh = shot()
    for i in range(takes.LIMIT + 3):
        takes.add(sh, "picture", f"S03-{i}.png")
    assert len(takes.listing(sh, "picture")) == takes.LIMIT
    assert sh["picture"] == f"S03-{takes.LIMIT + 2}.png"   # the newest is still the one in use


def test_the_take_you_are_using_never_falls_off():
    sh = shot()
    for i in range(takes.LIMIT):
        takes.add(sh, "picture", f"S03-{i}.png")
    oldest = takes.listing(sh, "picture")[-1]
    takes.pick(sh, "picture", oldest["id"])                # go back to the first good one
    for i in range(takes.LIMIT + 2):                       # then try several more
        takes.add(sh, "picture", f"S03-late-{i}.png")
        takes.pick(sh, "picture", oldest["id"])
    kept = {t["file"] for t in takes.listing(sh, "picture")}
    assert oldest["file"] in kept, "the take being used must survive every prune"
    assert sh["picture"] == oldest["file"]


def test_nothing_still_in_use_is_offered_for_deletion():
    sh = shot()
    for i in range(takes.LIMIT + 4):
        takes.add(sh, "picture", f"S03-{i}.png")
    freed = takes.prune(sh, "picture")
    assert not (set(freed) & takes.keeps(sh))


def test_a_take_is_a_picture_or_a_clip_and_nothing_else():
    with pytest.raises(ValueError):
        takes.add(shot(), "audio", "S03.wav")


def test_the_step_note_says_how_much_was_redone():
    shots = [shot(), shot()]
    takes.add(shots[0], "picture", "a.png")
    takes.add(shots[1], "picture", "b.png")
    assert takes.summary(shots) == "2 shots, 2 takes"
    takes.add(shots[1], "picture", "b2.png")
    assert takes.summary(shots) == "2 shots, 3 takes (1 redone)"


# ---------- the whole point, end to end on a cooking run ----------
def test_redoing_one_bad_shot_keeps_the_other_ten():
    from studio.skilllab import asmr_cooking as AC
    shots = [{"n": i + 1, "title": f"Shot {i + 1}"} for i in range(11)]
    for sh in shots:
        takes.add(sh, "picture", f"S{sh['n']:02d}.png", model="flux")
        takes.add(sh, "video", f"S{sh['n']:02d}.mp4", model="macro move")
    p = {"recipe": {"shots": shots}, "steps": {st: {} for st in AC.STAGES}, "video": "final.mp4"}

    AC.reset(p, "pictures", n=4)                            # only shot 4, the one that came back wrong
    assert shots[3]["picture"] is None, "shot 4 is ready to be drawn again"
    assert shots[3]["video"] is None, "and so is its clip, because the picture it was made from is going"
    assert [sh["picture"] for sh in shots if sh["n"] != 4] == [f"S{i:02d}.png" for i in (1, 2, 3, 5, 6, 7, 8, 9, 10, 11)]
    assert len(takes.listing(shots[3], "picture")) == 1, "the bad one is still there to go back to"

    takes.add(shots[3], "picture", "S04b.png", model="flux")  # the second attempt
    assert shots[3]["picture"] == "S04b.png"
    first = takes.listing(shots[3], "picture")[-1]
    assert takes.pick(shots[3], "picture", first["id"])        # ...which is worse, so go back
    assert shots[3]["picture"] == "S04.png"
    assert "finish" not in p["steps"] and "video" not in p, "the final video is remade from the chosen takes"
