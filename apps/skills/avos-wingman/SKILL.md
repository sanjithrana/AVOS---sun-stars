---
name: avos-wingman
description: Write a character short the way WINGMAN was written - a one-page production bible sheet that locks the characters, then a shot-by-shot video prompt with hard cuts, a locked camera and diegetic audio. Use for Pixar-style character films, mascot shorts, ad films with a character, or any time the same character has to survive across several shots.
---

# The WINGMAN pattern

A character short falls apart for one reason: the character changes between shots. The fix is to spend the first
generation on a **production bible sheet** - a single image that fixes the design - and then never describe the
character from memory again.

Two prompts. The sheet, then the film.

## Why it works

| The problem | What the pattern does |
|---|---|
| The character drifts between shots | One sheet holds turnarounds and expressions; every later shot references it |
| The model fumbles camera moves | Locked-off camera only. All the energy comes from the cutting |
| Generated audio is generic | Per-shot diegetic audio lines, and one deliberate silence |
| Output looks like a trademarked character | The costume is described as original, and the negative list says so |

## Prompt 1 - the production bible sheet

16:9, one image. The point is the character lock in the middle of it; everything else makes the sheet readable.

```
A single-page animation production bible sheet, landscape 16:9, on a warm cream parchment ground
with thin hairline brown rules dividing every section.

REFERENCE ROLES - Use reference image 1 for LAYOUT AND TEMPLATE ONLY: its grid architecture, panel
hierarchy, label system, ground and typographic treatment. Do not carry over its content, characters,
colours or subject matter. Use reference image 2 for CHARACTER DESIGN LOCK: preserve the exact forms,
proportions, eyes, costume and expressions as shown. Do not redesign the characters.

TITLE BLOCK - top left. Large flowing script reading "<TITLE>". Beneath it in small wide-tracked
serif caps: "<SIX-WORD LOGLINE>". A small line-drawn icon of <a prop from the story> to the right.

HERO KEY ART - a large panel filling the upper-left quadrant beneath the title. <The single best
frame in the film: who, where, what light.> Photoreal 3D render, shallow depth of field.

CHARACTER DESIGN SHEET - lower-left quadrant, headed "CHARACTER DESIGN SHEET". Split into labelled
columns, one per character. Each column: three turnaround poses labelled FRONT, 3/4 VIEW, SIDE VIEW
<plus any costume change, labelled>. Beneath them a full-width strip headed "FACIAL EXPRESSIONS":
small head studies labelled <four to five emotions the story actually needs>.

STORYBOARD - the entire right half, headed "STORYBOARD". Seven numbered panels, three across, three
across, then one full-width at the bottom. Each panel: a numbered circle, a timecode, a rendered
film-still thumbnail above, and four labelled text rows below reading ACTION, CAMERA, LIGHTING, MOOD.
  1 - 0:00-0:02
  ACTION: ...   CAMERA: ...   LIGHTING: ...   MOOD: ...
  <...seven of them...>

SETTING DESIGN - a wide panel across the lower centre, headed "SETTING DESIGN": a clean unpopulated
render of the location.

COLOR PALETTE - lower right, headed "COLOR PALETTE". Six swatches in a three-by-two grid, each with
its hex code and name beneath in small serif caps.

BOTTOM BAR - a full-width strip across the base in four columns, each with a small line-drawn icon
and a heading: CAMERA MOVEMENT / LIGHTING AND MOOD / SOUND DESIGN / NARRATIVE NOTE (the last in
italic serif, one sentence saying what the film is actually about).

PALETTE OF THE SHEET ITSELF: warm cream parchment, sepia-brown ink, muted gold title, hairline rules.
TYPOGRAPHY: elegant serif throughout.
STYLE: production bible, archival, hand-assembled, warm, editorial.

Do not add any characters other than <the cast>. Do not redesign them. No watermark.
```

### The REFERENCE ROLES block is the part to copy

Without it a model blends every reference into one soup. Naming each image's job - *this one for layout only, that one
for the design, do not cross them* - is what makes two references behave. Keep it even with one reference.

Reference limits worth knowing before you attach anything: **FLUX.2 klein takes at most 4 references, each under
512x512**. **Seedance takes `images[:9]`.** If you have more, the sheet itself is the reference - that is its job.

## Prompt 2 - the film

```
Pixar-quality 3D animated short, 24fps cinematic, 16:9, 15 seconds, 7 hard cuts, no transitions.

CHARACTERS:
<NAME> - <species/kind>, <fur or surface and its colour>, <eyes: size, colour, catchlights>,
<beak/mouth>, <body shape>, wears <clothing>.
<...one block per character, written once and never paraphrased later...>

COSTUME (<who> wears this from shot <n> onward) - an ORIGINAL costume: <colours> bodysuit with
<pattern>, <mask or headpiece> and <an emblem you invented>. Fabric has real cloth weave and soft
specular sheen.

SETTING: <the place, in one-point perspective if it has depth, with the two or three props that matter>
LIGHTING: <key from where, rim from where, what the shadows do>, shallow depth of field.

SHOT 1 (0.0-2.0s) - <SHOT SIZE> <angle>, <camera move or "locked off">. <What happens, in present
tense, one or two sentences.> AUDIO: <what is heard>.
<...seven shots, each with its own timecode and its own AUDIO line...>

STYLE: <render style>. <The one or two craft notes that matter - fur strands catching rim light,
subsurface scattering, snappy anticipation-and-overshoot on big moves, held stillness between beats,
micro-acting in blinks and eye darts.>

CAMERA: Static or extremely slow push-ins ONLY. No handheld, no shake, no whip pans, no orbits, no
dolly zooms. All energy comes from the cutting rhythm and character performance.

AUDIO OVERALL: Fully diegetic, no separate music score. <The dynamic contrast - what is loud, where
it drops to near-silence, and at which second.>

NEGATIVE: no text, no subtitles, no watermarks, no camera shake, no slow motion, no crossfades or
dissolves, no extra characters, no crowd, no branded or trademarked costume designs, no human
characters.
```

## The seven beats

The shot count is not arbitrary. Seven is enough for a turn and a payoff and short enough to hold one idea.

1. **Establish** - wide, from behind, slow dolly in. Small in a big place.
2. **Want** - what the character sees and wants. Usually on a screen or across a room.
3. **Attempt** - the decision, or the costume change. Cut to it; never animate the transformation.
4. **Peak** - the biggest, most confident frame. Extreme close-up or hero angle.
5. **Fail** - the physical gag. One beat, one thud.
6. **Reaction** - cut to the other character. This is the laugh.
7. **Land** - a wider two-shot, very slow push in, the quiet version of the relationship. Deadpan to camera.

Shot 4 is the one to overwrite if the film is not working. If the peak is not confident, the fall is not funny.

## Hard rules

- **Hard cuts only.** No dissolves, no transitions. Say it twice - once in the header, once in the negative.
- **Locked camera.** Models fake handheld badly, and a still camera makes a generated shot look deliberate.
- **Audio per shot, diegetic.** One WHOOSH, one THUD, one laugh. A music bed makes everything feel like stock.
- **One silence.** Loud for the first four seconds, then an abrupt drop. The silence is the joke's setup.
- **Original costume, stated as original.** Describe the emblem you invented. This is both a legal line and a quality
  line: "superhero suit" alone gets you a smudged copy of a famous one.

## Running it in AVOS

The 7-shot prompt is written as one block so it reads as one film, but **do not ask a video model for all 15 seconds in
one generation** - no current model honours a seven-item cut list, and Seedance clamps any request to 4-15 seconds
anyway. Generate shot by shot and assemble:

1. **Skill Lab → Prompt to Video** with the sheet prompt → one bible image.
2. Keep that image. It is the character lock for everything after it.
3. For each of the seven shots: the shot's own text as the prompt, the bible sheet as the reference image, 2-3 seconds.
4. Assemble the seven clips in order. Hard cuts, no transitions - which is what you wanted anyway.

Budget at the catalogue rates: seven clips of about 2 seconds is roughly 14 seconds of video. On Seedance 2.0 Mini
(~$0.155/s) that is about **$2.20** a film; on Wan 2.2 (~$0.08/s) about **$1.10**. The bible image is a few cents.

If a shot comes back with the character redrawn, do not re-describe the character in words - re-attach the sheet and cut
the shot description down. The sheet is doing the work.

## Worked example

The WINGMAN short: two baby owls alone in an empty cinema, the boy owl tries to fly like the superhero on the screen,
gets about a foot off the seat, flops back down, and she laughs until she cries and then leans on his shoulder. Title
"WINGMAN", logline "ONE POSE. NO LIFTOFF.", narrative note *"He wanted to be the hero on the screen. He ended up being
the one she leans on."*

That note is the test. If you cannot write one italic sentence saying what the film is about, the seven shots will not
add up to anything.
