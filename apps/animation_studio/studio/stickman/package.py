"""The written production package, in the sheet's delivery order, as one Markdown file you can paste into Google Flow or any
image/video tool, whether or not this app generated the media. Prompts are shown in full, never summarised."""
from __future__ import annotations

from . import continuity, prompts, spec, styles


def _fence(text: str) -> str:
    return "```\n" + text.strip() + "\n```\n"


def build(p: dict) -> str:
    t, b = p["project"], p.get("brief") or {}
    out = [f"# {p['title']}\n", f"{t['date_place']} · {len(p['clips'])} clips × {spec.CLIP_SECONDS} s = {len(p['clips']) * spec.CLIP_SECONDS} s · {p['aspect']} · English narration · tone: {t['tone']}\n"]
    st = styles.get(p.get("style"))
    out.append(f"Style: **{st['name']}** · made for {st['made_for']}. Prompt contract adapted from Stickman Video Director (MIT).\n\n")
    out.append("## 1. Fact brief and sources\n")
    out.append("**Verification status: PENDING.** This studio did not check any source. Treat everything below as a researcher's draft and confirm each claim against the "
               "named kinds of sources before publishing.\n")
    if b:
        out.append(f"- **Event:** {b['event']} · **Date:** {b['date']} · **Location:** {b['location']}\n- **People:** {', '.join(b['people']) or 'n/a'}\n"
                   f"- **Cause:** {b['cause']}\n- **Turning point:** {b['turning_point']}\n- **Outcome:** {b['outcome']}\n")
        out.append("\n**Facts**\n\n" + "\n".join(f"- {f['claim']} _({f['confidence']})_" for f in b["facts"]) + "\n")
        if b["disputed"]:
            out.append("\n**Where sources disagree**\n\n" + "\n".join(f"- {x}" for x in b["disputed"]) + "\n")
        out.append("\n**Sources to check**\n\n" + ("\n".join(f"- {x}" for x in b["sources_to_check"]) or "- (none suggested)") + "\n")
        if b["dramatization_notes"]:
            out.append("\n**Dramatization (staging, not record)**\n\n" + "\n".join(f"- {x}" for x in b["dramatization_notes"]) + "\n")
    out.append("\n## 2. Story and narration by clip\n\n| Clip | Time | Narration | Main visual action | Purpose |\n|---|---|---|---|---|\n")
    for c in p["story"]["clips"]:
        out.append(f"| C{c['n']:02d} | {c['t0']}-{c['t1']} s | {c['narration']} | {c['main_action']} | {c['purpose']} |\n")
    out.append("\nNarration is an estimate of timing (about 2.5 spoken words per second). Measure the recorded voice before final assembly and leave room for breaths.\n")
    out.append("\n## 3. Visual style and character designs\n\n" + prompts.style_lock(p) + "\n\n**Global continuity block**\n\n" + _fence(prompts.global_block(p))
               + "\n**Frozen voice block (repeated verbatim in every clip)**\n\n" + _fence(styles.voice_block(p)))
    for c in p["roster"]:
        out.append(f"\n### {c['id']} · {c['name']}\n\n**Immutable identity paragraph**\n\n" + _fence(prompts.identity(c)))
    out.append("\n## 4. Character reference sheet prompts\n")
    for c in p["roster"]:
        out.append(f"\n### CHARACTER REFERENCE SHEET PROMPT · {c['id']}\n\nMetadata (kept outside the image prompt): ID {c['id']}; palette " + ", ".join(f"{a['name']} {a['hex']}" for a in c["accents"]) + ".\n\n" + _fence(prompts.sheet_prompt(p, c)))
    out.append("\nKeep the full sheet as the master reference. Where a multi-panel sheet confuses scene generation, crop a single view and attach that instead. A filename alone does not make a reference available to a model: attach the image.\n")
    out.append("\n## 5. Character consistency agent instructions\n\n" + _fence(p.get("consistency") or prompts.consistency_prompt(p)))
    out.append("\n## 6. Clip packages\n")
    for c in p["clips"]:
        out.append(f"\n### Clip {c['n']} · {c['t0']}-{c['t1']} s · files C{c['n']:02d}_scene, C{c['n']:02d}_video, C{c['n']:02d}_voice\n\n"
                   f"**Narration:** {p['story']['clips'][c['n'] - 1]['narration']}\n\n**Characters and references to attach:** " + ", ".join(f"{x['id']} sheet" for x in c["chars"]) + "\n\n"
                   f"**Scene-image prompt** ({spec.words(c['scene_prompt'])} words)\n\n" + _fence(c["scene_prompt"]) +
                   f"\n**10-second animation prompt** ({spec.words(c['animation_prompt'])} words)\n\n" + _fence(c["animation_prompt"]) +
                   f"\n**Sound notes:** {', '.join(c['sfx']) or 'none'}; music: {c['music']}.\n\n"
                   f"**Outgoing continuity state:** {c['outgoing']['summary']} " + "; ".join(f"{x['id']} {x['position']}, {x['facing']}, holding {x['holds']}, {x['emotion']}" for x in c["outgoing"]["chars"]) +
                   f". Next clip: {'matches this last frame' if c['transition'] == 'match' else 'intentional cut - ' + (c['transition_note'] or 'change of place')}.\n")
    out.append("\n## 7. Stitching guide\n\n" + "\n".join(
        f"- C{c['n']:02d} → C{c['n'] + 1:02d}: ends on {c['outgoing']['summary']} " + ("Next clip opens on this frame (match cut)." if c["transition"] == "match" else f"Planned cut: {c['transition_note'] or 'change of place'}.")
        for c in p["clips"][:-1]) + "\n\nInspect each join in the real clips: trim to the frame where the motion matches, and use a short audio crossfade. One continuous "
        "voice and music track over the whole edit is the safest way to keep the narrator identical.\n")
    out.append("\n## 8. Assembly guide and continuity checklist\n\n"
               "1. Generate the reference sheets (section 4); review and correct the designs.\n2. Generate each scene image (section 6) with the right sheets attached.\n"
               "3. Animate each scene image with its animation prompt; review identity and action; regenerate only clips with material problems.\n"
               "4. Assemble the numbered clips; record and time the narration (C01_voice …); place sound effects and music; add captions and verified labels in the editor.\n"
               f"5. Export in {p['aspect']}.\n\n**Duration.** Each clip is {spec.CLIP_SECONDS} s, so the total is clip count × {spec.CLIP_SECONDS} = {len(p['clips']) * spec.CLIP_SECONDS} s. "
               "Confirm generated durations and narration lengths before export. If a tool returns a different length, trim a longer take, generate an extension, or combine supported takes with a deliberate cut; "
               "do not slow motion or stretch speech until it looks or sounds unnatural. Wording like \"exactly 10 seconds\" does not guarantee the exported duration.\n\n"
               "**Continuity checklist**\n\n")
    issues = continuity.check(p)
    out.append("\n".join(f"- [ ] {i['clip']} ({i['level']}): {i['text']}" for i in issues) or "- [x] No continuity problems found by the automatic check.")
    out.append("\n- [ ] Topic is specific; important claims are supported by sources you checked\n- [ ] Invented staging is separate from fact\n- [ ] The story has a hook and a clear outcome\n"
               "- [ ] Narration fits ten seconds per clip\n- [ ] Every recurring character has a reference image\n- [ ] Every clip has a scene prompt and an animation prompt\n- [ ] Incoming and outgoing states agree between clips\n")
    return "".join(out)
