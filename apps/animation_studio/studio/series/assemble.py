"""Cutting a part together: every shot fitted to its length, dialogue + sound effects on one track, the score
ducked under the voices, subtitles as a soft track (and a .srt next to the file), then parts → the episode.

    fit_shot(clip, seconds)    the clip scaled/cropped to the series format at 24 fps, trimmed or held to length
    shot_audio(...)            the line (or silence) + its sound effects, exactly as long as the shot
    part(...)                  shots → part.mp4 (+ part.srt)
    episode(...)               approved parts → episode.mp4 (+ episode.srt)
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .. import config
from .media import _ff, probe_seconds

FPS = 24


def fit_shot(src: Path, out: Path, seconds: float, w: int, h: int) -> Path:
    _ff(["-i", str(src), "-an", "-vf",
         f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},setsar=1,"
         f"tpad=stop_mode=clone:stop_duration={seconds:.3f},format=yuv420p",
         "-t", f"{seconds:.3f}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", str(out)])
    return out


def shot_audio(out: Path, seconds: float, line: Path | None, sfx: Path | None, line_at: float = 0.12,
               ambience: Path | None = None, ambience_at: float = 0.0, ambience_volume: float = 0.22) -> Path:
    """One 48 kHz stereo track, exactly `seconds` long: the line (delayed a touch) over the shot's sound effects, over
    the scene's ambience (looped, continuing from where the previous shot of the scene left it)."""
    ins = ["-f", "lavfi", "-t", f"{seconds:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    filters, labels = [], ["[0:a]"]
    if line is not None:
        ins += ["-i", str(line)]
        ms = int(line_at * 1000)
        filters.append(f"[{len(labels)}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[l]")
        labels.append("[l]")
    if sfx is not None:
        ins += ["-i", str(sfx)]
        filters.append(f"[{len(labels)}:a]aresample=48000,aformat=channel_layouts=stereo,volume={0.55 if line is not None else 0.9}[s]")
        labels.append("[s]")
    if ambience is not None and ambience.is_file():
        ins += ["-stream_loop", "-1", "-i", str(ambience)]
        filters.append(f"[{len(labels)}:a]aresample=48000,aformat=channel_layouts=stereo,"
                       f"atrim=start={ambience_at % max(0.5, probe_seconds(ambience)):.3f},asetpts=PTS-STARTPTS,volume={ambience_volume}[b]")
        labels.append("[b]")
    graph = ";".join(filters + [f"{''.join(labels)}amix=inputs={len(labels)}:duration=first:normalize=0,atrim=0:{seconds:.3f}[a]"])
    _ff([*ins, "-filter_complex", graph, "-map", "[a]", "-t", f"{seconds:.3f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(out)])
    return out


def _srt_time(t: float) -> str:
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def srt(rows: list[tuple[float, float, str]]) -> str:
    return "".join(f"{i + 1}\n{_srt_time(a)} --> {_srt_time(b)}\n{t}\n\n" for i, (a, b, t) in enumerate(rows) if t)


def part(shots: list[dict], work: Path, out: Path, w: int, h: int, music: Path | None, subtitles: list[tuple[float, float, str]],
         music_volume: float = 0.22) -> Path:
    """shots: [{"video": fitted.mp4, "audio": shot.wav, "seconds": s}] in order."""
    work.mkdir(parents=True, exist_ok=True)
    vlist, alist = work / "video.txt", work / "audio.txt"
    vlist.write_text("".join(f"file '{Path(x['video']).resolve().as_posix()}'\n" for x in shots), "utf-8")
    alist.write_text("".join(f"file '{Path(x['audio']).resolve().as_posix()}'\n" for x in shots), "utf-8")
    video, dialog = work / "video.mp4", work / "dialog.wav"
    _ff(["-f", "concat", "-safe", "0", "-i", str(vlist), "-c", "copy", str(video)])
    _ff(["-f", "concat", "-safe", "0", "-i", str(alist), "-c", "copy", str(dialog)])
    total = probe_seconds(video)
    mix = work / "mix.wav"
    if music is not None and music.is_file():
        # the score loops under the whole part, ducks under the voices, fades in and out
        _ff(["-i", str(dialog), "-stream_loop", "-1", "-i", str(music), "-filter_complex",
             f"[1:a]aresample=48000,aformat=channel_layouts=stereo,volume={music_volume},atrim=0:{total:.3f},"
             f"afade=t=in:d=1.5,afade=t=out:st={max(0.0, total - 2.0):.3f}:d=2[m];"
             f"[0:a]asplit=2[d][key];[m][key]sidechaincompress=threshold=0.03:ratio=8:attack=15:release=350[duck];"
             f"[d][duck]amix=inputs=2:duration=first:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]",
             "-map", "[a]", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(mix)])
    else:
        _ff(["-i", str(dialog), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000", "-ar", "48000", "-c:a", "pcm_s16le", str(mix)])
    sub = out.with_suffix(".srt")
    sub.write_text(srt(subtitles), "utf-8")
    args = ["-i", str(video), "-i", str(mix)]
    maps = ["-map", "0:v", "-map", "1:a"]
    if sub.stat().st_size:
        args += ["-i", str(sub)]
        maps += ["-map", "2:s", "-c:s", "mov_text", "-metadata:s:s:0", "title=Subtitles"]
    tmp = out.with_suffix(".tmp.mp4")
    # -t, not -shortest: the subtitle track ends with the last line, and a part that ends on action must not be cut there
    _ff([*args, *maps, "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{total:.3f}", "-movflags", "+faststart", str(tmp)])
    tmp.replace(out)
    return out


def episode(parts: list[Path], out: Path, subtitles: list[tuple[float, float, str]]) -> Path:
    lst = out.parent / "episode_parts.txt"
    lst.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in parts), "utf-8")
    sub = out.with_suffix(".srt")
    sub.write_text(srt(subtitles), "utf-8")
    tmp = out.with_suffix(".tmp.mp4")
    args = ["-f", "concat", "-safe", "0", "-i", str(lst)]
    maps = ["-map", "0:v", "-map", "0:a"]
    if sub.stat().st_size:
        args += ["-i", str(sub)]
        maps += ["-map", "1:s", "-c:s", "mov_text"]
    _ff([*args, *maps, "-c:v", "copy", "-c:a", "copy", "-movflags", "+faststart", str(tmp)])
    tmp.replace(out)
    return out


def frame_stats(video: Path, at: float = 0.5) -> tuple[float, float] | None:
    """(mean brightness, spread) of one frame: a blank or broken clip has almost no spread."""
    r = subprocess.run([config.ffmpeg(), "-v", "error", "-ss", f"{at:.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", "scale=64:-1,format=gray", "-f", "rawvideo", "-"], capture_output=True)
    data = r.stdout
    if not data:
        return None
    n = len(data)
    mean = sum(data) / n
    var = sum((b - mean) ** 2 for b in data) / n
    return mean, var ** 0.5
