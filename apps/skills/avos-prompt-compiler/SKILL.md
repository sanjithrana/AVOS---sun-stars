---
name: avos-prompt-compiler
description: Reference - how a shot's scene graph, motion blueprint and Design DNA become each model's prompt (deterministic code, agentic_core/creative/compiler.py)
used_by: Facts and Series (code); read this to understand or tune the phrasing per model
---
# Prompt compiler (reference)

The compiler is code, not an AI call, so the same shot always compiles to the same prompts and `params_hash`. It is
the bridge between structured control and natural-language conditioning:

```
scene graph (WHERE) + motion blueprint (WHEN) + Design DNA (LOOK) → keyframe prompt + motion prompt + negative prompt
```

## Keyframe prompt (Qwen-Image-Edit / Z-Image / FLUX)

1. What each reference picture is ("picture 1 is Raju's character sheet; picture 3 is the kitchen").
2. "ONE frame of an animated episode: <framing>, <angle from camera height>, <lens words (mm)>".
3. Each actor: "<name> <left/centre/right, foreground/background>: <pose>, <expression>, facing <x>" (+ "the one
   speaking"); listeners keep their mouths closed.
4. Props, place + time, lighting key + mood.
5. "Every character looks exactly like their sheet", the Design DNA style clause, any change note, "no text".

## Motion prompt, phrased per renderer

- **LTX-2.3**: one flowing chronological paragraph: the main action first, then timed actions ("At 1.5s, …"), who and
  where, the camera move and its ease, light, the DNA's animation and style clauses, "characters stay consistent".
- **Wan 2.2**: short and concrete: the timed actions, the camera, the animation clause, the style clause.
- **InfiniteTalk / LongCat**: "<name> talks <emotion>, lips in sync…", gestures, camera, style.

Camera moves are words from a fixed table (push_in → "The camera slowly pushes in", ease power2 → "with a smooth
ease"). To support a new video model, add one phrasing branch in `motion_prompt`; nothing else changes.
