"""ASMR Cutting: the count the person asked for is the count they get, and the sound lands on the frame the blade does."""
from __future__ import annotations

import wave
import io

from studio.series import writers
from studio.skilllab import asmr_cutting as XC
from studio.skilllab import cutscene, foley, pipeline, store

from .conftest import needs_ffmpeg


def test_the_count_and_the_object_come_out_of_the_persons_own_line():
    for line, cuts, obj in (
        ("papaya, 50 cuts", 50, "papaya"),
        ("Object = Papaya, Cuts = 50", 50, "papaya"),            # the workflow's own shorthand
        ("a bar of blue soap, 24 cuts", 24, "blue soap"),
        ("watermelon 40 slices", 40, "watermelon"),
        ("cut a mango into 12 pieces", 12, "mango"),
        ("butter", XC.DEFAULT_CUTS, "butter"),
        ("", XC.DEFAULT_CUTS, "papaya"),
    ):
        assert XC.cuts_in(line) == cuts, line
        assert XC.object_in(line) == obj, line
    assert XC.cuts_in("200 cuts on a cucumber") == cutscene.MAX_CUTS       # capped, never refused


def test_a_watermark_only_ever_comes_from_the_person():
    assert XC.handle_in("papaya, 50 cuts, @mystudio") == "@mystudio"
    assert XC.handle_in("papaya, 50 cuts") == ""
    assert XC.object_in("@mystudio carrot 30 cuts") == "carrot"            # the handle is not part of the object


def test_the_beat_follows_the_length_but_stays_watchable():
    assert round(XC.beat_for(18, 50), 2) == 0.25                           # the workflow's six frames at 24 fps
    assert round(XC.beat_for(12, 50), 3) == 0.132                          # a shorter video just comes quicker
    assert XC.beat_for(12, cutscene.MAX_CUTS) == 0.12                      # too many for the length: clamped, not dropped
    assert XC.beat_for(28, 10) == 0.60                                     # too few: the shot would drag otherwise


def test_a_bad_spec_is_repaired_rather_than_trusted():
    d = {"object": "Papaya", "shape": "nonsense", "skin": "#7ea64a", "flesh": "oops", "texture": "zzz"}
    got = XC.norm(d, "papaya, 50 cuts", "")
    assert got["shape"] == "tall" and got["texture"] == "wet"
    assert got["skin"] == [126, 166, 74] and got["flesh"] == [238, 132, 72]  # the bad colour fell back to the real one
    assert XC.norm(d, "papaya", "bar")["shape"] == "bar"                   # the person's own choice beats the AI's


def test_every_object_gets_a_shape_a_palette_and_a_sound():
    for name, shape in (("papaya", "tall"), ("carrot", "long"), ("soap", "bar"), ("apple", "round")):
        assert cutscene.shape_for(name) == shape
        skin, flesh, _ = cutscene.colours_for(name)
        assert skin != flesh, f"{name}: a cut face that matches the skin does not read on screen"
    assert foley.texture_for("carrot") == "crisp" and foley.texture_for("soap") == "dry"
    assert foley.texture_for("butter") == "soft" and foley.texture_for("papaya") == "wet"


def test_the_shot_has_one_impact_per_cut_and_the_counter_ends_full():
    from PIL import Image, ImageDraw
    seconds, draw, (bg, size), impacts = cutscene.scene({"object": "papaya", "cuts": 9, "gap": 0.25}, 108, 192)
    assert len(impacts) == 9 and size == (108, 192)
    assert round(impacts[1] - impacts[0], 3) == 0.25
    assert seconds > impacts[-1] + cutscene.FALL                           # the pieces have time to fall
    im = Image.new("RGB", (216, 384), bg)                                  # mgfx draws at twice the size
    draw(seconds - 0.1, ImageDraw.Draw(im, "RGBA"), im)
    assert im.convert("L").getextrema()[1] > 80                            # the last frame is not a black screen


def test_one_sound_per_impact_and_it_lands_on_the_impact():
    impacts = [1.2 + i * 0.25 for i in range(8)]
    b = foley.cuts_wav(impacts, 6.0, "wet", 3, tumble=impacts[-1] + 0.9)
    with wave.open(io.BytesIO(b)) as w:
        assert w.getframerate() == foley.SR and w.getnchannels() == 1
        n = w.getnframes()
        import array
        a = array.array("h"); a.frombytes(w.readframes(n))
    assert abs(n / foley.SR - 6.0) < 0.1
    quiet = max(abs(v) for v in a[: int(0.9 * foley.SR)])                  # before the first stroke
    hit = max(abs(v) for v in a[int(1.19 * foley.SR): int(1.26 * foley.SR)])
    assert hit > quiet * 4, "the first knife stroke should be clearly louder than the room before it"


def test_the_skill_is_wired_into_the_pipeline():
    assert XC.ID in pipeline.SKILLS
    spec = pipeline.spec_of({"skill": XC.ID})
    assert spec["stages"] == ("plan", "render") and set(spec["run"]) == {"plan", "render"}
    assert XC.last_stage({"media": "prompts"}) == "plan" and XC.last_stage({"media": "media"}) == "render"


@needs_ffmpeg
def test_a_run_makes_the_video_with_no_model_at_all(monkeypatch):
    monkeypatch.setattr(writers, "uses_ai", lambda s: False)               # no crew: the colour table has to carry it
    pid = store.new_id()
    store.save({"id": pid, "skill": XC.ID, "subject": "carrot, 5 cuts, @mystudio", "aspect": "9:16", "seconds": 12,
                "media": "media", "status": "working", "stage": "plan", "steps": {}, "log": []})
    pipeline._run(pid, "plan")
    p = store.load(pid)
    assert p["status"] == "done", p.get("error")
    assert p["spec"]["cuts"] == 5 and p["spec"]["object"] == "carrot" and p["spec"]["texture"] == "crisp"
    assert p["spec"]["watermark"] == "@mystudio"
    assert p["video"] == "final.mp4" and store.file_path(pid, p["video"])
    assert p["finalSeconds"] > cutscene.FALL                                # a real length, not a stub
    assert "no picture or video model was used" in p["steps"]["render"]["note"]
