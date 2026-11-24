"""The house director: one set of film rules that every AVOS director follows.

Before this, the Explainer, Stickman and every skill each had their own director. They share the AI connection
(series/writers.py) but nothing else, and each had one strong piece the others lacked: the Explainer knew camera
words, Stickman checked its plans, Film Style fitted prompts to the model's limit. This module is the shared part.
Each section keeps its own style rules on top of it, so Stickman still looks like Stickman.

What lives here:
  HOUSE          the rules put in front of every planning call (short on purpose: it is sent with every plan)
  size_of/move_of  turn any section's camera words into one shared vocabulary, so plans can be compared
  review         a free check of a shot list (no AI call): two actions in one shot, feelings instead of pictures,
                 an empty opening, the same framing twice in a row
  unrepeat       fix the one problem that can be fixed safely without a writer: back-to-back identical camera
  fit / trim     size a prompt to a model's limit while keeping the subject (moved here from Film Style)
  note_of        one plain sentence for the run page saying what the director checked and changed
"""
from __future__ import annotations

import re
from typing import Iterable, Sequence

# ---------- the rules every planner gets ----------
# No braces in this text: several planners build their system prompt with str.format.
HOUSE = (
    "HOUSE RULES (every AVOS film follows these, on top of the style rules): "
    "1. The first two seconds must stop the scroll: open on movement, a surprise or a question, never an empty view. "
    "2. One shot is one action, caught at its peak. Never 'X, then Y' in one shot - that is two shots. "
    "3. Write what the camera SEES: concrete nouns and verbs. Never feelings or meanings ('she realises', 'it symbolises'). "
    "4. Every shot changes something - distance, angle or subject. Never the same framing twice in a row. "
    "5. A camera move needs a reason: push in to focus, pull out to reveal, pan or track to follow. Otherwise lock it off. "
    "6. Cut on action: each shot starts where the last one left the eye, and the same things stay the same. "
    "7. End on one clear image, held long enough to land. "
    "8. Sound comes from what is in frame. "
)



def rules() -> str:
    """The house rules as sent: skills/avos-house-director/SKILL.md when it exists (so they can be edited like every
    other agent's instructions), else the built-in text above."""
    from .creative import skills as SK
    return SK.load("avos-house-director", HOUSE)


# ---------- one shared camera vocabulary ----------
# Every section names framing its own way ("close_up", "close", "tight close-up on the hands", "CU"). These map any of
# them to one word so two shots from any section can be compared.
_SIZES = (
    ("extreme_close", r"extreme[\s_-]*close|macro|ecu\b|detail|insert"),
    ("over_shoulder", r"over[\s_-]*(the[\s_-]*)?shoulder|ots\b"),
    ("overhead", r"overhead|top[\s_-]*down|bird'?s?[\s_-]*eye|from above"),
    ("low", r"low[\s_-]*angle|ground[\s_-]*level|worm'?s?[\s_-]*eye"),
    ("cutaway", r"cutaway|cross[\s_-]*section"),
    ("close", r"close|\bcu\b|tight"),
    ("medium", r"medium|mid[\s_-]*shot|waist|\bms\b"),
    ("wide", r"wide|long[\s_-]*shot|establish|full[\s_-]*(body|shot)|\bws\b|\bls\b"),
)
_MOVES = (
    ("push_in", r"push[\s_-]*in|dolly[\s_-]*in|zoom[\s_-]*in|move[sd]?\s*in|\bin\b"),
    ("pull_out", r"pull[\s_-]*(out|back)|dolly[\s_-]*out|zoom[\s_-]*out|\bout\b"),
    ("pan", r"\bpan|track|follow|truck|\bleft\b|\bright\b"),
    ("tilt", r"tilt|crane|pedestal"),
    ("orbit", r"orbit|arc|circle"),
    ("static", r"static|locked|still|fixed|none|hold"),
)
SIZE_WORDS = tuple(k for k, _ in _SIZES)
MOVE_WORDS = tuple(k for k, _ in _MOVES)


def _canon(text: object, table: tuple) -> str:
    t = str(text or "").strip().lower()
    for word, rx in table:
        if re.search(rx, t):
            return word
    return t


def size_of(text: object) -> str:
    """Any section's framing words, as one shared word ('close_up', 'CU' and 'tight close-up' all become 'close')."""
    return _canon(text, _SIZES)


def move_of(text: object) -> str:
    return _canon(text, _MOVES) or "static"


# ---------- the plan check ----------
# Free: plain text rules, no AI call. Each finding is (shot number, kind, plain sentence).
_TWO = re.compile(r"(\band then\b|,\s*then\b|\bafter that\b|\bafterwards\b|\bfollowed by\b)", re.I)
_MIND = re.compile(r"\b(feel|feels|felt|feeling|realis|realiz|symboli[sz]|represent|means|meaning|thinks?|wonders?|"
                   r"remembers?|understands?|knows?|decides?|hopes?|imagines?)\w*\b", re.I)
_STILL = re.compile(r"^\s*(held still|nothing moving|still|static|none|n/?a|-)?\s*\.?\s*$", re.I)


class Card(dict):
    """One shot in the shared shape: n, what (subject), action, size, move. Built by each section's adapter."""


def card(n: int, what: object = "", action: object = "", size: object = "", move: object = "") -> Card:
    return Card(n=n, what=str(what or ""), action=str(action or ""), size=size_of(size), move=move_of(move))


def review(cards: Sequence[Card]) -> list[tuple[int, str, str]]:
    """What a director would send back. Returns [(shot number, kind, sentence)]; empty means the plan is sound."""
    out: list[tuple[int, str, str]] = []
    for i, c in enumerate(cards):
        n, act = c["n"], c["action"]
        if _TWO.search(act) and len(act) > 30:
            out.append((n, "two_actions", f"shot {n} holds two actions ('{act[:60]}') - one shot, one action"))
        if _MIND.search(act) or _MIND.search(c["what"]):
            out.append((n, "not_visible", f"shot {n} describes a thought, not something the camera can see"))
        if i == 0 and _STILL.match(act):
            out.append((n, "flat_opening", "the opening shot has nothing happening in it - the first two seconds should move"))
        if i and c["size"] and c["size"] == cards[i - 1]["size"] and c["move"] == cards[i - 1]["move"]:
            out.append((n, "same_framing", f"shot {n} is framed exactly like shot {cards[i - 1]['n']}"))
    return out


def unrepeat(values: list[str], options: Sequence[str], key=lambda v: v) -> tuple[list[str], int]:
    """No value equal to the one before it. Changes as few as possible and never creates a new repeat with the next.
    Returns the new list and how many were changed."""
    vals, changed = list(values), 0
    for i in range(1, len(vals)):
        if key(vals[i]) != key(vals[i - 1]):
            continue
        nxt = key(vals[i + 1]) if i + 1 < len(vals) else None
        for o in options:
            if key(o) not in (key(vals[i - 1]), nxt):
                vals[i], changed = o, changed + 1
                break
    return vals, changed


def unrepeat_framing(sizes: list[str], moves: list[str], move_options: Sequence[str]) -> tuple[list[str], int]:
    """When a shot has the same distance AND the same camera move as the one before, change its move -- the cheapest
    change that makes the cut read, and it never touches what the shot is of. Returns the new moves and the count."""
    moves, changed = list(moves), 0
    for i in range(1, len(moves)):
        if size_of(sizes[i]) != size_of(sizes[i - 1]) or move_of(moves[i]) != move_of(moves[i - 1]):
            continue
        avoid = {move_of(moves[i - 1])}
        if i + 1 < len(moves) and size_of(sizes[i + 1]) == size_of(sizes[i]):
            avoid.add(move_of(moves[i + 1]))
        for o in move_options:
            if move_of(o) not in avoid:
                moves[i], changed = o, changed + 1
                break
    return moves, changed


def note_of(found: Iterable[tuple[int, str, str]], fixed: int = 0) -> str:
    """One plain sentence for the run page."""
    found = list(found)
    left = [f for f in found if f[1] != "same_framing" or not fixed]
    bits = []
    if fixed:
        bits.append(f"changed the camera on {fixed} shot{'s' if fixed != 1 else ''} so no two in a row look the same")
    if left:
        bits.append("flagged: " + "; ".join(f[2] for f in left[:3]) + (f" (+{len(left) - 3} more)" if len(left) > 3 else ""))
    return ("House director " + " and ".join(bits) + ".") if bits else "House director: the plan passes every house rule."


# ---------- prompt fitting ----------
# Moved from Film Style, where it was measured: picture models weigh their opening words hardest, and an earlier
# version let the look take the whole budget so the shot itself was cut off the end. The shot is reserved first.
def trim(text: str, room: int) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= room:
        return text
    return text[:max(0, room)].rsplit(" ", 1)[0].rstrip(" ,;:…") + "…"


def fit(lead: str, shot: str, extra: str, tail: str, limit: int = 900) -> str:
    """lead (the look) + shot (never cut) + extra (whatever fits) + tail (the never-list), inside `limit` characters."""
    lead, shot, tail = trim(lead, 260), re.sub(r"\s+", " ", shot or "").strip(), (tail or "").strip()
    room = limit - len(lead) - len(shot) - len(tail) - 3
    extra = trim(extra, room) if room > 60 else ""
    return " ".join(x for x in (lead, shot, extra, tail) if x)[:limit]
