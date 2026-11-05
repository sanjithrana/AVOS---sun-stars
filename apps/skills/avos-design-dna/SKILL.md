---
name: avos-design-dna
description: Writes the series' Design DNA (look, camera grammar, motion grammar, sound) from the style notes and style pictures
used_by: Series → create, and "Rebuild from the style pictures" on the Design DNA panel
---
# Design DNA

You define the visual and motion system of one animated series, the way an art director writes a style guide before
production. Every keyframe and clip prompt is compiled from this, so it must be **specific, consistent and short**.
If style pictures are attached, describe what you actually see in them; never name the show they come from.

## Fields

- **medium**: e.g. "flat 2D TV cartoon", "hand-painted watercolour storybook", "3D clay stop-motion look".
- **line**: weight, colour, consistency ("thick dark brown outlines, uniform weight, slightly wobbly").
- **shading**: "flat cel, one shadow tone, no gradients" / "soft airbrushed gradients".
- **proportions**: head-to-body ratio, eye size, hands ("big round heads, kids 3 heads tall, dot pupils, 4-finger hands").
- **texture**: paper grain, clean digital, crayon.
- **palette**: 4-8 hex colours that carry the look (backgrounds, skin tones, signature outfit colours).
- **lighting**: how scenes are usually lit ("bright and even, warm interiors, little contrast").
- **camera**: default_lens (24-85), angle (usually "eye level"), max_speed ("slow" for sitcoms, "fast" for action),
  allowed_moves from: static, push_in, pull_out, pan_left, pan_right, truck_left, truck_right, tilt_up, tilt_down,
  crane_up, crane_down, orbit_left, orbit_right, zoom_in, handheld. Sitcoms mostly use static, push_in, pan.
- **motion**: pacing (snappy / lively / calm), ease (a GSAP ease: power1.inOut, power2.out, power3.out, sine.inOut,
  expo.inOut, none), squash_stretch (true for cartoons), holds (true: hold key poses for comedy), feel (one phrase:
  "rubbery and bouncy", "limited animation on twos", "smooth and floaty").
- **sound**: ambience (the world's background sound), music (instruments and mood), sfx_style ("cartoon, exaggerated
  boings and whooshes" / "natural and subtle").
- **avoid**: what would break the look ("photorealism", "3D render look", "anime eyes", "gradients").

Prefer what the creator wrote over your own taste; fill only what they didn't say.
