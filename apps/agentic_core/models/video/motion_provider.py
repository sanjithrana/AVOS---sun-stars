import hashlib
import tempfile
from pathlib import Path

from agentic_core.media.ffmpeg import run_ffmpeg
from agentic_core.models.video.base import VideoProvider

FPS = 30

# Camera moves, each as ffmpeg zoompan expressions. `P` is the eased
# progress 0 -> 1 across the clip (smoothstep), so moves start and end
# gently instead of snapping. Zoom stays modest (<= 1.18) so a 2x
# supersampled source never shows pixel stepping.
_EASE = "(on/{n})*(on/{n})*(3-2*(on/{n}))"
_CENTER_X = "iw/2-(iw/zoom/2)"
_CENTER_Y = "ih/2-(ih/zoom/2)"

MOVES: dict[str, dict[str, str]] = {
    "zoom_in": {"z": "1+0.18*P", "x": _CENTER_X, "y": _CENTER_Y},
    "zoom_out": {"z": "1.18-0.18*P", "x": _CENTER_X, "y": _CENTER_Y},
    "pan_right": {"z": "1.15", "x": "(iw-iw/zoom)*P", "y": _CENTER_Y},
    "pan_left": {"z": "1.15", "x": "(iw-iw/zoom)*(1-P)", "y": _CENTER_Y},
    "pan_up": {"z": "1.15", "x": _CENTER_X, "y": "(ih-ih/zoom)*(1-P)"},
    "push_in_up": {"z": "1+0.15*P", "x": _CENTER_X, "y": "(ih-ih/zoom)*(0.65-0.3*P)"},
}
MOVE_ORDER = list(MOVES)


def pick_move(seed: int | None, prompt: str) -> str:
    """Deterministic per shot (same shot -> same move), varied across
    shots so consecutive cuts don't all zoom the same way."""
    basis = f"{seed}:{prompt}" if seed is not None else prompt
    index = int(hashlib.sha256(basis.encode()).hexdigest()[:8], 16) % len(MOVE_ORDER)
    return MOVE_ORDER[index]


def zoompan_filter(move: str, width: int, height: int, frames: int) -> str:
    n = max(frames - 1, 1)
    ease = _EASE.format(n=n)
    spec = {k: v.replace("P", f"({ease})") for k, v in MOVES[move].items()}
    # Supersample 2x before zoompan: zoompan positions on integer pixels,
    # so working at 2x and downscaling removes the visible "wobble".
    sw, sh = width * 2, height * 2
    return (
        f"scale={sw}:{sh}:force_original_aspect_ratio=increase:flags=lanczos,"
        f"crop={sw}:{sh},setsar=1,"
        f"zoompan=z='{spec['z']}':x='{spec['x']}':y='{spec['y']}':d={frames}:s={width}x{height}:fps={FPS},"
        f"format=yuv420p"
    )


class MotionVideoProvider(VideoProvider):
    """
    Free "image + camera motion" clips: takes the shot's AI-generated
    still and renders a smooth Ken Burns style move (zoom in/out, pan)
    with ffmpeg. No GPU, no API key, a few seconds per shot.

    It's moving pictures, not character animation - the honest free
    baseline. Pick 'replicate' or 'comfyui' for real AI motion.
    """

    name = "motion"
    cost_per_clip_usd = 0.0

    async def generate(
        self,
        prompt: str,
        *,
        width: int = 720,
        height: int = 1280,
        seed: int | None = None,
        duration_seconds: float = 2.0,
        image: bytes | None = None,
    ) -> bytes:
        if not image:
            raise RuntimeError(
                "The 'motion' video provider animates the shot's image, but no image was "
                "generated. Pick an image provider (e.g. Pollinations) for this project."
            )
        # Even dimensions are required by yuv420p/H.264.
        width, height = width - width % 2, height - height % 2
        duration = max(0.5, float(duration_seconds))
        frames = max(2, round(duration * FPS))
        move = pick_move(seed, prompt)

        with tempfile.TemporaryDirectory(prefix="avos-motion-") as tmp:
            src = Path(tmp) / "frame.img"
            out = Path(tmp) / "clip.mp4"
            src.write_bytes(image)
            await run_ffmpeg(
                [
                    "-i", str(src),
                    "-vf", zoompan_filter(move, width, height, frames),
                    "-frames:v", str(frames),
                    "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                    str(out),
                ],
                timeout=300,
            )
            return out.read_bytes()
