"""
Assemble the finished video:

    per shot (in timeline order)
      AI clip   -> scaled/cropped to the frame, trimmed or slowed/held
                   to the shot's exact length
      image     -> animated with a camera move (motion provider)
      nothing   -> a plain dark card (keeps timing intact)
    -> concatenated -> narration mixed in -> captions burned in -> MP4

Every shot occupies [its start, next shot's start) on the narration
timeline, so cuts land on the semantic beats and there are no gaps.
"""

import asyncio
import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from agentic_core.media.ffmpeg import probe_duration, run_ffmpeg
from agentic_core.models.video.motion_provider import FPS, pick_move, zoompan_filter
from agentic_core.pipelines.render.captions import CaptionWord, build_ass

# Final output size per aspect ratio: Full HD (override with RENDER_SIZE, e.g.
# "720x1280" for faster renders on a slow PC).
RENDER_SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080)}
MAX_SLOWDOWN = 1.6  # a short AI clip is slowed at most this much, then held


@dataclass
class RenderSegment:
    start: float
    end: float
    clip: bytes | None = None
    image: bytes | None = None
    seed: int | None = None
    prompt: str = ""


@dataclass
class RenderResult:
    video: bytes
    duration_seconds: float
    width: int
    height: int
    sources: list[str] = field(default_factory=list)  # "clip" | "image" | "card" per shot
    music: str | None = None  # file name of the background track used


AUDIO_EXTS = (".mp3", ".wav", ".m4a", ".ogg", ".flac", ".aac")


def _audio_files(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in AUDIO_EXTS)


def pick_music(library: str | Path | None, mood: str, key: str) -> Path | None:
    """A track from <library>/<mood>/, else any track in <library>/
    (excluding sfx/). Deterministic per key, so a re-render keeps its
    track, but different videos get different tracks."""
    if not library:
        return None
    root = Path(library)
    tracks = _audio_files(root / mood) or _audio_files(root)
    if not tracks:
        return None
    return tracks[int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) % len(tracks)]


def pick_sfx(library: str | Path | None) -> Path | None:
    """The transition sound played on each cut: <library>/sfx/, files
    with 'whoosh' in the name preferred."""
    if not library:
        return None
    files = _audio_files(Path(library) / "sfx")
    whooshes = [f for f in files if "whoosh" in f.name.lower() or "swoosh" in f.name.lower()]
    return (whooshes or files or [None])[0]


def build_audio_filter(*, has_music: bool, cut_times: list[float], has_sfx: bool, total: float,
                       music_volume: float, sfx_volume: float) -> str:
    """Voice on top; music ducked under the voice (sidechain) with fades;
    a whoosh on every cut. Inputs: 1 = narration, 2 = music, 3 = sfx."""
    chains = ["[1:a]aresample=44100,aformat=channel_layouts=stereo,apad[voice]"]
    mix = ["[vmix]"]
    if has_music:
        chains[0] = chains[0].replace("[voice]", "[voicein]")
        chains.append("[voicein]asplit=2[vmix_pre][vkey]")
        chains.append("[vmix_pre]anull[vmix]")
        fade_out = max(0.0, total - 1.5)
        chains.append(
            f"[2:a]aresample=44100,aformat=channel_layouts=stereo,volume={music_volume:.3f},"
            f"afade=t=in:d=0.8,afade=t=out:st={fade_out:.2f}:d=1.5[music]"
        )
        chains.append("[music][vkey]sidechaincompress=threshold=0.02:ratio=6:attack=15:release=350[mduck]")
        mix.append("[mduck]")
    else:
        chains[0] = chains[0].replace("[voice]", "[vmix]")
    if has_sfx and cut_times:
        n = len(cut_times)
        base = f"[3:a]aresample=44100,aformat=channel_layouts=stereo,volume={sfx_volume:.3f}"
        if n > 1:
            chains.append(f"{base},asplit={n}" + "".join(f"[s{i}]" for i in range(n)))
        else:
            chains.append(f"{base}[s0]")
        for i, t in enumerate(cut_times):
            ms = max(0, int((t - 0.15) * 1000))  # lead in slightly so the whoosh peaks on the cut
            chains.append(f"[s{i}]adelay={ms}|{ms}[sd{i}]")
            mix.append(f"[sd{i}]")
    if len(mix) == 1:
        chains.append(f"{mix[0]}anull[aout]")
    else:
        chains.append("".join(mix) + f"amix=inputs={len(mix)}:duration=first:normalize=0[aout]")
    return ";".join(chains)


def parse_size(value: str | None, aspect_ratio: str) -> tuple[int, int]:
    if value and "x" in value.lower():
        w, h = value.lower().split("x", 1)
        try:
            width, height = int(w), int(h)
            return width - width % 2, height - height % 2
        except ValueError:
            pass
    return RENDER_SIZES.get(aspect_ratio, RENDER_SIZES["9:16"])


def segment_durations(segments: list[RenderSegment], total: float) -> list[float]:
    ordered = sorted(segments, key=lambda s: s.start)
    durations = []
    for i, seg in enumerate(ordered):
        start = 0.0 if i == 0 else seg.start
        end = ordered[i + 1].start if i + 1 < len(ordered) else max(total, seg.end)
        durations.append(max(0.4, end - start))
    return durations


# Shot segments prepared at once (each is one ffmpeg process). RENDER_PARALLEL overrides.
RENDER_PARALLEL = max(1, int(os.getenv("RENDER_PARALLEL") or max(1, min(4, (os.cpu_count() or 2) // 2))))


def _fit_filter(width: int, height: int) -> str:
    return (
        f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={width}:{height},setsar=1"
    )


async def _normalize_clip(src: Path, out: Path, duration: float, width: int, height: int) -> None:
    clip_len = await probe_duration(src)
    speed = 1.0
    if clip_len < duration:
        speed = min(MAX_SLOWDOWN, duration / max(clip_len, 0.1))
    vf = (
        f"{_fit_filter(width, height)},setpts={speed:.4f}*PTS,fps={FPS},"
        f"tpad=stop_mode=clone:stop_duration={duration:.3f},format=yuv420p"
    )
    await run_ffmpeg(
        ["-i", str(src), "-an", "-vf", vf, "-t", f"{duration:.3f}",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-r", str(FPS), str(out)],
        timeout=600,
    )


async def _image_clip(src: Path, out: Path, duration: float, width: int, height: int, seed, prompt) -> None:
    frames = max(2, round(duration * FPS))
    await run_ffmpeg(
        ["-i", str(src), "-vf", zoompan_filter(pick_move(seed, prompt), width, height, frames),
         "-frames:v", str(frames), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", str(out)],
        timeout=600,
    )


async def _card_clip(out: Path, duration: float, width: int, height: int) -> None:
    await run_ffmpeg(
        ["-f", "lavfi", "-i", f"color=c=0x101018:s={width}x{height}:r={FPS}:d={duration:.3f}",
         "-vf", "format=yuv420p", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", str(out)],
        timeout=120,
    )


def _filter_path(path: Path) -> str:
    # Escape for use inside an ffmpeg filter argument.
    return str(path).replace("\\", "/").replace(":", r"\:").replace("'", r"\'")


async def render_video(
    segments: list[RenderSegment],
    *,
    audio: bytes,
    audio_ext: str,
    words: list[CaptionWord],
    aspect_ratio: str = "9:16",
    size: str | None = None,
    captions: bool = True,
    caption_font: str = "DejaVu Sans",
    caption_words: int = 3,
    music: str | Path | None = None,
    music_volume: float = 0.22,
    sfx: str | Path | None = None,
    sfx_volume: float = 0.5,
) -> RenderResult:
    if not segments:
        raise ValueError("Nothing to render: the project has no shots.")

    width, height = parse_size(size, aspect_ratio)
    ordered = sorted(segments, key=lambda s: s.start)

    with tempfile.TemporaryDirectory(prefix="avos-render-") as tmp_dir:
        tmp = Path(tmp_dir)
        audio_path = tmp / f"narration.{audio_ext.lstrip('.')}"
        audio_path.write_bytes(audio)
        audio_len = await probe_duration(audio_path)
        total = max(audio_len + 0.4, ordered[-1].end)
        durations = segment_durations(ordered, total)

        # Each shot's segment is its own ffmpeg run: prepare them side by side (CPU cores), join in order.
        parts: list[Path] = [tmp / f"part_{i:03d}.mp4" for i in range(len(ordered))]
        sources: list[str] = [""] * len(ordered)
        sem = asyncio.Semaphore(RENDER_PARALLEL)

        async def prepare(i: int, seg: RenderSegment, duration: float) -> None:
            out = parts[i]
            async with sem:
                if seg.clip:
                    src = tmp / f"clip_{i:03d}.bin"
                    src.write_bytes(seg.clip)
                    await _normalize_clip(src, out, duration, width, height)
                    sources[i] = "clip"
                elif seg.image:
                    src = tmp / f"image_{i:03d}.img"
                    src.write_bytes(seg.image)
                    await _image_clip(src, out, duration, width, height, seg.seed, seg.prompt)
                    sources[i] = "image"
                else:
                    await _card_clip(out, duration, width, height)
                    sources[i] = "card"

        await asyncio.gather(*(prepare(i, seg, d) for i, (seg, d) in enumerate(zip(ordered, durations))))

        concat_list = tmp / "parts.txt"
        concat_list.write_text("".join(f"file '{p.as_posix()}'\n" for p in parts), encoding="utf-8")
        joined = tmp / "joined.mp4"
        await run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(joined)])

        vf = "format=yuv420p"
        if captions and words:
            ass = tmp / "captions.ass"
            ass.write_text(
                build_ass(words, width=width, height=height, total_duration=total, font=caption_font,
                          max_words=caption_words),
                encoding="utf-8",
            )
            vf = f"subtitles='{_filter_path(ass)}',format=yuv420p"

        music_path = Path(music) if music else None
        sfx_path = Path(sfx) if sfx else None
        cut_times, t = [], 0.0
        for d in durations[:-1]:
            t += d
            cut_times.append(t)
        inputs = ["-i", str(joined), "-i", str(audio_path)]
        inputs += ["-stream_loop", "-1", "-i", str(music_path)] if music_path else ["-f", "lavfi", "-i", "anullsrc"]
        if sfx_path:
            inputs += ["-i", str(sfx_path)]
        audio_filter = build_audio_filter(
            has_music=bool(music_path), cut_times=cut_times, has_sfx=bool(sfx_path), total=total,
            music_volume=music_volume, sfx_volume=sfx_volume,
        )

        final = tmp / "final.mp4"
        await run_ffmpeg(
            [
                *inputs,
                "-filter_complex", f"[0:v]{vf}[vout];{audio_filter}",
                "-map", "[vout]", "-map", "[aout]",
                "-t", f"{total:.3f}",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", "-ar", "44100",
                "-movflags", "+faststart",
                str(final),
            ],
            timeout=1200,
        )
        return RenderResult(
            video=final.read_bytes(),
            duration_seconds=round(await probe_duration(final), 2),
            width=width,
            height=height,
            sources=sources,
            music=music_path.name if music_path else None,
        )
