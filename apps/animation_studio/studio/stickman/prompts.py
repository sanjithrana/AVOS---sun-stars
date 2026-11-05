"""The prompts, composed by code so nothing is paraphrased. They follow the Stickman Video Director prompt contract
(github.com/kaomei/stickman-video-director, MIT): every standalone 10-second prompt repeats, in this order, the output spec,
the environment, the FROZEN character anchor and cast cards, palette (ordinary colour names only, never hex), composition for
the ratio, the inherited first frame, three timed beats [0-3s] [3-7s] [7-10s], the exact audio-only narration, the FROZEN
voice block, the music lock (clip 1 sets it, later clips continue it), the final-frame hand-off and the negatives."""
from __future__ import annotations

from . import spec, styles

NEGATIVE = ("character redesign, style drift, costume or colour changes, extra limbs or fingers, merged bodies, duplicate leads, prop duplication, "
            "flicker, unplanned cuts, illegible generated text, logos, watermarks")


def style(p: dict) -> dict:
    return styles.get(p.get("style"))


def palette(p: dict) -> str:
    """Accent colours by NAME only: models paint hex codes as text."""
    seen, out = set(), []
    for c in p.get("roster") or []:
        for a in c["accents"]:
            if a["name"] not in seen:
                seen.add(a["name"])
                out.append(a["name"])
    return ", ".join(out[:4]) or "a small set of saturated accent colours on props only"


def style_lock(p: dict) -> str:
    st = style(p)
    return f"STYLE ({st['name']}): {st['look']} DRAWING GRAMMAR: {st['anchor']}"


def style_short(p: dict) -> str:
    st = style(p)
    return f"Stickman animated video, {st['name']} style. {st['look']}"


def negatives(p: dict) -> str:
    return f"Negative constraints: {style(p)['negative']}; {styles.COMMON_NEGATIVE}; {NEGATIVE}."


def identity(c: dict, p: dict | None = None) -> str:
    """The frozen cast card. In a fixed-character style the lead IS the style's tested anchor, word for word."""
    st = style(p or {})
    if st.get("fixed") and c.get("id") == "CHAR_01":
        return f"{c['id']} - {c['name']} ({c['role']}): {st['anchor']}"
    acc = ", ".join(a["name"] for a in c["accents"])
    return (f"{c['id']} - {c['name']}, {c['role']}, {c['age_presentation']} presentation, drawn in the style's grammar. Head: {c['head_shape']}; about "
            f"{c['height_heads']} head-heights tall; {c['proportions']}. Face: {c['eyes']}, {c['brows']}, {c['mouth']}. Hair or headwear: {c['hair_or_headwear']}. "
            f"Clothing: {c['clothing']}. Footwear: {c['footwear']}. Accent colours: {acc}. Signature prop: {c['signature_prop']}. Distinguishing feature: "
            f"{c['distinguishing_feature']}. IMMUTABLE: head shape, proportions, line weight, face, headwear, costume, colours, prop. MAY CHANGE: expression, pose, "
            f"damage state ({c['planned_damage']}).")


def _chars(p: dict, ids: list[str]) -> list[dict]:
    by = {c["id"]: c for c in p["roster"]}
    return [by[i] for i in ids if i in by]


def composition(p: dict) -> str:
    if p.get("aspect") == "16:9":
        return "Composition 16:9: stage the action left, centre and right, lateral tracking, deliberate negative space."
    if p.get("aspect") == "1:1":
        return "Composition 1:1: centred staging with clear foreground and background layers."
    return "Composition 9:16: foreground and background depth, vertical reveals, stacked motion, interface-safe space at top and bottom."


def bible_text(p: dict) -> str:
    b = p.get("bible") or {}
    if not b:
        return ""
    props = " ".join(f"{x['name']}: {x['look']}{'; ' + x['rule'] if x.get('rule') else ''}." for x in b.get("props") or [])
    rules = " ".join(r.rstrip(".") + "." for r in b.get("visual_logic") or [])
    return " ".join(x for x in (f"LAYOUT: {b['layout']}" if b.get("layout") else "", f"PROPS: {props}" if props else "", f"RULES: {rules}" if rules else "") if x)


def layout_prompt(p: dict) -> str:
    """The fixed location continuity reference: the whole place, its lights and props, before any clip is drawn."""
    b = p.get("bible") or {}
    return (f"Create a {p['aspect']} location continuity reference for the stickman film '{p['title']}': the full spatial arrangement of the main "
            f"location, wide view, readable foreground, midground and background. {style(p)['look']} {bible_text(p)} "
            + ("Show the lead character small in the scene for scale, exactly as on the attached identity sheet. " if p.get("roster") else "")
            + f"Every prop in its fixed place with its exact count. {negatives(p)}") if b else ""


def sheet_prompt(p: dict, c: dict) -> str:
    if style(p).get("proposal"):
        prop = next((x for x in (p.get("bible") or {}).get("props") or [] if x["name"].lower() in (c.get("signature_prop") or "").lower()), None)
        return (f"Character identity sheet for the stickman film '{p['title']}': clean front, three-quarter and side views of ONE character at the same "
                f"scale on a plain neutral warm-grey background, even soft light. {style(p)['look']} CHARACTER: {identity(c, p)}"
                + (f" Holding {prop['name']} ({prop['look']}) {prop['rule']}." if prop else f" Signature prop: {c['signature_prop']}.")
                + f" Reference only, not a scene. Identical design in every view. {negatives(p)}")
    return (f"Create a clean character reference sheet of ONE character only, for the stickman video '{p['title']}'. Plain light background, consistent "
            f"scale, ample spacing between panels, crisp 2D linework, no scenic background. {style_lock(p)} CHARACTER: {identity(c, p)} "
            "LAYOUT: clearly separated panels. Row 1: full-body front, three-quarter, side and back views at the same scale. Row 2: expression studies - "
            "neutral, happy, worried, shocked, angry, determined. Row 3: a close-up of the head or headwear and a separate view of the signature prop "
            f"({c['signature_prop']}). Identical design, outline weight and colours in every panel. {negatives(p)}")


def scene_prompt(p: dict, clip: dict) -> str:
    who = _chars(p, [c["id"] for c in clip["chars"]])
    place = " ".join(f"{c['id']}: {c['position']}, {c['facing']}, pose {c['pose']}, expression {c['expression']}, holding {c['prop_grip']}." for c in clip["chars"])
    return (f"Create a {p['aspect']} still image: the FIRST FRAME of clip {clip['n']} ({clip['t0']}-{clip['t1']} s) of the stickman video '{p['title']}'. "
            f"Match the attached style reference exactly. {style_lock(p)} Setting: {clip['location']}, {clip['time_of_day']}; {clip['scenery']}. "
            f"CHARACTERS, use exactly: " + " ".join(identity(c, p) for c in who) +
            f" Palette accents: {palette(p)}. {composition(p)} Framing: {clip['framing']}, {clip['camera_angle']}. Foreground: {clip['foreground']}; "
            f"middle: {clip['middle']}; background: {clip['background']}. Positions: {place} First-frame state: {clip['opening_setup']} {bible_text(p)} "
            f"This still shows only the moment BEFORE the main action, never a sequence. {negatives(p)}")


def animation_prompt(p: dict, clip: dict) -> str:
    who = _chars(p, [c["id"] for c in clip["chars"]])
    b = clip["beats"]
    vo = p["story"]["clips"][clip["n"] - 1]["narration"]
    out = clip["outgoing"]
    final = "; ".join(f"{c['id']} {c['position']}, {c['facing']}, holding {c['holds']}, feeling {c['emotion']}" for c in out["chars"])
    nxt = ("The next clip opens on this exact final frame." if clip["transition"] == "match" else
           f"Planned cut after this clip: {clip['transition_note'] or 'change of place'}.")
    inherit = (f"First frame inherited from the previous clip: {clip['incoming']['summary']}" if clip.get("incoming") else
               f"First frame: {clip['opening_setup']}")
    return (f"OUTPUT: stickman animated video, about ten seconds, {p['aspect']}, 720p, 24 FPS, synchronized audio. Animate the supplied first frame of clip "
            f"{clip['n']} of '{p['title']}'; do not invent a different opening composition. "
            f"ENVIRONMENT: {style(p)['look']} Setting: {clip['location']}, {clip['time_of_day']}; {clip['scenery']}. "
            f"CHARACTER LOCK, unchanged for the whole clip: " + " ".join(identity(c, p) for c in who) +
            f" PALETTE: {palette(p)} (accents on props and effects). {composition(p)} {bible_text(p)} {inherit} "
            "Rapid scene changes, kinetic motion-graphic transformations and frequent visual events, while preserving an identical stick-figure design, "
            "constant line weight and strict temporal consistency. "
            f"TIMED VISUAL BEATS: [0-3s] {b['setup']} [3-7s] {b['escalation']} [7-10s] {b['payoff']} "
            f"Camera: {clip['camera_move']}, one motivated move. Prop: {clip['prop_interaction']}. Every limb shows only its current pose; motion trails on props only. "
            f'NARRATION (audio voiceover only, strictly no speech bubbles, no dialogue boxes; do not add, omit, paraphrase, repeat, caption or display any words): "{vo}" '
            f"VOICE: {styles.voice_block(p)} {styles.music_lock(p, clip['n'])} SFX: {', '.join(clip['sfx']) or 'crisp sounds on each physical action'}. "
            f"FINAL FRAME at 10 s: {final}. {nxt} {negatives(p)}")


def global_block(p: dict) -> str:
    st = style(p)
    return (f"GLOBAL CONTINUITY: {p['aspect']}, {len(p.get('clips') or [])} clips x {spec.CLIP_SECONDS} s, style {st['name']}. Character anchor: "
            f"{st['anchor']} Environment: {st['look']} Accents: {palette(p)}. Narrator: {styles.voice_block(p)} Music: {st['music']}, set in clip 1 and "
            "continued identically. Every clip ends on the state the next clip opens on, or a named cut.")


def consistency_prompt(p: dict) -> str:
    rec = []
    for c in p["clips"]:
        rec.append(f"Clip {c['n']}: location {c['location']}, {c['time_of_day']}; characters {', '.join(x['id'] for x in c['chars'])}; "
                   f"outgoing state: {c['outgoing']['summary']} Transition into next: {c['transition']}.")
    t = p.get("project") or {}
    return ("CHARACTER CONSISTENCY AGENT INSTRUCTIONS\n\n"
            "You are the character and visual continuity supervisor for this stickman video. Apply the fixed designs below to every scene prompt and every "
            "image you are able to inspect. Preserve character identity across changes in pose, expression, camera angle, and location. When asked to generate or revise "
            "a scene, use its approved references as well as the written specifications.\n\n"
            f"PROJECT: {p['title']} - {t.get('date_place') or ''}. Format {p['aspect']}, {len(p['clips'])} clips of ten seconds. Tone: {t.get('tone') or ''}.\n"
            f"{style_lock(p)}\n\nCHARACTERS:\n" + "\n".join(identity(c, p) for c in p["roster"]) +
            "\n\nAPPROVED REFERENCE IMAGES: " + (", ".join(f"{c['id']} sheet" for c in p["roster"] if (p.get("assets") or {}).get(f"sheet:{c['id']}")) or
                                                  "none available yet; rely provisionally on the written designs and mark visual matching as unverified") +
            "\n\nENVIRONMENT RULES: stay inside the style's world; generic background people stay visually subordinate and never duplicate a lead.\n\n"
            "RULES: Lock head shape, proportions, line weight, facial feature spacing, hair or headwear, costume shapes, accent colours and signature accessories. "
            "Never transfer one character's features or clothing to another. Preserve character scale relative to recurring props and other characters. Keep left and right "
            "accessories consistent in the character's own orientation. Do not invent costume variants, missing props, extra fingers, extra limbs, merged bodies or duplicate leads.\n\n"
            "CONTINUITY RECORD (update after every clip: clip ID, characters present, location, time of day, costume state, expression, pose, position, direction of movement, "
            "prop owner, which hand holds the prop, persistent physical changes; record the outgoing state and the next clip's incoming state; never silently reset a dropped "
            "object, damaged costume, opened door or changed location; at a cut or time jump state what changes and what stays fixed):\n" + "\n".join(rec) +
            "\n\nUSE REFERENCES HONESTLY: attach approved reference images where the tool supports them. If an image is unavailable, say so and rely provisionally on the written "
            "design. If a design and a reference conflict, report the specific mismatch and ask only the necessary question. A seed, a repeated name or a text-only instruction does "
            "not guarantee identity.\n\n"
            "REVIEW: before returning any new scene prompt, compare it with the project style, character identities and continuity record. For an uploaded output, report PASS or "
            "REVISE only for features you can inspect; if revision is needed give a precise corrective prompt listing mismatched traits and required replacements. Never silently "
            "change an approved design to match a flawed generation.\n\n"
            "OUTPUT CONTRACT: return (1) the requested scene prompt or correction, (2) a brief continuity check, (3) the updated outgoing state. Keep these notes outside the image or "
            "animation prompt so they are not treated as on-screen text.")


def reference_video_prompt(p: dict, clip: dict, n_images: int, has_prev: bool) -> str:
    """The Seedance reference-to-video prompt, in the shape of the SJinn Amber Noir clips: what each reference is for, the fixed
    appearance, timed action and camera, native audio with the exact narration, voice, music and sound cues, then the negatives."""
    st, b = style(p), clip["beats"]
    total = len(p.get("clips") or []) or p.get("clip_count") or 1
    vo = p["story"]["clips"][clip["n"] - 1]["narration"]
    who = _chars(p, [c["id"] for c in clip["chars"]])
    refs = ["@Image1 is the approved opening composition of this clip and guides the starting camera, pose and scene."]
    if n_images > 1:
        refs.append("@Image2 is the exact character identity" + (" and prop design." if n_images else "."))
    if n_images > 2:
        refs.append("@Image3 is the fixed location layout, prop arrangement, palette and lighting.")
    if has_prev:
        refs.append("@Video1 is the preceding clip, supplied only to keep the same characters, setting, narrator, music and its ending state; continue forward without replaying it.")
    final = "; ".join(f"{c['id']} {c['position']}, {c['facing']}, holding {c['holds']}, feeling {c['emotion']}" for c in clip["outgoing"]["chars"])
    music = (p.get("bible") or {}).get("music") or st["music"]
    cont = "Begin the musical theme" if clip["n"] == 1 else "Continue the same musical theme without a fresh introduction"
    return (f"Create clip {clip['n']} of a {total}-part {st['name']} illustrated film, exactly {spec.CLIP_SECONDS} seconds, {p['aspect']}. " + " ".join(refs) +
            f" Visual style and fixed appearance: {st['look']} " + " ".join(identity(c, p) for c in who) + f" {bible_text(p)} "
            f"Action and camera timing: 0-3 seconds, begin from @Image1: {b['setup']} 3-7 seconds: {b['escalation']} 7-10 seconds: {b['payoff']} "
            f"Camera: {clip['camera_move']}. End on: {final}. "
            f'Audio: generate native synchronized audio. Exact off-screen English narration, spoken once with no additions, omissions or repetition: "{vo}" '
            f"Narrator direction: {styles.voice_block(p)} The visible characters do not mouth or speak the narration. Music direction: {cont}: {music}. "
            f"Sound cues: {', '.join(clip['sfx']) or 'synchronized effects for every physical action'}. Keep the same ambience with no intelligible background speech. "
            "Movement must replace each prior pose: no residual arm, duplicate hand, duplicate character or duplicate prop. "
            f"No subtitles, titles, captions, speech bubbles, readable signs, labels, logos, watermarks or any on-screen text. {style(p)['negative']}.")
