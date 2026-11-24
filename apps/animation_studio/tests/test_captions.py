"""Caption styles and options, branding, Hinglish, saved looks, the estimate and the captions-only job."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading

import pytest

from studio.autoclip import captions, cut, pipeline, store, translit

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
SRT = "1\n00:00:01,000 --> 00:00:04,000\nthis is the moment it all changed\n\n2\n00:00:04,500 --> 00:00:07,000\nand nobody saw it coming\n"


@pytest.fixture(autouse=True)
def root(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "ROOT", tmp_path / "ac")
    yield


def words(n=8, t0=0.5):
    return [{"w": w, "s": t0 + i * 0.4, "e": t0 + i * 0.4 + 0.35} for i, w in enumerate("this is the moment it all changed forever".split()[:n])]


def dialogues(a: str, style: str = "Default") -> list[str]:
    return [ln for ln in a.splitlines() if ln.startswith("Dialogue:") and f",{style},," in ln]          # not the glitch / echo copies (named "Echo")


def t(s: str) -> float:
    h, m, r = s.split(":")
    return int(h) * 3600 + int(m) * 60 + float(r)


def test_every_style_builds_one_caption_at_a_time():
    for st in captions.STYLES:
        a = cut.ass_for(words(), 0, 5, st, 720, 1280)
        assert a and dialogues(a), st
        ev = [(t(x.split(",")[1]), t(x.split(",")[2])) for x in dialogues(a)]
        assert all(e1 <= s2 + 1e-6 for (_, e1), (s2, _) in zip(ev, ev[1:])), st
    assert set(captions.LABELS) >= {"bounce", "pop", "hype", "clean", "none", "karaoke", "gaming", "desi"}


def test_size_position_font_and_offset_are_applied():
    a = cut.ass_for(words(), 0, 5, "bounce", 720, 1280, cap={"size": 150, "x": 0.5, "y": 0.3, "font": "Anton", "offset_ms": -200, "upper": True})
    assert "Style: Default,Anton,90," in a                                   # 0.047 * 1280 * 1.5
    assert "\\pos(360,384)" in a and "THIS" in a
    first = dialogues(a)[0]
    assert first.split(",")[1] == "0:00:00.30"                               # 0.5 s - 0.2 s
    b = cut.ass_for(words(), 0, 5, "bounce", 720, 1280, cap={"font": "Not A Font", "size": 999})
    assert "Style: Default,Poppins,96," in b                                 # unknown font ignored, size capped at 160%


def test_animations():
    k = cut.ass_for(words(4), 0, 5, "karaoke", 720, 1280)
    assert "\\kf" in k and len(dialogues(k)) == 1
    tw = cut.ass_for(words(4), 0, 5, "typewriter", 720, 1280)
    assert "\\alpha&HFF&" in tw
    for anim, mark in (("fade", "\\fad("), ("slide", "\\move("), ("zoom", "\\fscx70"), ("elastic", "\\fscx135"), ("shake", "\\frz4"), ("pulse", "\\fscx110")):
        assert mark in cut.ass_for(words(4), 0, 5, "clean", 720, 1280, cap={"anim": anim}), anim
    assert "\\3a&H00&" in cut.ass_for(words(4), 0, 5, "boxed", 720, 1280) and "\\blur3" in cut.ass_for(words(4), 0, 5, "neon", 720, 1280)


def test_long_words_shrink_instead_of_wrapping():
    long = [{"w": "unbelievablyhuge", "s": 0.1, "e": 0.9}]
    a = cut.ass_for(long, 0, 2, "word", 720, 1280)
    fs = int(re.search(r"\\fs(\d+)", dialogues(a)[0]).group(1))
    assert len("UNBELIEVABLYHUGE") * fs * captions._width("Anton", True) <= 720 - 100 + 1


def test_brand_events():
    br = pipeline.clean_brand({"wm": {"kind": "text", "text": "@me", "pos": "tl", "opacity": 50}, "lower": {"on": True, "name": "Rohit", "sub": "comedian"},
                               "end": {"on": True, "text": "Follow @me", "sub": "part 2", "secs": 2}, "junk": 1})
    assert set(br) == {"wm", "lower", "end"}
    a = cut.ass_for([], 0, 10, "none", 720, 1280, brand=br)                  # branding without captions still makes a file
    assert a and "@me" in a and "ROHIT" not in a and "Rohit" in a and "COMEDIAN" in a and "Follow @me" in a
    end = [ln for ln in a.splitlines() if ",End," in ln]
    assert end and all(ln.split(",")[1] == "0:00:08.00" for ln in end)
    assert cut.ass_for([], 0, 10, "none", 720, 1280) is None


def test_hinglish():
    assert translit.to_roman("नि मैं कुछ नि पीती") == "ni main kuchh ni piti"
    assert translit.to_roman("समझना बहुत मुश्किल है") == "samajhna bahut mushkil hai"
    assert translit.to_roman("GTA 6 क्या बात है!") == "GTA 6 kya baat hai!"
    a = cut.ass_for([{"w": "कुछ", "s": 0.1, "e": 0.5}, {"w": "नहीं", "s": 0.5, "e": 0.9}], 0, 2, "desi", 720, 1280, roman=True)
    assert "kuchh" in a and "nahi" in a and "कुछ" not in a


def test_build_opts_reads_caption_and_brand_from_forms():
    o = pipeline.build_opts({"caption": "gaming", "cap": json.dumps({"size": 120, "evil": 1}), "brand": json.dumps({"wm": {"kind": "text", "text": "@x"}}),
                             "cap_lang": "roman", "whisper_model": "medium", "mode": "captions", "count": 9})
    assert o["caption"] == "gaming" and o["cap"] == {"size": 120} and o["brand"]["wm"]["text"] == "@x" and o["cap_lang"] == "roman"
    assert o["whisper_model"] == "medium" and o["mode"] == "captions" and o["count"] == 1 and o["tighten"] is False and o["smart"] == "off"
    bad = pipeline.build_opts({"caption": "nope", "cap_lang": "klingon", "whisper_model": "huge", "mode": "x", "cap": "{bad"})
    assert bad["caption"] == "bounce" and bad["cap_lang"] == "auto" and bad["whisper_model"] == "small" and bad["mode"] == "clips" and bad["cap"] == {}


def test_estimate_grows_with_work():
    a = pipeline.estimate(10, {"count": 3}, cpus=4)
    b = pipeline.estimate(10, {"count": 10}, cpus=4)
    c = pipeline.estimate(1, {"mode": "captions"}, cpus=4)
    assert a["low"] < b["low"] and a["low"] <= a["high"] and c["clips"] == 1 and c["high"] <= a["high"]


def test_saved_looks():
    store.save_brand({"name": "GTA", "caption": "gaming", "cap": {"size": 120, "bad": 1}, "brand": {"wm": {"kind": "text", "text": "@g"}}, "evil": 1})
    store.save_brand({"name": "gta", "caption": "pop"})                       # same name replaces
    b = store.brands()
    assert len(b) == 1 and b[0]["caption"] == "pop" and "evil" not in b[0]
    assert store.delete_brand("GTA") == []
    with pytest.raises(ValueError):
        store.save_brand({"name": "  "})


def test_api_fonts_logo_brands_system_estimate(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from studio.autoclip.routes import router
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    ov = c.get("/api/autoclip").json()["capabilities"]
    assert "gaming" in ov["caption_styles"] and ov["caption_styles"]["gaming"]["hi"].startswith("#") and "karaoke" in ov["anims"]
    assert any(f["name"] == "Bangers" for f in ov["fonts"]) and "medium" in ov["whisper_models"]
    assert c.get("/api/autoclip/fonts/file/Bangers.ttf").status_code == 200
    font = captions.ASSETS / "LilitaOne.ttf"
    r = c.post("/api/autoclip/fonts", files={"file": ("MyFont.ttf", font.read_bytes(), "font/ttf")})
    assert r.status_code == 200 and r.json()["added"] == "Lilita One"
    assert c.post("/api/autoclip/fonts", files={"file": ("x.ttf", b"not a font", "font/ttf")}).status_code == 400
    assert c.post("/api/autoclip/brands", json={"name": "Look", "caption": "neon"}).json()["brands"][0]["caption"] == "neon"
    s = c.get("/api/autoclip/system").json()
    assert s["cpus"] >= 1 and "encoder" in s
    assert c.post("/api/autoclip/estimate", json={"minutes": 5, "opts": {"count": 2}}).json()["clips"] == 2
    assert c.post("/api/autoclip/estimate", json={"minutes": 0}).status_code == 400
    if shutil.which("ffmpeg"):
        png = tmp_path / "l.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=120x40", "-frames:v", "1", str(png)], check=True)
        assert c.post("/api/autoclip/brand/logo", files={"file": ("l.png", png.read_bytes(), "image/png")}).status_code == 200
        assert c.get("/api/autoclip/brands").json()["has_logo"] is True


@needs_ffmpeg
def test_captions_only_job_keeps_the_whole_clip_with_branding_and_logo(tmp_path):
    src = tmp_path / "mine.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=1280x720:r=25:d=9", "-f", "lavfi", "-i", "sine=f=300:d=9",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(src)], check=True)
    (store.ROOT / "brand").mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=white:s=200x80", "-frames:v", "1", str(store.ROOT / "brand" / "logo.png")], check=True)
    o = pipeline.build_opts({"mode": "captions", "caption": "gaming", "layout": "blur", "edit": "off", "music": "none", "accurate": "false",
                             "brand": {"wm": {"kind": "logo", "pos": "tl", "size": 20}, "end": {"on": True, "text": "Follow me"}}})
    job = pipeline.new_job(o, {"kind": "upload", "name": "mine"})
    d = store.jdir(job["id"])
    shutil.copy(src, d / "source.mp4")
    (d / "source.srt").write_text(SRT)
    pipeline._cancel[job["id"]] = threading.Event()
    pipeline._run(job["id"])
    j = store.load(job["id"])
    assert j["status"] == "done", j.get("error")
    assert len(j["clips"]) == 1
    c = j["clips"][0]
    assert c["start"] == 0 and c["end"] >= 8.9 and (d / c["file"]).is_file()
    assert j["steps"]["get"]["secs"] is not None and j["steps"]["cut"]["secs"] is not None
    ass = (d / c["file"]).with_suffix(".ass").read_text()
    assert "Follow me" in ass and "MOMENT" in ass
