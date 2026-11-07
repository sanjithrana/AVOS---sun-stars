---
name: avos-prompt-to-video
description: How to write the prompts for every hop AVOS makes - prompt to picture, picture to clip, and a storyboard plus a picture to a clip - so a run keeps one look from the first frame to the last.
used_by: Any step that writes a picture or motion prompt (explainer, stickman, skill lab, series)
---

You write the prompts that make the pictures and the clips. A run is a chain of small hops, and every hop can lose the look: the
job is to hand each model so little room to drift that the shots cut together as one piece of film.

There are four hops. Use the one that matches what you have.

| You have | You want | Hop |
|---|---|---|
| words only | one picture | **1. prompt to picture** |
| one picture | one moving shot | **2. picture to clip** |
| words + a locked look | every picture of a video | **1, repeated, with the look block** |
| a picture + the shot's place in the story | a shot that cuts with the ones around it | **3. picture + storyboard to clip** |

---

## 1. Prompt to picture

Write ONE self-contained prompt. Never "same as the last one", never "as before": each prompt is read alone, by a model with no
memory of the others.

**Order matters more than wording.** Free picture services cut a long prompt off the end - Pollinations at 900 characters, FLUX
at about 256 tokens - so what you put last may never be read. Write in this order:

1. **The look** - the style sentence, word for word, the same in every shot of the video.
2. **The subject and its action** - one clear subject doing one thing.
3. **The environment** - where it is.
4. **The composition** - what sits where, and which part of the frame is kept empty.
5. **Depth** - foreground, midground, background, so the picture has planes instead of a flat wall.
6. **Light and palette** - the key light's direction, the three or four colours.
7. **The hard rules** - the short tail: no text, no logos, no watermark.

Keep the whole thing **under about 1,200 characters**. If it is longer, cut from the middle, never from the front.

**One hero.** One subject, at most three supporting objects, everything else removed. A prompt that names eight things gets a
picture of none of them.

**Say what is in the frame, not what it means.** "A red line falling across a big screen" draws. "The company was in trouble"
draws nothing.

**Leave room on purpose.** If something is composited in later - a character, a card, a caption - say which part of the frame
stays calm: *"the LEFT third is kept almost empty, flat ground, low detail"*.

**Negative prompt.** Always send one. Start from this and add what this look must never become:

```
text, letters, numbers, logo, label, watermark, caption, signature, blurry, low detail, deformed hands, extra fingers,
cropped head, cropped feet, cluttered frame, muddy shadows
```

**Sizes.** 16:9 is 1280x720, 9:16 is 720x1280, 1:1 is 1024x1024. Ask for the shape the video will be in; do not crop later.

**Seeds.** The same prompt and the same seed give the same picture. Change the seed to get a different take of the same prompt;
change the prompt to get a different picture. Keep one seed per character so a face stays put.

### With reference pictures

A reference is worth more than a paragraph of description. When the step can pass them:

- Up to **four** references, each under **512x512** (FLUX.2 klein's limit).
- Say what each one is and what to take from it, in order: *"Picture 1 is the character's model sheet: keep his face, hair and
  suit exactly. Picture 2 is the set: keep its colours and shapes."*
- Then write the new picture as usual. The references fix identity; the prompt fixes the moment.
- Never write "the character from before". The model sees only what you attach.

---

## 2. Picture to clip

The picture is **frame one**. The clip prompt's whole job is to say what changes from it - nothing else.

**Open by naming the still.** *"Animate this exact photograph as a 5-second shot. Keep the frame, the lighting and every object
exactly as they are."* Without that line the model redraws the scene and the cut jumps.

**One action per clip.** Stacked actions multiply drift. One thing happens; everything else holds.

**One camera move, slowly.** A slow push in, a slow pull out, or a small drift. Name it once. "No other camera move, no cuts, no
transitions, no morphing, no object replacement."

**Say the physics.** What the material actually does: paper bends and settles, liquid falls and splashes, steam rises, cloth
flutters, metal locks with weight. This is what separates a moving photograph from a shot.

**Length.** Ask for 4 to 15 seconds; a video model is given a whole number of seconds in that range and anything outside it is
clamped. Pace it: *"the action lands in the first third, the rest settles."*

**Sound.** If the model makes its own audio, name the sound as the sound - *"loud oil sizzle tsssss"*, *"a dry paper tap"* - and
say what must not be there: *"no music, no voice, no narration."* If it does not, the clip is silent and the sound is added later.

**End the prompt with what must not change:** no new characters, no new objects, no style change, no text.

---

## 3. Picture + storyboard to clip

Same as hop 2, plus the one thing a single shot cannot know: where it sits in the story.

**Give the shot its neighbours, not the whole plot.** What the shot before left behind, and what the shot after needs to find.
One sentence each. The model does not need the script.

**Carry the state forward.** Whatever changed in the last shot is still changed in this one: the onion is still chopped, the
building is still burned, the chart is still on the screen. Say it: *"Already true in this scene: ..."*.

**Chain off the canonical reference, never off the last output.** Re-attach the character's model sheet and the product's
reference to every shot. Chaining a shot off the previous shot's last frame compounds every small error until the face is a
stranger's by shot six.

**Start frame and end frame.** When the step can pass two pictures, the pair does the work and the words only name the one action
that carries A into B: *"Reference 1 is the first frame, reference 2 is the last frame. Between them, one continuous movement:
<the action>. No cuts."* Both frames must share an anchor that does not move - the same table, the same horizon - or the cut
reads as a jump.

**Explain every fate.** If something leaves the frame, say where it went: *"the hand withdraws out of frame to the left"*. If
something arrives, say where from. Objects that blink out of existence are the clearest sign of a machine-made cut.

---

## The look block

A video keeps one look because every prompt carries the same sentence, not because the model remembers. Write the look once,
paste it word for word into every picture prompt of that video, and never reword it per shot. If the look has to change, change
it in one place and redraw everything.

A look block names: the medium and finish, how objects are built, the lighting, the palette, and what it must never be.

> A handcrafted paper-cut diorama: every object cut from layered cardstock with exposed edges, real paper thickness and deep
> shadows between the layers, soft museum lighting from the top left, warm earth tones. NOT photographic, NOT 3D, NOT a painting.

## Before you send a prompt

1. Does it stand alone, with no reference to an earlier prompt?
2. Is the look block the first thing in it, word for word?
3. One hero subject, one action?
4. Under ~1,200 characters, with the hard rules in the tail?
5. Is there a negative prompt?
6. For a clip: does it start by naming the still, hold everything else, and change exactly one thing?
7. For a shot in a story: is the state from the shot before stated, and is the canonical reference attached?

## When it comes out wrong

| What you see | What it is | Fix |
|---|---|---|
| The style drifts shot to shot | The look block was reworded, or left out of a shot | Paste it identically into every prompt |
| The picture ignores the end of the prompt | It was cut at 900 characters | Shorten it; move what matters to the front |
| A face changes between shots | The shot was chained off the previous output | Attach the canonical model sheet to every shot |
| Text or a watermark appears | No negative prompt, or the tail was cut off | Send the negative; keep the tail short |
| The clip redraws the scene | The prompt did not name the still as frame one | Open with "Animate this exact photograph... keep everything as it is" |
| Everything moves at once | More than one action was asked for | One action per clip; split the rest into another shot |
| The cut jumps between two shots | No shared anchor, or an unexplained fate | Share a fixed element; say where things went |
| The frame is a dark, empty room | A mood word was given instead of objects | Name the objects and the light: bright, and what is in the frame |
| A composited element covers the subject | No empty area was reserved | Say which third of the frame stays calm |
