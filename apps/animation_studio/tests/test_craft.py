import subprocess
from pathlib import Path

from studio import config
from studio.autoclip import craft, pick


def W(text, t0=0.0, step=0.4, gap_after=None):
    out, t = [], t0
    for i, w in enumerate(text.split()):
        out.append({"w": w, "s": round(t, 3), "e": round(t + 0.3, 3)})
        t += step
        if gap_after and i in gap_after:
            t += gap_after[i]
    return out


def test_sentences_split_on_punctuation_and_pauses():
    ws = W("so this is it. And then we went home", gap_after={7: 1.0})
    ss = craft.sentences(ws)
    assert len(ss) == 3 and ss[0]["last"] == "it"


def test_finish_moves_edges_to_sentence_edges_and_past_a_dangling_end():
    ws = W("Intro stuff here. The big moment starts now and it gets wild. Then the payoff lands hard. Bye now.")
    # a clip that starts mid-sentence and ends right after 'and'
    s = ws[5]["s"]
    e = ws[8]["e"]
    out = craft.finish([{"start": s, "end": e, "score": 5}], ws, 3, 30)
    assert out[0]["start"] == ws[3]["s"]                       # "The big moment..." starts a sentence
    assert out[0]["end"] >= ws[11]["e"]                        # ended on 'and' so it runs to the end of that sentence


def test_dedupe_drops_repeats_and_overlaps_keeping_the_better_one():
    ms = [{"start": 0, "end": 30, "score": 9}, {"start": 100, "end": 130, "score": 5}, {"start": 200, "end": 230, "score": 4}, {"start": 20, "end": 50, "score": 3}]
    tx = ["the secret mission finale boss fight dragon castle", "the secret mission finale boss fight dragon castle again", "cooking pasta tonight with garlic butter", "anything else"]
    assert craft.dedupe(ms, tx) == [0, 2]


def test_tighten_plan_cuts_long_pauses_and_fillers():
    ws = W("so I think um that this is really good", gap_after={1: 2.0})
    spans = craft.tighten_plan(ws, 0.0, ws[-1]["e"] + 0.2)
    assert spans and len(spans) >= 2
    kept = sum(b - a for a, b in spans)
    assert kept < ws[-1]["e"] - 1.5
    new = craft.remap_words(ws, spans)
    assert all(w["w"].lower() != "um" for w in new) and new[0]["s"] >= 0
    assert craft.map_time(ws[3]["s"] + 0.05, spans) is None     # inside the removed 'um'


def test_tighten_plan_leaves_tight_speech_alone():
    ws = W("this is already a very tight clip of speech with no gaps")
    assert craft.tighten_plan(ws, 0.0, ws[-1]["e"]) is None


def test_tight_render_makes_a_shorter_video_with_audio(tmp_path):
    src = tmp_path / "in.mp4"
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=25:duration=10", "-f", "lavfi", "-i", "sine=frequency=440:duration=10",
                    "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(src)], check=True)
    out = tmp_path / "tight" / "t.mp4"
    dur = craft.tight_render(str(src), out, [(1.0, 3.0), (5.0, 7.5), (8.0, 9.0)], config.ffmpeg(), True)
    assert abs(dur - 5.5) < 0.01
    assert abs(pick.duration(str(out)) - 5.5) < 0.4


def test_ai_rerank_orders_finalists_and_flags_unfinished(monkeypatch):
    from studio.series import writers
    monkeypatch.setattr(writers, "uses_ai", lambda s: True)
    monkeypatch.setattr(writers, "ask", lambda *a, **k: {"best": [3, 1, 99, 1], "unfinished": [1, "x"]})
    ms = [{"start": 0, "end": 20}, {"start": 30, "end": 50}, {"start": 60, "end": 80}]
    best, unf = craft.ai_rerank({}, ms, ["a", "b", "c"], 2)
    assert best == [2, 0] and unf == [0]
    monkeypatch.setattr(writers, "ask", lambda *a, **k: None)
    assert craft.ai_rerank({}, ms, ["a", "b", "c"], 2) is None


def test_extend_runs_to_the_next_sentence_end():
    ws = W("One two three. Four five six seven. Eight nine ten.")
    m = craft.extend({"start": 0, "end": ws[2]["e"]}, ws, 10.0)
    assert m["end"] > ws[6]["e"]


def test_whisper_window_listens_to_a_small_stretch_and_returns_source_times(tmp_path, monkeypatch):
    from studio.autoclip import transcript
    src = tmp_path / "in.mp4"
    subprocess.run([config.ffmpeg(), "-v", "error", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=30", str(src)], check=True)
    seen = {}

    def fake(path, log=None, model="base", prompt=None, task="transcribe"):
        seen["dur"] = pick.duration(path)
        return [{"start": 1.0, "end": 2.0, "text": "hi there", "words": [{"w": "hi", "s": 1.0, "e": 1.4}, {"w": "there", "s": 1.5, "e": 2.0}]}]
    monkeypatch.setattr(transcript, "whisper", fake)
    cues = transcript.whisper_window(str(src), 10.0, 20.0)
    assert 9 < seen["dur"] < 11                                   # only the window was handed to whisper
    assert cues[0]["start"] == 11.0 and cues[0]["words"][1]["e"] == 12.0


def test_find_source_ignores_leftover_halves_of_an_unmerged_download(tmp_path):
    from studio.autoclip import intake
    (tmp_path / "source.f251.webm").write_bytes(b"a" * 50)          # audio-only half
    (tmp_path / "source.srt").write_text("x")
    (tmp_path / "source.mp4.part").write_bytes(b"p")
    assert intake.find_source(tmp_path) is None
    (tmp_path / "source.mp4").write_bytes(b"v" * 100)
    assert intake.find_source(tmp_path).name == "source.mp4"


def test_hype_sees_a_boom_in_a_video_that_is_loud_all_the_way_through():
    from studio.autoclip import hype
    lv = [-20.0 + (i % 5) * 0.2 for i in range(1800)]                 # steady loud background for 30 minutes
    for i in range(900, 908):
        lv[i] = -8.0                                                  # one sudden boom
    h = hype.curve(lv)
    assert max(h[895:915]) > 3 * max(h[100:800] + [0.01])
    ms = hype.moments(h, 3, 20, 60, None, 0.0, "relative")
    assert ms and abs(ms[0]["peak"] - 904) < 10


def test_hype_relative_fallback_never_returns_nothing_for_a_calm_video():
    from studio.autoclip import hype
    h = [0.05 + 0.02 * ((i * 7) % 11) / 11 for i in range(1200)]
    assert hype.moments(h, 2, 20, 60, None, 0.0, "balanced") == []
    assert hype.moments(h, 2, 20, 60, None, 0.0, "relative")


def test_footage_game_is_detected_and_titles_never_name_the_wrong_one():
    from studio.autoclip import meta, presets
    assert meta.detect("Guys we're in GTA 5 and this stunt is impossible", "Beating GTA 6 right now") == "gta5"
    assert meta.detect("so this is gta six and it looks great", "") == "gta6"
    assert meta.detect("nothing about a game here", "") is None
    assert meta.detect("GTA 5 is older than GTA 6", "") is None                     # both named equally often: unclear
    pre, note = meta.franchise_prefix("GTA 6", "gta5")
    assert pre == "GTA 5" and "not GTA 6" in note
    assert meta.franchise_prefix("GTA 6", "gta6") == ("GTA 6", "")
    assert meta.franchise_prefix("Minecraft", "gta5") == ("Minecraft", "")           # only the game presets are corrected
    assert presets.title(presets.PRESETS["gta6"], "impossible stunt", "Oh my god", "GTA 5").startswith("GTA 5 impossible stunt")


def test_hashtags_are_few_true_and_learned():
    from studio.autoclip import meta
    clip = {"text": "Guys we're in GTA 5 and Kai Cenat shoots a basketball from the helicopter", "moment": "impossible stunt", "title": "x",
            "description": "A wild one #gta6 #wild"}
    tags = meta.hashtags(clip, None, 5, "")
    low = [t.lower() for t in tags]
    assert len(tags) <= 5 and low[0] == "gta5" and "gta6" not in low and "gtavi" not in low     # the AI's wrong-game tag is dropped
    assert "stunt" in low and "kaicenat" in low and "shorts" in low
    assert meta.hashtags({"text": "no game here", "moment": ""}, None, 5, "")[0].lower() == "shorts"
    rows = [{"tags": ["gta5", "funny"], "views": 100}] * 3 + [{"tags": ["gta5", "npc"], "views": 1000}] * 3
    lift = meta.learn(rows)
    assert lift["npc"] > 1.5 and lift["funny"] < 0.5 and meta.learn(rows[:4]) == {}
    tags2 = meta.hashtags({"text": "this npc is a heist robbery", "moment": ""}, None, 4, "", {"heist": 0.2, "npc": 2.0})
    assert [t.lower() for t in tags2].index("npc") < [t.lower() for t in tags2].index("heist") if "heist" in [t.lower() for t in tags2] else True


def test_title_without_ai_does_not_end_on_a_dangling_word():
    from studio.autoclip import pick
    assert not pick.title_for("Guys we're in GTA 5 and we are about to try this impossible stunt with a", 1).endswith(" a")
    assert "Highlight" not in pick.title_for("", 3)


def test_captions_never_draw_two_lines_on_top_of_each_other():
    import re
    from studio.autoclip import cut
    words = []
    t = 0.0
    for w in "god we got this one perfectly come on that is it oh yes".split():
        words.append({"w": w, "s": round(t, 3), "e": round(t + 0.32, 3)})
        t += 0.34                                                     # lines follow each other with almost no gap
    ass = cut.ass_for(words, 0.0, t + 1, "bounce", 720, 1280, None)
    ev = []
    for ln in ass.splitlines():
        m = re.match(r"Dialogue: 0,(\d+):(\d+):(\d+)\.(\d+),(\d+):(\d+):(\d+)\.(\d+),", ln)
        if m:
            g = [int(x) for x in m.groups()]
            ev.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 100, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 100))
    ev.sort()
    assert ev and all(ev[i][1] <= ev[i + 1][0] + 0.011 for i in range(len(ev) - 1))


def test_pop_captions_change_colour_every_word():
    from studio.autoclip import cut
    words = [{"w": w, "s": i * 0.4, "e": i * 0.4 + 0.35} for i, w in enumerate(["bro", "car", "nah", "see", "feel"])]
    a = cut.ass_for(words, 0, 3, "pop", 720, 1280)
    assert a and "BRO" in a
    cols = {c for c in cut.POPCOL if c in a}
    assert len(cols) >= 3 and "pop" in cut.CAPTIONS


def test_caption_junk_is_dropped():
    from studio.autoclip import cut, transcript
    ws = [{"w": w, "s": i * 0.3, "e": i * 0.3 + 0.25} for i, w in enumerate([">>", "boy", "[", "__", "]", "oh", "[Music]", ">> god", "♪", "no."])]
    assert [x["w"] for x in transcript.clean_words(ws)] == ["boy", "oh", "god", "no."]
    a = cut.ass_for(ws, 0, 4, "clean", 720, 1280)
    dl = "\n".join(x for x in a.splitlines() if x.startswith("Dialogue"))
    assert dl and ">>" not in dl and "[" not in dl and "♪" not in dl


def test_best_line_title_and_generic_tags():
    from studio.autoclip import pick, meta
    t = pick.title_for("Yeah. She just got down taking a nookie bokey Hey girl. No no no no no. Wait, he's still got those tigers!", 1)
    assert t == "Wait, he's still got those tigers!"
    assert "*" in pick.title_for("fuck this shit bro", 2)
    tags = meta.hashtags({"moment": "funny moment", "text": "gta 6 funny bro", "title": "x"}, None, 5)
    assert "moment" not in [x.lower() for x in tags] and "gaming" in tags and "Shorts" in tags


def test_whole_frame_keeps_corner_cam_in_the_game_frame():
    from studio.autoclip import reframe
    fr = [{"t": t * 0.5, "faces": [{"cx": 0.15, "cy": 0.15, "w": 0.1, "m": 0.0}], "col": [1.0] * reframe.BINS} for t in range(8)]
    for whole, want in ((True, "camtop"), (False, "facecam")):
        sc = reframe.plan_scenes(fr, [0.0, 4.0], 1920, 1080, None, 0.0, "split", reframe.FPS, whole)
        assert sc[0]["layout"] == want, (whole, sc[0]["layout"])


def test_visual_scan_sees_a_burst_of_change(tmp_path):
    import shutil, subprocess
    from studio.autoclip import visual
    ff = shutil.which("ffmpeg")
    if not ff:
        return
    out = tmp_path / "v.mp4"
    # 12 s of calm grey, a burst of noise at 6-7 s
    r = subprocess.run([ff, "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=gray:s=320x180:r=15:d=12", "-vf",
                        "geq=lum='if(between(T,6,7),random(1)*255,128)':cb=128:cr=128", "-pix_fmt", "yuv420p", str(out)], capture_output=True, text=True)
    assert out.is_file(), r.stderr
    v = visual.scan(str(out), 0, None)
    assert v and len(v["hype"]) >= 11
    assert max(range(len(v["hype"])), key=lambda i: v["hype"][i]) in (5, 6, 7)
    assert v["hype"][2] < 0.2


def test_red_tint_is_in_the_render_graph():
    from studio.autoclip import polish
    ed = polish.plan_edit([{"w": "no", "s": i * 0.5, "e": i * 0.5 + 0.4} for i in range(30)], 0, 15, {"edit": "punchy", "music": "none"}, "x", 1, peaks=[4.0, 10.0])
    assert ed["tint"] == [10.0]
