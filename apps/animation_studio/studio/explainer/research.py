"""Research before the script: the topic's facts come from real text (Wikipedia, free and keyless), each fact keeps its
source link, and the script writer is told to use ONLY those facts. Nothing here can stop a video: when the web or the AI
writer isn't available the project says why research was skipped and the script is written as before."""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from ..series import writers

API = "https://en.wikipedia.org/w/api.php"
UA = "AVOS-Studio research (contact: local user)"
TIMEOUT = 12
MAX_BRIEF = 300            # a long brief (a full script) already says what to show: research is for short ideas
MAX_FACTS = 10

SYSTEM = """You are the research desk of a science video channel. You get source texts and a topic. Answer with ONE JSON object only:
{"research_questions":[3 short questions a viewer would ask],
 "verified_facts":[{"fact":"one plain, checkable sentence","source":<number of the source text it comes from>}],
 "misconceptions":["a common wrong belief about this topic, stated so it can be corrected"],
 "scientific_unknowns":["what is still uncertain or debated, if anything"]}
Rules: every fact must be stated in the source text you cite, in your own simple words, with no added numbers. Give 5-10 facts.
Never use outside knowledge. If the sources do not cover something, leave it out."""


class ResearchError(RuntimeError):
    pass


def _clean(topic: str) -> str:
    t = re.sub(r"\s+", " ", re.sub(r"(?i)^(how|why|what|when|where|who)\b( does| do| is| are| did| can)?\s*", "", topic or "")).strip(" ?.!")
    return t[:90]


def _get(params: dict[str, Any]) -> dict:
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": "2"})
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=TIMEOUT) as r:
            return json.loads(r.read(2_000_000).decode("utf-8", "replace"))
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise ResearchError(f"couldn't reach Wikipedia ({str(e)[:100]})") from e


def find(topic: str, limit: int = 3) -> list[dict]:
    """[{title, url, text}] for the best matching articles (introductions, plain text)."""
    q = _clean(topic)
    if len(q) < 3:
        raise ResearchError("the topic is too short to search")
    data = _get({"action": "query", "generator": "search", "gsrsearch": q, "gsrlimit": limit, "prop": "extracts|info", "exintro": 1,
                 "explaintext": 1, "exlimit": limit, "exchars": 2200, "inprop": "url", "redirects": 1})
    pages = sorted((data.get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 99))
    out = [{"title": str(p.get("title") or "")[:120], "url": str(p.get("fullurl") or ""), "text": " ".join(str(p.get("extract") or "").split())}
           for p in pages]
    out = [p for p in out if len(p["text"]) > 200 and p["url"].startswith("https://")]
    if not out:
        raise ResearchError("no article matched this topic")
    return out[:limit]


def _sentences(text: str, n: int) -> list[str]:
    s = [x.strip() for x in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text) if 40 <= len(x.strip()) <= 260]
    return s[:n]


def _validate(raw: Any, sources: list[dict]) -> dict | None:
    if not isinstance(raw, dict):
        return None
    facts = []
    for f in raw.get("verified_facts") or []:
        f = f if isinstance(f, dict) else {"fact": str(f)}
        txt = " ".join(str(f.get("fact") or "").split())[:260]
        try:
            i = int(f.get("source")) - 1
        except (TypeError, ValueError):
            i = -1
        if len(txt) >= 20 and 0 <= i < len(sources):
            facts.append({"fact": txt, "source": {"title": sources[i]["title"], "url": sources[i]["url"]}})
    if len(facts) < 3:
        return None
    lst = lambda k, n: [" ".join(str(x).split())[:220] for x in (raw.get(k) or []) if str(x).strip()][:n]  # noqa: E731
    return {"questions": lst("research_questions", 4), "facts": facts[:MAX_FACTS], "misconceptions": lst("misconceptions", 3), "unknowns": lst("scientific_unknowns", 3)}


def run(s: dict, topic: str, log: Callable[[dict], None] | None = None) -> dict:
    """The research package for a project (never raises): {status: ok|skipped, reason, topic, sources, facts, questions, misconceptions, unknowns}."""
    base: dict[str, Any] = {"status": "skipped", "reason": "", "topic": _clean(topic), "sources": [], "facts": [], "questions": [], "misconceptions": [], "unknowns": []}
    try:
        srcs = find(topic)
    except ResearchError as e:
        return {**base, "reason": str(e)}
    base["sources"] = [{"title": x["title"], "url": x["url"]} for x in srcs]
    pkg = None
    if writers.uses_ai(s):
        body = "\n\n".join(f"[Source {i + 1}] {x['title']}\n{x['text']}" for i, x in enumerate(srcs))
        try:
            pkg = _validate(writers.ask(s, "story", SYSTEM, f"Topic: {topic}\n\n{body}\n\nWrite the JSON research package.", log, max_tokens=1800, temperature=0.2), srcs)
        except Exception as e:  # noqa: BLE001 - the AI writer failing must not stop the video
            base["reason"] = f"the AI writer could not summarise the sources ({str(e)[:100]}); using the opening sentences instead"
    if pkg is None:                                    # no AI writer, or its answer was unusable: the articles' own first sentences, still sourced
        facts = [{"fact": t, "source": {"title": x["title"], "url": x["url"]}} for x in srcs for t in _sentences(x["text"], 3)]
        if len(facts) < 3:
            return {**base, "reason": base["reason"] or "the articles had too little text to use"}
        pkg = {"questions": [], "facts": facts[:MAX_FACTS], "misconceptions": [], "unknowns": []}
    return {**base, **pkg, "status": "ok"}


def facts_block(r: dict | None) -> str:
    """What the script writer must obey (empty when there is no usable research)."""
    if not r or r.get("status") != "ok" or not r.get("facts"):
        return ""
    lines = ["Verified facts (every factual claim in the narration must come from these; do not add numbers or claims that are not here; if unsure say less):"]
    lines += [f"- {f['fact']}" for f in r["facts"]]
    if r.get("misconceptions"):
        lines.append("Common mistakes to avoid or gently correct: " + " | ".join(r["misconceptions"]))
    if r.get("unknowns"):
        lines.append("Still uncertain (say so, never state as fact): " + " | ".join(r["unknowns"]))
    return "\n".join(lines) + "\n"
