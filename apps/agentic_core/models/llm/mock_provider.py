import json
import re

from agentic_core.models.llm.base import LLMProvider


class MockLLMProvider(LLMProvider):
    """
    Deterministic, offline stand-in for a real LLM.

    Used automatically when no provider API key is configured (see
    ``factory.get_llm_provider``), and directly in unit tests per the
    Week 2 plan ("unit test with a mocked LLM response").

    It does not "understand" prompts. Every prompt builder embeds a
    ``TASK: <name>`` marker plus ``KEY: value`` fields, and this mock
    synthesizes a well-formed response in exactly the shape a real
    provider is asked for. That keeps every round-trip
    (prompt -> response -> parsed contract) exercised end-to-end without
    any network call. A missing TASK marker defaults to "script" for
    backward compatibility with early callers.

    Previously it always answered with script JSON, so research_topic
    stored a JSON blob as its single "research note".
    """

    name = "mock"

    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        task = _extract(prompt, "TASK") or "script"

        if task == "research":
            return self._research(prompt)
        return self._script(prompt)

    def _research(self, prompt: str) -> str:
        topic = _extract(prompt, "TOPIC") or "the topic"
        # Plain bullet lines, not JSON: research_topic splits on newlines.
        return "\n".join(
            [
                f"- {topic} can be found all around us in everyday life.",
                f"- One simple, surprising fact about {topic} is easy to show on screen.",
                f"- {topic} changes over time, which makes for a good visual story.",
                f"- A kind, curious question about {topic} helps viewers stay engaged.",
            ]
        )

    def _script(self, prompt: str) -> str:
        topic = _extract(prompt, "TOPIC") or "the topic"
        duration = float(_extract(prompt, "DURATION_SECONDS") or 30)
        notes = _extract_notes(prompt)

        scene_count = max(2, round(duration / 8))
        per_scene = round(duration / scene_count, 1)

        beats: list[str] = [f"Have you ever wondered about {topic}? Let's find out together."]
        for note in notes:
            if len(beats) >= scene_count - 1:
                break
            beats.append(note.rstrip(".") + ".")
        while len(beats) < scene_count - 1:
            beats.append(f"Look closely, and {topic} has even more to show us.")
        beats.append(f"Now you know a little more about {topic}. Keep exploring!")

        scenes = [
            {
                "narration": narration,
                "visual_description": (
                    f"Bright, friendly illustration about {topic}: "
                    f"scene {i + 1} of {scene_count}."
                ),
                "estimated_seconds": per_scene,
            }
            for i, narration in enumerate(beats)
        ]

        return json.dumps({"scenes": scenes})


def _extract(prompt: str, key: str) -> str | None:
    match = re.search(rf"^{key}:\s*(.+)$", prompt, flags=re.MULTILINE)
    return match.group(1).strip() if match else None


def _extract_notes(prompt: str) -> list[str]:
    """Bullet lines under a 'RESEARCH_NOTES:' header, if present."""
    match = re.search(r"^RESEARCH_NOTES:\s*\n((?:- .*\n?)+)", prompt, flags=re.MULTILINE)
    if not match:
        return []
    return [line[2:].strip() for line in match.group(1).splitlines() if line.startswith("- ")]
