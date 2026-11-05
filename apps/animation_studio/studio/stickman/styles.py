"""Stickman visual styles, taken from Stickman Video Director (github.com/kaomei/stickman-video-director, MIT licence,
Copyright (c) 2026 Stickman Video Director contributors). The character anchors, environment locks, negatives, voice and
music locks below are the repo's tested wording, repeated VERBATIM in every prompt of a video (that repetition is what keeps
the stick figure, the look and the narrator the same from clip to clip).

    arc "heartbeat": the 5-stage high-completion engine (hook, disrupt assumptions, insider secrets, truth, elevation + question)
    arc "payoff":    setup, escalation, ironic payoff (no forced discussion question)
    arc "story":     story beats with deliberate reaction pauses (historical / cozy shorts)"""
from __future__ import annotations

from pathlib import Path

REFS = Path(__file__).parent / "style_refs"

_LIMBS = ("Exactly two arms and two legs are visible per figure. Each limb appears only in its current pose: raising or lowering the right arm "
          "replaces that arm's previous line, never leaving a resting arm beneath an active arm.")

STYLES: list[dict] = [
    {"id": "a1-dark", "code": "A1.2", "name": "Classic · White on black", "group": "Classic Minimalist", "arc": "heartbeat", "fixed": True,
     "made_for": "Science, psychology, business breakdowns, mental models",
     "look": "Flat, uniform, pitch-black canvas. Pure white line art with up to three saturated accent colours on props and graphic effects only.",
     "anchor": ("Use minimalist two-dimensional white line animation. Show the same consistent stick figure with a hollow circular head, occasional simple "
                "line expressions, no detailed facial features, no hair, no clothing, no filled body, stable proportions, connected line limbs, and uniform "
                f"medium line weight. {_LIMBS} The figure stays white; accent colors affect only props and graphic effects."),
     "negative": ("no gray tint, no paper texture, no gradients, no shadows, no 3D depth, no filled heads, no duplicated or retained limb poses, no detached "
                  "body lines, no inverted polarity, no unexplained colours"),
     "music": "quiet, thoughtful piano and subtle soft ambient synth, building gentle optimistic momentum"},
    {"id": "a1-light", "code": "A1.1", "name": "Classic · Black on white", "group": "Classic Minimalist", "arc": "heartbeat", "fixed": True,
     "made_for": "Science, psychology, business breakdowns, mental models",
     "look": "Flat, uniform, digitally pure-white canvas with no gray tint, paper texture, gradients, shadows, lighting, bloom, fog or 3D depth. Up to three saturated accent colours on props and graphic effects only.",
     "anchor": ("Use minimalist two-dimensional black line animation. Show the same consistent stick figure with a hollow circular head, occasional simple "
                "line expressions, no detailed facial features, no hair, no clothing, no filled body, stable proportions, connected line limbs, and uniform "
                f"medium line weight. {_LIMBS} The figure stays black; accent colors affect only props and graphic effects."),
     "negative": ("no gray tint, no paper texture, no gradients, no shadows, no 3D depth, no filled heads, no duplicated or retained limb poses, no detached "
                  "body lines, no inverted polarity, no unexplained colours"),
     "music": "quiet, thoughtful piano and subtle soft ambient synth, building gentle optimistic momentum"},
    {"id": "a2-tech", "code": "A2.1", "name": "Modern Pop · Minimal Tech", "group": "Modern Pop", "arc": "heartbeat", "fixed": True,
     "made_for": "AI tools, tech products, tutorials, career insights",
     "look": ("A modern bright white studio space with subtle light-gray perspective grid lines on the floor plane. High-key studio lighting, clean white "
              "negative space, sleek glowing cyan and electric blue glass holographic UI elements (icon-only, no text)."),
     "anchor": ("A minimalist 2D animated stick figure wearing a bright red beanie (smooth rounded knit, no pom-pom) and a yellow t-shirt, with simple black "
                "stick limbs and shorts. Simple black lines, vibrant colors, smooth 2D animation style. Minimal dot eyes only, no detailed pupils."),
     "negative": ("strictly minimalist studio aesthetic, no circuit board textures, no sci-fi wall panels, no spaceship corridors, no cracked concrete, no grunge "
                  "textures, no photorealistic human skin"),
     "music": "quiet, thoughtful piano and subtle soft ambient synth, building gentle optimistic momentum"},
    {"id": "a2-story", "code": "A2.2", "name": "Modern Pop · Colorful Story", "group": "Modern Pop", "arc": "heartbeat", "fixed": True,
     "made_for": "Personal growth, everyday experiences, motivational journeys",
     "look": ("A rich full-color cinematic environment that fits the scene (a warm lamplit room, a dusk highway, a mountain ridge above golden clouds). "
              "Cinematic volumetric lighting, soft depth of field, atmospheric narrative mood; the character stays flat smooth 2D vector animation."),
     "anchor": ("A minimalist 2D animated stick figure wearing a bright red beanie (smooth rounded knit, no pom-pom) and a yellow t-shirt, with simple black "
                "stick limbs and shorts. Simple black lines, vibrant colors, smooth 2D animation style. Minimal dot eyes only, no detailed pupils."),
     "negative": "no photorealistic human skin or faces, no 3D humanoid CGI uncanny valley models, no chaotic line glitches",
     "music": "warm cinematic piano and soft strings, building gentle optimistic momentum"},
    {"id": "a3-cave", "code": "A3", "name": "Prehistoric Cave", "group": "Prehistoric Cave", "arc": "payoff", "fixed": False,
     "made_for": "Satirical stories, visual analogies, ironic callbacks",
     "look": ("Crude hand-drawn 2D black outlines, earthy ochre and brown prehistoric scenery (caves, camps, forests, river crossings, rocky plains), small "
              "warm fire accents and a subtle paper texture."),
     "anchor": ("Crude hand-drawn 2D cartoon characters with white filled round heads, expressive simple cartoon eyes, brows and mouths, thin black stick "
                f"limbs and animal-hide clothing. {_LIMBS}"),
     "negative": "no photorealistic skin, no glossy 3D characters, no modern studio UI, no extra humans, no duplicate props, no colour swatches",
     "music": "understated primitive percussion with dry pauses for the jokes"},
    {"id": "a4-cozy", "code": "A4", "name": "Cozy Storytelling", "group": "Cozy Storytelling", "arc": "story", "fixed": True,
     "made_for": "Relatable life stories, emotional growth, educational stories",
     "look": ("A full-color 2D cartoon environment with gentle atmospheric light. Each clip opens in a different recognizable story location (an office, a "
              "metro platform, a street-side cafe, a park) with wide, close and tracking shots inside it."),
     "anchor": ("One minimalist 2D cartoon protagonist with a white filled circular head, two small dark oval eyes, simple eyebrow strokes and a short curved "
                "mouth. The torso is a slim closed tapered shape with solid white fill inside its dark outline. Both arms and both legs are dark single-line "
                "strokes with constant medium weight; hands are small dark rounded shapes and feet are short dark rounded strokes. No hair or clothing "
                "accessories. Keep the same head-to-body proportions, white head and torso fill, and outline weight in every shot. Exactly two arms and two "
                "legs exist; a moving limb replaces its previous pose rather than leaving another limb behind. Expressions change only the simple facial "
                "marks, never the head shape or character design."),
     "negative": "no photorealistic backgrounds, no 3D characters, no hand-drawn sketchbook texture, no duplicated props, no end-state resets",
     "music": "a gentle acoustic guitar and soft piano motif with the same tempo and instrumentation in every clip"},
    {"id": "a5-history", "code": "A5", "name": "Historical Cartoon", "group": "Historical Cartoon", "arc": "story", "fixed": False, "history": True,
     "made_for": "History explainers, historical daily life, civilisation stories",
     "look": ("Polished 2D cel-shaded historical cartoon, clean thick black outlines, softly shaded period clothing, and sunlit painterly full-color "
              "historical landscapes and architecture of the era."),
     "anchor": ("2D cartoon stickman characters with round white heads and a short sturdy white neck growing naturally from the clothed shoulders, one "
                "continuous white head-and-neck silhouette. Balanced adult proportions, about four head-heights tall. An expressive storybook face: two solid "
                "black vertical oval eyes, character-specific eyebrows, nose and mouth. Thin black arms and legs, exactly two of each. Each wrist ends in one "
                "compact solid black rounded mitten-shaped palm with a subtle thumb bump, no separate fingers, no white gloves."),
     "negative": ("no blood or gore, no photorealistic faces, no 3D CGI, no paper texture, no fused or duplicate heads, no costume changes, no individual "
                  "fingers, no white hands or gloves, no floating head, no background gap between head and neckline"),
     "music": "era-appropriate instruments: restrained drums, brass and strings for epic beats, light plucked strings and woodwinds for daily life"},
    {"id": "a6-amber", "code": "A6", "name": "Amber Noir", "group": "Amber Noir", "arc": "payoff", "fixed": True, "native_audio": True, "captions": False,
     "proposal": True, "made_for": "What-if scenarios, modern fables, psychology, gentle suspense with a warm or ironic payoff",
     "look": ("Cinematic Amber Noir illustration with angular scenery, warm amber highlights, deep plum and muted-purple shadows, restrained "
              "two-dimensional cel shading, glowing shop windows, dusk streets with readable foreground, midground and background."),
     "anchor": ("A slender, visibly two-dimensional stickman with a small solid matte-black circular head attached to a short black neck, no hair, small "
                "pale-cream eye marks and a modest expressive pale-cream mouth line, simple black arms, hands, legs and feet. He wears the same rust-orange "
                "hoodie with the hood down, dark charcoal trousers and simple black shoes throughout. Warm motivated amber edge light keeps his black "
                "silhouette readable against the plum shadows. He acts with eyes, posture and gestures and never mouths the narration."),
     "negative": ("no photorealism, no glossy plastic, no 3D CGI, no hair, no changed hoodie colour, no residual arm or duplicate hand, no duplicate "
                  "character or prop, no autonomous monster or floating shadow, no readable signs or labels"),
     "music": "one continuous quiet theme of soft felt piano, muted bass pulses and airy atmospheric tones, gentle suspense resolving warmly, narration prominent",
     "voice": ("Off-camera English narration from a warm adult baritone with an American accent. Conversational, evenly paced, clearly articulated and "
               "intimate, with understated suspense and dry humor. Retain the same pitch, texture, pace and close-recorded character across the film.")},
    {"id": "b1-line", "name": "Minimal Line Art", "group": "Autopilot", "arc": "heartbeat", "fixed": True, "code": "B1", "autopilot": True,
     "made_for": "YouTube explainers, education, psychology, workplace stories, product intros",
     "look": ("Near-white paper background, lively hand-drawn black linework like a friend sketching while explaining, a few colourful props as accents, "
              "generous clean space for a headline. Illustrated scene with subtle animation."),
     "anchor": ("A hand-drawn stick figure with a round white head, expressive drawn face (eyebrows, eyes, mouth that show emotion clearly), thin black "
                f"line body and limbs, no clothing. {_LIMBS}"),
     "negative": "no paper clutter, no gradients, no 3D, no photorealism, no busy backgrounds",
     "music": "a light, curious acoustic underscore, very quiet under the voice"},
    {"id": "b2-color", "name": "Colorful Hand-Drawn", "group": "Autopilot", "arc": "story", "fixed": True, "code": "B2", "autopilot": True,
     "made_for": "Everyday psychology, sleep, habits, attention, relatable life explainers",
     "look": ("Warm paper texture, fine ink lines, soft muted colours, cosy everyday settings (a bedroom at night, a kitchen, a street), illustrated "
              "metaphors and gentle motion."),
     "anchor": ("A small stick figure with a round white head, simple dot eyes and a small mouth, thin dark ink-line limbs and body, drawn with fine "
                "slightly wobbly ink lines. Same proportions and line weight in every scene."),
     "negative": "no harsh neon colours, no 3D, no photorealism, no clutter",
     "music": "a soft lullaby-like piano with warm pads, gentle and slow"},
    {"id": "b3-tv", "name": "Retro TV", "group": "Autopilot", "arc": "heartbeat", "fixed": True, "code": "B3", "autopilot": True,
     "made_for": "Everyday science, psychology, animal behaviour, curious facts, short mysteries",
     "look": ("A dark late-night broadcast screen: near-black background with faint bloom, subtle scanlines and analog texture, luminous white-and-gray "
              "figures, clean minimal composition."),
     "anchor": ("A rounded white stick figure with a glowing white head and body made of soft thick white strokes, no face or minimal dot eyes, light gray "
                "shading, slight bloom glow. Animals and objects are drawn in the same rounded white-and-gray treatment."),
     "negative": "no bright colours, no detailed faces, no photorealism, no 3D",
     "music": "a low warm analog synth drone with a soft curious melody"},
    {"id": "b4-thriller", "name": "Survival Thriller", "group": "Autopilot", "arc": "payoff", "fixed": True, "code": "B4", "autopilot": True,
     "made_for": "Survival rules, urban legends, disaster escapes, suspense with a twist",
     "look": ("Refined full-color 2D hand-drawn story illustration: clear confident black ink contours, broad painted colour fields, restrained cel-shaded "
              "shadow patches, stark light and shadow, half-shadowed openings, threats emerging from the dark; readable foreground, midground and background."),
     "anchor": ("Plain circular white heads, tiny black oval or dot eyes and an optional short minimal mouth; unclothed single-black-line torso and black "
                "stick limbs, simple small feet, compact rounded white cartoon gloves outlined in black."),
     "negative": "no gore, no photorealism, no 3D rendering, no cluttered detail",
     "music": "a quiet continuous dark ambient bed with low drones; causal sound effects for every danger"},
]
BY_ID = {s["id"]: s for s in STYLES}
DEFAULT = "a5-history"

VOICE = {
    "male": ("One off-screen adult male narrator throughout. General American accent, warm clean baritone, medium-low pitch, gentle chest resonance, no "
             "raspiness or breathiness. Calm conversational delivery, restrained pitch variation, steady speaking pace, and close, dry studio sound. Keep the "
             "same vocal timbre, register, accent, pace, and recording quality throughout. Emotional progression belongs to the visuals and music; do not "
             "change the narrator's voice or switch to character dialogue."),
    "female": ("One off-screen adult female narrator throughout. General American accent, clear warm mid-high voice, gentle forward resonance, no raspiness "
               "or breathiness. Lively conversational delivery with controlled pitch variation, steady speaking pace, and close, dry studio sound. Keep the "
               "same vocal timbre, register, accent, pace, and recording quality throughout. Emotional progression belongs to the visuals and music; do not "
               "change the narrator's voice or switch to character dialogue."),
}

COMMON_NEGATIVE = ("no visible words, letters, numbers, captions, subtitles, interface copy, palette labels, logos or watermarks; no speech bubbles or "
                   "dialogue boxes; no extra limbs, malformed anatomy, disconnected lines or changed proportions; no unintended characters; no abstract "
                   "liquid or shape morphing; no idle standing")


def get(sid: str | None) -> dict:
    return BY_ID.get(sid or "", BY_ID[DEFAULT])


def voice_block(p: dict) -> str:
    st = get(p.get("style"))
    if st.get("voice") and p.get("voice") != "female":
        return st["voice"]
    return VOICE["female" if p.get("voice") == "female" else "male"]


def music_lock(p: dict, n: int) -> str:
    m = get(p.get("style"))["music"]
    if n <= 1:
        return f"Audio: voiceover clearly audible over {m}. Synchronized crisp SFX on physical actions; voice-first mix."
    return (f"Audio: voiceover seamlessly continues the identical {m} from clip 1, maintaining identical tempo, instrumentation and narrative momentum. "
            "Synchronized crisp SFX on physical actions; voice-first mix.")


def reference(sid: str | None) -> bytes | None:
    """The style's sample frame (from the repo's previews), handed to the picture model as a style reference."""
    f = REFS / f"{get(sid)['id']}.jpg"
    return f.read_bytes() if f.is_file() else None


def public() -> list[dict]:
    return [{k: s[k] for k in ("id", "code", "name", "group", "made_for", "arc", "look")} | {"history": bool(s.get("history")), "mode": "autopilot" if s.get("autopilot") else "director",
                                                                          "native_audio": bool(s.get("native_audio")), "captions": s.get("captions", True)}
            for s in STYLES]


ARC = {
    "heartbeat": ("Structure the narration with the 5-stage high-completion engine, scaled over the clips: 1 Golden Hook (a counter-intuitive question or "
                  "visual paradox in the first seconds, never a greeting); 2 Disrupting Assumptions (state what everyone believes, then shatter it in one "
                  "sentence); 3 Unveiling Insider Secrets (the hidden mechanism or real obstacle); 4 Ultimate Truth Revelation (the underlying logic, the "
                  "aha); 5 Elevation (a memorable punchline and an open question that makes viewers take sides in the comments)."),
    "payoff": ("Structure it as setup, escalation and ironic payoff: a premise and conflict, a tempting solution that escalates, then a reversal or callback. "
               "Leave room for a deadpan reaction beat of half a second to two seconds; do not force a discussion question onto a visual punchline."),
    "story": ("Structure it as a short story: a concrete visual problem in the first two seconds, escalation where every clip advances the story or "
              "clarifies cause and effect, a turning point, and a real consequence or memorable insight at the end. Physical actions, deliberate reaction "
              "pauses allowed."),
}
