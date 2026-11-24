# Checklist (look at the stills, fix before the full render)

1. **Frame 0 is a poster**: the hero, the hook prop and an expressive face, big and clear.
2. **Every sentence is on screen**, in order; each reaction lands on its word (0-3 frames before it).
3. **Faces in frame**: no head cut by the edge; the stickman isn't hidden behind a counter, board or bubble.
4. **Continuity**: a cut onion stays cut, the same character keeps the same shirt and hat.
5. **Zoom circles and labels** sit inside the frame (draw them with `s.screen(...)`), never cropped.
6. **Captions** (y ≈ 1440) don't cover the face or the key prop; nothing important below y ≈ 1570 or within 100 px of the sides.
7. **Something always moves**: idle bob + blinks (`CS.alive`), drifting clouds, twinkling stars, waves.
8. **Sound**: the voice is clear; every visible action has an effect; the music stops before the punchline.
9. **The file**: 1080x1920, 30 fps, voice length + tail, with sound.
