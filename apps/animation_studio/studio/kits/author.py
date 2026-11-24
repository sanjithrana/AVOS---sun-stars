"""The AI half of the kits: the writer crew does what Claude would do in each kit's SKILL.md.

  script   the narration (your own words are kept when you paste a script)
  build    the file the engine plays: story.js (story engines), one HTML file (animation styles) or styles/<name>.js (3D styles)
           Each answer is checked by really loading it in the browser; a page error is sent back for repair (up to 3 rounds).
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Callable, Optional

from ..series import writers
from . import paths

Log = Callable[[dict], None]
WORDS_PER_SECOND = 2.5


def _read(p: Path, limit: int | None = None) -> str:
    t = p.read_text("utf-8", errors="replace") if p.is_file() else ""
    return t[:limit] if limit else t


def ask_text(s: dict, who: str, system: str, prompt: str, log: Log | None = None, max_tokens: int = 9000, temperature: float = 0.6) -> str | None:
    c = writers.crew(s, who, log)
    if not c.enabled:
        return None
    return asyncio.run(c.ask(system, prompt, want_json=False, temperature=temperature, max_tokens=max_tokens, keep=False))


def code_of(text: str | None, lang: str = "javascript") -> str:
    """The code in an answer: the biggest fenced block, else the whole text."""
    if not text:
        return ""
    blocks = re.findall(r"```(?:[a-zA-Z]*)\n(.*?)```", text, re.S)
    if blocks:
        return max(blocks, key=len).strip()
    return re.sub(r"^```[a-zA-Z]*\n?|```$", "", text.strip()).strip()


def slug_of(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "short"


# ---------- the script ----------
def write_script(s: dict, kit_dir: Path, subject: str, seconds: int, log: Log, topic_hint: str = "") -> dict:
    words = len(subject.split())
    if words >= 45:                                    # the person brought their own script: keep their words
        title = subject.strip().split("\n")[0][:60].rstrip(".,:;")
        return {"title": title or "My short", "script": subject.strip(), "own": True}
    guide = _read(kit_dir / "references" / "script.md", 2500) or _read(kit_dir / "SKILL.md", 2500)
    n = int(seconds * WORDS_PER_SECOND)
    system = writers.system("kit-script", (
        "You write the narration for a short vertical video, in the exact style of the guide below. Open with a hook that works as the first image, "
        "build to a twist or payoff in the last line. Short sentences, one idea each, spoken English, no stage directions, no emoji, no hashtags.\n"
        "Facts must be true. Do not invent quotes or statistics.\n\nGUIDE\n" + guide +
        '\n\nAnswer with ONE JSON object: {"title":"short title","script":"the narration, one sentence per line"}'))
    out = writers.ask(s, "kit-script", system, f"Topic: {subject}\n{topic_hint}\nLength: about {n} words ({seconds} seconds spoken).", log, max_tokens=1800)
    if isinstance(out, dict) and isinstance(out.get("script"), str) and len(out["script"].split()) >= 12:
        return {"title": str(out.get("title") or subject)[:70], "script": out["script"].strip()}
    raise writers.WriterError("The AI writers didn't return a usable script. Try again, or pick another AI crew (Models).")


# ---------- story engines ----------
def story_system(kit_dir: Path) -> str:
    refs = kit_dir / "references"
    ex = next(iter(sorted((kit_dir / "examples").glob("*/story.js"))), None)
    return (f"You are the animation director and creative coder of the kit below. You write ONE file, story.js, that the kit's engine plays.\n"
            f"Follow the engine reference exactly: use only the helpers it lists, no other libraries, no network, no Math.random at frame time (use the seeded one).\n\n"
            f"=== ENGINE REFERENCE ===\n{_read(refs / 'engine.md', 12000)}\n\n=== WORKFLOW ===\n{_read(refs / 'workflow.md', 3200)}\n\n"
            f"=== CHECKLIST ===\n{_read(refs / 'checklist.md', 1500)}\n\n"
            f"=== A FINISHED EXAMPLE (different story: copy its structure and craft, not its content) ===\n{_read(ex, 13000) if ex else ''}\n\n"
            "Output ONLY the JavaScript of story.js (a /* SHOT PLAN */ comment, then window.SHORT = {...}). No explanation, no markdown fence.")


def story_prompt(title: str, script: str, timing: str) -> str:
    return (f"Title: {title}\nSlug: {slug_of(title)}\nNarration script (put it VERBATIM in the `script` field of window.SHORT):\n{script}\n\n"
            f"Word timing of the real narration (seconds): {timing}\n"
            "Write one shot per sentence, vary shot sizes, make every visible action carry a sound. End on the payoff.")


def pin_script(code: str, script: str) -> str:
    """Make sure SHORT.script is exactly the narration (the engine lines the voice up against it)."""
    lit = "`" + script.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${") + "`"
    new, n = re.subn(r"(\bscript\s*:\s*)`(?:\\.|[^`\\])*`", lambda m: m.group(1) + lit, code, count=1, flags=re.S)
    if n:
        return new
    return code + f"\nwindow.SHORT && (window.SHORT.script = {lit});\n"


def timing_summary(words: list[dict], max_items: int = 60) -> str:
    out, cur, t0 = [], [], None
    for w in words:
        t0 = w["start"] if t0 is None else t0
        cur.append(w["text"])
        if re.search(r"[.!?…]$", w["text"]) or len(cur) >= 14:
            out.append(f'{t0:.1f}s "{" ".join(cur[:5])}…"')
            cur, t0 = [], None
    if cur:
        out.append(f'{t0:.1f}s "{" ".join(cur[:5])}…"')
    return "; ".join(out[:max_items]) + f"; ends {words[-1]['end']:.1f}s"


# ---------- animation styles ----------
def anim_system(kit_dir: Path, style: str) -> str:
    refs = kit_dir / "references"
    return ("You are an animation director and creative coder. You turn the narration into a short animated film drawn entirely in code, in ONE look, as ONE self-contained HTML file.\n"
            "Start from the template below and keep its player, its frame contract (window.ready, window.CONFIG, window.renderFrame, draw(t) pure in t) and its structure. "
            "No downloaded images, fonts or models. Keep the narration's words and order; every beat shows what is said, in this style's own drawing language. "
            "Keep important things out of the top 240 px and bottom 350 px of a 9:16 frame.\n\n"
            f"=== WORKFLOW ===\n{_read(refs / 'workflow.md', 3200)}\n\n=== THE STYLE (its rules beat any habit) ===\n{_read(refs / 'styles' / (style + '.md'), 6000)}\n\n"
            f"=== CHECKLIST ===\n{_read(refs / 'checklist.md', 1500)}\n\n=== TEMPLATE ===\n{_read(refs / 'player-template.html', 9000)}\n\n"
            "Output ONLY the complete HTML file. No explanation.")


# ---------- 3D styles ----------
def style3d_system(kit_dir: Path, ref_style: str) -> str:
    return ("You are a 3D animation director and three.js creative coder. You write ONE style file, styles/<name>.js, that the kit's STAGE and SOUND engine plays.\n\n"
            f"=== KIT DOCUMENTATION ===\n{_read(kit_dir / 'SKILL.md', 9000)}\n\n"
            f"=== THE REFERENCE STYLE `{ref_style}` (keep its look and technique, change the story) ===\n{_read(kit_dir / 'styles' / (ref_style + '.js'), 14000)}\n\n"
            "Rules: update(t) sets the whole scene for time t and must be deterministic (no Math.random, Date or timers); no downloaded models or textures; "
            "put a sound on every visible event; end on the payoff; words are short captions pinned with S.pin, kept between 12% and 82% of the frame height in 9:16.\n"
            "Output ONLY the JavaScript of the style file. No explanation, no markdown fence.")


def style3d_prompt(key: str, title: str, script: str, timing: str, duration: float) -> str:
    return (f"Register the style under EXACTLY this key: (window.STYLES = window.STYLES || {{}})[\"{key}\"] = {{ name, card, content, duration: {duration:.1f}, samples, fonts, grade, build(S), sound(k) }}.\n"
            f"Topic / title: {title}\nNarration (a voiceover will be mixed in; show what it says, beat by beat):\n{script}\n\nTiming of the narration: {timing}\n"
            f"The animation lasts {duration:.1f} seconds; plan 3-5 beats that follow from each other.")


def repair_prompt(code: str, error: str) -> str:
    return (f"Your file failed when the engine loaded and drew frames. Browser error:\n{error[:700]}\n\nHere is the file:\n{code[:30000]}\n\n"
            "Return the COMPLETE corrected file only (same format as before, no explanation, no fence). Fix the root cause, don't remove the story.")


def build_with_repair(s: dict, who: str, system: str, prompt: str, finish: Callable[[str], str], check: Callable[[str], Optional[str]],
                      log: Log, rounds: int = 3, max_tokens: int = 14000) -> str:
    """Ask for the file, test it, send errors back. `finish` post-processes (pin the script); `check` returns an error or None."""
    code = finish(code_of(ask_text(s, who, system, prompt, log, max_tokens=max_tokens, temperature=0.5)))
    last = ""
    for i in range(rounds + 1):
        err = check(code) if code else "the answer had no code"
        if not err:
            return code
        last = err
        log({"type": "warn", "text": f"The file did not run yet ({err[:160]}). " + (f"Asking the writer to fix it (round {i + 1} of {rounds})." if i < rounds else "")})
        if i == rounds:
            break
        code = finish(code_of(ask_text(s, who, system, repair_prompt(code, err), log, max_tokens=max_tokens, temperature=0.3))) or code
    raise writers.WriterError("The AI wrote code that still doesn't run after 3 repairs "
                              f"({last[:200]}). Code this size needs a strong writer: pick Claude, Gemini, OpenAI or a large Ollama model in Models, or try again.")
