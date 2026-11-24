"""The AI transcript editor (ported from AutoClip, MIT) and the clip-edge rules."""
from __future__ import annotations

from studio.autoclip import boundaries, finder, signals


def rows(n=200, step=5.0):
    return [{"start": i * step, "end": i * step + step - 0.3, "text": f"line {i}."} for i in range(n)]


def test_windows_cover_everything_with_overlap():
    r = rows(1200, 5.0)                                   # 100 minutes
    w = finder.windows(r, 3600, 240, 10**9)
    assert w[0][0] == 0 and w[-1][1] == len(r) - 1 and len(w) == 2
    assert w[1][0] < w[0][1]                              # they share rows
    assert len(finder.windows(r, 1200, 80, 10**9)) >= 5


def test_parse_checks_rows_length_and_score():
    r = rows(50)
    raw = {"clips": [{"start": 2, "end": 8, "title": "**Good**", "reason": "x", "score": 1.4},
                     {"start": 40, "end": 99, "title": "out of range", "score": 0.9},
                     {"start": 3, "end": 3, "title": "too short", "score": 0.9},
                     {"start": 5, "end": 9, "title": "", "score": 0.9},
                     "junk"]}
    got = finder.parse(raw, 0, 49, r, 30, 45)
    assert len(got) == 1 and got[0]["title"] == "Good" and got[0]["llm"] == 1.0 and got[0]["start"] == 10.0


def test_find_dedupes_and_survives_a_bad_answer():
    r = rows(100)
    calls = []

    def ask(prompt, body):
        calls.append(body)
        if len(calls) == 1:
            return "not json"                             # retried once
        return {"clips": [{"start": 10, "end": 17, "title": "A", "score": 0.9}, {"start": 11, "end": 18, "title": "A again", "score": 0.8},
                          {"start": 40, "end": 47, "title": "B", "score": 0.75}]}
    got = finder.find(r, ask, 30, 45, 3)
    assert [g["title"] for g in got] == ["A", "B"] and len(calls) == 2
    assert "10|0:50|line 10." in calls[0]
    assert finder.find(r, lambda p, b: 1 / 0, 30, 45, 3) == []


def test_rows_from_words_when_there_are_no_cues():
    w = [{"w": x, "s": i * 0.5, "e": i * 0.5 + 0.4} for i, x in enumerate("hello there. how are you doing today?".split())]
    rr = finder.rows_of(None, w)
    assert rr[0]["text"] == "hello there." and rr[1]["text"].endswith("today?")


def words_of(text, t0=0.0, step=0.5):
    return [{"w": x, "s": t0 + i * step, "e": t0 + i * step + 0.4} for i, x in enumerate(text.split())]


def test_never_end_on_the_next_question():
    ws = words_of("this is the answer and it is great. " * 8 + "so what about the next thing?", 0)
    end = ws[-1]["e"] + 3
    m = boundaries.drop_trailing_question({"start": 0.0, "end": end}, ws, 20)
    assert m.get("cut_question") and m["end"] <= ws[-6]["s"] + 0.1


def test_start_moves_to_the_peak_on_a_sentence_edge():
    ws = words_of("slow intro words here. the big moment now happens here and more", 0)
    curve = [0.2] * 60
    for i in range(5, 8):
        curve[i] = 0.95
    m = boundaries.start_on_peak({"start": 0.0, "end": 40.0}, curve, 0.0, ws, 20)
    assert 0 < m["start"] <= 5 - boundaries.PEAK_LEAD + 0.4
    assert boundaries.start_on_peak({"start": 0.0, "end": 40.0}, [0.2] * 60, 0.0, ws, 20)["start"] == 0.0


def test_hold_the_reaction():
    curve = [0.1] * 50
    curve[40:44] = [0.9] * 4
    assert boundaries.hold_reaction({"start": 10, "end": 40}, curve, 0.0)["end"] > 40
    assert boundaries.hold_reaction({"start": 10, "end": 30}, curve, 0.0)["end"] == 30


def test_voice_coming_back_is_a_signal():
    ws = words_of("ok ok", 0) + words_of("no way bro what was that", 10, 0.3)
    v = boundaries.voice_return(ws, 20)
    assert v and max(v) > 0.5 and v.index(max(v)) in (9, 10)
    assert "voice" in signals.WEIGHTS and "voice" in signals.NAMES


# ---------- frames, templates, caption modes, music riser ----------
import shutil  # noqa: E402
import subprocess  # noqa: E402

import pytest  # noqa: E402

from studio.autoclip import captions, cut, pipeline, polish, templates  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")


def test_template_settings_are_cleaned():
    t, c = templates.clean("x_dark", {"pad": 99, "radius": "12", "color": "#123456", "evil": 1, "bg": "nope"})
    assert t == "x_dark" and c["pad"] == 15 and c["radius"] == 12 and c["color"] == "#123456" and c["bg"] == "color" and "evil" not in c
    assert templates.clean("bogus", None)[0] == "none"
    o = pipeline.build_opts({"template": "breaking", "canvas": '{"pad": 4}', "layout": "split"})
    assert o["template"] == "breaking" and o["canvas"]["pad"] == 4 and o["canvas"]["bg"] == "gradient" and o["layout"] == "split"


def test_headline_is_pinned_above_the_clip():
    st, ev = templates.head_events("x_light", "Rohit says he never trained for this, and then he won the whole thing", "@show", 30, 720, 1280, 500)
    assert st and ev and any("@show" in e for e in ev)
    ys = [int(e.split("\\pos(")[1].split(",")[1].split(")")[0]) for e in ev]
    assert max(ys) < 500 and all(e.split(",")[2] == "0:00:30.00" for e in ev)
    a = templates.add_to_ass(None, st, ev, 720, 1280)
    assert "Style: Head," in a and a.count("[Events]") == 1
    _, ev2 = templates.head_events("breaking", "Big news", "", 10, 720, 1280, 600)
    assert any("BREAKING NEWS" in e for e in ev2)


def test_caption_modes():
    ws = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25} for i, w in enumerate("well, this is the moment everything changed for us".split())]
    full = cut.ass_for(ws, 0, 4, "clean", 720, 1280, cap={"mode": "full_line"})
    assert any("\\N" in ln for ln in full.splitlines() if ln.startswith("Dialogue"))
    one = cut.ass_for(ws, 0, 4, "clean", 720, 1280, cap={"mode": "one_by_one"})
    assert len([ln for ln in one.splitlines() if ln.startswith("Dialogue")]) == len(ws)
    assert "\\alpha&HFF&" in cut.ass_for(ws, 0, 4, "clean", 720, 1280, cap={"mode": "build_up"})
    assert set(captions.MODES) >= {"pop_in", "pop_line", "one_by_one", "build_up", "highlight", "full_line"}


def test_music_riser_climbs_at_the_end():
    a = polish.audio_chain({"music": {"volume": 0.1, "riser": True}, "loudness": True}, True, 1, [], 30)
    assert "if(gt(t,24.00)" in a
    assert "if(gt(t" not in polish.audio_chain({"music": {"volume": 0.1}, "loudness": True}, True, 1, [], 30)
    assert polish.resolve({"riser": "true"})["riser"] is True


@needs_ffmpeg
@pytest.mark.parametrize("layout,tpl,canvas", [("wide", "x_light", None), ("centered", "none", {"bg": "gradient", "radius": 30, "pad": 6}),
                                               ("wide", "breaking", None), ("split", "none", None), ("pip", "none", None), ("trio", "none", None),
                                               ("centered", "tiktok_hook", None), ("podcast", "podcast", None)])
def test_framed_layouts_render(tmp_path, layout, tpl, canvas):
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=25:d=3", "-f", "lavfi", "-i", "sine=f=300:d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(src)], check=True)
    t, c = templates.clean(tpl, canvas)
    st, ev = templates.head_events(t, "A headline for this clip", "@me", 2, 720, 1280, templates.box(layout, t, c, 720, 1280)[1])
    ass = templates.add_to_ass(None, st, ev, 720, 1280)
    out = tmp_path / "o.mp4"
    cut.cut(str(src), str(out), 0.5, 2.5, layout, "720p", ass, None, None, None, 4 / 3, {"tpl": t, "canvas": c})
    dur, aud = cut.media_info(str(out))
    assert out.is_file() and dur > 1.5 and aud


def test_captions_break_after_punctuation():
    ws = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25} for i, w in enumerate("that's it! stay forward! how you feel?".split())]
    a = cut.ass_for(ws, 0, 3, "bounce", 720, 1280)
    lines = [ln.split(",,")[-1] for ln in a.splitlines() if ln.startswith("Dialogue") and ",Default,," in ln]
    import re as _re
    plain = {_re.sub(r"\{[^}]*\}", "", x).strip().lower() for x in lines}
    assert not any("it! stay" in p or "forward! how" in p for p in plain)


def test_no_face_scene_keeps_the_whole_frame():
    from studio.autoclip import reframe
    fr = [{"t": i / 2, "faces": [], "col": [1.0] * reframe.BINS} for i in range(8)]
    fr[0]["col"] = [5.0] + [1.0] * (reframe.BINS - 1)
    sc = reframe.plan_scenes(fr, [0.0, 4.0], 1920, 1080)
    assert sc[0]["layout"] == "blur"


def test_every_card_template_draws(tmp_path):
    from studio.autoclip import cards
    names = [k for k, v in templates.TEMPLATES.items() if v.get("card")]
    assert {"x_light", "x_dark", "linkedin", "threads", "yt_banner", "comment", "podcast_show", "quote", "phone", "glow", "terminal"} <= set(names)
    for t in names:
        tt, c = templates.clean(t, None)
        bx = templates.box("wide", tt, c, 720, 1280)
        f = cards.render(tt, {"name": "Alex", "handle": "alex", "episode": "4", "size": 140}, "A long hook line " * 12, 720, 1280, bx, tmp_path / f"{t}.png")
        from PIL import Image
        im = Image.open(f)
        assert im.size == (720, 1280) and im.getbbox(), t
    assert len(templates.TEMPLATES) - 1 >= 13


def test_card_fields_are_cleaned():
    c = templates.clean_card({"name": "  A  B ", "font": "Comic", "size": 999, "verified": "false", "evil": 1, "hook": "x" * 500})
    assert c["name"] == "A B" and "font" not in c and c["size"] == 160 and c["verified"] is False and "evil" not in c and len(c["hook"]) == 220
    o = pipeline.build_opts({"template": "yt_banner", "card": '{"name": "Me", "verified": true}'})
    assert o["card"]["name"] == "Me" and o["card"]["verified"] is True


@needs_ffmpeg
def test_card_overlay_renders(tmp_path):
    from studio.autoclip import cards
    src = tmp_path / "s.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=25:d=3", "-f", "lavfi", "-i", "sine=f=300:d=3",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(src)], check=True)
    t, c = templates.clean("terminal", None)
    ov = cards.render(t, {"name": "Me"}, "Hook", 720, 1280, templates.box("wide", t, c, 720, 1280), tmp_path / "c.png")
    out = tmp_path / "o.mp4"
    cut.cut(str(src), str(out), 0.5, 2.5, "wide", "720p", None, None, None, None, 4 / 3, {"tpl": t, "canvas": c, "overlay": ov})
    assert cut.media_info(str(out))[0] > 1.5
