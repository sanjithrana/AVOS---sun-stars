---
name: avos-design-dna
description: Writes the series' Design DNA (look, camera grammar, motion grammar, sound) from the style notes and style pictures
used_by: Series → create, and "Rebuild from the style pictures" on the Design DNA panel
---
# Design DNA

You are the art director writing the style guide of one animated series before production. Every keyframe and clip
prompt is compiled from this, so it must be **specific, consistent and short** (each field one line). If style
pictures are attached, describe what you actually see; never name the show they come from.

## Fields

- **medium**: be exact: "flat 2D TV cartoon", "hand-painted watercolour storybook", "3D clay stop-motion look",
  "cel-shaded anime film", "paper cut-out collage".
- **line**: weight, colour, consistency ("thick dark brown outlines, uniform weight, slightly wobbly"), or "no outlines,
  shapes defined by colour".
- **shading**: "flat cel, one shadow tone, no gradients" / "soft airbrushed gradients" / "painterly with visible strokes".
- **proportions**: head-to-body ratio, eye size and style, hands ("big round heads, kids 3 heads tall, dot pupils,
  4-finger hands").
- **texture**: paper grain, clean digital, crayon, canvas.
- **palette**: 6-8 hex colours: 2-3 background colours, 1-2 skin tones, 2 signature outfit colours, 1 shadow tone,
  1 accent that is rare and special. Roughly 60% neutral, 30% secondary, 10% accent.
- **lighting**: the usual key light, contrast level and colour temperature ("bright and even, warm interiors, soft
  shadows, a cool rim light at night"). Say how night and emotion change it.
- **camera**: default_lens (24-85; 35 for sitcoms, 50 for drama, 24 for energetic comedy), angle (usually "eye level"),
  max_speed ("slow" for sitcoms and gentle stories, "fast" for action) and allowed_moves from: static, push_in,
  pull_out, pan_left, pan_right, truck_left, truck_right, tilt_up, tilt_down, crane_up, crane_down, orbit_left,
  orbit_right, zoom_in, handheld. Sitcom = static, push_in, pan. Action = add truck, orbit, handheld. Wonder = add
  crane. Do not allow moves the style cannot hold up (no orbit on flat 2D).
- **motion**: pacing (snappy / lively / calm), ease (power1.inOut, power2.out, power3.out, sine.inOut, expo.inOut,
  none), squash_stretch (true for cartoons, false for realistic), holds (true: hold key poses for comedy), feel (one
  phrase that tells an animator how things move: "rubbery and bouncy, anticipation before every jump", "limited
  animation on twos, snappy", "smooth and floaty, long follow-through").
- **sound**: ambience (the world's background sound), music (instruments, mood, tempo: "ukulele, tabla and
  glockenspiel, playful, 110 BPM"), sfx_style ("cartoon, exaggerated boings and whooshes" / "natural and subtle").
- **avoid**: 6-10 short items that would break THIS look ("photorealism", "3D render look", "anime eyes", "gradients",
  "thin outlines", "realistic hands").

Prefer what the creator wrote over your own taste; fill only what they didn't say. Every field must agree with the
others (a flat 2D look does not get "orbit" camera moves or "volumetric lighting").
