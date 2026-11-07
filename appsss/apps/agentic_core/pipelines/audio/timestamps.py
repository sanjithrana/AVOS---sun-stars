import re

from packages.contracts.audio import SentenceTimestamp, WordTimestamp

_SENTENCE_END = re.compile(r"[.!?]$")


def extract_sentence_timestamps(
    words: list[WordTimestamp],
) -> list[SentenceTimestamp]:
    """
    Group word-level timestamps into sentence-level timestamps by
    splitting on sentence-ending punctuation.
    """
    if not words:
        return []

    sentences: list[SentenceTimestamp] = []
    current: list[WordTimestamp] = []

    for word in words:
        current.append(word)
        if _SENTENCE_END.search(word.word):
            sentences.append(_flush(current))
            current = []

    if current:
        sentences.append(_flush(current))

    return sentences


def _flush(words: list[WordTimestamp]) -> SentenceTimestamp:
    return SentenceTimestamp(
        text=" ".join(w.word for w in words),
        start=words[0].start,
        end=words[-1].end,
        word_count=len(words),
    )
