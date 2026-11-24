---
name: avos-film-style
description: Steers the Film Style skill - 66 looks from the Lemo-Opuscar library, each its own entry in the Skills tab, where the style locks every prompt so a six-shot film holds one look. Use when writing or debugging a film-* skill run, or adding a style.
---

# Film Style — 66 looks, one implementation

Each of the 66 styles is its own Skills-tab entry (`film-art-deco`, `film-risograph`, `film-silent-film`, …) built at
import time by `film_style.skills()`. They share one set of stages and one RUN. Adding a style is a record in
`filmstyles.py`, not a new module.

## Where the look comes from

Upstream renders each style **in code** with Node and headless Chrome. The container has neither, so AVOS does the
other half of the job: it uses each style as a **lock on the prompts** it sends to the picture and video models it
already has. The look holds because every shot in a run carries the same look sentence, the same colour rule and the
same list of what the style is not.

`filmstyles.py` is generated — `python tools/extract_styles.py skills/lemo-opuscar studio/skilllab/filmstyles.py`.
Never hand-edit it. The extractor compresses a twelve-page `STYLE.md` into about a thousand characters and drops two
things on the way:

- **Real names.** The library names artists, directors and buildings as grammar. Those have no place in a prompt sent
  to a picture model, and upstream itself says never to copy a poster layout, a real building, a character, a
  typeface design or a melody. Every parenthetical that is only proper names is stripped.
- **Build notes.** Half of a style prompt is how to render it — canvas channels, blend modes, shader maths. None of it
  means anything to a picture model and all of it would crowd out the budget. A dimension like `320x180 pixels` is a
  look and stays; `mix(1, ink_i, coverage_i)` is not and goes.

## The prompt budget is the whole game

Pollinations cuts a prompt at **900 characters**. A style's look alone is about a thousand. So `_fit()` reserves the
shot first and gives the look what is left:

```
[the one-line look, up to 260]  [camera, shape, what is in frame, the action, the light]  [as much more look as fits]  [NEVER]
```

An earlier version led with the look and let it take the whole budget. Every shot of a film came out with the same
prompt and no subject in it. There is a test per style for exactly this — the subject and the action must both
survive at 900 characters, in all 66.

The long list of things to avoid goes to the model as `negative=NEGATIVE`, where it costs no budget. `NEVER` in the
prompt is one short sentence, because anything in both is paid for twice.

## Stages

| Stage | What happens |
|---|---|
| `plan` | The writer gets the look, what the style is **not**, and how it moves, and returns `{title, logline, shots[]}`. Each shot: subject, action, camera, light, beat. Cameras never repeat twice running. No writer → a plain three-beat plan, and the run still finishes. |
| `pictures` | One picture per shot. Chain capped at `MAX_CHAIN = 2`, `compose.too_same()` redraws a collapsed shot fresh, `compose.fill()` cuts bands and fills the frame, every version kept as a take. |
| `motion` | A video model if one is ready, otherwise a slow camera move with sound synthesised from the style's own sound palette. |
| `finish` | Joined, no music. |

Shot counts: 15 s → 3 shots, 30 s → 6, 45 s → 9, 60 s → 12, at 4–6 seconds each.

## Writing a good subject

The writer turns one line into shots, so give it something with a turn in it. `a student shipping her first app at
3am` works; `technology` does not. The style's own example line is on each skill's page — those are the shape to copy.

## Picking a style

`skills/lemo-opuscar/INDEX.md` lists all 66 by category with what each suits. The short version: **Information &
Keynote** and **Edit & Documentary** for explaining something; **Hand-drawn & Painting** and **Print & Printmaking**
when the texture is the point; **Cartoon & Anime** and **Games** for character and comedy; **Evidence Films** when
the subject is a real event and the film must look like it is checking itself.

## What this is not

It is not the upstream renderer. Upstream makes a 60-second film in code for nothing; this makes one with the picture
and video models AVOS already has, so it costs what those cost and the look is as close as a prompt can hold it. If
you want the real thing, install the plugin — `skills/lemo-opuscar/README-AVOS.md` has the two commands.

Credit: styles from the Lemo-Opuscar library by Lemomo, MIT.
