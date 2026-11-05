"""
Real video output: narration voice timing, the four video providers
(Replicate and ComfyUI against simulated servers - no network in tests),
captions, and the final ffmpeg render.

ffmpeg-dependent tests are skipped if ffmpeg isn't installed (it is in
the api/worker image).
"""

import asyncio
import json
import shutil
import subprocess
import sys
import types
from pathlib import Path

import httpx
import pytest

from agentic_core.media.ffmpeg import probe_duration, sniff_video_ext
from agentic_core.models.video import comfyui_provider, replicate_provider
from agentic_core.models.video.comfyui_provider import ComfyUIVideoProvider, fill_placeholders, frame_count
from agentic_core.models.video.factory import get_video_provider, resolve_video_choice
from agentic_core.models.video.motion_provider import MOVE_ORDER, MotionVideoProvider, pick_move
from agentic_core.models.video.replicate_provider import ReplicateVideoProvider, build_model_input
from agentic_core.pipelines.audio.tts import EdgeTTSProvider, MockTTSProvider, align_words, get_tts_provider
from agentic_core.pipelines.render.assemble import RenderSegment, parse_size, render_video, segment_durations
from agentic_core.pipelines.render.captions import CaptionWord, build_ass, chunk_words

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def _run(coro):
    return asyncio.run(coro)


def _ffmpeg_bytes(args: list[str], suffix: str, tmp_path: Path) -> bytes:
    out = tmp_path / f"gen{len(list(tmp_path.iterdir()))}.{suffix}"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, str(out)], check=True)
    return out.read_bytes()


def _png(tmp_path: Path, size: str = "720x1280") -> bytes:
    return _ffmpeg_bytes(["-f", "lavfi", "-i", f"testsrc2=s={size}", "-frames:v", "1"], "png", tmp_path)


def _patch_httpx(monkeypatch, module, handler):
    real = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(handler)
        return real(*args, **kwargs)

    monkeypatch.setattr(module.httpx, "AsyncClient", factory)


# -- TTS ---------------------------------------------------------------------


def test_tts_default_is_offline_mock(monkeypatch):
    monkeypatch.delenv("TTS_PROVIDER", raising=False)
    assert isinstance(get_tts_provider(), MockTTSProvider)


def test_tts_edge_selected_with_voice(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "edge")
    monkeypatch.setenv("TTS_VOICE", "en-GB-RyanNeural")
    provider = get_tts_provider()
    assert isinstance(provider, EdgeTTSProvider)
    assert provider.voice == "en-GB-RyanNeural"


def test_tts_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "nope")
    with pytest.raises(ValueError, match="Unknown TTS_PROVIDER"):
        get_tts_provider()


def test_align_words_keeps_punctuation_for_sentence_splitting():
    text = "Meet the Sun. It is 93 million miles away!"
    bounds = [
        ("Meet", 0.1, 0.3), ("the", 0.3, 0.4), ("Sun", 0.4, 0.8),
        ("It", 1.0, 1.1), ("is", 1.1, 1.2), ("93", 1.2, 1.8),
        ("million", 1.8, 2.2), ("miles", 2.2, 2.5), ("away", 2.5, 2.9),
    ]
    words = align_words(text, bounds, 3.2)
    assert [w.word for w in words] == text.split()
    assert words[2].word == "Sun." and (words[2].start, words[2].end) == (0.4, 0.8)
    assert words[-1].word == "away!" and words[-1].end == 2.9


def test_align_words_interpolates_skipped_tokens_and_falls_back():
    words = align_words("Hello — world", [("Hello", 0.0, 0.5), ("world", 0.9, 1.4)], 1.6)
    assert words[1].word == "—" and words[1].start == 0.5 and words[1].end == 0.9
    # Nothing matches -> even spread over the real duration.
    spread = align_words("one two three four", [("x", 0, 1)], 4.0)
    assert [(w.start, w.end) for w in spread] == [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0), (3.0, 4.0)]


def test_edge_tts_provider_returns_audio_and_word_timings(monkeypatch):
    class FakeCommunicate:
        def __init__(self, text, voice, *, rate, boundary):
            assert boundary == "WordBoundary"
            self.text = text

        async def stream(self):
            yield {"type": "audio", "data": b"ID3fake-mp3"}
            offset = 1_000_000
            for token in ("Hi", "there"):
                yield {"type": "WordBoundary", "offset": offset, "duration": 3_000_000, "text": token}
                offset += 4_000_000

    monkeypatch.setitem(sys.modules, "edge_tts", types.SimpleNamespace(Communicate=FakeCommunicate))

    async def fake_duration(audio_bytes, boundaries):
        return 1.2

    monkeypatch.setattr("agentic_core.pipelines.audio.tts._audio_duration", fake_duration)
    audio = _run(EdgeTTSProvider().synthesize("Hi there."))
    assert audio.format == "mp3" and audio.audio_bytes == b"ID3fake-mp3"
    assert [(w.word, w.start, w.end) for w in audio.words] == [("Hi", 0.1, 0.4), ("there.", 0.5, 0.8)]


# -- Factory -----------------------------------------------------------------


def test_factory_new_providers(monkeypatch, tmp_path):
    for name in ("VIDEO_PROVIDER", "REPLICATE_API_TOKEN", "COMFYUI_URL"):
        monkeypatch.delenv(name, raising=False)
    assert isinstance(get_video_provider("motion"), MotionVideoProvider)
    with pytest.raises(ValueError, match="REPLICATE_API_TOKEN"):
        get_video_provider("replicate")
    with pytest.raises(ValueError, match="COMFYUI_URL"):
        get_video_provider("comfyui")

    monkeypatch.setenv("REPLICATE_API_TOKEN", "r8_test")
    monkeypatch.setenv("REPLICATE_VIDEO_MODEL", "kwaivgi/kling-v2.1")
    replicate = get_video_provider("replicate")
    assert isinstance(replicate, ReplicateVideoProvider) and replicate.model == "kwaivgi/kling-v2.1"

    monkeypatch.setenv("COMFYUI_URL", "http://comfy:8188")
    assert isinstance(get_video_provider("comfyui"), ComfyUIVideoProvider)
    assert resolve_video_choice("mock") is None and resolve_video_choice("") is None


# -- Replicate ---------------------------------------------------------------


def test_replicate_inputs_per_model_family(monkeypatch):
    monkeypatch.delenv("REPLICATE_VIDEO_INPUT_JSON", raising=False)
    common = dict(prompt="p", image_ref="data:x", seed=7, duration_seconds=4.0, width=720, height=1280,
                  resolution="480p")
    seedance = build_model_input("bytedance/seedance-1-lite", **common)
    assert seedance == {"prompt": "p", "duration": 5, "resolution": "480p", "aspect_ratio": "9:16",
                        "image": "data:x", "seed": 7}
    assert build_model_input("kwaivgi/kling-v2.1", **common)["start_image"] == "data:x"
    minimax = build_model_input("minimax/video-01", **common)
    assert minimax["first_frame_image"] == "data:x" and "seed" not in minimax
    assert build_model_input("wan-video/wan-2.2-i2v-fast", **common) == {"prompt": "p", "image": "data:x", "seed": 7}

    monkeypatch.setenv("REPLICATE_VIDEO_INPUT_JSON", '{"resolution": "720p", "camera_fixed": true}')
    tuned = build_model_input("bytedance/seedance-1-lite", **common)
    assert tuned["resolution"] == "720p" and tuned["camera_fixed"] is True


def test_replicate_generate_polls_until_done_and_downloads(monkeypatch):
    calls: list[str] = []
    polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(f"{request.method} {request.url}")
        if request.url.host == "api.replicate.com":
            assert request.headers["Authorization"] == "Bearer r8_test"
        else:  # the output file host never gets the API token
            assert "Authorization" not in request.headers
        if request.method == "POST":
            body = json.loads(request.content)
            assert body["input"]["image"].startswith("data:image/png;base64,")
            return httpx.Response(201, json={
                "id": "p1", "status": "starting",
                "urls": {"get": "https://api.replicate.com/v1/predictions/p1"},
            })
        if request.url.path == "/v1/predictions/p1":
            polls["n"] += 1
            if polls["n"] < 2:
                return httpx.Response(200, json={"id": "p1", "status": "processing", "urls": {}})
            return httpx.Response(200, json={"id": "p1", "status": "succeeded",
                                             "output": "https://replicate.delivery/clip.mp4"})
        return httpx.Response(200, content=b"\x00\x00\x00\x18ftypmp42clip")

    _patch_httpx(monkeypatch, replicate_provider, handler)
    provider = ReplicateVideoProvider("r8_test", poll_interval=0)
    clip = _run(provider.generate("a sun", seed=1, duration_seconds=4.0, image=b"\x89PNG\r\n\x1a\nimg"))
    assert clip.endswith(b"clip") and sniff_video_ext(clip) == "mp4"
    assert calls[0] == "POST https://api.replicate.com/v1/models/bytedance/seedance-1-lite/predictions"
    assert polls["n"] == 2


def test_replicate_billing_error_is_explained(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"detail": "Insufficient credit"})

    _patch_httpx(monkeypatch, replicate_provider, handler)
    with pytest.raises(RuntimeError, match="Insufficient credit.*billing"):
        _run(ReplicateVideoProvider("r8_test").generate("x"))


# -- ComfyUI -----------------------------------------------------------------


def test_comfyui_frame_counts_follow_model_rules():
    assert frame_count(4.0, 24, 8, 121) == 97      # LTX: 8k+1
    assert frame_count(4.0, 16, 4, 81) == 65       # Wan: 4k+1
    assert frame_count(10.0, 24, 8, 121) == 121    # capped


def test_comfyui_placeholders_become_typed_values():
    graph = {"3": {"inputs": {"seed": "{{SEED}}", "text": "cinematic, {{PROMPT}}", "length": "{{FRAMES}}",
                              "image": "{{IMAGE}}"}}}
    filled = fill_placeholders(graph, {"{{SEED}}": 5, "{{PROMPT}}": "a sun", "{{FRAMES}}": 97,
                                       "{{IMAGE}}": "avos_1.png"})
    assert filled["3"]["inputs"] == {"seed": 5, "text": "cinematic, a sun", "length": 97, "image": "avos_1.png"}


def test_comfyui_generate_uploads_queues_waits_and_downloads(monkeypatch, tmp_path):
    workflow = {
        "1": {"class_type": "LoadImage", "inputs": {"image": "{{IMAGE}}"}},
        "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{PROMPT}}"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": "{{SEED}}", "length": "{{FRAMES}}"}},
    }
    path = tmp_path / "video.json"
    path.write_text(json.dumps(workflow))
    queued: dict = {}
    history_calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/upload/image":
            return httpx.Response(200, json={"name": "avos_x.png", "subfolder": "", "type": "input"})
        if request.url.path == "/prompt":
            queued.update(json.loads(request.content)["prompt"])
            return httpx.Response(200, json={"prompt_id": "abc"})
        if request.url.path == "/history/abc":
            history_calls["n"] += 1
            if history_calls["n"] == 1:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"abc": {
                "status": {"status_str": "success", "completed": True},
                "outputs": {"9": {"images": [{"filename": "AVOS_00001.mp4", "subfolder": "video",
                                              "type": "output"}]}},
            }})
        if request.url.path == "/view":
            assert request.url.params["filename"] == "AVOS_00001.mp4"
            return httpx.Response(200, content=b"\x00\x00\x00\x18ftypmp42comfy")
        return httpx.Response(404)

    _patch_httpx(monkeypatch, comfyui_provider, handler)
    provider = ComfyUIVideoProvider("http://comfy:8188", str(path), poll_interval=0)
    clip = _run(provider.generate("a sun", seed=3, duration_seconds=4.0, image=b"\x89PNG..."))
    assert clip.endswith(b"comfy")
    assert queued["1"]["inputs"]["image"] == "avos_x.png"
    assert queued["2"]["inputs"]["text"] == "a sun"
    assert queued["3"]["inputs"] == {"seed": 3, "length": 97}


def test_comfyui_rejects_non_api_export(tmp_path):
    path = tmp_path / "video.json"
    path.write_text(json.dumps({"nodes": [], "links": []}))
    with pytest.raises(RuntimeError, match="Export \\(API\\)"):
        _run(ComfyUIVideoProvider("http://comfy:8188", str(path)).generate("x"))


def test_comfyui_reports_workflow_errors(monkeypatch, tmp_path):
    path = tmp_path / "video.json"
    path.write_text(json.dumps({"2": {"inputs": {"text": "{{PROMPT}}"}}}))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/prompt":
            return httpx.Response(200, json={"prompt_id": "abc"})
        return httpx.Response(200, json={"abc": {"status": {"status_str": "error", "messages": [
            ["execution_error", {"exception_message": "CUDA out of memory"}]]}, "outputs": {}}})

    _patch_httpx(monkeypatch, comfyui_provider, handler)
    with pytest.raises(RuntimeError, match="CUDA out of memory"):
        _run(ComfyUIVideoProvider("http://comfy:8188", str(path), poll_interval=0).generate("x"))


# -- Motion + render ---------------------------------------------------------


def test_motion_moves_are_deterministic_and_varied():
    assert pick_move(1, "a") == pick_move(1, "a")
    assert len({pick_move(seed, "shot") for seed in range(40)}) == len(MOVE_ORDER)


@needs_ffmpeg
def test_motion_provider_renders_clip_of_requested_length(tmp_path):
    clip = _run(MotionVideoProvider().generate("sun", width=360, height=640, seed=2, duration_seconds=2.5,
                                               image=_png(tmp_path, "360x640")))
    out = tmp_path / "m.mp4"
    out.write_bytes(clip)
    assert sniff_video_ext(clip) == "mp4"
    assert abs(_run(probe_duration(out)) - 2.5) < 0.1


def test_motion_provider_needs_an_image():
    with pytest.raises(RuntimeError, match="image provider"):
        _run(MotionVideoProvider().generate("x", image=None))


def test_captions_chunks_and_highlight():
    words = [CaptionWord(t, i * 0.5, i * 0.5 + 0.4) for i, t in enumerate("Meet the Sun. It is huge!".split())]
    chunks = chunk_words(words)
    assert [[w.text for w in c] for c in chunks] == [["Meet", "the", "Sun."], ["It", "is", "huge!"]]
    ass = build_ass(words, width=720, height=1280, total_duration=4.0)
    assert ass.count("Dialogue:") == 6
    assert r"{\c&H00F2FF&}Sun{\c&HFFFFFF&}" in ass  # spoken word highlighted, "." dropped
    assert "huge!" in ass


def test_segment_timeline_has_no_gaps():
    segs = [RenderSegment(0.2, 2.0), RenderSegment(2.0, 5.0), RenderSegment(5.0, 6.0)]
    assert segment_durations(segs, 7.0) == [2.0, 3.0, 2.0]
    assert parse_size("1080x1920", "9:16") == (1080, 1920)
    assert parse_size(None, "16:9") == (1920, 1080)


@needs_ffmpeg
def test_render_video_joins_clip_image_and_card_with_audio_and_captions(tmp_path):
    clip = _ffmpeg_bytes(["-f", "lavfi", "-i", "testsrc=s=320x568:r=24:d=1"], "mp4", tmp_path)
    audio = _ffmpeg_bytes(["-f", "lavfi", "-i", "sine=frequency=300:duration=3.6"], "mp3", tmp_path)
    segments = [
        RenderSegment(0.0, 1.2, clip=clip),
        RenderSegment(1.2, 2.4, image=_png(tmp_path, "640x360"), seed=1, prompt="x"),
        RenderSegment(2.4, 3.6),
    ]
    words = [CaptionWord(t, i * 0.6, i * 0.6 + 0.5) for i, t in enumerate("one two three four five six.".split())]
    result = _run(render_video(segments, audio=audio, audio_ext="mp3", words=words, size="360x640"))
    assert result.sources == ["clip", "image", "card"]
    assert (result.width, result.height) == (360, 640)
    assert 3.6 <= result.duration_seconds <= 4.3
    out = tmp_path / "final.mp4"
    out.write_bytes(result.video)
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert sorted(probe) == ["audio", "video"]


# -- Free image chain / provider failures ------------------------------------


def test_free_image_chain_prefers_cloudflare_then_pollinations(monkeypatch):
    from agentic_core.models.image.factory import get_image_provider

    for name in ("CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN", "IMAGE_SERVICE_URL"):
        monkeypatch.delenv(name, raising=False)
    assert [m.provider.name for m in get_image_provider("free").members] == ["pollinations"]

    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "acc")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok")
    monkeypatch.setenv("IMAGE_SERVICE_URL", "http://sd:7860")
    chain = get_image_provider("free")
    assert [m.provider.name for m in chain.members] == ["cloudflare", "pollinations", "local"]
    assert not any(m.is_paid for m in chain.members)  # never spends money


def test_pollinations_402_fails_fast_without_retrying(monkeypatch):
    from agentic_core.models.image import pollinations_provider
    from agentic_core.models.image.pollinations_provider import PollinationsProvider

    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(402, json={"error": "Payment Required"})

    _patch_httpx(monkeypatch, pollinations_provider, handler)
    with pytest.raises(RuntimeError, match="402"):
        _run(PollinationsProvider(retry_backoff_seconds=0).generate("sun"))
    assert calls["n"] == 1


def test_cloudflare_sends_no_seed_by_default(monkeypatch):
    """flux-1-schnell (the default model) rejects a 'seed' field with a 400."""
    from agentic_core.models.image import cloudflare_provider
    from agentic_core.models.image.cloudflare_provider import CloudflareImageProvider

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"success": True, "result": {"image": "aGk="}})

    monkeypatch.delenv("CLOUDFLARE_IMAGE_SEED", raising=False)
    _patch_httpx(monkeypatch, cloudflare_provider, handler)
    assert _run(CloudflareImageProvider("acc", "tok").generate("sun", seed=123)) == b"hi"
    assert "seed" not in seen


def test_cloudflare_clamps_seed_and_explains_auth_errors(monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_IMAGE_SEED", "1")
    from agentic_core.models.image import cloudflare_provider
    from agentic_core.models.image.cloudflare_provider import CloudflareImageProvider

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(403, json={"success": False, "errors": [{"message": "Authentication error"}]})

    _patch_httpx(monkeypatch, cloudflare_provider, handler)
    with pytest.raises(RuntimeError, match="Authentication error.*CLOUDFLARE_API_TOKEN"):
        _run(CloudflareImageProvider("acc", "tok").generate("sun", seed=744740083238347671))
    assert 0 <= seen["seed"] < 2_147_483_647


# -- Week 4b: styles, fal.ai, music ------------------------------------------


def test_style_presets_and_script_guidance_reach_the_prompt():
    from agentic_core.pipelines.script.generator import _build_prompt
    from agentic_core.styles import get_style

    assert get_style(None).name == "storybook" and get_style("nope").name == "storybook"
    viral = get_style("viral_3d")
    assert "3D" in viral.visual_style and viral.caption_words == 2 and viral.music_mood == "suspense"
    prompt = _build_prompt(topic="t", duration_seconds=30, aspect_ratio="9:16", audience="general",
                           style_guidance=viral.script_guidance)
    assert "hook" in prompt


def test_fal_inputs_per_model():
    from agentic_core.models.video.fal_provider import build_fal_input

    kling = build_fal_input("fal-ai/kling-video/v2.1/standard/image-to-video", prompt="p", image_url="data:x",
                            duration_seconds=4.2, width=720, height=1280, seed=9)
    assert kling["duration"] == "5" and kling["image_url"] == "data:x" and "seed" not in kling
    assert build_fal_input("fal-ai/kling-video/v2.1/pro/image-to-video", prompt="p", image_url=None,
                           duration_seconds=8, width=720, height=1280, seed=None)["duration"] == "10"
    wan = build_fal_input("fal-ai/wan/v2.2-a14b/image-to-video", prompt="p", image_url="data:x",
                          duration_seconds=4, width=720, height=1280, seed=2**40)
    assert 0 <= wan["seed"] < 2_147_483_647


def test_fal_queue_submit_poll_fetch(monkeypatch):
    from agentic_core.models.video import fal_provider
    from agentic_core.models.video.fal_provider import FalVideoProvider

    polls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "queue.fal.run":
            assert request.headers["Authorization"] == "Key fal_test"
            if request.method == "POST":
                assert json.loads(request.content)["image_url"].startswith("data:image/png;base64,")
                return httpx.Response(200, json={
                    "request_id": "r1",
                    "status_url": "https://queue.fal.run/m/requests/r1/status",
                    "response_url": "https://queue.fal.run/m/requests/r1",
                })
            if request.url.path.endswith("/status"):
                polls["n"] += 1
                return httpx.Response(200, json={"status": "IN_PROGRESS" if polls["n"] < 2 else "COMPLETED"})
            return httpx.Response(200, json={"video": {"url": "https://v3.fal.media/files/clip.mp4"}})
        assert "Authorization" not in request.headers
        return httpx.Response(200, content=b"\x00\x00\x00\x18ftypmp42fal")

    _patch_httpx(monkeypatch, fal_provider, handler)
    clip = _run(FalVideoProvider("fal_test", poll_interval=0).generate("x", image=b"\x89PNG\r\n\x1a\nimg"))
    assert clip.endswith(b"fal") and polls["n"] == 2


def test_fal_empty_balance_is_explained(monkeypatch):
    from agentic_core.models.video import fal_provider
    from agentic_core.models.video.fal_provider import FalVideoProvider

    _patch_httpx(monkeypatch, fal_provider,
                 lambda r: httpx.Response(403, json={"detail": "User is locked. Reason: Exhausted balance."}))
    with pytest.raises(RuntimeError, match="FAL_KEY|balance"):
        _run(FalVideoProvider("fal_test").generate("x", image=b"img"))


def test_factory_fal(monkeypatch):
    monkeypatch.delenv("FAL_KEY", raising=False)
    with pytest.raises(ValueError, match="FAL_KEY"):
        get_video_provider("fal")
    monkeypatch.setenv("FAL_KEY", "k")
    assert get_video_provider("fal").name == "fal"


def test_music_picking(tmp_path):
    from agentic_core.pipelines.render.assemble import pick_music, pick_sfx

    assert pick_music(tmp_path, "suspense", "p1") is None and pick_sfx(tmp_path) is None
    (tmp_path / "suspense").mkdir()
    (tmp_path / "sfx").mkdir()
    for n in ("a.mp3", "b.mp3", "notes.txt"):
        (tmp_path / "suspense" / n).write_bytes(b"x")
    (tmp_path / "calm.mp3").write_bytes(b"x")
    (tmp_path / "sfx" / "click.wav").write_bytes(b"x")
    (tmp_path / "sfx" / "Whoosh_01.mp3").write_bytes(b"x")
    assert pick_music(tmp_path, "suspense", "p1").name in ("a.mp3", "b.mp3")
    assert pick_music(tmp_path, "suspense", "p1") == pick_music(tmp_path, "suspense", "p1")
    assert pick_music(tmp_path, "uplifting", "p1").name == "calm.mp3"  # falls back to the root
    assert pick_sfx(tmp_path).name == "Whoosh_01.mp3"


@needs_ffmpeg
def test_render_mixes_music_and_whooshes(tmp_path):
    voice = _ffmpeg_bytes(["-f", "lavfi", "-i", "sine=frequency=400:duration=3"], "mp3", tmp_path)
    music = tmp_path / "bed.mp3"
    music.write_bytes(_ffmpeg_bytes(["-f", "lavfi", "-i", "sine=frequency=110:duration=1"], "mp3", tmp_path))
    whoosh = tmp_path / "whoosh.wav"
    whoosh.write_bytes(_ffmpeg_bytes(["-f", "lavfi", "-i", "anoisesrc=d=0.4"], "wav", tmp_path))
    segs = [RenderSegment(0, 1.5), RenderSegment(1.5, 3.0)]
    result = _run(render_video(segs, audio=voice, audio_ext="mp3", words=[], size="160x284",
                               music=music, sfx=whoosh))
    assert result.music == "bed.mp3" and result.duration_seconds >= 3.0  # music looped to full length
