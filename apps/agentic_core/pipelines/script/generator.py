import json

from packages.contracts.script import Script, ScriptScene
from agentic_core.models.llm.base import LLMProvider
from agentic_core.models.llm.factory import get_llm_provider


class ScriptGenerationError(RuntimeError):
    """Raised when the LLM response can't be parsed into a valid Script."""


SYSTEM_PROMPT = (
    "You are the Writer agent in an automated video production system. "
    "Given a topic, target duration, and audience, produce a scene-by-scene "
    "script. Respond with ONLY a JSON object of the shape "
    '{"scenes": [{"narration": str, "visual_description": str, '
    '"estimated_seconds": number}, ...]}. No prose outside the JSON.'
)


def _build_prompt(
    *,
    topic: str,
    duration_seconds: int,
    aspect_ratio: str,
    audience: str,
    research_notes: list[str] | None = None,
    style_guidance: str = "",
) -> str:
    notes_block = ""
    if research_notes:
        notes_block = "RESEARCH_NOTES:\n" + "\n".join(
            f"- {note}" for note in research_notes
        ) + "\n"

    return (
        "TASK: script\n"
        f"TOPIC: {topic}\n"
        f"DURATION_SECONDS: {duration_seconds}\n"
        f"ASPECT_RATIO: {aspect_ratio}\n"
        f"AUDIENCE: {audience}\n"
        f"{notes_block}"
        "Write a script that fits the target duration, broken into short "
        "scenes suitable for short-form vertical video. Use the research "
        "notes (if any) as the factual basis for the narration."
        + (f"\n{style_guidance}" if style_guidance else "")
    )


async def generate_script(
    *,
    project_id: str,
    topic: str,
    duration_seconds: int,
    aspect_ratio: str = "9:16",
    audience: str = "general",
    research_notes: list[str] | None = None,
    llm: LLMProvider | None = None,
    style_guidance: str = "",
) -> Script:
    """
    Generate a full Script for a project via the configured LLM provider.

    Uses the deterministic MockLLMProvider by default (see
    ``agentic_core.models.llm.factory``), so this works fully offline in
    tests and in dev without any API key.
    """
    provider = llm or get_llm_provider()

    prompt = _build_prompt(
        topic=topic,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        audience=audience,
        research_notes=research_notes,
        style_guidance=style_guidance,
    )

    raw = await provider.complete(prompt, system=SYSTEM_PROMPT)

    try:
        data = json.loads(_strip_code_fence(raw))
        raw_scenes = data["scenes"]

        if not raw_scenes:
            raise ValueError("LLM returned zero scenes.")

        scenes = [
            ScriptScene(
                index=i,
                narration=s["narration"],
                visual_description=s["visual_description"],
                estimated_seconds=float(s["estimated_seconds"]),
            )
            for i, s in enumerate(raw_scenes)
        ]
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ScriptGenerationError(
            f"Could not parse script from LLM ({provider.name}) response: {exc}"
        ) from exc

    return Script(
        project_id=project_id,
        topic=topic,
        scenes=scenes,
        total_estimated_seconds=sum(s.estimated_seconds for s in scenes),
        model=provider.name,
    )


def _strip_code_fence(text: str) -> str:
    """Some providers wrap JSON in ```json ... ``` even when told not to."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:]
    return stripped.strip()
