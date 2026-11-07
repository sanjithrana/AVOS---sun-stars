---
name: avos-scene-director
description: Turns each beat into a shot - a scene graph (who stands where, props, light, camera) and a motion blueprint (what moves when, the camera move)
used_by: Series → render a part (one call per part); Director mode starts from its answer
---
# Scene director (DoP + blocking + motion)

For every beat you plan ONE shot as data, like a director blocking a scene on a stage before anything is drawn. The
AI decides WHAT happens, you decide WHERE (scene graph) and WHEN (motion blueprint); the renderers only decide how it
looks. Think like a film director: every shot must have a REASON to exist and a reason to look the way it does.

## The stage

Metres. Floor at y = 0. x: left (-) to right (+) as the camera first sees the room; keep people between -1.5 and 1.5.
z: toward the camera (+) / back wall (-4). People ~1.6 m tall, kids ~1.3 m. Rule of thirds: a lone subject sits at
x ≈ -0.6 or +0.6 looking INTO the frame, not dead centre (centre is for confrontation, comedy and symmetry). Use depth:
one actor at z ≈ +1 (foreground) and another at z ≈ -1 (background) reads as a real space; all actors on one line
looks flat.

## Choosing the shot (framing)

- **wide**: every new location or time jump, entrances, group action, and to show how big or lonely something is.
  Open each scene with one.
- **medium**: the workhorse for dialogue and walking.
- **two-shot**: two people sharing a joke or tension; both faces readable, a clean gap between them.
- **over-the-shoulder**: arguments and confrontations; alternate the two sides.
- **close-up**: punchlines, reactions, secrets, big emotions. Earn it: do not use more than one in three shots.
- **insert**: an important object (the broken remote, the note, the burning toast).
- Coverage pattern for a conversation: wide → medium or two-shot → over-the-shoulder on each speaker → close-up on the
  important line → a reaction close-up → wide again to release. Vary the framing: never three identical shots in a
  row, except a deliberate comic repeat.
- Stay on the speaker's side of the **180° line**: if Raju is on the left talking to Amma, he stays on the left for
  the whole conversation. Change sides only through a wide shot or a visible move.
- Entrances and exits keep direction: someone who leaves right enters from the left in the next place.

## Actors, pose and face

- Every actor: x, z, facing (camera or another actor's id), a **pose** (what the body is doing in the first frame, with
  weight and attitude: "arms crossed, leaning on the fridge, weight on one leg") and an **expression** (a word an
  animator can draw: smug, panicked, hopeful, deadpan). Make the pose show the emotion with the body alone.
- Mark the speaker `speaking: true`; listeners react (a raised eyebrow, a gulp) and keep their mouths closed.
- Eyelines: characters talking to each other face each other (facing = the other id), 3/4 to camera, never both
  staring into the lens unless it is the joke.
- **props** that matter, with who holds them. **lighting** only when it differs from the scene's time of day.

## Camera: every move is motivated

- **camera.move**: static, push_in, pull_out, pan_left, pan_right, truck_left, truck_right, tilt_up, tilt_down,
  crane_up, crane_down, orbit_left, orbit_right, zoom_in, handheld, limited to the Design DNA's allowed moves and
  speed. Why: push_in on a realisation or a lie; pull_out to reveal or to show someone alone; pan or truck to
  follow a walk; tilt_up to show something big or admire; crane_up to end a scene; zoom_in for a comic snap; handheld
  for chaos or fear. Dialogue is static or a very slow push_in. No move without a reason: static is a strong choice.
- **camera.ease**: power1.inOut for gentle moves, power2.out to settle on a punchline, power3.out for snappy comedy,
  sine.inOut for dreamy, expo.inOut for drama, none for a steady crawl.
- Angle comes from the story: a low camera makes someone powerful or scary, a high camera makes someone small or
  trapped. Choose the framing and pose that sell it.

## Motion blueprint

- **tracks**: per actor, 1-4 timed keys ({t, action, optional x/z for where they end up}). Start at t = 0 with the pose
  of the first frame. Actions are physical, visible and specific ("slams the ladle on the counter", "tiptoes to the
  door, glancing back"), timed inside the shot's length. Comedy: anticipation (the wind-up) → action → hold (the
  reaction). Give big actions room: a jump needs ~1 s, a double-take ~0.6 s.
- Talking shots: the speaker's mouth is handled by lip-sync, so their track is about head, hands and body.
- **environment**: background life (steam, curtains, a ceiling fan, traffic outside, falling leaves), at most two.
- **picture**: one vivid line a painter can draw: who, where in the frame, the pose, the expression, the key prop, and
  the light ("Raju, left third, crouched behind the sofa with the remote hidden behind his back, wide guilty eyes,
  warm lamp light"). No camera jargon here, no story summary.
- **sfx**: the sounds this shot makes, concrete and synced ("remote clatters on tiles, a guilty gulp").
