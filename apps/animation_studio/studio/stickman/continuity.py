"""The continuity record across clips and the checks that need no AI: who is where, what they hold, what changed."""
from __future__ import annotations


def record(p: dict) -> list[dict]:
    out = []
    for c in p["clips"]:
        out.append({"clip": f"C{c['n']:02d}", "characters": [x["id"] for x in c["chars"]], "location": c["location"], "time_of_day": c["time_of_day"],
                    "costume": {x["id"]: x["clothing_state"] for x in c["chars"]}, "expression": {x["id"]: x["expression"] for x in c["chars"]},
                    "pose": {x["id"]: x["pose"] for x in c["chars"]}, "position": {x["id"]: x["position"] for x in c["chars"]},
                    "direction": {x["id"]: x["facing"] for x in c["chars"]}, "holds": {x["id"]: x["prop_grip"] for x in c["chars"]},
                    "outgoing": c["outgoing"], "incoming": c["incoming"], "transition": c["transition"], "transition_note": c["transition_note"]})
    return out


def check(p: dict) -> list[dict]:
    """Issues worth a look, each {clip, level, text}. A matched transition must carry the same people, place and props; a cut must say what changes."""
    issues: list[dict] = []
    clips = p["clips"]
    roster = {c["id"] for c in p["roster"]}
    for i, c in enumerate(clips):
        tag = f"C{c['n']:02d}"
        if not all(x["id"] in roster for x in c["chars"]):
            issues.append({"clip": tag, "level": "error", "text": "a character in this clip is not in the roster"})
        if i == 0:
            continue
        prev = clips[i - 1]
        if c["transition"] == "match" or prev["transition"] == "match":
            if prev["location"].strip().lower() != c["location"].strip().lower():
                issues.append({"clip": tag, "level": "warn", "text": f"location changes from '{prev['location']}' to '{c['location']}' without a marked cut"})
            held = {x["id"]: x["holds"] for x in prev["outgoing"]["chars"]}
            for x in c["chars"]:
                before = held.get(x["id"])
                if before and before not in ("nothing", "empty hands") and x["prop_grip"] in ("empty hands", "nothing"):
                    issues.append({"clip": tag, "level": "warn", "text": f"{x['id']} held '{before}' at the end of C{prev['n']:02d} but starts with empty hands"})
            gone = {x["id"] for x in prev["outgoing"]["chars"]} - {x["id"] for x in c["chars"]}
            if gone and c["transition"] == "match":
                issues.append({"clip": tag, "level": "warn", "text": f"{', '.join(sorted(gone))} leaves between clips without a stated exit"})
        elif not c["transition_note"] and not prev["transition_note"]:
            issues.append({"clip": tag, "level": "info", "text": "cut without a note on what changes and what stays fixed"})
    return issues
