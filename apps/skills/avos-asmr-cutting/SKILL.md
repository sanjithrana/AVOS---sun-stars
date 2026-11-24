---
name: avos-asmr-cutting
description: Make an ASMR cutting video - one object, an exact number of knife strokes, a counter from 0/N to N/N, a sound on every impact, and the slices falling at the end. Use when someone asks for a cutting, slicing or chopping reel, names an object and a cut count, or says "Object = X, Cuts = N".
---

# ASMR Cutting

One object on a board. The knife comes down exactly N times. A counter steps 0/N to N/N. Each stroke has its own sound.
After the last cut the pieces go over and the cut faces turn up. That is the whole form, and it works because the count
is exact and the sound lands on the same frame as the blade.

In AVOS this is a Skill Lab skill (`asmr-cutting`) that draws every frame in Python and synthesises every sound, so a
run costs nothing, needs no key, needs no Blender, and gives the same video twice. A 50-cut papaya takes about 45
seconds to render and comes out at 17.7 seconds, 1080x1920.

## The two things to ask for

```
Object = papaya
Cuts   = 50
```

Nothing else is required. Everything below has a working default.

**The count is exact.** "About fifty" is not an answer. If the person says 50, the video has 50 strokes and the counter
ends at 50/50. If a count will not fit the length they picked at a watchable pace, make the video longer and say so -
never quietly drop cuts.

## Running it in AVOS

Skill Lab → **ASMR Cutting** → type `papaya, 50 cuts` → run.

| Control | What it does |
|---|---|
| Subject | The object and the count: `papaya, 50 cuts`, `Object = Papaya, Cuts = 50`, `a bar of blue soap, 24 cuts` |
| Shape | `auto` works it out from the object. Override with round / long / bar / tall |
| Length | 12s, 18s, 28s - this sets the beat between strokes, not the number of them |
| Aspect | 9:16 for reels, 1:1 |
| Make | **Plan and video**, or **The plan only** if you just want the spec |

The beat is clamped between 0.12s and 0.60s per stroke. At 18 seconds with 50 cuts it lands on 0.25s, which is the beat
the original workflow uses (six frames at 24 fps).

## What gets decided for you

The AI writes one small JSON spec - what the object looks like - and nothing else. The shot, the timing and the sound
are fixed in code.

```json
{"object":"papaya","shape":"tall","skin":"#7ea64a","flesh":"#ee8448","seeds":"#262024","texture":"wet","title":"cutting a papaya"}
```

- **shape** - `round` apple, onion · `long` carrot, candle · `bar` soap, butter, cheese · `tall` papaya, melon, loaf
- **texture** - what the knife sounds like going through it: `wet` ripe fruit · `crisp` carrot, apple · `dry` soap,
  clay · `soft` butter, bread, cake
- **skin / flesh** - must be clearly different from each other, or the cut will not read on screen

If no AI writer is configured, or it fails, the skill falls back to a built-in colour table (papaya, watermelon, mango,
carrot, cucumber, apple, orange, lemon, tomato, onion, potato, banana, soap, butter, cheese, chocolate, bread, cake,
clay, tofu) and the run still finishes.

## The look

Vertical 9:16. A wooden board with real grain on a dark ground, one soft warm pool of light from the upper left. The
object sits on the board with a contact shadow. A steel chef's knife descends, holds in the cut for a beat, then lifts
to the next position. A white flash on the impact frame. The counter sits above the board, the object's name under it.

After the last stroke there is a beat of stillness, then the slices topple like dominoes - leftmost first, each leaning
on the one to its right - and fan apart so the flesh faces turn toward the camera. That fan is the payoff shot; it is
why the object needs a flesh colour that contrasts with its skin.

## Sound

One synthesised hit per impact, placed at the exact impact time. Each hit is a split (filtered noise, the knife through
the material) plus a knock (the board under it), with the balance and brightness set by the texture. Small random
variation between strokes so fifty hits do not sound like one hit repeated. A few soft wooden knocks under the fall, and
quiet room tone throughout.

Nothing is recorded or downloaded. There is no sound library to install.

## Watermark

Empty by default. If the person wants their handle on it, put it in the project's `watermark` field and it is drawn in
the bottom safe margin at low opacity. **Never carry somebody else's handle into a video** - the handle in the original
workflow belongs to its author.

## Objects that work well

Papaya, watermelon and melon (green outside, bright inside - the strongest contrast). Carrot and cucumber (long, many
thin slices). Soap and butter (clean bar, no seeds, very satisfying fan). Apple and orange (round, the slices curve).
Bread and cake (soft, pale inside).

Objects that do not: anything whose inside looks the same as its outside (a potato, a block of clay) - the fan at the
end has nothing to reveal. Give those a flesh colour a few shades lighter at least.

## When to use something else

- Cooking a dish with ingredients and steps → **ASMR Cooking**
- A stat, a journey or a device coming apart → **Motion Graphics**
- A brand or founder story → **Company Story**

## Credit

The form - object, exact cut count, counter, impact-aligned sound, slices falling, watermark in the safe margin - is
from the Hinglish ASMR cutting guide that drives Blender through Codex. AVOS draws it directly instead, so it needs none
of that toolchain.
