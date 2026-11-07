"""The crew: one function per step of ReelMimic's workflow. Each writes the CONTRACT.md files for its step.

A step uses the project's AI crew (Ollama by default) for the creative parts and the built-in tools (analysis,
renderer, measurements, ffmpeg) for everything that can be computed. When the AI's answer is unusable the step
falls back to the engine's own draft, so a weak local model never leaves the job stuck.
"""
from __future__ import annotations

from typing import Any

from .. import jobs
from ..llm import Crew, CrewError
from . import final, pre, prod
from .common import P

PHASES = {
    "style": pre.style, "plan": pre.plan, "pre_cast": pre.pre_cast, "pre_assets": pre.pre_assets, "plan_frames": pre.plan_frames,
    "replan": pre.replan, "setup": prod.setup, "cast_qa": prod.cast_qa, "cast_fix": prod.cast_fix, "build_chunk": prod.build_chunk,
    "shot_qa": prod.shot_qa, "fix_chunk": prod.fix_chunk, "shared_fix": prod.shared_fix, "assemble": final.assemble,
    "critique": final.critique, "revise": final.revise,
}


async def run_phase(phase: str, jid: str, vars: dict, session: str, who: str, abort: Any) -> dict:
    job = jobs.load(jid)
    d = jobs.dir_of(jid)

    def log(ev: dict) -> None:
        jobs.log(jid, {**ev, "who": ev.get("who") or who})
    crew = Crew(job.get("agent") or "ollama", jid, session, who, log, abort, d)
    p = P(jid=jid, dir=d, job=job, vars=vars or {}, crew=crew, who=who, log=log, abort=abort)
    fn = PHASES.get(phase)
    if not fn:
        return {"ok": False, "stderr": f"unknown phase {phase}"}
    try:
        r = await fn(p)
    except CrewError as e:
        log({"type": "error", "text": str(e)})
        return {"ok": False, "stderr": str(e), "lastError": str(e)}
    if abort.aborted:
        return {"ok": False, "stderr": "cancelled"}
    return r or {"ok": False}
