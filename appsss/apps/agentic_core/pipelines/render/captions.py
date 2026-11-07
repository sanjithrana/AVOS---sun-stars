"""
Short-form style burned-in captions as an ASS subtitle file: big bold
text with a thick outline, 1-3 words on screen at a time, the word being
spoken highlighted. Timings come straight from the narration's
per-word timestamps.
"""

import re
from dataclasses import dataclass

_SENTENCE_END = re.compile(r"[.!?]$")
_SOFT_BREAK = re.compile(r"[,;:]$")


@dataclass(frozen=True)
class CaptionWord:
    text: str
    start: float
    end: float


def _ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(word: str) -> str:
    # Keep ?/! (they read well on screen), drop other trailing punctuation.
    word = word.strip().strip('"“”')
    word = re.sub(r"[.,;:]+$", "", word)
    return word.replace("{", "(").replace("}", ")").replace("\\", "/")


def chunk_words(words: list[CaptionWord], max_words: int = 3) -> list[list[CaptionWord]]:
    """Group words into on-screen chunks, never crossing a sentence end."""
    chunks: list[list[CaptionWord]] = []
    current: list[CaptionWord] = []
    for word in words:
        current.append(word)
        if (
            len(current) >= max_words
            or _SENTENCE_END.search(word.text)
            or (_SOFT_BREAK.search(word.text) and len(current) >= 2)
        ):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def build_ass(
    words: list[CaptionWord],
    *,
    width: int,
    height: int,
    total_duration: float,
    font: str = "DejaVu Sans",
    max_words: int = 3,
    uppercase: bool = False,
) -> str:
    font_size = round(height * 0.064)
    outline = max(3, round(font_size * 0.09))
    margin_v = round(height * 0.24)  # lower third, clear of the platform UI
    # ASS colours are &HAABBGGRR. White text, black outline, yellow highlight.
    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {width}\nPlayResY: {height}\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Caption,{font},{font_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{outline},2,2,60,60,{margin_v},1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    lines: list[str] = []
    chunks = chunk_words(words, max_words=max_words)
    for ci, chunk in enumerate(chunks):
        chunk_end = chunks[ci + 1][0].start if ci + 1 < len(chunks) else min(total_duration, chunk[-1].end + 0.6)
        texts = [_clean(w.text) for w in chunk]
        if uppercase:
            texts = [t.upper() for t in texts]
        for wi, word in enumerate(chunk):
            start = word.start if wi > 0 else max(0.0, word.start - 0.05)
            end = chunk[wi + 1].start if wi + 1 < len(chunk) else chunk_end
            if end <= start:
                continue
            parts = [
                (r"{\c&H00F2FF&}" + t + r"{\c&HFFFFFF&}") if i == wi else t
                for i, t in enumerate(texts)
            ]
            # Small pop on the first word of each chunk.
            pop = r"{\fscx108\fscy108\t(0,90,\fscx100\fscy100)}" if wi == 0 else ""
            lines.append(
                f"Dialogue: 0,{_ass_time(start)},{_ass_time(end)},Caption,,0,0,0,,{pop}{' '.join(parts)}"
            )
    return header + "\n".join(lines) + "\n"
