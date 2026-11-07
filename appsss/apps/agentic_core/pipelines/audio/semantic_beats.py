from packages.contracts.audio import SemanticBeat, SentenceTimestamp


def extract_semantic_beats(
    sentences: list[SentenceTimestamp],
) -> list[SemanticBeat]:
    """
    Derive shot-change beats from sentence timestamps.

    Heuristic for now (one beat per sentence start) — the plan calls
    for this to mature alongside the physics/video agents in Week 3+,
    where beats will factor in visual_description changes from the
    Script contract too, not just narration boundaries.
    """
    return [
        SemanticBeat(time=sentence.start, label=f"beat_{i + 1}")
        for i, sentence in enumerate(sentences)
    ]
