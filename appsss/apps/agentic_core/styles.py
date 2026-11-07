"""
Style presets: one choice per project (New Project -> Style) that sets how
the script is written, how every shot looks, which music mood is used and
how captions are cut. Add a preset here and in desktop/types/project.ts's
STYLE_PRESETS.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class StylePreset:
    name: str
    # Appended to every shot's image/video prompt via the WorldState style.
    visual_style: str
    # Extra instructions for the Writer agent (script LLM).
    script_guidance: str
    # Subfolder of the music library to pick a track from.
    music_mood: str
    # Words on screen at once.
    caption_words: int
    # Added to the image-to-video prompt so clips move the right way.
    motion_hint: str
    # Default Blender environment for the 'blender' video provider.
    blender_environment: str = "grid_studio"


STORYBOOK = StylePreset(
    name="storybook",
    visual_style="bright, friendly storybook illustration",
    script_guidance="",
    music_mood="uplifting",
    caption_words=3,
    motion_hint="gentle natural motion",
)

VIRAL_3D = StylePreset(
    name="viral_3d",
    visual_style=(
        "photorealistic 3D CGI render, Blender Cycles style, realistic human characters "
        "with detailed skin and simple shorts, soft studio lighting, clean light-blue "
        "grid floor and backdrop, vertical framing, sharp focus"
    ),
    script_guidance=(
        "STYLE: viral 3D-animation facts short (like 'what would happen if...' and 'science trick' channels). "
        "Open with a one-line hook question or bold claim in the first 2 seconds. "
        "Short, punchy sentences (max ~12 words), present tense, one surprising fact per scene, "
        "build tension, end with a twist or punchline - no 'subscribe', no outro. "
        "Every visual_description must show ONE concrete physical action by a 3D human "
        "character (or object) in a simple scene, e.g. 'a muscular man in black shorts "
        "punches a giant gorilla on a blue grid floor'. "
        "Vary the camera: alternate medium shots of the presenter with macro close-ups of hands, props and the key detail. "
        "When the explanation is invisible (air pressure, electricity, heat), show it as ONE 3D cutaway or cross-section "
        "with glowing arrows or colour flows - never letters, numbers, labels or charts. "
        "A short funny cutaway to a second character reacting is welcome near the end."
    ),
    music_mood="suspense",
    caption_words=2,
    motion_hint="smooth realistic 3D character animation, dynamic action, physically plausible motion",
)

PRESETS = {p.name: p for p in (STORYBOOK, VIRAL_3D)}
KNOWN_STYLES = tuple(PRESETS)


def get_style(name: str | None) -> StylePreset:
    return PRESETS.get((name or "").strip().lower(), STORYBOOK)
