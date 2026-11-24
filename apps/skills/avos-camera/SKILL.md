---
name: avos-camera
description: The camera vocabulary for AVOS prompts - shot sizes, angles and moves, which of them a video model actually honours, and when to leave the camera locked. Use when writing a shot plan or a clip prompt and choosing how the shot is framed and whether it moves.
used_by: Any step writing a shot plan, a picture prompt or a motion prompt
---

# Camera

Two decisions per shot: **how close** and **whether it moves**. Get the first right and most shots work. Get the
second wrong and the shot looks generated.

## The default is locked off

Current video models fake a moving camera badly. Handheld comes out as jitter, a whip pan smears, an orbit bends the
geometry, a dolly zoom does neither thing properly. A still camera, by contrast, looks deliberate — and all the
energy then comes from the cut and the performance, which is where it belongs in a 5-second shot.

So AVOS's clip prompts say **locked off, or an extremely slow push**, and name the moves to avoid explicitly:
*no handheld, no shake, no whip pan, no orbit, no dolly zoom, no speed ramp.*

Break that rule when the move **is** the shot — a slow crane up to reveal scale, a push in that lands on a face at
the cut. One move, named once, slowly. Never two moves in one clip: a model given "pan left while craning down" does
a third thing that is neither.

## Shot sizes, closest to widest

The ladder is the useful part. A film that stays on one rung reads as one long take however much the content changes.

| Size | What is in frame | Reach for it when |
|---|---|---|
| Extreme close | one feature: an eye, a hand, a notch | tension, texture, the detail the plot turns on |
| Close | a face, or an object filling the frame | the emotional beat; the reveal |
| Medium | waist up, or an object with its immediate surroundings | the thing itself, head on, where most work happens |
| Wide | the whole body or object with its place around it | establishing; the last look |
| Extreme wide | the place, the subject small or absent | scale, isolation, the opening |
| Overhead | straight down | laid-out things: a board, a desk, a map, choreography |
| Insert | a detail cut in from elsewhere | a clock, a label, a hand on a switch |

**The rule AVOS enforces in code:** never the same size twice running. `norm_plan` rotates when a writer repeats,
because a writer handed six shots will write "medium" six times.

## Angles

| Angle | What it does |
|---|---|
| Eye level | neutral; the default, and invisible |
| Low angle | the subject gains weight and threat; good for the shot before a fall |
| High angle | the subject loses it; good for the moment after |
| Overhead | removes the subject's agency entirely; also the only honest way to shoot a flat surface |
| Over the shoulder | puts the viewer behind someone; needs two bodies to be worth it |

## Moves, when you do use one

| Move | Prompt phrase | Use for |
|---|---|---|
| Slow push in | "an extremely slow push in toward <subject>" | the safest move there is; intimacy, a build |
| Slow pull out | "a slow pull back, revealing <what>" | context arriving; the end of a sequence |
| Crane up | "the camera rises from <near thing> to <wide thing>" | intimate to grand, in one move |
| Crane down | "the camera descends from <wide> to <one figure>" | the reverse; arriving somewhere |
| Lateral track | "tracking alongside <subject> as it moves" | only when the subject moves with it |
| Drift | "a small drift, a few centimetres" | keeps a still shot alive without claiming a move |

Everything else — orbits, super dollies, levitation, dolly zooms — is a shot you will regenerate three times and
still not use. If you want one, make the picture do it: a low angle drawn into the still costs nothing and never
wobbles.

## Shot length

4 to 15 seconds is what the model accepts, and it is a **parameter**, not prompt text. Inside that: an extreme close
can hold 2–3 seconds before it dies, a wide establishing shot wants 4–5, a shot with an action in it needs long
enough for the action to *finish* — see `avos-when-it-fails`, "The action never finishes".

Pace it in words, since that is direction rather than configuration: *"the action lands in the first third, the rest
settles."*

## Putting it together

A shot line that works names three things and no more:

> **Extreme close, low angle, locked off.** The blade is already buried halfway through the onion, the near half
> fallen clear, the knife in contact with the board.

Size, angle, move — then what is happening, written as a state rather than a verb. Anything else in that sentence is
budget spent on something the model will not honour.
