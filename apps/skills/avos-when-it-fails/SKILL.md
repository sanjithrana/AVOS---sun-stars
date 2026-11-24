---
name: avos-when-it-fails
description: Diagnose a bad run - symptom, cause, and the one thing to change. Covers shots that repeat, a style that loses to its subject, actions that never finish, hands that mime, black bands, and sound that is a default rather than a design. Use whenever a video comes out wrong and you are about to change the prompt.
used_by: Anyone reading back a finished run, and any step deciding whether to redraw
---

# When it comes out wrong

A bad generation is almost never "the model is bad". It is one of about a dozen failures, each with a different cause
and a different fix, and guessing between them wastes a run. Find the symptom, read the mechanism, change the **one**
thing named. Changing three things at once teaches you nothing.

Everything marked **measured** was found by taking a real AVOS run apart, not by reading a spec sheet.

---

## Every shot looks like the one before it

**Symptom.** Six shots, two or three distinct images. Often a creeping drift rather than exact copies: shot 3 and 4
are nearly the same, 8 and 9 are nearly the same.

**Mechanism.** The shots were drawn as a chain, each one edited *from* the previous picture. An edit model's safest
answer is its own input, so a long chain drifts toward no change at all. **Measured:** an eleven-shot cooking run had
four pairs scoring 0.95–0.98 alike on a 16×16 thumbprint, against 0.71–0.91 for shots that genuinely moved on.

**Counter.** Cap the chain. No shot should be more than two edits from a fresh drawing (`MAX_CHAIN = 2`), and any
chained result that comes back ≥94% like its reference is redrawn from its own words with no reference at all
(`compose.too_same`). If you are writing prompts by hand, the same rule applies: redraw, do not re-edit.

**The trap.** A chain *feels* right because it preserves continuity. It preserves continuity by preserving everything,
including the parts that were supposed to change.

---

## The style lost to the subject

**Symptom.** You asked for a drawn, printed or animated look and got photographs. A blueprint film comes back as
stock photos of engineers; a woodcut film comes back as a photo with a filter.

**Mechanism.** A concrete subject noun is a far stronger signal to a picture model than a paragraph of art direction.
**Measured:** `film-blueprint` with the subject "engineering" returned six photoreal men in hard hats. Blueprint's
look was in the prompt the whole time — as prose, after the subject, where it lost.

**Counter.** State the medium as a flat fact in the **first words**, where it cannot be trimmed: *"A DRAWING, not a
photograph: drawn line on a surface."* End with *"Not a photograph."* Put `photograph, stock photo, real person,
human face, dslr` in the **negative field**, which costs no prompt budget because it is a separate parameter.

**The trap.** Describing the style beautifully is not the same as declaring the medium. "Cyanotype paper, Prussian
blue, white linework" describes a drawing; it does not forbid a photograph of one.

---

## The action never finishes

**Symptom.** The shot list reads as full coverage and nothing in the film lands. The lid is still closing, the hand
is still reaching, the knife is still descending. Every shot is an attempt; none is a result. It survives review
because each shot looks fine on its own.

**Mechanism.** Shots get written by what they *contain*, not by what has to *finish* inside them, so the runtime goes
on the approach and the completion falls past the end of the clip.

**Counter.** Name the completion as a visible fact and let it settle: *the lid seats flush and stays there*, *the
glass comes to rest on the wood*, *the blade is through and touching the board*. Where the pace needs the cut sooner,
open the **next** shot with the result already true — the laptop shut, the room already dark — so the sequence
inherits what the cut skipped.

---

## Hands mime; the object never changes

**Symptom.** Fingers work convincingly over a pack that stays sealed, a cap that never breaks, a surface that never
creases. An actor rehearsing without a prop. **Measured in AVOS:** every prep shot of a cooking run had the knife
hovering above the board, touching nothing.

**Mechanism.** The manipulation was written as its verb — *tears it open*, *twists the cap off*, *chops the onion* —
which gives the model a gesture and no mechanism. With no structure, no anchor and no material response stated, the
gesture is the only part it can render.

**Counter.** Write the causal chain, in order:

1. **Structure** — what the object is before contact (sealed along the top edge, whole, capped).
2. **Anchor** — what holds it steady (the other hand gripping the body, the base flat on the board).
3. **Force** — where it is applied and which way it travels (thumb and forefinger at the notch, pulling across).
4. **Material feedback** — what the material visibly does (the film parts from the notch, the halves rock apart).
5. **Finished state** — what is true when it is done (a continuous opening, the near half fallen clear).

AVOS does this with `peak_of()`, which names the instant: *"the blade is already buried halfway through, the cut
piece has fallen away, and the knife is in contact with the board. Not hovering, not finished."*

**The cheaper route.** If the manipulation only *gets you to* the next state rather than being the point of the shot,
use two states and a sound instead — sealed pack, a tear heard off screen, hands already inside. It cannot fail this
way.

---

## Black bands down the top and bottom

**Symptom.** The video is letterboxed inside its own frame, and it gets worse as the run goes on.

**Mechanism.** Not the clip filter — that crops correctly. The bands are baked into the **pictures**: one shot comes
back in the wrong shape with padding, and every later shot edited from it copies the padding forward. **Measured:**
ten of eleven frames banded, between 6% and 20% of the frame, all descended from shot 2.

**Counter.** Cut bands off and cover-crop **the moment a picture arrives**, before anything else sees it
(`compose.fill`). Never pad to fit: cropping loses a strip of the edge, padding loses the shot. Writing "no black
bars" in the prompt does nothing, because by shot 3 it is not the model doing it.

---

## The sound is a default, not a design

**Symptom.** A flat, featureless bed under the whole film. Nothing happens in it. **Measured:** RMS 7.5, unchanged
across all 60 half-seconds of a 30-second film.

**Mechanism.** The sound description didn't match any cue the synthesiser knows, so it fell through to its default.
AVOS's `foley.py` is a **kitchen** synthesiser — sizzle, chop, pour, boil, stir, knock — and a film style asking for
"contrapuntal mechanical music: harpsichord, bassoon, strings spiccato" matches none of it and lands on `stir`.

**Counter.** Decide what kind of sound the look actually wants before synthesising anything (`sound_plan`). If it
wants a score, AVOS has no music model: lay quiet room tone at about −48 dBFS, say so in the step note, and leave the
track clear. A drone pretending to be sound design is worse than silence.

**The trap.** A normaliser hides this. AVOS's `_wav_bytes` pushed every cue to peak 0.82, so a bed meant to sit under
a film came out as loud as a knife hitting a board. If everything is the same loudness, nothing is mixed.

---

## Every shot is the same camera

**Symptom.** Six shots, one focal length, one height. Technically varied content that reads as one long take.

**Mechanism.** Nothing forced variety, so the writer repeated whatever it wrote first.

**Counter.** Never the same camera twice running — enforce it in code, not in the brief (`norm_plan` rotates when the
writer repeats). And give the fallback plan real beats: a plain six-beat ladder (place / detail / the thing itself /
from above / from below / the last look) beats six copies of "seen plainly".

---

## Walking, fighting and crowds

**Symptom.** Legs that slide, limbs that belong to nobody, a fight that goes choppy when assembled.

**Mechanism.** These are the hardest things a video model does. Walking needs weight transfer over several steps;
crowds need every body tracked; a fight cut from separate clips has no shared momentum.

**Counter.** Design around them rather than through them. Walk *into* or *out of* frame rather than across it. Hold
crowds in the background and out of focus. For a fight, generate it as one longer move rather than three clips that
have to agree. If a shot needs any of these to work, it is the shot to rewrite, not the prompt.

---

## Before you blame the model

1. **Was there a writer?** No AI writer means the fallback plan, which is six beats on your raw subject line and not
   a film. AVOS now says so in the step note; older runs did not.
2. **Did it actually run out of credit?** `fal.ai: no credit left` is caught and the run carries on with camera
   moves, which looks like a style failure if you don't read the note. Check **Analytics**.
3. **Is the subject still in the prompt?** Pollinations cuts at 900 characters. If the look ate the budget, the
   subject was trimmed off the end and every shot is the same picture of nothing.
4. **Change one thing.** Then look. Then change the next.
