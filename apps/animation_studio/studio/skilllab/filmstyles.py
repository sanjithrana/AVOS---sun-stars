"""The 66 Lemo-Opuscar film styles, compressed into prompt material AVOS can use.

Generated from skills/lemo-opuscar/styles/*/STYLE.md by tools/extract_styles.py. Do not hand-edit: regenerate.

Each record is what a picture model can actually act on -- the look, what the style is NOT, its materials,
colour logic, motion and camera -- compressed from a twelve-page style prompt to a few hundred characters,
because Pollinations cuts a prompt at 900 characters and FLUX at about 256 tokens.

The upstream 'References' lines are deliberately left out. They name real artists, films and buildings as
grammar, and the upstream itself says never to copy a poster layout, a real building, a character, a typeface
design or a melody. Those names have no place in a prompt sent to a picture model, so they are not here.
"""
from __future__ import annotations

STYLES: dict[str, dict] = {
 "archive-lighttable": {
  "name": "Archive Light Table",
  "cat": "Evidence Films",
  "line": "The telegram said 57 seconds; under a loupe, the Wrights' glass negatives and the archive say 59.",
  "uses": [
   "Brand history",
   "Archive stories",
   "Museums"
  ],
  "quote": "Real archive objects (glass negatives, slides, letters, telegrams, clippings, drawings) lie on a cool, backlit light table. A loupe comes down on one of them, and inside the glass the object comes alive: a negative turns positive, a line of type lights up, a number lifts off the page, a photograph o",
  "essence": "The objects are real: scans of public-domain or licensed archive items, at their true proportions, with their real damage (broken corners, emulsion edges, folds, pencil marks). Nothing in them is drawn or… Light comes from below: the table glows a near-white cool grey; film and glass transmit it, paper glows warm at its edges, opaque things read darker than the table",
  "nots": "stand a generated image in for an archive object. Keep a FACTS.md in the project folder (claim, source URL, quoted wording, or how a figure was derived) and deliver it with the film.",
  "material": [
   "The photograph space: after the push the lens stops being a lens. A photo gains depth from a ground-plane nearness map (zero at the horizon, linear in the row below it),…",
   "Sampling: all texture reads inside the branching lens code use explicit gradients (textureGrad), otherwise quads that cross a branch pick a wrong mip level and leave…",
   "Post: a light vignette and fine moving grain (heavier inside photographs). No film damage, no sepia, no halftone"
  ],
  "colour": [
   "Neutral ground: the light table (near-white, cool) and the archive's own tones (silver greys, paper tans). Do not regrade the archive into a colour scheme",
   "One signal colour (e.g. a signal orange) for marks, readings, anchors and the verdict; never as a fill behind pictures, never for decoration",
   "Text is ink (near-black) on light areas and paper-white on dark caption plates; choose the contrast by the ground, never colour on colour"
  ],
  "motion": [
   "The camera glides across the table, slows to let the loupe land, then pushes. Speed lives in the glides and pushes; holds are for reading",
   "What never moves: the archive's own content outside a photograph space, and the table itself"
  ],
  "camera": [],
  "sound": [
   "Ambience: the light table's ballast hum (100 Hz and harmonics), starter clicks, room tone. Inside a photograph the hum gives way to that…",
   "Foley: the loupe on glass (a clack with a high ring), paper sweeps for glides and lit lines, ticks for scales and counters, a pen stroke…"
  ]
 },
 "art-deco": {
  "name": "Art Deco",
  "cat": "Graphic & Type",
  "line": "A grand hotel, 1930: a bellboy races lifts and revolving doors to deliver one letter before midnight.",
  "uses": [
   "Luxury & hospitality",
   "Galas",
   "Invitations"
  ],
  "quote": "Black lacquer, engraved gold line and airbrushed geometry: a 1930s poster that moves. Every composition has a centre axis, transitions open or close along it, and light arrives as bulbs switching on one by one.",
  "essence": "A world built from gold keylines on warm black, filled with airbrushed hard-edged volumes, organised around one vertical axis. Ornament is the picture: sunbursts are backgrounds, stepped arches are frames, a dial is a progress bar, a bulb marquee is a reveal. Motion is mechanical and symmetrical: things unfold from the centre, doors split along the seam, lights switch on in counted order. Native register: glamour…",
  "nots": "a gold-foil slideshow (things move and have volume), not Art Nouveau (no whiplash curves, no flowers), not a flat vector poster (volumes are airbrushed and rimmed), not a 60s spy title (no silhouettes on flat colour).",
  "material": [
   "Ground: warm lacquer black, never neutral grey-black; a night sky may drift toward a deep emerald near the horizon",
   "Gold is a banded metal gradient (dark – light – hot – light – dark); animate its sheen offset for a light sweep",
   "Volumes: hard edge + airbrush (airbrush): a directional gradient from shade to light inside the shape, one consistent light direction (upper left by default), a thin…",
   "Motifs (sunburst, stepped arch / ziggurat, fish-scale, chevrons, fan, four-point sparkle, speed lines, clock face, dial) are structural (a background, a frame, a…"
  ],
  "colour": [
   "Three constants: warm black ground, gold line and metal, ivory for paper, gloves, light and type",
   "One saturated accent reserved for the protagonist (or the one object the story follows). It is the only large saturated area, so the eye finds it in any wide…",
   "The one-colour exception: any single element can be drawn in its own colour through the same fill + keyline + glow (color option) while everything else stays…"
  ],
  "motion": [
   "Draw-on follows the music: a gold line grows at the speed of the phrase under it and lands on the hit",
   "Bulbs have an ignition overshoot (~1.6× flash settling in ~0.18 s) and a relay \"chunk\"; once a sign is lit, a fast chase may run across it",
   "Mechanical easing: doors, dials and hands move with firm ease-in-out and a small settle, like machinery; nothing floats"
  ],
  "camera": [],
  "sound": [
   "Symphonic jazz of the 1920s–30s, not a 60s big band. Options: stride or concert piano, clarinet (trill; a glissando by time-varying…",
   "Rhythm families to choose from: foxtrot, Charleston, tango, a slow torch-song ballad, a fanfare in the manner of a newsreel"
  ]
 },
 "ascii-crt": {
  "name": "ASCII / CRT Terminal",
  "cat": "Graphic & Type",
  "line": "A moon-base AI wakes after forty years to a signal from Earth, and replies by drawing “home” in characters.",
  "uses": [
   "Developer tools",
   "Sci-fi",
   "Tech brands"
  ],
  "quote": "Everything on screen is a real character on a monospace grid, lit by the phosphor of an old monochrome CRT.",
  "essence": "A single monochrome terminal screen: P3 amber (or P1 green) phosphor glowing on dark glass, curved at the edges, with scanlines. Every image, including title, landscape, face, room and subtitles, is made of real glyphs placed on a character grid and chosen by ink density. The film has one camera, the screen itself. It moves only by changing the font size of the grid: bigger characters push in, smaller characters…",
  "nots": "a hacker-movie green rain, not a pixel-art game (no sprites, no free pixels), not a sci-fi HUD (no vector lines, no free-floating panels).",
  "material": [
   "Grids: column count per shot (title ~20, terminal 80, picture 200+); a push-in can go until one cell holds a sub-grid of its own",
   "Glow: multi-level bloom plus a faint halo"
  ],
  "colour": [
   "One phosphor carries everything: amber, green or white, in its own brightness ramp. No second hue for decoration",
   "At most one soft second colour, used for one thing only (the emotional object), switched on at a single moment, on a downbeat, and never taken back casually",
   "Examples: amber screen with an ice blue-white for something far away; green screen with a warm pink for a living thing; white P4 screen with a pale gold for a…"
  ],
  "motion": [
   "Characters never move off-grid, except in a declared transformation moment. Typing, scrolling and counters jump from cell to cell. A roller flips digits…",
   "Only three things move continuously: grid scale (the camera), CRT physics, and particles in a transformation",
   "Typing speed is performance: machine output is even and fast (~10–40 ms/char); dramatic lines slow to note values of the score; human typing is hand-timed,…"
  ],
  "camera": [],
  "sound": [
   "Music: an original analog-synth score, rendered in code (numpy / numba): PolyBLEP saw and square oscillators, a resonant 4-pole ladder…",
   "Technique options: grow a single arpeggio as an image forms; hold the only major chord for one moment; drop everything, reverb tails…"
  ]
 },
 "backrooms": {
  "name": "Liminal Found Footage",
  "cat": "Cinema & Eras",
  "line": "A new night-shift hire films their first night in an endless yellow office, following the rules on the wall.",
  "uses": [
   "Horror",
   "Mystery & ARG",
   "Game teasers"
  ],
  "quote": "Camcorder tapes recovered from empty, endless, fluorescent-lit spaces. Rules instead of monsters.",
  "essence": "One first-person camcorder recording (1990s VHS, 4:3), handheld, continuous An empty, familiar-but-wrong interior that repeats: an office, a hotel floor, a school, a mall, a parking level, a hospital wing. Humming fluorescent light, no people",
  "nots": "a horror film (no monster close-ups, no gore, no jump scares, no score stings), not an ASCII/CRT terminal piece (the artefacts are tape and lens, not phosphor and scanlines), not a ruin (clean is part of the style).",
  "material": [
   "Frame: 4:3 pillarboxed in 1920×1080. Render 3D at low resolution (e.g. 720×540) and let the VHS pass upscale; low resolution hides CG cleanliness",
   "Space: axis-aligned partitions on a grid with random gaps and stubs, pillars, a drop ceiling of tiles with recessed light panels at regular intervals. A hand-authored…",
   "Restrained decay: tide-marks at the foot of some walls, a discoloured band under the ceiling, rare peeling seams, a few yellowed or missing tiles, dead insects in…",
   "Printed matter: office laser-print on yellowed paper, condensed sans headers, form numbers and revisions, numbered rules, a polite closing line from \"Management\". Pinned…"
  ],
  "colour": [
   "One dominant sickly hue from the location's materials (mustard wallpaper, institutional green, hospital blue, beige laminate), with a darker trim and a mottled…",
   "Exactly one saturated colour: a signal such as a red alarm lamp, a green emergency sign, an amber warning light. It is the only thing that blooms (drive its…",
   "White balance drifts; colour is never graded clean"
  ],
  "motion": [
   "One continuous handheld take. Cuts happen only where the tape breaks: power-on roll-in, tracking tear, REC off",
   "Looking down shows only shoe toes and floor, never legs",
   "Lights flicker as short blackouts (~0.1 s); auto-exposure catches up with a lag (~0.45 s) and gain noise pumps"
  ],
  "camera": [],
  "sound": [
   "No score. Only what the tape would have recorded. Music exists only inside the world (hold music, a radio through walls, a tinny PA…",
   "Fluorescent bed: 120 Hz (or 100 Hz) + harmonics, a buzzy band-passed component, a faint ballast whine, bad-tube bursts; gated by the same…"
  ]
 },
 "blueprint": {
  "name": "Blueprint",
  "cat": "Graphic & Type",
  "line": "An inventor's blueprint draws, explodes and assembles a cloud-catching machine, and its revision cloud starts to rain.",
  "uses": [
   "Engineering",
   "Hardware launches",
   "Tech explainers"
  ],
  "quote": "Engineering drawings that come alive on a sheet of cyanotype paper: white technical line work on Prussian blue, drawn in drafting order, with annotations that move.",
  "essence": "The whole film happens on one sheet of blueprint paper lying on a dark drafting table. The camera moves over it like an eye reading a drawing White line work on uneven Prussian blue: centre lines, outlines, hatching, dimension lines, leader lines with numbered balloons, a title block, a notes column",
  "nots": "Hologram HUD (no glowing wireframe, no 3D orbit), not Whiteboard (no marker on white), not Copperplate Engraving (no burin tonal hatching as the whole look).",
  "material": [
   "Occlusion by painter's order: every solid is filled with \"paper\" before its outline is stroked. Oblique extrusion: stroke the outline at N depth steps at 2× width, then…",
   "Hatching (fine-line shading) for sections, soil, weights, at 45°, spacing 8–14 units",
   "Cyanotype and water: a drop blooms deeper blue with a pale tide line; white lines inside the stain go soft; ink signatures bleed",
   "The one real thing (optional, at most once): a drawing symbol that leaves the drawing language gets soft volume, one gradient across its whole shape, glow, and a shadow…"
  ],
  "colour": [
   "Blue and white only. The blue varies in value (coating, stains, folds); the white varies in weight and softness, never in hue",
   "One non-blue colour, used exactly once: a rubber-stamp ink (red is classic; a green APPROVED or black VOID work too). It carries the verdict",
   "The \"real\" object at the climax may carry light (white glow, soft value), not a new hue"
  ],
  "motion": [
   "Draw-on truncated by arc length with a glowing nib at the head; items staggered within a layer; each layer starts on a beat",
   "Mechanisms step on the grid like an escapement: a gear advances one tooth per subdivision with a short ease-out; meshing phases computed so teeth really…"
  ],
  "camera": [],
  "sound": [
   "Contrapuntal, mechanical music: harpsichord, bassoon, strings spiccato, harp, celesta, music box, clavichord, a small wind ensemble.…",
   "Options for the arc (in any order, use what the story needs): instruments dropping out with a written-out ritardando into true silence; a…"
  ]
 },
 "brick-toy": {
  "name": "Brick Toy",
  "cat": "Materials & 3D",
  "line": "A brick astronaut builds a rocket from spare parts and flies to a brick moon.",
  "uses": [
   "Toys & kids",
   "Product builds",
   "Space"
  ],
  "quote": "Stop-motion toy-brick films shot like macro photography on a real desk: a world built from interlocking plastic bricks with round studs, animated a pose at a time.",
  "essence": "A brick world on a real surface (a wooden desk, a kitchen table, a windowsill), shot with a macro lens and animated in stop-motion. The charm is the tension between the toy world and the real room.",
  "nots": "a low-poly isometric island (no flat-shaded facets, no floating diorama), not a clay or felt stop-motion (no deformation: bricks are rigid), not a clean product render of a toy (this world is played with, handled, knocked over).",
  "material": [
   "Plastic: ABS with strong clearcoat (~0.85, clearcoat roughness ~0.07); a roughness map with faint fingerprints and scratches (base ~0.17, scratches up to ~0.65); a bevel…",
   "Ambient occlusion is mandatory: GTAO (radius a few studs) darkens seams between stacked bricks, stud bases and contact points. Without it bricks look pasted on",
   "Supersample 2× (render 3840×2160, deliver 1080p): thin stud edges and bevel highlights shimmer without it",
   "Lens: physical depth of field (CoC ∝ |1/focus − 1/z|). Scale aperture with shot size: widest for close-ups, less for mediums, least for a wide (too much blurs the hero…"
  ],
  "colour": [
   "A toy palette: a handful of saturated brick primaries plus white, black, greys, tan. Each built object has one dominant colour and at most one or two trim…",
   "The real world stays natural and muted: wood, paper, ceramic, daylight. The saturated colour belongs to the toys, which makes them pop against the room",
   "Whites must read white: grade slightly cool so white bricks don't go cream from the room bounce; soft contrast, saturation lifted ~10 %"
  ],
  "motion": [
   "Characters act with big readable poses held for several drawings: a V of arms for pride, arms flung up for alarm, a bowed head for sadness, a hop for joy. Walk…",
   "Collapses and falls use real rigid-body physics: tip about the base edge, then independent bodies with gravity (a lower-than-true value reads better at this…",
   "Tiny imperfections are allowed. Bricks never stretch, squash or morph"
  ],
  "camera": [],
  "sound": [
   "Instruments: small, acoustic, playful (glockenspiel, toy piano, pizzicato, ukulele, whistling, claps, melodica); a brass or orchestral…",
   "Foley (synthesizable): plastic creak before a failure, tiny plastic footsteps, a crash of many clacks, a brick click (short transient +…"
  ]
 },
 "briefing-board": {
  "name": "Engineering Briefing Board",
  "cat": "Evidence Films",
  "line": "Four bridge types are tested on one briefing wall, and the ship that must pass under picks the winner.",
  "uses": [
   "Engineering",
   "Option comparisons",
   "Briefings"
  ],
  "quote": "One real whiteboard wall, filmed: window light on enamel, ghosts of erased marker, frame and tray. Cut-out photographs of real things land on it with weight; tags, magnets, a ruler and stamps are pinned to it; marker ink draws itself in three colours with fixed meanings. The camera rides the lines f",
  "essence": "1. A physical board in a room: enamel, window falloff, a sliding reflection, ghosts of earlier work, frame and tray. 2. Real things on it: cut-out photographs of the real objects, a few millimetres off the board, shadowed by one window, parallaxing. They are evidence: never a generated image presented as a real object. 3. Ink that means something: graphite for names and rules, blue for water and measurement, red…",
  "nots": "Whiteboard Explainer (a hand drawing line art on a flat page): the board is a filmed object, subjects are photographs. Not Data Storytelling: comparisons are dimension lines in real units beside real objects. Not a keynote: no headers, centred bullets, page turns.",
  "material": [
   "Board (z 0): procedural enamel, wiped ghost strokes, smudges, a window falloff, a sliding diagonal reflection; the frame shadows a warm grey wall",
   "Secondary layer (only where the camera never goes before the end): the photos as pinned prints, a source card, sums on sticky notes, a small sketch. Texture and proof…",
   "Camera: parallax by height, sub-frame motion blur (180° shutter), light grain. Only subtitles are screen-space"
  ],
  "colour": [
   "Ground: the enamel and its light falloff; the wall around is neutral warm grey",
   "Red is rare: two or three red marks per frame at most, never on a red object. Full colour belongs to the photographs; props stay neutral; a red magnet is a…"
  ],
  "motion": [
   "Weight: prints are lowered from the camera side, land, bounce and settle as the shadow tightens; magnets clack on to pin them; tags swing; removed magnets pop…",
   "Blurred in motion, sharp where words are read. Every 1–2 beats something lands, draws or swings; only silences and judgement holds go still",
   "Ink draws at the speed of a hand; dimension lines land with an arrowhead tap"
  ],
  "camera": [],
  "sound": [
   "Room: an air-conditioning bed and traffic through the window, about 20 dB under the voice — audible, not a hiss; silences keep only this",
   "Foley: felt-tip squeaks scaled to stroke length, nib taps, magnet clacks (a pitch per magnet in a row), suction pops, print landings (board…"
  ]
 },
 "caption-news": {
  "name": "Caption News",
  "cat": "Edit & Documentary",
  "line": "America lost 1.3 million bee colonies, yet the count rose 6 %: a news short that works with the sound off.",
  "uses": [
   "Social news",
   "Report explainers",
   "Data shorts"
  ],
  "quote": "Social-video news that reads with the sound off. Real footage, photos and the source document are the ground; huge captions are the lead actor, slammed in a chunk at a time with one keyword on a yellow block. Hard cuts on a music grid, numbers that roll, a source tag that slides in whenever a figure",
  "essence": "1. Sound-off first. Every beat must be understood from the picture and the captions alone; the voice adds pace, not information. 2. The caption is the shot. One Chinese line, set huge, slammed in two or three chunks, one keyword in a yellow block; one English line under it. The footage is chosen to sit under the line. 3. Evidence on screen. Each number arrives with its source: a source tag slides in; key figures are…",
  "nots": "Data Storytelling (charts are short inserts between footage, never the whole film, never a dashboard). Not a TV news package (no anchor, no lower-third ticker, no studio, no scrolling crawl). Not a keynote: no headers, no centred title-and-bullets, no page turns.",
  "material": [
   "Wikimedia Commons (video and photos): read the licence on each file page. Fine: CC0, public domain, CC BY (credit author, title, licence on screen and in CREDITS). Not…",
   "U.S. federal agencies (USDA, USGS, NASA, NOAA, NARA): works of federal employees are public domain; check that the page does not credit a contractor or a third party.…",
   "Internet Archive: only items whose own page states public domain or a CC0/CC BY licence; U.S. works published before 1931 are public domain",
   "Library of Congress: read each item's rights statement; \"no known restrictions\" is not enough"
  ],
  "colour": [
   ""
  ],
  "motion": [
   ""
  ],
  "camera": [],
  "sound": []
 },
 "cel-anime-80s": {
  "name": "80s Cel Anime",
  "cat": "Cartoon & Anime",
  "line": "A courier girl rides through a rain-soaked neon city to deliver a tape before the dawn launch.",
  "uses": [
   "Music videos",
   "Game trailers",
   "Nostalgia"
  ],
  "quote": "Hand-painted cel animation from the golden age of Japanese OVAs, re-created in code: flat two-tone cels over airbrushed backgrounds, backlit neon, limited-animation timing, played back as a late-80s videotape on a CRT television.",
  "essence": "Background painting: soft airbrushed gradients, glowing windows, wet reflections; painted once at load (colour + emissive pair), then only slid Light: backlit cel (透過光): signs, lamps, title letters glowing through the frame; flares, halation",
  "nots": "moe anime (round eyes, giant irises, hatched blush), not vector clip-art (uniform black lines, gradients in shapes), not a film-print pastiche (no gate weave or scratches: this is tape).",
  "material": [
   "Cel rendering. Fill, then a hard shadow crescent, then a hard highlight crescent, then the coloured outline. No gradients inside a cel shape (exception: one \"harmony\"…",
   "People the 80s way. Construct the head (sphere + jaw): long egg-shaped face, soft-point chin, far eye foreshortened with a cheekbone turn in 3/4. Almond eyes near the…",
   "Backgrounds. Painted once at load: sky gradients, airbrushed clouds with lit undersides, buildings or landscape with painted light sources, and always a matching…",
   "Light and lens. Bloom strongly from the emissive canvas, weakly from the colour canvas above ~0.9; tint the widest bloom red-orange (halation). Flares: star-burst,…"
  ],
  "colour": [
   "Painted plates carry gradients and atmosphere; cels are flat, few-colour, saturated. Each time of day gets its own colour model, never a filter over the frame",
   "The protagonist has one accent colour that pops in every lighting set. Line colours are dark versions of their fill",
   "Skin gets its own colour in every set; multiplying daylight skin by a tint turns faces pink under neon"
  ],
  "motion": [
   "Move light, not drawings: coloured bands sweeping across a held cel (source-atop)",
   "Impact frames: 2 frames of an inverted or monochrome silhouette over radial lines, then the result",
   "Hold the peak: a painted still with a slow pan, only cycles moving"
  ],
  "camera": [],
  "sound": [
   "Instruments (city pop, synth funk, anime-opening pop): saxophone or synth-brass lead, FM electric piano with a bell transient, slap bass,…",
   "Techniques, as options: band-pass the score to cassette/AM when a diegetic source plays, then open it; a brass hit on a title; a drum fill…"
  ]
 },
 "chalkboard": {
  "name": "Chalkboard",
  "cat": "Hand-drawn & Painting",
  "line": "Chalk writes a popular claim about two characters, wipes it, and traces 射 back three thousand years.",
  "uses": [
   "Word origins",
   "Myth-busting",
   "Lessons"
  ],
  "quote": "A real classroom blackboard on which chalk writes itself, stroke by stroke in true stroke order, with no hand, no chalk stick and no eraser in sight. One idea is taught the way a teacher does it: write what people think, wipe it with one pass, write what is true in the same place.",
  "essence": "Not Whiteboard Explainer: that style is a bright glossy board, coloured markers, floating marker props and magnets, ghost marks of old lessons, and a camera travelling across a knowledge map of many regions to explain how something works. Chalkboard is a dark matte slate with nothing floating in front of it, kept clean, one question per board, the camera facing it flat; it advances by writing a claim, wiping it and…",
  "nots": "Whiteboard Explainer: that style is a bright glossy board, coloured markers, floating marker props and magnets, ghost marks of old lessons, and a camera travelling across a knowledge map of many regions to explain how something works. Chalkboard is a dark matte slate with nothing floating in front o",
  "material": [
   "Each stroke is baked once into a board-space coverage sprite (coverage, arc length, lateral position). A partial stroke reveals pixels up to the current arc length with…",
   "Chalk edges are firm; loose powder only at the lift-off of a stroke (two to five grains). Never sugar the board",
   "Writing strokes carry a width profile per stroke type (start bump, corner bumps, taper for 撇 / 提, foot for 捺, quick lift for hooks) and a pressure profile (heavier at…",
   "Board, panels, frame, tray, clock and wall are baked once in world units; the slate grain is a periodic tile drawn in world space (soft-light) only when the camera is…"
  ],
  "colour": [
   "Ground: deep ink green slate, wood frame, warm white wall and a coloured dado if the room is seen",
   "White chalk carries every structure: characters, lines, labels, arrows",
   "The accent chalk (example: orange) is reserved for the one component the lesson tracks; it never decorates and never draws arrows or underlines that are not…"
  ],
  "motion": [
   "Chalk speed, measured on our demo: a big character takes about 0.1 s per stroke including the air between strokes (a ten-stroke character about 1 s), labels…",
   "When reading time and chalk speed pinch in a short film, change the words, not the hand. Ways that work (choose per film): fewer and shorter blocks on the…",
   "Camera eases in and out (cubic), never bounces except a whip landing"
  ],
  "camera": [],
  "sound": [
   "Voice first: it is the loudest element; music sits 15–18 dB under it and comes up only in the pauses",
   "Foley: real chalk recordings cut into grains, one grain chain per stroke, level from stroke size; a light knock on landings; the accent…"
  ]
 },
 "circuit-board": {
  "name": "Circuit Board",
  "cat": "Information & Keynote",
  "line": "Rivers become copper traces as current runs 2,080 km from a dam to a phone charger.",
  "uses": [
   "Energy",
   "Supply chains",
   "Devices"
  ],
  "quote": "The subject is drawn as a printed circuit board seen from straight above: the world is copper under green solder mask, routes are traces, places are pads, words are white silkscreen, and what flows (power, water, signals, goods) is light running along the copper. The camera rides that light and jump",
  "essence": "A top-down board in every frame: copper pour with clearances cut around everything, traces with 0/45/90° runs and mitred corners, gold pads and vias, white monoline silkscreen. Nothing is drawn in perspective Information moves as light on copper. The way the light moves is the explanation: a pulse, a stream, a rocking dash, a pad that flashes",
  "nots": "the library's Engineering Briefing Board (a whiteboard on which real photos are pinned and written over in marker): here there are no photos and no handwriting; the subject itself becomes copper, pads and silkscreen, and information travels as light along the traces. Not a blueprint (no white-on-blu",
  "material": [
   "A top-down board in every frame: copper pour with clearances cut around everything, traces with 0/45/90° runs and mitred corners, gold pads and vias, white monoline…",
   "Information moves as light on copper. The way the light moves is the explanation: a pulse, a stream, a rocking dash, a pad that flashes",
   "Two scales on one board: whole regions (a map, a supply chain, a city) are drawn in the same language as single components, and the camera passes between them without…"
  ],
  "colour": [
   "Ground: green solder mask in three values (dark laminate, mid pour, light rim/trace). The film is green; never recolour the mask per scene",
   "Metal: gold for pads and vias, one bare-copper accent at most",
   "Ink: one off-white for all silkscreen"
  ],
  "motion": [
   "Kinds of current, told apart only by how the light moves:",
   "AC / alternating: short dashes rocking back and forth along the trace (a slowed mains frequency) over a faint energised line",
   "DC / one-way: a continuous lit stream behind a travelling head, with slow streaks inside and an afterglow that dims slowly behind the head"
  ],
  "camera": [],
  "sound": []
 },
 "city-symphony": {
  "name": "Time-lapse Symphony",
  "cat": "Edit & Documentary",
  "line": "One day in New York in time-lapse: rivers of light, a grid on the sixteenths, 1899 beside today.",
  "uses": [
   "City films",
   "Music montages",
   "Openers"
  ],
  "quote": "A city film cut like a piece of minimalist music: time-lapse turns traffic, crowds and clouds into rivers of light, the cuts get denser with the score's subdivisions, one thing is slowed almost to a stop, and the film ends on a hard cut to black on a downbeat. No narrator. The music carries it.",
  "essence": "An edit style. The picture is real footage of a place (time-lapse, hyperlapse, aerials, slow motion, archive film, photographs). The style lives in how time is bent and where the cuts fall, not in a drawn look Machines fast, people slow. Cars, trains, clouds and light are sped up until they become lines; the one slowed moment is something fragile (a soap bubble, steam, a flag, a flock), and people appear as crowds,…",
  "nots": "",
  "material": [
   "Never generated images; never restored, colourised or speed-corrected archive copies; never YouTube mirrors of archive films"
  ],
  "colour": [
   ""
  ],
  "motion": [
   "Speed is the main instrument. Shot speeds run from 0.3× to 75×; every speed above 1× uses frame blending (a 360° shutter): each output frame averages the…"
  ],
  "camera": [
   "Density follows the score. The editor never cuts faster than the current subdivision, and the slowest picture sits under the place where the…",
   "Counterpoint split: two halves, archive left, today right, the same kind of place or shape; the gutter grows from the centre in 8 frames"
  ],
  "sound": [
   "Music only. No narrator, no source sound (the footage soundtracks are other people's music), no sound effects. A narrator would turn…"
  ]
 },
 "countdown": {
  "name": "Live Countdown Split-screen",
  "cat": "Edit & Documentary",
  "line": "The last minute of the Artemis II launch, uncut: one cell opens to nine, and they merge into one at ignition.",
  "uses": [
   "Launches",
   "Countdowns",
   "Live events"
  ],
  "quote": "An edit style, not a look. Real footage of one event with a known zero (a launch, a verdict, a final whistle, polls closing), shown in real time: screen time equals event time, a clock ticks every second, and the screen splits into more and more cells as the moment nears, every cell showing the same",
  "essence": "1. Real time. One continuous stretch of the event, never cut, never re-ordered, never sped up. Slow-motion sources are played back at real speed. The clock and the picture can be checked against each other at any frame. 2. The clock is the lead. It ticks every whole second (sound and a falling digit), it says who is in control, and it changes state at zero. 3. Cells show the same second. Every video cell is synced…",
  "nots": "a montage (time jumps), not a security wall (the layout never moves), not a flashback structure (real time cannot go back), not a slide deck (cells that don't follow events, text filling the cells, centred titles with page turns).",
  "material": [
   "Data drawn by us: checklists, bars, a flight or process profile, a second countdown to the next milestone. Every number comes from an official source (§10)",
   "Burned-in text in the sources (broadcast bugs, camera IDs, timers, tracker readouts) is cropped by a per-shot usable region, or blurred out (ffmpeg delogo) after it has…"
  ],
  "colour": [
   "Orange means \"now / synced / done\". Grey means \"pending / not synced\". Nothing else is coloured; colour belongs to the footage."
  ],
  "motion": [
   "Swaps (one source replaces another in the same rectangle) wipe in from the left. Hard cuts only between full-screen sources",
   "Never: slow push-ins on video to fake motion, page-turn transitions, centred pop-up words, speed ramps"
  ],
  "camera": [],
  "sound": [
   "Changing the music (e.g. a Suno track): never move the clock or the cuts; choose or stretch a track so a downbeat lands exactly on zero and…"
  ]
 },
 "crayon-book": {
  "name": "Crayon Picture Book",
  "cat": "Hand-drawn & Painting",
  "line": "The moon can't sleep, so a little girl climbs onto the roof to sing it a lullaby.",
  "uses": [
   "Picture books",
   "Bedtime stories",
   "Kids' learning"
  ],
  "quote": "A picture-book page drawn live in wax crayon on toothy paper, with a watercolour wash that reveals what the crayon was hiding.",
  "essence": "A children's picture book page being drawn while you watch: wax crayon on warm off-white paper, a limited box of crayons, child-logic perspective, colour that spills past the outline, and every line gently boiling because each frame is a fresh drawing. The tone is picture-book storytelling: tender, unhurried, music-led, a few lines of narration that are literally the words printed on the page. Any topic becomes one…",
  "nots": "\"cute vector art with a crayon filter\": the look comes from material physics (wax sticks only to the peaks of the paper tooth, pressure decides how much of the tooth it reaches, watercolour is repelled by wax). Not a whiteboard explainer (no marker, no hand), not a watercolour painting (the wash is ",
  "material": [
   "Occlusion: a front part erases what is behind it inside its outline; characters \"keep the paper white\" behind them (a knock-out that restores paper and resets wax), the…"
  ],
  "colour": [
   "A box of about a dozen crayons, never more. Outlines in one dark colour (indigo, dark brown, plum), never black. One white crayon reserved for wax resist",
   "At most one watercolour per film, chosen for what it reveals (ultramarine for night, rose for dawn, sap green for rain). It never paints the characters",
   "Saturated crayon on lots of bare paper; value comes from pressure, not extra hues. One accent on a character may echo the story"
  ],
  "motion": [
   "Drawing on: lines reveal along their length in 0.4–0.9 s; colouring row by row; text letter by letter",
   "Acting: substitution, a new drawing per pose on the beat; two key drawings alternate for a repeated action. Big simple poses; a child's drawing doesn't…"
  ],
  "camera": [],
  "sound": [
   "Silence is a beat: a full beat of nothing after a failure; a short breath before a wordless passage",
   "Mix: music under narration, rising for wordless passages; metal voices get a gentle high lift. −14 LUFS"
  ]
 },
 "dark-keynote": {
  "name": "Dark Tech Keynote",
  "cat": "Information & Keynote",
  "line": "Launch film for Tidy, a fictional app: one buried cursor snaps hundreds of windows back into place.",
  "uses": [
   "Product launches",
   "SaaS",
   "Keynotes"
  ],
  "quote": "A software launch film where the interface itself is the star: near-black gradient, hairline grid, soft light, one brand accent, and UI that moves with snap-grid precision. Light reveals, one giant number, and a sound design that is as ordered as the pixels.",
  "essence": "A keynote-grade product film for software. There is no physical product and no glass render: the protagonist is the interface (a cursor, windows, notifications, tiles, a number). It lives on a dark stage lit by soft, cool light, with one brand accent reserved for the single most important element.",
  "nots": "a glass product render (no physical object), not a screencast (no real OS or apps), not a hologram HUD (no scanlines), not a chart film (one number, not a chart).",
  "material": [
   "Light is the reveal tool: only pixels the light has passed turn on; unlit areas sit at a few percent"
  ],
  "colour": [
   "A cool neutral ladder only: near-black stage, three surface steps, text in three greys (primary, secondary, label). Neutrals are slightly blue, never warm brown",
   "One accent, saturated and luminous, with its own glow. It is reserved for what the product is or does: the protagonist element, the call to action,…",
   "Secondary hues only as category codes in motion (a trail per data type), desaturated, and never on static UI"
  ],
  "motion": [
   "Flights follow curved paths with overshoot along the final tangent; same-type elements bend the same way and never cross",
   "Disappearing is designed (retract one part per beat, CRT-off squash into a point); nothing just fades",
   "The stage and grid never move on their own; only the camera moves them"
  ],
  "camera": [
   "Transitions = UI expand / collapse: every shot change is an interface element expanding into the frame or the frame collapsing into an element. No…"
  ],
  "sound": [
   "Tuned percussion and pads: marimba, vibraphone (mallet or bowed), glockenspiel, celesta, a synth pad or drone, a low sine pulse, a shaker,…",
   "Foley materials: cursor tick, low-profile keys, notification glass, file plop, window whoosh, glitch accents, stacking thumps, felt mallet…"
  ]
 },
 "data-physical": {
  "name": "Data Physicalization",
  "cat": "Evidence Films",
  "line": "Twelve years of wind and solar stacked as real plates, spiralling round a walnut dial until solar overtakes.",
  "uses": [
   "Annual reports",
   "Investor decks",
   "Energy data"
  ],
  "quote": "Real statistics built as real objects: every unit is a countable piece of material (a plate, a block, a coin, a bar) stacked to exact scale on a crafted base, shot like a product in a studio — soft key, long shadows, shallow depth of field, physically based materials. The camera reads a number at th",
  "essence": "Scale is exact. Heights, counts and areas are computed from the data; rounding is one unit at most and written in the facts. Two series compared on the same base use the same unit Studio light, real matter. Metal reflects an HDRI, wood shows grain, acrylic transmits; nothing glows, nothing is outlined, no fake UI",
  "nots": "Isometric Infographic (no icons, no flat colour coding), not Glass Product Render (the object is data), not Data Storytelling (no paper chart or inked axes), not Dark Tech Keynote (no black stage or neon), not Brick Toy (no toy proportions, no characters).",
  "material": [
   "Pieces: thin boxes or cylinders instanced in the thousands, each with a few-millimetre random offset and yaw, a ±7 % value change and a hairline gap: that is what makes…",
   "Material per series, chosen so two series separate in one glance at thumbnail size: brushed metal against tinted acrylic, pale wood against dark stone, copper coins…",
   "Base: a real-texture slab (wood veneer, stone) with inlaid marks: a tick ring, the series' paths, the labels of categories or years, cut into the surface at the base's…",
   "Rendering: PBR (transmission for acrylic), an HDRI at low intensity for reflections only, a warm key at 20–35° with long soft shadows, one or two cool rims so metal and…"
  ],
  "colour": [
   "The set is warm and neutral: a seamless greige sweep, the base in a natural material, the series in material colours (silver, pale teal, brass, oak). Material,…",
   "One accent (e.g. signal orange) for the reading or verdict that matters on this screen; nothing else is accent-coloured",
   "Ink is near-black at two strengths (value, then labels at ~60 %)"
  ],
  "motion": [
   "Cascade: a stack assembles bottom-to-top in 0.5–1.0 s, each piece dropping a few centimetres with an ease-out",
   "Feed: one period's increase arrives piece by piece from out of frame, quintic ease-out, a yaw that unwinds (\"placed\", not \"dropped\"), 8–16 pieces per second,…",
   "A single heavy object falls with gravity, lands with one small damped bounce, its shadow tightening"
  ],
  "camera": [],
  "sound": [
   "The material's own sound is the foley: metal plates tick bright and short (inharmonic partials 3–8 kHz), acrylic toks duller (1–3 kHz),…",
   "The ruler sings: every ruler piece (each 10th) rings a pitched mallet note, one timbre per series (e.g. glockenspiel for metal, glass harp…"
  ]
 },
 "dataviz": {
  "name": "Data Storytelling",
  "cat": "Information & Keynote",
  "line": "A hundred years of summer temperatures, where the chart itself tells the story.",
  "uses": [
   "Data journalism",
   "Reports",
   "Climate & science"
  ],
  "quote": "A chart that tells a story: real data, drawn mark by mark on cream paper by a red–blue pencil, with handwritten notes pinned to the numbers. The chart itself is the camera, the rhythm and the plot.",
  "essence": "Not a dashboard (one idea at a time), not a keynote with charts (no slides), never decoration.",
  "nots": "a dashboard (one idea at a time), not a keynote with charts (no slides), never decoration.",
  "material": [
   "Paper: warm cream, fixed-seed fibre noise and a faint dot grid in world space. Ink: dark warm ink for axes and series, pale warm grey for grid and zero line, IBM Plex…",
   "Marks: data dots carry a thin ink ring so pale values stay visible on cream. A mark lands with a short pop and a thin ripple; suppress ripples when marks arrive closer…",
   "Handwriting in pencil, per-glyph jitter, graphite grain, written on as the tip dances over the x-height. Leaders are wobbly curves ending in an un-closed ring around the…",
   "Layout: a plot box fixed in world space, a memory zone for early notes, every note pinned in data space (value + pixel offset) so rescales keep the layout, a bottom band…"
  ],
  "colour": [
   "Colour encodes one thing: the value. Diverging data uses a ramp (ColorBrewer RdBu family) centred on the mean of a meaningful reference period, with a…",
   "Honesty beats drama: pale values stay pale; never stretch a ramp to make a change look bigger",
   "The two pencil leads have meanings: blue for memories and human notes, red for records and warnings. A change of lead marks a turn"
  ],
  "motion": [
   "Rescale reads as ratchet clicks (stepped, each step eased); a calm rescale is smooth",
   "No fades to blank or dissolves. Transitions are chart operations: axis growth, pull-backs, rescales, morphs, a cell widening into the next frame"
  ],
  "camera": [],
  "sound": [
   "Ambience follows the places the notes evoke (J-cuts in, L-cuts out). Foley is graphite, paper and wood: tick-and-paper taps, scratches for…",
   "Bed: detuned-saw pad, soft kick, noise shaker, low-passed hats, sine sub, sample-and-hold blips, drones; harmony can darken or brighten…"
  ]
 },
 "desktop-flythrough": {
  "name": "Desktop Flythrough",
  "cat": "Materials & 3D",
  "line": "A cat photo hops across app cards on a sunlit desk, from one phone to a friend's.",
  "uses": [
   "App explainers",
   "Workflows",
   "Products"
  ],
  "quote": "App screens and tools lie on a sunlit desk as printed paper cards; small pixel characters, popped up into voxel toys, carry the work from card to card, while one unbroken camera flies after them, whips between stops and finally pulls back over the whole desk.",
  "essence": "The desk is the world. A matte paper mat with a regular dot grid lies on a light wooden desk, lit by one low warm sun through a window. Everything sits on it and casts a long, soft shadow. A few everyday desk… Interfaces are paper cards. Phones, tools and dashboards are rounded slabs a few millimetres thick with the interface printed on top. They are places: characters stand and hop on them, and parts of the…",
  "nots": "a screen recording (no cursor, no glowing monitor, no real app chrome or logos); not a brick or clay toy film (pixel voxels on printed paper); not an isometric infographic (perspective camera, real light); not flat motion graphics (everything has thickness and a shadow).",
  "material": [
   "Light: one directional sun low from the back-left (about 20° up, so a toy's shadow is two or three times its height), a 4096 soft shadow map that follows the camera…",
   "Props: the same voxel recipe (crosses, ticks, bells) or plain rounded primitives (bricks, presses, drawers, towers, tent cards, stamps). Data that rises out of a card is…",
   "Impact ring: a thin accent-coloured ring spreads over the paper from an impact and fades in about a second"
  ],
  "colour": [
   "One light ground (the mat) with a slightly darker dot, cool-tinted so the warm sun leaves it fresh; a warm wooden desk around it; cards in a near-white of the…",
   "Two or three support hues for the cast and props, mid-saturated, never neon; one warm cast colour against the cool ground. Red only for failure or trouble (an…",
   "Judge the rendered frame: avoid grey on grey; keep the vignette light and the shadows tinted by the sky fill"
  ],
  "motion": [
   "Hops: an arc with squash and stretch (stretch about 14 % in the air, squash about 30 % for 0.2 s on landing, a small anticipation squash before take-off).…",
   "Characters act: they blink every couple of seconds, bounce on the beat while they wait, squint when they are squashed, lean towards what they look at",
   "Slam: drops from above with ease-in, lands on a downbeat, squashes, jolts the card, sends out a ring"
  ],
  "camera": [
   "One take, no cuts, no dissolves. Targets are live subjects; between keys the target follows a Hermite path with live end points; drift is a breath,…",
   "At a key where a whip starts, the target rests first (or the camera stutters). A character's take-off is the natural start of a whip. A whip between…"
  ],
  "sound": [
   "Score: bright and warm, acoustic in feel: marimba (with vibraphone under long notes), plucked bass, a soft synthetic kick (a short sine…",
   "Foley: every action has a sound. Pop: a marimba note from the current chord plus an upward sweep. Hop: a soft tick. Landing: a felt thump.…"
  ]
 },
 "engraving": {
  "name": "Copperplate Engraving",
  "cat": "Print & Printmaking",
  "line": "A natural-history plate engraves itself: the burin cuts the copper, the bee builds up line by line, and a watercolour wash brings it to life.",
  "uses": [
   "Museum labels",
   "Science explainers",
   "Brand heritage"
  ],
  "quote": "An intaglio plate that engraves itself: a burin cuts swelling lines into copper, a proof is pulled, and the figure builds up — outline, hatching, cross-hatching — until engraved lettering, magnified details and a hand-laid wash make a finished plate.",
  "essence": "An intaglio print: the line is ink held in a groove a burin cut into copper. Three rules:",
  "nots": "a woodcut (black block, white gouges — woodcut), not a pen sketch (loose broken lines — urban-sketch), not an engineering drawing (blueprint), not a sepia filter.",
  "material": [
   "One light direction for the whole film (upper left by convention); heavier outlines away from it; tone fields come from the shape (pillow lighting, analytic spheres and…",
   "Roundels: double-ruled circle, ruled-machine ground with a white halo round the subject, content authored at a large radius and scaled in. Leaders: hairlines from a dot…"
  ],
  "colour": [
   "The print is two values, paper and ink; all tone is line density",
   "Colour is transparent wash only, in muted earth and mineral pigments, one stronger pigment at most. Never opaque, never on lettering, rules or paper outside…",
   "Reserve it: the whole subject at one moment, or only the part that matters — or none"
  ],
  "motion": [
   "A long single stroke may be followed by the camera; start it partly cut so no frame is empty. Keep a full build to a few seconds",
   "Roundels fly on an eased arc with a small lift, growing log-linearly to size. Colour blooms from one point with a ragged front and a wet rim that dries;…",
   "Nothing fades or slides like UI: lines are cut, text cut or written, colour blooms, sheets are pressed, peeled or laid down"
  ],
  "camera": [],
  "sound": [
   "Room: a quiet workroom (faint clock), paper room once the print exists",
   "Instruments (choose): harpsichord, string quartet, solo cello or viola da gamba, lute, chamber organ, glass harmonica for a cold subject.…"
  ]
 },
 "game-show": {
  "name": "Game Show Flat",
  "cat": "Games",
  "line": "The history of AI as a rhythm game: models take the stage on the beat, and a report card closes the show.",
  "uses": [
   "Tech timelines",
   "Year in review",
   "Variety shows"
  ],
  "quote": "A rhythm-game variety show in flat vector: toy-like mascots with thick ink outlines on candy-coloured stripes and sunbursts, every hit landing on a fixed tempo grid, call-and-response patterns, and a judgement word when each round is won.",
  "essence": "Everything is on the grid. One fixed, fast tempo. Every pop, drop, stamp, typed character and camera punch sits at a (bar, beat) and is also a sound event; the score is generated from the picture's own… One drawing kit, many sets. Flat fills, one heavy ink outline, round caps, hard offset shadows; each round gets a new saturated background colour and pattern",
  "nots": "a microgame frenzy (no timer or one-verb command per 3 s game, no change of art style per round), not a mid-century cartoon (no textured painted backgrounds, no character acting), not a keynote (no slow reveals, no gradients).",
  "material": [
   "Characters: a rounded bean body, stubby arms with mitten hands, oval eyes with a catch-light, a mouth that swaps to an open one. Humans share the construction; older…",
   "UI kit: round card, corner sticker banner, judgement word, burst (star + ring + speed lines), scoreboards"
  ],
  "colour": [
   "Ink + paper + candy. Near-black ink, white, and a warm cream for cards and paper props; around eight saturated candy hues (yellow, orange, red, pink, green,…",
   "Characters own colours. A contestant's body colour is its identity and never changes; keep it distinct from the set it stands on (a character is never the same…",
   "Big words are white or yellow with a thick ink stroke; judgement words may be pink or yellow"
  ],
  "motion": [
   "Entrances drop from the sky with ease-in and land exactly on their beat, so the sound lands with them. Crowds drop in one per beat or half-beat",
   "Pops use back-ease for anything appearing (cards, stickers, stamps, words); ease-in for exits. Nothing fades in slowly: things are either on or popping",
   "Shout pose: arms up + open mouth for about half a beat"
  ],
  "camera": [],
  "sound": [
   "All synthesized from the picture's events: a sine kick with soft saturation, band-passed noise snare and clap, hats, slap bass, detuned-saw…",
   "A bright major pop harmony on a short chord loop, one chord per bar; each round gets its own flavour (funk, quiz, electro, dream, heavy…),…"
  ]
 },
 "glass-product": {
  "name": "Glass Product Render",
  "cat": "Materials & 3D",
  "line": "Unboxing and close-ups of Aura, fictional glass earbuds, in strip-light sweeps and caustics.",
  "uses": [
   "Product launches",
   "Consumer tech",
   "Beauty"
  ],
  "quote": "Launch-film product rendering in transparent and frosted glass: a dark-field studio, strip-light sweeps, dispersion, caustics, light travelling inside the object, slow exploded views that snap shut on a downbeat.",
  "essence": "A single hero object of glass, metal and light floating in an infinite black studio. Long strips behind and beside it turn clear glass into a thin white outline with rainbow edges; the internals show through as in a display case. Everything moves slowly and precisely; every cut, sweep and pulse lands on the beat.",
  "nots": "reproduce a real product silhouette (a famous phone or headphone outline), a real brand name, logo, typeface or UI.",
  "material": [
   "Frosted glass: transmission ~0.85, roughness ~0.4, milky tint, thick. On black it reads as dark grey plastic unless something bright is behind or inside it: an opaque…",
   "Background: black with an optional dark-grey radial sweep that separates glass edges; the floor fades into it, no horizon line. Floor: black gloss, blurred mirror,…",
   "Post: 2× supersampling; physical DoF (shallow macro, deep exploded views); bloom only above ~1.1; Neutral tone mapping (AgX washes accents to white); grain 0. Model in…"
  ],
  "colour": [
   "The world is neutral: black, greys, the white of strip reflections, the metals' own tints",
   "Emitters that only illuminate (inside frosted glass) stay cool-white and dim",
   "Dispersion rainbows are allowed only at thick glass edges and in the caustic, never as a gradient on surfaces or type"
  ],
  "motion": [
   "The camera always drifts: slow orbits or push-ins; never a locked-off frame, never handheld, except a couple of frames of micro-shake on an impact",
   "Objects lift out of cradles tilted toward camera and settle upright; lids hinge at the back and stand behind the object as a backlit halo",
   "Light pulses and sweeps are events on the beat grid, not free animation"
  ],
  "camera": [],
  "sound": [
   "Minimal electronic, never piano-and-strings. Timbres, as options: bowed-glass or wet-finger tones, granular crystal clouds, glass bells and…",
   "Lock every pulse, sweep and snap to the score: write the cue map first and share one hit list between the score and the renderer; light…"
  ]
 },
 "halftone-dossier": {
  "name": "Halftone Dossier",
  "cat": "Print & Printmaking",
  "line": "A chubby orange cat stands trial for testing gravity and 4 a.m. parkour, and walks free.",
  "uses": [
   "Humour",
   "Pet content",
   "Social shorts"
  ],
  "quote": "A retro print case file: cream archive paper, overprinted halftone dots in a few flat inks, huge heavy headlines with misregistered shadows, rubber stamps that slam, and thick-outlined characters. The film is a file that is read out one exhibit at a time.",
  "essence": "The whole film is paper. A warm cream sheet with low-frequency mottling, fine grain, a vignette and a fold; dark scenes are printed on it too, never glowing Shading is never a gradient: it is halftone dots whose size follows a density field. Two or three dot layers at different screen angles overprint (multiply); that is the \"printed\" feel",
  "nots": "Risograph (no grainy two-ink riso texture as the whole look, no zine collage), not Swiss motion (no grid-driven kinetic type on white), not Game Show Flat (no candy sets, no rhythm-game rounds). Dots, paper and stamps must be visible in every frame.",
  "material": [
   "Grain layer (per frame): a few hundred paper-coloured specks and fewer ink specks, reseeded every 2 frames: dust on the print, not film grain",
   "Halftone-filled numerals and shapes: a flat fill overprinted with a darker halftone clipped to the glyph; giant numerals may bleed off the frame",
   "Stamps: a double rounded rectangle and bold text through a coarse ink-grain + displacement filter so edges are rough and the ink mottled; ~93 % opacity, tilted ±10°",
   "Props: starbursts, speech bubbles, confetti, radial rays, sticky notes, folders, clocks: all flat fill + ink outline"
  ],
  "colour": [
   "A paper ground, one dark ink, and four or five flat spot inks. The dark ink (navy, black-brown or deep green) carries every outline, body text and the caption…",
   "One ink is the overprint shadow colour (misregistration offsets, caption shadows); one is the highlight for keywords and numerals; one warm red is reserved for…",
   "Flat inks only. No gradients, no transparency ramps; tone comes from dot size and overprint"
  ],
  "motion": [
   "Everything enters with overshoot (back ease, 0.3–0.45 s): rising from below the frame or scaling from 0. Nothing fades in",
   "Stamp slam: ~0.09 s from ~2.6× to 1× (ease-in), then a small damped bounce; camera shake, flash and stamp sound on the same frame",
   "Squash landings preserve volume (scale(1/sq, sq) with a damped cosine)"
  ],
  "camera": [],
  "sound": [
   "Synth pop-print toolkit: synth kick, snare, clap, hat; a square-ish 8th-note bass; triangle pad; a marimba-like pluck (fundamental + ~4×…",
   "Silence before the stamp: empty the music just before a verdict so the stamp lands alone. Other options: a snare roll + rising sweep into a…"
  ]
 },
 "hd-2d": {
  "name": "HD-2D",
  "cat": "Games",
  "line": "The lighthouse goes dark; a girl carries the last flame through a night forest and up the storm cliffs.",
  "uses": [
   "Game trailers",
   "Fantasy",
   "Story films"
  ],
  "quote": "Hand-made pixel sprites standing like paper cut-outs inside a lit, fogged, fully 3D diorama, shot from a high three-quarter angle through a tilt-shift lens: a toy world where every lamp throws a real shadow.",
  "essence": "A 3D miniature set of boxes and cylinders wrapped in pixel-art textures, populated by flat 2D pixel sprites that receive light and cast shadows, seen from a high, far camera through a tilt-shift band so the world reads as a tabletop model. Light is the subject: practicals throw sprite shadows across the floor; shafts, fog, dust or rain hang in the air; strong bloom, heavy vignette. On top, a small RPG UI: chapter…",
  "nots": "a voxel game (no cubic characters), not a flat 2D pixel RPG (the set is real 3D with real light), not a tilt-shift photo of a real miniature (textures are pixels, not materials).",
  "material": [
   "Light rig per set: one dim shadow-casting key, a hemisphere fill, practical point lights with shadows (lamps, fires, windows, screens), and a front fill ~2 m before the…"
  ],
  "colour": [
   "Two temperatures: one large ambient key (cold, or pale, or dusty) against small warm or saturated practicals. The practicals carry the story; the ambient…",
   "The darkest value is a warm ink, never pure black; the brightest is the light source itself, bloomed",
   "Each set owns one fog colour and one light key, so a cut to a new place reads instantly"
  ],
  "motion": [
   "Poses are data: a parameter object per drawing; a new pose is a new table entry",
   "Weather is procedural: slanted rain streaks; lightning as a scripted flash curve (strike, dip, re-strike, decay) lifting sky, fill and exposure together",
   "The world never shakes except for impact; the set never moves, only the camera and what lives in it"
  ],
  "camera": [],
  "sound": [
   "Music: chamber-fantasy or cinematic colours (harp, celesta, strings, horns, low choir, timpani) or small folk instruments (lute, recorder,…",
   "Silence as a tool: a hard stop into a reverb tail, a pad alone, or one heartbeat when the light nearly dies; a short breath (< 1 s) when…"
  ]
 },
 "hologram-hud": {
  "name": "Sci-fi Hologram HUD",
  "cat": "Information & Keynote",
  "line": "An e-bike is scanned into a hologram; target boxes lock onto the battery, motor and brakes.",
  "uses": [
   "Spec walkthroughs",
   "Launch videos",
   "Trade shows"
  ],
  "quote": "An object is scanned into a glowing wireframe. Target boxes lock onto its parts; each opens in a local exploded view, a leader pulls out, and its number rolls from garbage glyphs into the real value. It may light up, once, into a solid hologram.",
  "essence": "The subject is always a line wireframe made of light above a round projector pad on a near-black stage, never a rendered object. Everything reads as scanned data: a scan plane grows the model, parts pull apart along their assembly axes, numbers are computed on screen.",
  "nots": "a type-driven keynote (dark-keynote), not a drafting sheet (blueprint), not a product render (glass-product). The subject stays a wireframe; it may gain translucent faces once, and even then the lines stay on top.",
  "material": [
   "Stage: near-black tinted by the hue, a radial lift behind the subject, a fading dot grid, a strong vignette",
   "Projector pad in true perspective: concentric rings (one bright, one dashed), ticks, faint rays; it rotates slowly and spins with any turntable move",
   "Hot edges (near-white of the hue) only for what matters now: the scan front, inner pieces flagged hot when opened, a light wave, a part being pinged",
   "Real CAD topology: tubes are rings plus longitudinal lines. Every part is physically connected: a floating piece is noticed first"
  ],
  "colour": [
   "One cold hue plus one warm accent, both parameters (e.g. mint/orange, violet/lime, ice-blue/red; choose from the subject)",
   "The hue carries lines, HUD and fills. The accent is spent on locked values only: a number turns accent-coloured at the frame it becomes true. Nothing else ever…",
   "White is heat: near-white edges and one-frame flashes mark what is active. Everything at rest sits in the hue's alpha levels"
  ],
  "motion": [
   "Target lock: oversized, rotated 45°, faint; snaps to fit in ~0.2 s (cubic ease-out), flashes white 3 frames on the downbeat",
   "Explode along each piece's assembly axis: the shell slides along its own axis, the contents stay in place and glow. Open over a beat or two, close fast",
   "Chip dock: a finished value slides into a side rail and stays until the end"
  ],
  "camera": [],
  "sound": [
   "Synth palette: saw/square arpeggio with ping-pong delay (scooped 1–4 kHz for the voice), square pulse, 8th bass, synth hats and claps,…",
   "Voice: calm, confident. Duck music and foley with a held envelope (no pumping between words); lock transients escape. −14 LUFS"
  ]
 },
 "impasto": {
  "name": "Impasto Oil Painting",
  "cat": "Hand-drawn & Painting",
  "line": "In a grey, rainy square one red umbrella opens, and a waltz paints the whole plaza in colour.",
  "uses": [
   "Music videos",
   "Art & culture",
   "Emotional ads"
  ],
  "quote": "Thick oil paint laid with a palette knife: big, flat, sharp-edged planes of colour, raked by light so every ridge of paint shows. Clarity first: value structure before texture, hard edges at the focus, calm planes everywhere else.",
  "essence": "A moving oil painting made of knife strokes. Each stroke is a real object: a slanted plane of paint with a ridge where the blade pressed, a lip where it lifted off, broken streaks where the paint ran out, two colours dragged into each other. The world is repainted from its strokes every frame, but static paint never moves: only things that move in the story move. Light rakes across a height field, so the paint has…",
  "nots": "a Van Gogh swirl filter (strokes boiling everywhere), not a brush texture over flat vector art, not watercolour (paint is opaque), not a \"painterly\" photo filter (strokes are designed, not sampled from noise).",
  "material": [
   "Strokes never cross shape groups, so silhouettes stay crisp. Lost edges are opt-in (put two shapes in the same group)",
   "Light rakes over a height field; wet or glossy surfaces get slightly more specular",
   "Reflections (wet ground, glass, water) are explicit stacks of short horizontal knife dabs under each light source, broken and fading; never a painted rectangle",
   "Render supersampled (2×). No film grain: grain plus compression eats the knife edges"
  ],
  "colour": [
   "Planes of mixed, slightly broken colour; each stroke may drag a second colour (c2) into the first. No gradients made by blending pixels: gradients are made by…",
   "Warm light against cool shadow is the default temperature structure; the brightest, purest chroma is reserved for the story's subject (a prop, a crowd, a light…",
   "Colour can be an event. Every stroke can hold a grey and a colour version; a monochrome world with one coloured exception, or a world re-laid from grey to…"
  ],
  "motion": [
   "Moving figures are procedural strokes rebuilt each frame from fixed seeds, so their paint doesn't boil (walk cycles, IK arms, props that open and close)",
   "Actions sit on the music grid: a change of direction, a pop, a swell lands on a beat"
  ],
  "camera": [],
  "sound": [
   "Foley follows the paint and the world: palette-knife scrapes on every repaint or paint-over, wet dabs, the materials of the scene (wet…",
   "Beds in layers (a hiss, near grains, one distinct detail), filtered when the camera goes under cover"
  ]
 },
 "ink-wash": {
  "name": "Chinese Ink Wash",
  "cat": "Hand-drawn & Painting",
  "line": "A swordsman crosses the river on the water and splits the current with a single stroke.",
  "uses": [
   "Wuxia",
   "Cultural brands",
   "Poetry"
  ],
  "quote": "Xieyi ink painting on rice paper, animated: blank paper is space, one brushstroke is a mountain, a wave, a gesture or a cut.",
  "essence": "Most of the frame is empty paper (留白): water, sky, mist, silence. Things are painted into existence, not cut to.",
  "nots": "watercolour (no colour washes), not vector art with a brush texture (no flat fills or closed outlines), not a calligraphy title sequence.",
  "material": [
   "Paper is procedural, in the compositor, never a texture file: warm rice paper (around #F2ECDE), cloud mottling, long fibres, pulp flecks, grain that fades when zoomed…",
   "Ink is stroke opacity multiplied onto paper (never an overlay), in five tones (墨分五色):",
   "Loaded stroke: bristles darker on one side, so the stroke carries its own contour: this makes bodies, rocks and waves read as ink, not vectors",
   "Two layers: the wet one bleeds in the compositor (noisy blur, edge pigment accumulation, granulation); the dry one only gets fibre jitter and paper tooth"
  ],
  "colour": [
   "Ink only, from cool grey at low density to warm black at full density. No other hue in the world",
   "One vermilion (around #B02E22), for the seal and at most one tiny accent in the story (an object the protagonist carries). The accent finds the protagonist in…"
  ],
  "motion": [
   "Painted into existence: strokes appear in drawing order",
   "Stillness before action (when a decisive stroke is the event): hold, with at most a slow push-in, then let the stroke cross the frame in a few frames.…",
   "Nothing is tweened like a vector shape: things are painted, bloom or dissolve into mist"
  ],
  "camera": [],
  "sound": [
   "Cue to the picture, never loop: unmetred plucks suit emptiness, a pulse suits movement, rolls suit mass; painted strokes can each land on a…",
   "Silence is literal: zero the whole bus (music, ambience, reverb tails) with short fades. At most one sound inside it (a drip, one ring).…"
  ]
 },
 "iso-infographic": {
  "name": "Isometric Infographic",
  "cat": "Information & Keynote",
  "line": "A coffee's journey from the plantation to your hands, across one isometric world.",
  "uses": [
   "Process explainers",
   "Supply chains",
   "Annual reports"
  ],
  "quote": "A system diagram comes alive: an isometric diorama of flat three-tone blocks, thin ink labels and Isotype numbers, where things open up to show their insides and the numbers are drawn, not stated.",
  "essence": "Flat, true isometric. No perspective, no outlines on solids; shapes are separated only by the three tones of each face. The projection never rotates or tilts Infographic furniture is part of the picture: leader lines, label pins, dashed cut lines, hatched section faces, tracking rings, a legend, a route line all live in the world",
  "nots": "low-poly 3D (no perspective, no lighting beyond three face tones), not a flat 2D explainer (everything has isometric depth), not a blueprint (colour blocks, not line drawings on blue).",
  "material": [
   "The board: floats on a pale background with a faint isometric dot lattice and a soft blurred shadow; its front faces show strata (soil, water column, floors, pipes)…",
   "Composites (a terraced hill with shrubs, a crane over a ship) are drawn as one ordered item or given a depth bias; generic painter sorting fails on them",
   "Close-ups of hands or objects: flat faceted shapes in three tones, same logic as the blocks",
   "Level of detail by zoom: skip small world detail at high zoom, fade tall objects in by zoom so a pull-out never sweeps a giant shape through the frame"
  ],
  "colour": [
   "A pale neutral ground (cream, paper grey or pale blue) and 5–7 flat hues, each with its three tones; one ink colour",
   "Colour codes meaning, the way a legend does: one hue per material or role (water is always the same blue, the subject always its hue). Never reuse a hue for…",
   "The subject's hue is reserved: when the story needs \"this one\", everything else desaturates toward warm grey and only the subject keeps its colour (focus +…"
  ],
  "motion": [
   "Nothing moves without a line leading it: a route line is drawn slightly ahead, a leader grows before an inset opens, a cut line draws before a skin slides away",
   "Isotype fill: icons pop with a back-ease (overshoot), one per subdivision of the beat; count-up numbers run over the same span",
   "Vehicles follow polylines with ease-in-out and face their tangent"
  ],
  "camera": [],
  "sound": [
   "Music: acoustic and light: kalimba, marimba, nylon guitar, pizzicato, woodblock and hand percussion (shaker, bongo, cajon), upright or…",
   "Techniques (options): one sound per icon as numbers fill; instruments dropping out and a low-pass closing as the camera dives; J-cuts (the…"
  ]
 },
 "isometric-picture-book": {
  "name": "Isometric Picture Book",
  "cat": "Information & Keynote",
  "line": "Travellers board an isometric plane, and the order shows why one way is nearly twice as fast.",
  "uses": [
   "Everyday rules",
   "Queues",
   "Comparisons"
  ],
  "quote": "A calm explainer of an everyday rule, set in one real place drawn in true isometric with flat colour: small faceless people seen from behind do the thing in order, while serif type lands on the ground, character by character, as if painted there. Whatever hides the action (a roof, a wall) is cut awa",
  "essence": "Not Isometric Infographic: that style builds a model on a floating board over a dot lattice and labels it with sans-serif pins, icon statistics and inset bubbles to trace a process; here there is no board edge, no pins and no icons: the place is real and full bleed, the labels are serif words lying on its floor, and the explanation is people obeying a rule. Not Low-poly Isometric Island: no lighting, no faceted…",
  "nots": "Isometric Infographic: that style builds a model on a floating board over a dot lattice and labels it with sans-serif pins, icon statistics and inset bubbles to trace a process; here there is no board edge, no pins and no icons: the place is real and full bleed, the labels are serif words lying on i",
  "material": [
   "Solids are flat-shaded in three tones per colour: top lifted toward warm paper, +y face the base colour, +x face dropped toward a warm umber. Curved bodies (a fuselage,…",
   "Ground surfaces carry only their functional markings (painted lanes, chevrons, lead-in lines, stop bars, seat squares) and a faint tile or slab grid",
   "Cut-aways are part of the model: the near wall is cut low and the far wall keeps its windows; a lid is its own solid with a paper-coloured underside, hinged on the far…",
   "People are billboards anchored at their feet, about 1.6–1.8 m tall: a round hair-dark head with a sliver of skin at the ear, a two-tone torso, separate trouser legs,…"
  ],
  "colour": [
   "The accent never decorates; it appears only where the rule is. It stays small because its rarity is what makes the eye go to it: many frames carry none at all.…",
   "The subject hue and the marking colour must be clearly apart, in hue and in value, from the four tops: people have to stand out from the place they move…",
   "Shade toward warm umber and paper, never toward grey or violet: dirty shadows are the fastest way to lose this look"
  ],
  "motion": [
   "A rewind runs the same motion backwards, faster, with a counter running down"
  ],
  "camera": [],
  "sound": []
 },
 "kino-montage": {
  "name": "Constructivist Montage",
  "cat": "Edit & Documentary",
  "line": "The Empire State's 1931 brochure credits its builders; the site film and Hine's photos answer: 2,500 a day.",
  "uses": [
   "Industry histories",
   "Milestones",
   "Collective effort"
  ],
  "quote": "Real archive footage, photographs and documents, printed as one ink-and-paper poster with a single red, and cut on a machine beat. Diagonal bands carry the type; windows cut along the axis hold the film; people are scissored out of photographs and stacked into structures; numbers count, documents ar",
  "essence": "Not Data Storytelling or a keynote: no centred headline with bullets, no slide transitions, no header bars; data appears as marked documents, counters and measured bars inside the composition. Not Swiss Motion Graphics: asymmetric, diagonal, no grid of white space, no thin rules as decoration. Not Art Deco or 60s Spy Titles: no gold, no fine lines, no jazz. Not a museum slideshow: archive material is never shown \"as…",
  "nots": "Data Storytelling or a keynote: no centred headline with bullets, no slide transitions, no header bars; data appears as marked documents, counters and measured bars inside the composition. Not Swiss Motion Graphics: asymmetric, diagonal, no grid of white space, no thin rules as decoration. Not Art D",
  "material": [
   "Four kinds of element only: bands (red or ink, along the axis), windows (rectangles or parallelograms holding film or photographs), cut-outs (people scissored from…",
   "The print grade (one function for film, photos and documents): luminance → percentile stretch (film: one pair of percentiles per clip, so it never pumps; 0.7 / 99.5;…",
   "Cut-outs: a person-segmentation model (u2net_human_seg via onnxruntime) → threshold 0.5 → median filter → largest component → 7 px paper border dilated outside the mask.…",
   "Documents: scans at full resolution, never retyped. They are marked: a red highlighter bar in multiply over the exact sentence, a hand-drawn red ellipse round a heading,…"
  ],
  "colour": [
   "Everything photographic is ink-on-paper; nothing else has colour. Red is never laid on red: a red block on a red ground becomes ink"
  ],
  "motion": [
   ""
  ],
  "camera": [],
  "sound": [
   "Score: an original machine ostinato (eighths, minor, e.g. D–D–F–D–A–D–E–F) in spiccato cellos + staccato bassoon, staccato tuba / trombone…",
   "Original sound alternates with music: in one section the orchestra stops and a real recording (a rivet gun, a machine, a crowd) carries the…"
  ]
 },
 "lidar-survey": {
  "name": "LiDAR Survey",
  "cat": "Evidence Films",
  "line": "A laser survey strips the canopy off a Connecticut forest and finds 3.4 km of old farm walls.",
  "uses": [
   "Heritage",
   "Environment",
   "Site surveys"
  ],
  "quote": "Real airborne laser points of a real place, floating in the dark as a measured cloud; a scan line or a cutting plane passes through them and the points condense into a solid, raking-lit surface, which is then measured with hairline instruments. One designed camera move carries the whole film: the cl",
  "essence": "Not Sci-fi Hologram HUD (no invented interface: the points are real, sparse where the survey was), not Satellite Briefing (photographs from above; here a 3D cloud flown through), not Blueprint, not Low-poly Isometric, not Glass Product Render.",
  "nots": "Sci-fi Hologram HUD (no invented interface: the points are real, sparse where the survey was), not Satellite Briefing (photographs from above; here a 3D cloud flown through), not Blueprint, not Low-poly Isometric, not Glass Product Render.",
  "material": [
   "Points: GL points sized in world units (0.12–0.3 m), floor of one output pixel, soft discs, opaque and depth-tested (additive only for a ghost layer); colour from height…",
   "Quantise for the browser: uint16 positions (2 cm / 1 cm) plus a byte each for height above ground, class, intensity, seed",
   "Height above ground for every return (minus a ground model triangulated from class-2 returns) drives the colour ramp, the cutting plane and the ruler",
   "The solid surface: a 0.5–1 m mesh of the ground or surface model, smooth normals, baked short-radius AO, a low raking sun (20–35°), faint contours, crests lightened.…"
  ],
  "colour": [
   "Background near-black with a cold tint; never pure black, never a gradient sky",
   "The front and seams: one cool near-white; it is light, not a colour",
   "The solid surface: warm neutral (stone, clay, plaster), lit; its colour never competes with the accent"
  ],
  "motion": [
   "The front moves on an ease, slowest where the subject is; a cutting plane steps on the beat (eased steps, short holds) so the layers read",
   "Points appear behind a front or by height, never by random fade-in across the whole frame",
   "Readings land with a small pop; traced features light up along their length in order"
  ],
  "camera": [],
  "sound": [
   "Weight and synthesis: timpani, bass drum, gran cassa for condensations and cuts, a reversed swell into the main impact; low-passed…",
   "Dry and wet: one option is electronics while the subject is still points, and a single organic, wooden or bowed timbre (marimba, bowed…"
  ]
 },
 "living-screencast": {
  "name": "Living Screencast",
  "cat": "Information & Keynote",
  "line": "Clawd hops out of the terminal into the Claude app and acts out plan mode and self-checks in one take.",
  "uses": [
   "Product tutorials",
   "Feature launches",
   "Onboarding"
  ],
  "quote": "A product walkthrough that looks like a real screen recording, where a low-resolution mascot lives inside a high-resolution interface and acts out what the software is doing.",
  "essence": "The film looks like a screen recording of the real product, but it is not a recording. Every window, menu, diff line and button is redrawn in 2D, so the camera can go anywhere, every pixel is controllable and text stays sharp at any zoom.",
  "nots": "a dark tech keynote (no black stage, no invented abstract UI: this is the real product), not a pixel-art game (the world is hi-res vector UI; only the mascot and its props are pixels), not a real capture (nothing is a screenshot).",
  "material": [
   "Real UI, redrawn: every label, mode name and shortcut matches the real product; no screenshots, no lorem ipsum. Demo content (code, data, test output) is coherent, and…",
   "Pixel grid is sacred: the mascot, its props (pencil, \"!\", sparkles, heart, dust) and trails share one square-pixel grid with crisp edges. It scales with the camera; its…",
   "Window on wallpaper: the app floats on a desktop with a soft shadow; zoom never shows beyond the monitor",
   "Depth only where it serves attention: rack focus (blur the pane that doesn't matter), a vignette spotlight. Never blur text the viewer must read"
  ],
  "colour": [
   "The product's own interface colours rule: follow its real light and dark themes exactly",
   "The mascot keeps the product's or brand's mascot colour, or one saturated hue that no UI element uses, so it finds the eye in any frame",
   "Overlays (chapter pill, key HUD, captions) are neutral frosted glass; one accent at most, taken from the product"
  ],
  "motion": [
   "Mascot acting: jumps with anticipation crouch, stretch on take-off, tucked legs, landing squash with a damped bounce and dust. Idle breathes (a tiny squash) on…",
   "Eyes carry the acting (neutral / left / right / up / down / wide / happy / shut / blink): they look at what matters. Arms: down / up (cheer) / wave",
   "Cursor: smoothed, spring-eased paths, small push on click, never teleports"
  ],
  "camera": [],
  "sound": [
   "Two resolutions in the music: a hi-fi layer (piano, upright or electric bass, brushed or tight kit, glockenspiel, real samples) is the…",
   "Options: a low-passed \"night\" version of the band for a dark theme; a tom fill and crash at chapter seams; dropping the drums to build…"
  ]
 },
 "lowpoly-island": {
  "name": "Low-poly Isometric Island",
  "cat": "Materials & 3D",
  "line": "An island and its village grow tile by tile from an empty sea, each tile a note, into a starry night.",
  "uses": [
   "Game trailers",
   "World building",
   "Calm content"
  ],
  "quote": "A tiny faceted world seen through an orthographic isometric lens: everything is a geometric block, and everything that appears arrives with a bounce and a note.",
  "essence": "A miniature world built from flat-shaded low-poly geometry (hexagonal tile columns, box buildings with prism roofs, cone and icosahedron trees) floating in a faceted sea or void, watched by an orthographic camera at an isometric angle. No perspective and no horizon: distance dissolves into a screen-space sky gradient, so the world looks like a model suspended in colour. Light, not texture, tells time: every facet…",
  "nots": "a voxel game (no cubes-of-cubes, no pixel texture), not a tilt-shift photograph of a real place (no perspective, no photo detail), not a smooth-shaded 3D cartoon (no rounded normals, no subsurface).",
  "material": [
   "Props are primitive assemblies: boxes, prisms, low-segment cylinders and cones, icosahedra at detail 0, pinched boxes. Emissive parts (windows, lamps) get their own…"
  ],
  "colour": [
   "Pastel, low contrast, a handful of hues: one ground family (sand/grass/earth or its equivalent), one neutral rock, and a small set of wall and roof colours…",
   "Time of day is a keyframed set of colours (zenith, horizon, deep, shallow, sun colour, intensity, elevation, azimuth), interpolated. Day is airy and cool; dusk…",
   "At night, warm emissives are the only bright things (windows, lamps, a beam). Keep the sun sideways to the camera in key shots (low sun behind the target turns…"
  ],
  "motion": [
   "Rise from below: a short cubic ease up, then a damped-sine overshoot; a splash ring and spray the moment it breaks the surface. The event time is when it…",
   "Drop and stack (floors, roofs, rings): a fast ease-in fall, a damped bounce, and volume-preserving squash-and-stretch on landing",
   "Never moves: the projection (no perspective, no fov change)"
  ],
  "camera": [],
  "sound": [
   "Music can be event-driven: growth events carry a note, and the score synthesizes each one at its exact time, so the picture writes the…",
   "A single note can be a motif: one sound owned by the world (a bell, a chime, a horn) that returns changed"
  ]
 },
 "memphis-diorama": {
  "name": "Memphis Diorama",
  "cat": "Materials & 3D",
  "line": "One river bend, four seasons, one take; each turns when the big tree squats and springs back.",
  "uses": [
   "Web heroes",
   "Ambient loops",
   "Seasons"
  ],
  "quote": "A place built as a tabletop model: on warm white paper an organic, grainy frame grows open, and inside it a small world in flat Memphis colours, ink outlines, hard purple shadows and tiny patterns, full of small motions under a slow camera. Calm, bright and warm; a place you watch, not a story you f",
  "essence": "Paper and a grainy frame. A warm white ground; the picture lives in a rounded, organic frame whose edge dissolves into grain. It grows open from the centre at the start and draws back in at the end Memphis flat colour. Saturated primaries plus pastels, flat fills, no gradients; a deep-indigo ink outline; small patterns tiled on surfaces (dots, stripes, zigzags, terrazzo flecks, halftone)",
  "nots": "character animation: nobody acts. Code-made faces, gestures, getting in and out of cars always look stiff, so this style never shows them. Not an isometric infographic (that one is cool and diagrammatic; this one has weather, seasons and sound). Not tilt-shift (no photograph, no depth of field: ever",
  "material": [
   "Three tones only: the top face is the brightest, sun-facing sides keep the base colour, the faces turned away drop to about ×0.5–0.95. Hard edges between faces, never…",
   "Halftone in the shade: inside shadows, a staggered grid of lighter dots in world space, like a print. It turns dark areas into texture instead of dirt",
   "Patterns belong to the world: dots and stripes are computed from world coordinates and stay on the object as it moves. Pattern scale grows with distance so far surfaces…",
   "Detail is built, not textured: a house is a plinth, plank-striped walls, white corner trims, two roof slabs and a ridge, a gable with a round window, framed windows with…"
  ],
  "colour": [
   "The ground outside the frame is always warm white #FFFCF6; nothing else is drawn there",
   "5–7 saturated hues + 2–3 pastels carry the picture. Ink #25214A is only for outlines, type, tyres and window frames",
   "Cluster colour by area: neighbouring blocks differ in hue; one colour's share is controlled (a field type at about a third of the ground, not sprinkled at…"
  ],
  "motion": [
   "Shapes may be simple; motion may not. Everything eases. Vehicles accelerate, brake and nod; turns follow smooth curves, never polylines",
   "All natural motion is procedural and looping: water, trees, cloud shadows, leaves, snow, smoke, flocks. Every object has its own phase; nothing marches in step",
   "People are distant decoration: small, walking a cycle, flying a kite, rowing. No close-ups, no acting, no hand business"
  ],
  "camera": [
   "Prefer one continuous take, slow enough that the viewer can stop and look at any corner. When a long take must hold a composition, ease the camera…",
   "Transitions: only three — the frame draws in and grows out again; a wave sweeps across (colour, light, season); the ground is cut open (the Cutaway…"
  ],
  "sound": [
   "Warm, gentle and continuous: piano, Rhodes-like electric piano, marimba, celesta, music box, soft synth bass, a warm pad, brushes and…",
   "One piece, not a medley: when the place changes (a season, day to night), keep the same harmony and tempo and change only how thick the…"
  ]
 },
 "microgame": {
  "name": "Microgame Frenzy",
  "cat": "Games",
  "line": "A clumsy cadet survives a five-second boot camp, faster and faster, until the boss: landing home.",
  "uses": [
   "Game trailers",
   "Onboarding",
   "Social shorts"
  ],
  "quote": "A rapid-fire party-game film: one command word, a few seconds, one action. Every microgame is drawn in a completely different art style, and the film keeps getting faster.",
  "essence": "Each microgame uses a different visual medium (crayon, ink wash, terminal, risograph, pixel, blueprint, Swiss type, clay, cut paper, woodcut…). The jolt of each switch is both the joke and the beat One fixed home look holds the film together: a show stage with a host, a lives counter and a stage number, which the film returns to between games",
  "nots": "Game Show Flat (one art style, rounds of bars, call-and-response), not a style sampler reel (every game has stakes; lives connect them), not a montage (each game has a rule grasped in under a second).",
  "material": [
   "Each medium is a simplified re-drawing, 100–200 lines of code, built around one channel trick that makes it read at a glance:",
   "print media store plate densities (riso: a channel per plate, additive overprint, halftone, misregistration)",
   "technical media are line systems (blueprint: line weights and dimensions; Swiss: a strict grid, one sans, one signal colour)",
   "Hero translation: the hero is redrawn from scratch in each medium, but the same marks always survive (e.g. a hat shape, one coloured dot, a number on the chest). Make a…"
  ],
  "colour": [
   "The home stage owns a saturated party palette: a deep ground behind a rotating sunburst, two or three loud accents, plus a fixed success colour and a fixed…",
   "Each medium brings its own palette from its tradition (wax colours, one-ink-plus-vermilion, amber phosphor, three riso plates, a limited pixel palette,…",
   "One accent follows the hero across media where the medium allows (a single vermilion dot in ink, an inverse glyph in a terminal, a signal-red circle in Swiss…"
  ],
  "motion": [
   "Five things accelerate together at each speed-up: tempo, game length, stage dwell, command hold, character frame rate",
   "The timer is visible and on the beat: e.g. a fuse with one knot per beat, the spark passing each knot exactly on it. It freezes in a replay",
   "Unified transition through the frame-within-the-frame: push into the screen to start a game (~0.25 s), shrink the game back into it to return (~0.33 s) with a…"
  ],
  "camera": [],
  "sound": [
   "Music first: a tempo grid and a cue table before any animation; every picture hit lands on a listed cue",
   "A constant groove + one colour instrument per medium. The groove (kit with ghost notes, slap or synth bass, brass stabs, keys) runs…"
  ]
 },
 "microscope": {
  "name": "Microscope Story",
  "cat": "Evidence Films",
  "line": "One continuous move from a liver slide to a single nucleus; two circles, counted pixel by pixel, differ 2.4 times in blue.",
  "uses": [
   "Biomedicine",
   "Materials science",
   "Skincare science"
  ],
  "quote": "Real, licence-clean microscopy of a real specimen, seen as it is, and one continuous change of scale that carries the viewer from the glass slide in the hand to a single cell. Focus breathes when the magnification changes, a focal plane sweeps when the camera lands, and every scale bar, field of vie",
  "essence": "The specimen is a photograph: a real micrograph or whole-slide scan of the actual sample, CC0, public domain or CC BY. Nothing on the specimen is drawn, retouched or generated. A whole-slide image is the ideal… Scale is the camera: one log-space dive (and, when the story wants it, the climb back) through nested plates of the same sample. The scale bar shortens and jumps in a 1-2-5 sequence, the field-of-view readout…",
  "nots": "Satellite Briefing (no grey grade; the stain keeps its colour), not Sci-fi HUD (no glowing wireframes or crosshairs), not Data Storytelling (no chart paper), not a keynote (no slides or header bars).",
  "material": [
   "Plates: the WSI pyramid levels as plates in one world frame (level-0 pixels), the coarse levels whole and alpha-feathered at the scan edge, the fine levels as crops…",
   "The naked-eye plate: the scanner's own photo of the whole slide (many WSI files carry one), registered through the scan's area-of-interest metadata and checked against…",
   "One grade for every plate: glass normalised to a warm white, a little density and chroma in the stain, nothing else. No false colour, no film emulation",
   "The bench: graphite under a slow pool of light; a soft shadow under the slide"
  ],
  "colour": [
   "Glass: warm paper white. Bench: graphite. The stain is evidence and keeps its true colour (e.g. trichrome red and blue, H&E pink and purple)",
   "One accent, cool and away from the stain's hues (mint against red and blue; amber against a green or purple stain), only for the measured reading and the…",
   "Ink on glass is near-black; type on stain sits on a frosted panel in warm white"
  ],
  "motion": [
   "Magnification changes happen where the plates actually change, each with a breath of focus, a turret click and the new magnification said once, large",
   "Marks arrive by being made: a dimension line grows from its centre, a circle is drawn as an arc, a scan front counts pixels while the reading rolls, the…",
   "Never moves: the specimen under its marks, the instrument positions"
  ],
  "camera": [],
  "sound": [
   "Instrument foley: the objective turret (a click, a detent, a small metal ring), a focus servo, pen on glass for each line drawn, a…",
   "Music: hard-mallet vibraphone in 8ths and 16ths, marimba ticks, bowed vibraphone and water glasses for pads and the motif, glockenspiel for…"
  ]
 },
 "midcentury-toon": {
  "name": "Mid-century Cartoon",
  "cat": "Cartoon & Anime",
  "line": "A robot vacuum set up in three steps, told like a 1950s classroom film.",
  "uses": [
   "Set-up guides",
   "Help centres",
   "How-to"
  ],
  "quote": "1950s flat colour and limited animation for \"follow along\" films: colour printed a few pixels off its broken ink line, bodies that hold still while hands do the work, abstract colour-block rooms, a calm classroom narrator, and a cool-jazz combo.",
  "essence": "People and things are geometric: egg or bean heads with the nose part of the face outline, simple garments in two or three flat colours, four-finger cartoon gloves. A presenter's body is a held drawing: only arms, hands, eyes and mouth animate. Rooms are not drawn: a scene is one colour plane, a floor band, a horizon line with gaps, and one or two props.",
  "nots": "the 1930s rubber-hose cartoon (no black-and-white, no bouncing world, no hot jazz). Not a whiteboard explainer: it shows how to do, not why. The pictures are printed, not written on.",
  "material": [
   "Shading: one flat darker plane clipped inside a shape, never a gradient. Drop shadows are a copy of the shape offset down-right in a paper shade at ~50 %",
   "Ornaments: 4-point atomic sparkles, 8–18-point starbursts, sunburst rays (~30 wedges, semi-transparent), boomerang and kidney shapes, polka dots",
   "Grain: light; print, not film"
  ],
  "colour": [
   "A warm paper ground, a warm near-black ink, soft atomic-age complements. Nothing pure or neon",
   "One ground colour per scene: a lighter tint for walls, a darker shade for floors. Never place the product on its own colour, never the presenter on their own…",
   "The product keeps one colour through the whole film; the accent (a presenter's garment, stars, bullets) is a different hue. Step grounds rotate through the rest"
  ],
  "motion": [
   "Pop-ins: medallions, tags, labels and titles scale in with a back-ease (~0.25 s, strong overshoot)",
   "Reaching the floor: a kneel pose with 2-bone IK keeps the hands on the object while it moves; never stretch standing arms"
  ],
  "camera": [],
  "sound": [
   "Music: an original West-Coast cool-jazz combo: flute or muted trumpet, vibraphone (chords, arpeggios, glissandi, tremolo), pizzicato…",
   "Silence as a tool: cut everything, ambience included, for the beat before the most important action, so the first sound after it (the…"
  ]
 },
 "news-package": {
  "name": "Broadcast News Package",
  "cat": "Edit & Documentary",
  "line": "Four AI stories from one week in a full on-air package: rundown, headline strap, price board, spec card.",
  "uses": [
   "News round-ups",
   "Bulletins",
   "Market updates"
  ],
  "quote": "A television newsroom's on-air package, built entirely in code: a sting that becomes the channel bug, a rundown of today's stories that opens and closes the bulletin, a lower-third strap that never leaves the bottom of the frame, and full-frame graphics (split-flap price boards, a line breaking a th",
  "essence": "Not Caption News (that is captions-first social video: huge slammed captions are the lead, no rundown, no strap; here type is small and orderly and the graphics lead). Not Data Storytelling (one chart per beat, never a dashboard; the chart is an insert in a bulletin). Not a keynote: no centred title-and-bullets, no page turns. Not a studio show: no virtual set, no anchor, no fly-throughs — the package is flat…",
  "nots": "Caption News (that is captions-first social video: huge slammed captions are the lead, no rundown, no strap; here type is small and orderly and the graphics lead). Not Data Storytelling (one chart per beat, never a dashboard; the chart is an insert in a bulletin). Not a keynote: no centred title-and",
  "material": [
   "Wikimedia Commons: CC0, public domain or CC BY (credit author, title, licence on the end card and in CREDITS). Not used: CC BY-SA, \"no known restrictions\", unclear…",
   "U.S. federal agencies: public domain; check the page does not credit a contractor or third party",
   "Internet Archive: only items whose page states public domain, CC0 or CC BY; U.S. works published before 1931 are public domain",
   "Library of Congress / national archives: read each rights statement; \"no known restrictions\" is not enough"
  ],
  "colour": [
   "Structure to keep when you change the brand: one accent + one gold-like secondary + paper + ink, and a reserved alarm colour. Ink text on the accent; on paper, English secondary lines in a dark olive (#6E5A1E) because gold is too weak…"
  ],
  "motion": [
   ""
  ],
  "camera": [],
  "sound": []
 },
 "newsreel": {
  "name": "1920s Newsreel",
  "cat": "Edit & Documentary",
  "line": "1926: the papers say the Charleston will ruin America's knees; at Ford's own picnic the kids dance it anyway.",
  "uses": [
   "History stories",
   "Fads & eras",
   "Anniversaries"
  ],
  "quote": "A sound newsreel of the late 1920s, cut from real archive material: a searchlight-and-globe ident with a brass fanfare, a newspaper that spins into the lens, a fast and cheerful announcer on an optical soundtrack, place-and-date cards, maps, magazine pages and documents, wipes, flips and irises, and",
  "essence": "An edit style: the look is in how real material is arranged, cut, captioned and carried by sound, not in a drawing technique. - Archive in a projected gate: 1.37:1 picture, full height, rounded corners, black outside; everything inside it shares one silver grade, gate weave, flicker, scratches and dust. - News objects do the explaining: newspapers, magazine pages, books, telegrams, maps, records. They are filmed…",
  "nots": "silent-film (1920s Silent Film, in this library): that style is a drawn, inked comedy projected between velvet curtains, with intertitles instead of voices, a cinema pianist and no foley. Here nothing is drawn but the packaging; the footage and print are real; somebody always speaks; the soundtrack ",
  "material": [
   "Print: newspapers, magazines and books at their scan resolution; crop pages to the relevant fold so unrelated (and sometimes ugly) old stories never come into view",
   "Code-drawn packaging only: the ident (sunburst, two searchlights, wire globe), item title cards, maps, the end card. Never generate \"archive\" pictures"
  ],
  "colour": [
   "Monochrome warm silver for the picture; values do the work (check every shot as a thumbnail)",
   "No colour accents, no sepia wash on top of the silver, no colourised archive"
  ],
  "motion": [
   ""
  ],
  "camera": [],
  "sound": [
   "Counter-music: when the story has two sides, give the other side its own band (here an old-time reel: fiddle, plucked dulcimer, upright…",
   "Foley for every move: carbon-arc snap, rising whoosh with flutter for the spinning paper, thump + paper slap, telegraph clicks under a map…"
  ]
 },
 "one-line": {
  "name": "One-line Drawing",
  "cat": "Hand-drawn & Painting",
  "line": "One unbroken line draws a whole life, then the pen passes to a child.",
  "uses": [
   "Brand stories",
   "Life milestones",
   "Minimal ads"
  ],
  "quote": "A single ink line that never leaves the paper. Everything on screen is that one line being drawn; scenes don't cut, they morph.",
  "essence": "Not a whiteboard explainer (no hand, no marker, no erasing, no text-heavy boards), not ink wash (no tones, no brush bloom as a look), not a line-art animation with cuts and many strokes.",
  "nots": "a whiteboard explainer (no hand, no marker, no erasing, no text-heavy boards), not ink wash (no tones, no brush bloom as a look), not a line-art animation with cuts and many strokes.",
  "material": [
   "The line's character can change along the path (base width, alpha, tremble, dryness); blend over a short stretch at boundaries",
   "Ink bleed: the same polygon slightly wider, blurred on an offscreen layer, composited at ~20 %",
   "Pooling: extra round dots where speed drops low",
   "Tremble (perpendicular noise) and dry-brush gaps (long-scale noise + thin bristle strands) for age, fear or fatigue"
  ],
  "colour": [
   "Ink on paper. A warm black (around #1D1A17) on warm white; nothing else fills the frame",
   "One accent at most, used once, on a stretch of the line that means something; it returns to ink afterwards and stays visible in the final picture if the…",
   "Examples of an accent's job: red for love or danger; blue for water or cold; gold for money or a prize. Never a second accent"
  ],
  "motion": [
   "Corners (speed minima at high turn) can be exported to the soundtrack as candidate note onsets",
   "Speeds: ~300–700 units/s for travelling lines, ~50–150 for small details. The most important stroke is usually the slowest",
   "Retracing over an existing line is legal and invisible (it only thickens slightly)"
  ],
  "camera": [],
  "sound": [
   "Silence is literal: zero the music bus including reverb tails; drop room tone",
   "Mix: music ducks ~5 dB and the pen ~4 dB under voice; −14 LUFS; grain 0 (the paper is in the render)"
  ]
 },
 "paper-lantern": {
  "name": "Paper-cut Lightbox",
  "cat": "East Asian Traditions",
  "line": "An old night train makes its last run, from a snowy mountain halt through a long tunnel to the sea, its lit windows going out one by one at the end of the line.",
  "uses": [
   "Journeys and travel",
   "Farewells and anniversaries",
   "Places and their stories"
  ],
  "quote": "A layered paper-cut shadow box (纸雕灯) lit from behind: 6–9 sheets of cut card stacked in a shallow box, a warm light glowing through the paper, windows and moons burning through holes, soft shadows falling from each layer onto the next. The camera is a macro lens inside a lamp: it can show the box, o",
  "essence": "1. A paper layer: a flat cut sheet, one flat colour, fibre grain, a thin warm rim of light on its top edge and a dark band on its bottom edge. Back layers lighter and cooler, the front almost black: that value ladder is the depth. 2. Light through paper: a warm, cloudy translucency (pulp mottling), strongest near the light source. Windows, lanterns, trails of light are holes / emissive windows that burn and bloom.…",
  "nots": "flat paper-cut animation (here: depth, backlight, cast shadows), not shadow puppetry (no single screen, no rods), not a 3D diorama (every element is a flat sheet parallel to the box front).",
  "material": [
   "Lens: shallow depth of field, bloom, a gentle vignette; supersample 2× so cut edges stay crisp",
   "Real-world set (when used): wood frame, black lining, a dark room, an area light as the box's spill onto real objects"
  ],
  "colour": [
   "Back layers bright and translucent, front layers dark and opaque. Each layer is one flat colour; the ladder of values from back to front is the depth. Never…",
   "One temperature per stack, chosen by the scene (cool night, warm interior, violet or green elsewhere). Changing ladder is how the film says \"another place\"",
   "Light is warm (amber to gold) against the stack, and it is the only saturated element besides one accent"
  ],
  "motion": [
   "Everything moves like paper on a stick: layers slide (x/y), rotate about a pivot, scale in from 0 along one axis (\"written out\"), or light up. No squash and…",
   "Figures are optional. A film can tell its story with lit windows, vehicles, lamps and objects, and have no figure at all. When it has figures, they are jointed…",
   "Hard action lands on spoken words (use whisper word timings): an object slams, a character flashes, a light arc grows on its word"
  ],
  "camera": [],
  "sound": [
   "Instruments that sit like light behind paper: felt piano, music box, celesta, harp or plucked zithers, bamboo flutes, soft strings; a solo…",
   "Foley is paper and light: switch click + rising shimmer when a light turns on; paper rustle and slide; card-stock tap; lid thud; chimes on…"
  ]
 },
 "paper-popup": {
  "name": "Paper Pop-up Book",
  "cat": "Materials & 3D",
  "line": "A pop-up book opens on a desk; a sprite named Pip adventures through paper worlds and jumps out into ours.",
  "uses": [
   "Children's books",
   "Game trailers",
   "Story films"
  ],
  "quote": "A pop-up book on a real desk becomes a stage: flat cut-paper actors with white borders perform in front of paper sets that spring up from the page, under real lamp light and a real macro lens.",
  "essence": "Two worlds in one frame. The real world at human scale: a photoreal surface lit by an HDRI room, a few real objects, a macro lens (shallow focus, warm practical light, soft contact shadows). The paper world: a hardcover book in that room; when it opens, one board stands up as the backdrop and the lower page is the ground. Every set piece is a flat cut-paper card that lies on the page and pops up around its bottom…",
  "nots": "a papercut silhouette film (no one-colour lace, no backlight), not a 3D cartoon (nothing modelled round), not claymation (paper hinges, folds, curls and slides; it never squishes).",
  "material": [
   "Real units (metres): page 0.3–0.5 m wide, actors 3–5 cm, near plane a few mm, so HDRI, shadows and depth of field behave like a real macro shot",
   "Pop-up pieces: planes with art on the front and plain paper on the back (same alpha); alphaTest + alphaToCoverage; a custom depth material with the alpha map so the…",
   "The book is modelled: cloth cover with foil title (roughness/metalness map), page block with edge lines, a curling leaf",
   "Real world: HDRI environment and softly blurred background, real wood or fabric, a few CC0 props. Neutral tone mapping (ACES shifts paper colours)"
  ],
  "colour": [
   "Saturated children's-book colour, never neon; the real world stays natural and slightly warm so paper pops against it",
   "One dominant hue family per spread, so a page turn is also a colour change; a few accents (a red, a yellow, a gold) recur across spreads to stitch the book…",
   "Ink dark brown, border off-white, card backs plain paper"
  ],
  "motion": [
   "Pop-ups rise back to front (delay grows with distance from the reader), far pieces lying back, near ones folding forward face-down; they fold down in the same…",
   "Plants and light props sway a few hundredths of a radian around their base",
   "Characters are flat cards redrawn per quantized pose (walk phase, arms, eyes, mouth, look, blink); walk phase follows distance walked, so feet don't slide"
  ],
  "camera": [],
  "sound": [
   "Paper foley is the signature: page swish, cardboard thump, pop-up snap (short sine sweep + crinkle), fold and crease, pull-tab slide,…",
   "Character voices as typing blips: one waveform and pitch range per character, a blip every other letter"
  ]
 },
 "papercut-red": {
  "name": "Red Paper-cut",
  "cat": "East Asian Traditions",
  "line": "On New Year's Eve the beast Nian comes to town, and one girl's giant paper-cut lights up the village to scare it off.",
  "uses": [
   "Lunar New Year",
   "Festive greetings",
   "Folk tales"
  ],
  "quote": "Chinese window-flower paper-cuts brought to life: jointed red cut-outs on paper grounds, where the cut is the drawing and the holes are where the light gets in.",
  "essence": "Not shadow puppetry: no light behind a screen, no translucent dyed hide, no rods. Here the paper is front-lit and opaque; backlight is a special event you save for the moment that needs it. Not flat vector art (no strokes, no gradients), not a silhouette film (every shape's interior is cut).",
  "nots": "shadow puppetry: no light behind a screen, no translucent dyed hide, no rods. Here the paper is front-lit and opaque; backlight is a special event you save for the moment that needs it. Not flat vector art (no strokes, no gradients), not a silhouette film (every shape's interior is cut).",
  "material": [
   "Paper grain: a neutral-grey texture in soft-light inside each piece (dye mottling, fibres, specks), then the piece's alpha restored with destination-in, so holes stay…",
   "Paper thickness: each piece casts a tight soft shadow on the layer below; stacked folded paper shows 2–6 offset darker edges",
   "Figures: red block + yin lines. Every figure piece gets an inset contour (a thin slit a few units inside the outline): the classic double outline, which also separates…",
   "No floating islands. A closed ring cut would drop its centre out of real paper. Eyes are two crescents (upper and lower lid) that leave bridges, plus a pupil hole"
  ],
  "colour": [
   "China red (around #d2201f, range #c8102e–#d7261e) is the hero material. Depth and role are shown by paper tones one step apart, not by shading: near pieces one…",
   "Ground and hero must be different paper families. If background and hero are both red, the silhouettes stop popping. At night, all background layers are one…",
   "Gold foil is an accent kept for one late moment (a sun, a title, a coin); never a second main colour"
  ],
  "motion": [
   "In profile, a raised near arm crosses the face: keep hands forward of the face or let a prop cover them",
   "Cutting: the pattern is revealed through a mask of circles along the scissor path; the offcut drops once the outer edge is passed; blades open and close on a…",
   "Unfolding: successive unfolds a fraction of a second apart, each flap swinging from folded to flat with ease-out (the \"pa!\" snap), then a scale bump and warm…"
  ],
  "camera": [],
  "sound": [
   "Mix to −14 LUFS, no film grain (the paper fibres are the texture)"
  ]
 },
 "pictogram-motion": {
  "name": "Pictogram Motion",
  "cat": "Graphic & Type",
  "line": "A yellow umbrella left on a bus waits out a sunny day on the lost-property shelf, then opens with 312 others when the storm comes back: objects, vehicles, weather and signs as beat-locked geometric pictograms.",
  "uses": [
   "Public services and city stories",
   "Brand and event identity films",
   "Explainers told through signs and objects"
  ],
  "quote": "A beat-locked film built from three things only: a square-grid \"core graphic\" of circles, half-discs and tiny patterned cells whose rows slide past each other; geometric pictograms (objects, vehicles, weather, signs, and a disc-headed figure when one is needed) made of round-capped bars, discs and c",
  "essence": "What makes a frame read as this style at a glance: 1. The grid pattern: big discs and half-discs spanning square cells, about half the cells carrying a small motif, all in five tones of one hue, with whole rows cut and shifted sideways: the signature that drives backgrounds and transitions. 2. The pictogram set: objects, vehicles, weather and signs, and a human figure only when the film needs one, all flat and built…",
  "nots": "an isometric infographic (no depth, no 3D), not Swiss motion graphics (the pictograms and the pattern carry as much as the type), not a cartoon (pictograms never emote, figures have no faces), not a data film (numbers are labels, not charts).",
  "material": [
   "Pattern model: fill with a mid-dark tone; on grid nodes randomly place cell-radius discs in random tones and discs-with-inner-discs; then a fraction of cells get one…",
   "Stage: the hero pictogram (any object or figure) sits on a large sun disc in a neighbouring tone, crossed by one faint light sweep"
  ],
  "colour": [
   "Under type the pattern runs at low contrast; on chapter cards at full contrast",
   "Light hues take dark type and dark figures, and their disc uses the lighter tone; dark hues take cream. On the dark neutral, the disc uses a lighter tone or it…",
   "One cream and one ink serve every hue. No outlines, no highlights except the sweep"
  ],
  "motion": [
   "A grid of time: pick one tempo for the film; every shot starts on a beat and every key action in a pose (release, contact, landing) lands on an integer beat",
   "Pace ladder: normal cards last one bar; related sub-items become half-length rapid-fire runs. A second tempo comes from dividing the beat, never from changing…",
   "Easing: exponential ease-out for entrances, exponential in-out for whips and wipes; a back ease once at most"
  ],
  "camera": [],
  "sound": [
   "Type and music can carry the film alone; a voice is optional, calm, one or two lines per chapter",
   "Percussion is the spine: choose a drum family that suits the topic (frame drums, taiko, marching snares, steel pans, body percussion, an…"
  ]
 },
 "pixel-rpg": {
  "name": "16-bit Pixel RPG",
  "cat": "Games",
  "line": "At the final boss door a hero saves the game, and the save screen replays the whole journey.",
  "uses": [
   "Game trailers",
   "Recaps",
   "Nostalgia"
  ],
  "quote": "A short film that looks, sounds and behaves like a mid-90s console role-playing game: 320×180 pixels, a limited indexed palette, text boxes that type, menus, save files, chip music with echo.",
  "essence": "Not HD-2D (no depth of field, bloom or real-time light), not CRT nostalgia (no scanlines, no grain), not a parody.",
  "nots": "HD-2D (no depth of field, bloom or real-time light), not CRT nostalgia (no scanlines, no grain), not a parody.",
  "material": [
   "Master palette of ~32 colours (a free palette such as ENDESGA-32), plus protected duplicates of a few indices that no palette effect touches",
   "Dither: 4×4 Bayer for gradients and glows; light shafts as a flat 50 % checker with a 25 % edge",
   "Portraits 32×32, 3/4 view, base face + eye/brow and mouth overlays; they carry facial acting (the sprite face has one eye pixel)",
   "Props can be flat-shaded 3D shapes quantised to a few protected indices (e.g. a rotating crystal at 8 frames per 90°)"
  ],
  "colour": [
   "Protected indices: a few colours exempt from every effect become the thread through the film and allow match cuts between eras. Use one or two; more and they…",
   "Warm hues survive reductions: keep orange, pink and plum in reduced subsets, or the first step turns a scene solid red",
   "Example uses of protected colours: a red kite across a childhood; a gold coin in a grey economy; the green of one plant in a faded city"
  ],
  "motion": [
   "Output 24 fps. Sprites step at 8 fps (walk) to 12 fps (flames, blinks); camera and parallax move on ones at integer pixels",
   "Game-native acting: hop forward to act, cast pose, knockback recoil, kneel, KO blink (12 fps on/off) and vanish; breath = shoulders up 1 px",
   "UI motion: windows slide in over ~0.3 s (ease-out, integer px); a hand cursor bobs 1 px at 4 fps and stops when the character hesitates"
  ],
  "camera": [],
  "sound": [
   "Chiptune voices: pulse waves at 12.5/25/50 % duty, 4-bit triangle bass, LFSR noise drums, wavetable leads, SNES-style echo (a few taps…",
   "Techniques (options): regional variations of one motif; the arrangement losing one layer per palette step; a key change or the full band…"
  ]
 },
 "printed-long-take": {
  "name": "Printed Long Take",
  "cat": "Print & Printmaking",
  "line": "Red-crowned cranes in a Hokkaido valley, one scratchboard take, counted back from 33 to 1,927.",
  "uses": [
   "Journeys",
   "Wildlife",
   "Landscapes"
  ],
  "quote": "A three-dimensional world rendered as a scratchboard print, ink and paper with one red, crossed by one unbroken camera move. Depth, weather and light are all cut lines; the camera travels through the print instead of the print being turned page by page.",
  "essence": "Only ink, paper and one red. Every value is either ink or paper; grey exists only as a density of lines. One red is reserved for one small subject. A warm yellow may appear for the sun, a lamp or one material,… Tone is cut, not shaded. Shadow sides of hills carry knife lines that run down the fall line; skies are parallel horizontal cuts whose width makes the light; snow is paper with a few drift strokes; water is…",
  "nots": "woodcut (flat printed blocks, a mostly static camera, one block per image). Not ukiyo-e (flat colour fields, no depth travel). Not a toon-shaded 3D game (no smooth shading, no gradients, no specular). Not a pencil sketch (no hatching that follows form loosely; every line is a knife cut with a blunt ",
  "material": [
   "Two kinds of field. Every surface is either a paper field carrying ink cuts (lit faces, snow, sand, cloud, foam, steam) or an ink field carrying paper cuts (shadow…",
   "Faceted terrain: mountains and volcanoes are low-poly cones with flat facets. Lit facets are paper with a few fine ink cuts near the terminator; shadow facets are ink…",
   "Water is a ribbon cut into the snow (the ground is discarded inside a river mask), with bank walls and a paper snow lip. Ripples are short cuts across the flow, faded to…",
   "Print pass (screen space): paper fibre, ink mottling in the darks, soft grey blotches near the top of the sheet, a two-frame flicker, a light vignette. Nothing else…"
  ],
  "colour": [
   "Two values carry everything: ink (a warm black) and paper (a warm off-white). Never pure black or pure white, never a third grey fill",
   "A warm yellow is allowed for light itself (sun disc, its road on water, warm cuts in a dawn sky, a lamp) and one material at most. It never fills a large area…",
   "Value order by depth: far mountains paper with ink shadow facets; forest bands solid ink; the middle ground paper; foreground ink silhouettes. Keep the subject…"
  ],
  "motion": [
   "Easing: long monotone curves; the camera keeps momentum through key positions and decelerates into every hold. No bounce, no shake except one frame for an…",
   "Animals are flat silhouettes with three or four poses per action (sleep, wake, call, peck, walk, run, three wing frames, land, leap, bow). Wings cycle on fixed…",
   "Steam, snow and splashes are paper marks: horizontal cut wisps, square stabs, short arcs"
  ],
  "camera": [],
  "sound": [
   "Three layers. The world: the matter of the place (water under ice, frost cracking, wind in three weights, wings, steps on snow, small…",
   "Timbres that suit the medium: bowed vibraphone, harp, horn, low strings, pizzicato bass, xylophone, glockenspiel, timpani. Avoid synth pads…"
  ]
 },
 "risograph": {
  "name": "Risograph Print",
  "cat": "Print & Printmaking",
  "line": "A Sunday-morning bike ride through the city — bakery, park, riverside — each stop adding an ink until three misregistered plates overprint.",
  "uses": [
   "Indie brands",
   "Zines",
   "Lifestyle"
  ],
  "quote": "Animation that looks printed, frame by frame, on a stencil duplicator: two or three translucent spot inks overprinted on warm paper, halftone dots, ink grain, and plates that never quite line up.",
  "essence": "A risograph prints one colour at a time: each colour is its own stencil (\"plate\") with its own drum of translucent ink. That one fact makes the look:",
  "nots": "flat vector art with a noise overlay (every colour comes from the plates), not CMYK pop-art halftone (no process colours, no keyline), not screen-print posters (riso ink is translucent and grainy, not opaque). Never show the RISO brand, logo or machine trade dress; ink names are colour references on",
  "material": [
   "grain on the dot threshold, pinholes in solids, density varying with a feed-direction streak and a slow blot noise",
   "dots anchored to the paper (screen), not to objects: a pan slides the image under a fixed screen, as if each frame were printed anew",
   "a per-plate gate and a roller sweep (moving edge, slightly heavier ink band) let a plate arrive mid-shot",
   "Composition rules"
  ],
  "colour": [
   "2–3 spot inks, never more, plus paper; every other colour is an overprint or a tint. No gradients except stepped halftone",
   "Pick inks whose pairs mix into useful colours; at least one must carry a silhouette alone",
   "Paper is warm off-white (around #F4EEE2), never pure white; paper white is a colour too (knockouts, highlights, subtitles)"
  ],
  "motion": [
   "Grain boils partly (about a third re-rolls per print); sheet streaks and blots change only at cuts",
   "Simple cycles on few drawings; secondary motion (scarf, flag, tail) as a travelling sine wave"
  ],
  "camera": [],
  "sound": [
   "Instruments, as options: warm, dry, handmade, slightly lo-fi: upright or electric bass, vibraphone or marimba, nylon guitar, whistled or…",
   "Layering like plates (an option): each new plate brings one instrument, and they can leave one by one"
  ]
 },
 "rubber-hose": {
  "name": "1930s Rubber Hose Cartoon",
  "cat": "Cartoon & Anime",
  "line": "A coffee cup chases a runaway sugar cube around the kitchen, 1930s-cartoon style.",
  "uses": [
   "Food & drink",
   "Retro ads",
   "Kids"
  ],
  "quote": "Black-and-white hand-inked cartoons where every object is alive and swings to a hot jazz band.",
  "essence": "",
  "nots": "a 1950s flat cartoon (no limited animation, no colour, no graphic backgrounds), not a silent film (the synchronised music is the engine), not a \"retro filter\" over modern animation (no joints, no rendered shading).",
  "material": [
   "Limbs: noodle tubes of constant width (about 1/20 of the character's height), one smooth bend, round caps",
   "Gloves: palm + 3 fat fingers + thumb, flared cuff with a fold line, 3 stitch lines on the back. Outline the union only (stroke all parts thick first, then fill all)",
   "Mouths: smile with cheek ticks, open grin, \"O\", wavy (scared), pucker, tongue-out. Shoes: big black ovals with a white toe glint",
   "Object characters: the face sits on the body; a secondary feature carries the mood (steam, a flame, a lampshade tilt, a spring). A box-shaped object is a real projected…"
  ],
  "colour": [
   "Strictly greyscale: about 6 grey steps plus a separate character white. No hue anywhere, not even in the film damage",
   "Form shadow is one light-grey band, never a gradient",
   "Examples of the grey ramp's temperature: warm paper greys (our demo); cool silver-nitrate greys; a faint sepia print. Pick one and keep it for the whole film"
  ],
  "motion": [
   "Anticipation–hold–action: before every big move, crouch (squash to ~0.8), hold (let the band stop), then snap. Impacts get a squash with an exponential…",
   "Held frames are acting: a chain of holds, each glance on an eighth note with a woodblock tick, reads as thinking",
   "Freeze on a band stop: when the music stops, freeze everything, background breathing included"
  ],
  "camera": [],
  "sound": [
   "1930s hot dance band / ragtime: stride piano, clarinet, trumpet (open + plunger-mute \"wah-wah\"), trombone (smears), tuba oom-pah, banjo on…",
   "Mickey-mouse the score, as options: a band member \"answering\" a character (trombone raspberry, trumpet laugh); a stop (hard silence, reverb…"
  ]
 },
 "satellite-briefing": {
  "name": "Satellite Briefing",
  "cat": "Evidence Films",
  "line": "A satellite follows the map to the Aral Sea and finds a desert; only the part someone dammed came back.",
  "uses": [
   "Climate",
   "News explainers",
   "Geography"
  ],
  "quote": "Real satellite imagery of a real place, graded down to an analyst's grey, with thin white measurement lines drawn on the ground: a lock-on reticle, outlines, a range line, one reading. One continuous zoom built from stacked imagery plates carries the viewer from orbit to the ground and back, and tim",
  "essence": "The ground is a photograph: real, licence-clean, georeferenced satellite or aerial imagery of the actual place. Nothing on the ground is drawn, stylised or generated Two layers, two truths: the imagery is what the satellite saw; the hairlines are what the analyst measured. Marks are thin, white, sparse, and sit on real coordinates",
  "nots": "Data Storytelling (a chart on paper), not Sci-fi Hologram HUD (no glowing wireframes or invented chrome), not Blueprint, not Isometric Infographic (real nadir or oblique views, no diorama), not a keynote (no slides, header bars or chapter numbers).",
  "material": [
   "Screen space only for instruments (altitude, scale bar, imagery credit) and the transcript strip. Everything else is anchored to the ground",
   "Post: light grain in ffmpeg, a vignette, directional blur only on whip pans"
  ],
  "colour": [
   "Neutral ground: grey, roughly 3–65 % in value. White means measured",
   "One accent (warm, e.g. amber) for the single reading on screen, never decoration",
   "A second hue may mark the claim the imagery tests (a map, a plan, a promise): flat, cartographic, never used for anything measured"
  ],
  "motion": [
   "The camera never stops: distance interpolates in log space, segments ease, holds keep a 2–5 % creep or a slow rotation. No frozen frame longer than a second",
   "Marks arrive by being made: a line grows, an outline prints behind the scan, a counter rolls and lands with a small pop, a reticle snaps with overshoot",
   "Time changes are scans, never dissolves; their spacing tells the speed, and the camera moves with them (accelerating as the steps shorten, braking on the last)"
  ],
  "camera": [],
  "sound": [
   "Telemetry: FM pings (a lock-on ping worth bringing back), dry ticks on the grid that divide to accelerate, noise scans (rising for a…",
   "Weight: timpani, bass drum, gran cassa, bowed cymbal, a tam-tam reversed when time runs backwards. Measurements land on a pitched hit"
  ]
 },
 "scifi-toon": {
  "name": "Sci-Fi Sitcom Toon",
  "cat": "Cartoon & Anime",
  "line": "A jaded genius opens a portal just to buy coffee and tumbles through ever-stranger universes.",
  "uses": [
   "Comedy",
   "Tech brands",
   "Social shorts"
  ],
  "quote": "Adult-animation sci-fi sitcom: thick boiling outlines, flat colour, a duo whose reactions don't match, a glowing portal, and one palette per world.",
  "essence": "Copyright red lines (non-negotiable): Never reproduce any existing show's characters, silhouettes or colour combos (e.g. a spiky-blue-haired old man in a lab coat + a kid in a yellow shirt), names, catchphrases, burp gags, logos, or the look of…",
  "nots": "a kids' cartoon (dry humour, long pauses), not anime (no sparkly eyes), not a vector explainer (lines boil).",
  "material": [
   "Fill: flat colours only. Shadows are hard-edged darker shapes clipped inside the fill (one per form, away from the light). Glows are 1–2 flat translucent rings, not…",
   "Cast design: silhouettes must read in solid black. Give each lead one absurd costume idea. Avoid white lab coat + spiky hair",
   "Creatures: every world may get one creature that is disgusting and adorable; keep it non-verbal (sound effects) so the film stays a dialogue between the leads. Check…",
   "The portal (or whatever device moves between worlds): the only thing that glows. A lumpy rim with a thick outline, rotating spiral arms, a pale core, orbiting sparks,…"
  ],
  "colour": [
   "One palette per world, 3–5 colours, maximally different from the previous world in hue and value, so the audience reads \"we jumped\" from colour alone",
   "Line colour and eye white never change between worlds; everything else may",
   "Glow colour belongs to the travel device only: nothing else in any world may use it"
  ],
  "motion": [
   "Acting over moving: held poses with small changes (eye twitch, pupils sliding, a gulp, sweat drops). Idle life: breathing (±1 % squash), a nod driven by speech…",
   "What never moves in a cold pause: everything but the boil"
  ],
  "camera": [],
  "sound": [
   "Synthesized score, no samples needed. A theremin-like lead (sine + a little 2nd/3rd harmonic, legato portamento ~70 ms, vibrato fading in…",
   "Genre cues per world (options): surf guitar; polka accordion; toy-piano lullaby; elevator bossa (Karplus–Strong nylon guitar); brushed…"
  ]
 },
 "shadow-puppet": {
  "name": "Shadow Puppetry",
  "cat": "East Asian Traditions",
  "line": "Ten suns scorch the earth until the archer Hou Yi draws his bow, told with leather puppets on a lit screen.",
  "uses": [
   "Myths & folklore",
   "Heritage",
   "Festivals"
  ],
  "quote": "Chinese shadow theatre: translucent dyed-hide puppets, carved like lace, pressed against a cotton screen and lit from behind by oil lamps.",
  "essence": "A white cloth screen; behind it, flat puppets cut from translucent dyed hide, lit by an oil lamp. Colour arrives by transmitted light: dyes glow like stained glass, carved holes shine brightest, overlaps go darker. Puppets are jointed with visible thread rivets and moved by thin rods (neck and hands) that show as soft grey lines just off the screen. It is live theatre, not stop-motion: the screen flickers with the…",
  "nots": "a black silhouette film (colour is the second protagonist), not paper-cut (the light comes through), not stained glass (no lead lines; pieces move and overlap), not flat vector cut-out animation.",
  "material": [
   "lampLight: per lamp a broad lobe plus a tight hotspot (~6 : 1), each flickering independently (a few % of ~7 Hz value noise plus a faster sine). Warm light, never white",
   "Figures are jointed puppets: 8–12 pieces, head ~1.2× natural with large headwear, sleeves in a different dye from the torso, round joint lobes with a rivet (dark ring +…",
   "Scenery is carved set pieces on mostly empty lit cloth: one lace piece per element, a narrow carved ground strip, separate liftable strips for water or sky. Fire, smoke…"
  ],
  "colour": [
   "All colour is transmitted: a dye filters warm lamplight, so nothing is brighter than the lamp and every hue leans warm",
   "3–5 saturated dyes + raw hide (the neutral) + ink (outlines, hair, boots). Holes are the brightest value",
   "Overlap is darkness: plan which pieces cross"
  ],
  "motion": [
   "Body glides with the main rod; legs, plumes, tassels are simulated (damped pendulums / spring chains driven by body acceleration, pre-simulated at a fixed rate…",
   "Press on / lift off: arrivals come large and blurred onto the cloth and snap sharp (~0.5 s); exits grow, blur and fade (~1 s)",
   "A new lamp flares with overshoot; a snuffed lamp gutters with fast flicker"
  ],
  "camera": [],
  "sound": [
   "Silence: hard-cut the whole bed; at most one sound inside (a breath, a tap, a sizzle)",
   "Foley follows the materials: wooden clapper (醒木), match strike, lamp \"fwoomp\" and \"pfft\" + sizzle, rod taps on cloth, dry leather flaps on…"
  ]
 },
 "silent-film": {
  "name": "1920s Silent Film",
  "cat": "Cinema & Eras",
  "line": "A baker's boy chases a runaway loaf downhill, then breaks it in half for a hungry girl.",
  "uses": [
   "Comedy",
   "Retro brands",
   "Silent storytelling"
  ],
  "quote": "An engraved-illustration silent film projected in a picture house: ink line and silver wash, a 4:3 print that flickers and weaves between velvet curtains, intertitles instead of voices, and a cinema pianist who plays every beat.",
  "essence": "A one-reel film as it would look projected: - A 4:3 print in a gate between theatre curtains; the sides of the 16:9 frame are the picture house. - An ink drawing with washed greys and hatching, printed on silver stock that flickers, weaves, scratches and burns at the edges. - Nobody speaks. Beats are told by action in wide shots and by intertitle cards. - The only sound is a cinema instrument (piano, organ) and the…",
  "nots": "a noir (no hard shadows as mood, no voice-over), not a sepia photo filter on modern animation (the drawing itself is engraved and inked), not a Chaplin pastiche.",
  "material": [
   "Tonal painting + Redraw. Scenes are painted in grey values only (print densities roughly: ink 0.07, dark cloth 0.15–0.3, mid wood 0.45–0.6, skin 0.8, white linen…",
   "Frame: 1440×1080 in the centre of 1920×1080, a rounded aperture with a soft dark rim; velvet drapes at the sides lit by the screen's spill and by footlights. Curtains…"
  ],
  "colour": [
   "Monochrome silver, tinted only by the print: colder and harsher (more damage, less sepia) when things go wrong, warmer and cleaner when the film turns tender.…",
   "Values carry everything: dark clothes against pale walls, pale faces against dark interiors; check every shot as a thumbnail",
   "One colour, at most: an element drawn into a separate colour mask keeps its hue through the print (still getting grain, flicker, vignette). Use it for the…"
  ],
  "motion": [
   "Deadpan performance: the face barely changes; the body acts (crouch before effort, held poses, the two-frame snap of a double take, hands on knees). Objects…",
   "Keyframed, eased poses; only deliberate gags snap"
  ],
  "camera": [],
  "sound": [
   "Photoplay idiom: stride left hand, music by mood section in the manner of cue sheets (Hurry, Misterioso, Agitato, Tenderly, Maestoso), a…",
   "No foley, no voice. The projector is the ambience: lamp click, motor spin-up, claw-and-motor purr, film flapping on the take-up reel"
  ]
 },
 "silkscreen-poster": {
  "name": "Silkscreen Travel Poster",
  "cat": "Print & Printmaking",
  "line": "A traveller crosses the world one full-bleed screen print at a time, a ticket stub counting the distance from home, until the far side turns into the way back.",
  "uses": [
   "Destination guides",
   "Tourism",
   "Event posters"
  ],
  "quote": "Opaque, hard-edged flat inks pulled one colour at a time through a screen: 4–6 inks per poster, stepped colour bands instead of gradients, thin paper-white gaps where the registration slips. Information is revealed the way the print is made: one layer, one beat.",
  "essence": "A poster being printed on camera. Every colour is an opaque ink laid by its own pull; later ink covers earlier ink completely. No halftone, no fluorescent ink, no line work: a shape's edge is where one flat ink stops. Gradients are forbidden: skies and haze are stepped bands (a flat colour, thinning stripes, the next colour).",
  "nots": "risograph (translucent fluorescent overprint with halftone grain), not ukiyo-e (key-block line work with bokashi), not woodcut (carved line), not low-poly (3D facets). This style is opaque, line-free, flat and banded.",
  "material": [
   "One Path2D per ink layer, filled in the current transform's units; knock-outs are holes in the path. Any shape can be printed",
   "Pull reveal: a ragged squeegee front as a clip (a ~30 u drag tail); blade, bead and a sliver of handle ride on it",
   "Ink bead: a round tube with lit half, dark underside, rolling glints and viscous strands; a split fountain puts several colours in one bead",
   "Screen: a hinged frame with mesh, emulsion and tape; its shadow is a ring (even-odd), never a full rectangle"
  ],
  "colour": [
   "Values step from far (light) to near (dark); depth is value, never blur",
   "The accent is rare: the sun or light source, the one route or product, the most important number",
   "Paper is a colour: an unprinted area is the brightest thing on the sheet (water, snow, a beam of light)"
  ],
  "motion": [
   "Pulls are linear and steady (a squeegee does not ease). Accent inks start half a beat after the main ink of their layer",
   "Info items print left to right on subdivisions of the beat. There is no fade anywhere",
   "Screen lift: the frame hinges up (vertical squash + growing shadow) in ~0.4 s"
  ],
  "camera": [],
  "sound": [
   "Acoustic, hand-played instruments: strummed guitar, slide guitar, harmonica, upright bass, cajon or brushes, banjo, fiddle, accordion,…",
   "One pull, one hit: each ink lands on a musical event (a strum, a hit, a chord change); accelerate by subdividing, not by changing tempo. A…"
  ]
 },
 "spy-titles": {
  "name": "60s Spy Title Sequence",
  "cat": "Graphic & Type",
  "line": "Opening titles for an imaginary 1964 spy film: a chase for a stolen key until the shapes lock into the title.",
  "uses": [
   "Title sequences",
   "Event openers",
   "Trailers"
  ],
  "quote": "A cut-paper, four-ink opening title sequence for a film that never existed: silhouettes move through sets built out of the credits themselves, every brass stab is a cut, and a title is assembled from the pieces.",
  "essence": "Flat, opaque inks on paper: four colours, no gradients Hand-cut edges on every shape; pieces layered with cut gaps and small paper shadows",
  "nots": "flat vector motion graphics (the edges are cut, the paper is physical), not a halftone print style (no dots), not a Swiss grid (diagonals, jaunty type, playful), not a spy parody with gadgets and gun barrels.",
  "material": [
   "Paper texture: one full-frame texture multiplied on top (mottling + faint fibres), a sparse \"ink void\" speckle on dark ink, faint squeegee streaks; film grain in the mux…",
   "Silhouette figures: tall stylised adults (~7 heads), identity by hat, coat cut, shoes and one colour accent that doubles as a motion indicator (a tie or scarf streaming…",
   "The object of the chase sits on a black backing (an ink keyline) so it reads on any ground; it is the brightest thing in frame"
  ],
  "colour": [
   "Four inks: ink black, paper cream, one hot colour, one warm secondary. Darker \"shadow paper\" variants of those inks only for depth",
   "One dominant ground colour per scene, changing with the location; figures and type in the other inks",
   "The hot colour is reserved for one accent on the hero and for danger; the secondary marks the object of the chase"
  ],
  "motion": [
   "Run cycles of ~8 drawings, one step per beat, a strong lean, the accent flying back. Walks one step per beat, coats swinging",
   "Credits slide in along grid lines and stop dead on the beat (short ease-out); letters land with a paper slap",
   "Stop-time: at a stab the whole picture freezes (background scroll included) for a couple of beats in total silence, then resumes"
  ],
  "camera": [],
  "sound": [
   "1960s spy big band: stacked staccato trumpets and trombones in octaves with crash (the stab), surf guitar low-string twang through a spring…",
   "Techniques (options): a cut interval that shrinks as a chase accelerates; stop-time silence; a big chord for the title followed by a short…"
  ]
 },
 "stained-glass": {
  "name": "Stained Glass",
  "cat": "Graphic & Type",
  "line": "Sunlight crosses a cathedral window from dawn to dusk, waking each pane of a knight-and-dragon tale.",
  "uses": [
   "Legends",
   "Heritage",
   "Holiday stories"
  ],
  "quote": "A medieval stained-glass window seen from inside a dark stone hall, alive only where the sun touches it: light is the clock, the camera and the story.",
  "essence": "Not vector art with black outlines, not a kaleidoscope or Voronoi filter, not Tiffany Art Nouveau, not mosaic (mosaic reflects; glass transmits).",
  "nots": "vector art with black outlines, not a kaleidoscope or Voronoi filter, not Tiffany Art Nouveau, not mosaic (mosaic reflects; glass transmits).",
  "material": [
   "Hue-preserving tone mapping: per-channel 1-exp(-x) turns cobalt pastel; blend to per-channel only at the very top so a sun disc burns white while blue stays jewel blue",
   "Unlit panes: weak sky light + room-lit weathering haze, figures ghostly but readable. Lit panes: backlight ~2–3×, a soft, slightly skewed moving band edge",
   "Faces: almond eyes, heavy upper lid, big pupils, brow flowing into the nose. Expression lives in brows and mouth; change it by swapping the face piece, never morphing",
   "Backgrounds: hand-cut lozenge quarries (jittered lattice, shared vertices, a painted motif each); borders of a coloured band with pearls and a white fillet with a…"
  ],
  "colour": [
   "Two hues carry the picture (one deep, one hot); three or four more only as small touches. Example (Chartres logic): cobalt ground, ruby, touches of gold,…",
   "Greenish white glass sparingly (faces, fillets, sky). Flesh darker than you think, or backlit faces burn white",
   "A story light (candle, lamp, screen) may take a colour no glass uses, so it reads as a source"
  ],
  "motion": [
   "Crack: jagged lines race from the impact in ~¼ s, bright with light, a short white flash and a 2-frame shake",
   "Re-leading: piece groups slide one beat each with a small outward bump along the lead, each ending in a weld spark; cracks become mending leads",
   "Glass never bends or morphs; things appear by being lit, not faded in"
  ],
  "camera": [],
  "sound": [
   "Instruments: organ (pedal drone, soft stops, full), harp, hand chimes, tubular bells, recorder or a chant-like voice, water-glass notes,…",
   "Mode families: church modes, open fifths, drones, parallel organum"
  ]
 },
 "swiss-motion": {
  "name": "Swiss Motion Graphics",
  "cat": "Graphic & Type",
  "line": "A concert poster lays itself out by five Swiss design rules; the fifth is to break just one.",
  "uses": [
   "Brand identity",
   "Events",
   "Design education"
  ],
  "quote": "International Typographic Style in motion: a modular grid, one typeface, one signal colour, and movement as exact as a printing press.",
  "essence": "Pure 2D graphic design animated on a grid: flat paper, black type and bars, a very light grey and one saturated signal colour Every element snaps to the grid, every move lands on a beat, nothing bounces",
  "nots": "a keynote (no gradients, no glow, no device renders), not kinetic typography for a lyric video (words don't fly, spin or bounce), not data visualisation (bars have mass as graphic form, not as charted quantities, unless the grid gives them that meaning), not a Bauhaus pastiche of primary shapes.",
  "material": [
   "Artifact grid derived from the content: what the columns and rows mean is a design decision. Choose module sizes that give the elements mass; too many thin columns make…",
   "Surfaces: page, paper, ink, signal colour, grid lines in two or three light greys (on page, while building, on paper). No gradients, no shadows, no particles, no grain…",
   "A secondary voice can be light-grey elements under the black ones: depth without a second colour",
   "A 2D camera matrix (centre, scale, rotation) for all moves"
  ],
  "colour": [
   "Paper, ink, greys, and one signal colour. Only one thing carries the signal colour; that makes it the protagonist. It is the only thing allowed to be inexact",
   "Overprint is allowed: black type on the signal colour",
   "The signal colour can be red, orange, ultramarine or green; choose it for the topic, then never add a second"
  ],
  "motion": [
   "Two curves only: a precise ease cubic-bezier(.7,0,.2,1) for snaps; linear for lines being drawn, playheads and the exception. No overshoot, no spring, no bounce",
   "Durations are note values at the film's tempo. A snap starts one note value early and lands on the beat",
   "Entrances are wipes or clip-reveals, never fades: words rise out of a clip rect from below the baseline and leave upward; lines grow along their length; paper…"
  ],
  "camera": [],
  "sound": [
   "Music with a grid of its own: a steady pulse whose subdivisions give snap durations. Options: motorik / krautrock kit and bass, minimal…",
   "Techniques (options): drop the drums for the one moment of the exception; a near-silent bar before a reveal; thin the band during a reveal…"
  ]
 },
 "teardown": {
  "name": "Exploded Teardown",
  "cat": "Evidence Films",
  "line": "Half an open-source keyboard comes apart in one orbit, down to the chip, then closes with its real dimensions.",
  "uses": [
   "Hardware launches",
   "Product pages",
   "Spec explainers"
  ],
  "quote": "A real product, built from its own engineering files (CAD, PCB layout, bill of materials), lit like a studio packshot and taken apart in front of the camera: the layers lift on one axis, the camera travels between them, every part is named with the numbers its files contain, and it closes again into",
  "essence": "the object is real and exact: geometry, positions and counts come from the product's own files (STEP, KiCad, BOM, assembly guide). Nothing is eyeballed that a file can give it is shown apart: layers float on one axis with even, readable gaps, each still oriented as it sits in the product",
  "nots": "a glass product render (one object, material beauty, no disassembly), not a blueprint (line drawing on a grid, no light), not a keynote (slides, headline type, a stage), not an assembly manual (step numbers, arrows, hands).",
  "material": [
   "Each material keeps its character: plastics with soft sheen (roughness 0.55–0.7), boards with a thin clearcoat and traces as a raised, lighter relief under the mask,…",
   "Light: a warm key from above front, a cool rectangular rim behind that follows the camera so edges separate from the ground, a soft top light, a low HDRI for…",
   "Background: a dark graphite seamless sweep (screen-space radial gradient), floor visible only as soft shadow",
   "Effects anchored to the world (leaders, dimension lines, glows) are projected from 3D points every frame; only subtitles and title cards live in screen space"
  ],
  "colour": [
   "The product brings its own colours; the frame around it is neutral and dark, so the product is always the brightest, most saturated thing",
   "Interface ink is one warm white at two strengths (names at full, specs at about 60 %), plus one accent reserved for measured things: dimension lines, label…",
   "Values are ordered: ground darkest, product mid to light, labels lightest. Never put text on a busy, bright part without a dark backing"
  ],
  "motion": [
   "Separation: smooth start, fast middle, long settle (ease-in-out cubed); layers leave top first, 0.15–0.2 s apart; repeated parts (keys, screws) fan out in a…",
   "Closing: bottom first, quicker (about 1 s per layer), the last layer lands with a real mechanical response (a key travels its stroke and returns; nothing…",
   "While held apart, layers may float a millimetre or two with offset phases; during macro shots they hold perfectly still"
  ],
  "camera": [
   "At key moments the subject fills at least a third of the frame height. Labels live in a column on the free side (shift the projection with a view…",
   "Transitions are camera moves through the object itself. No cuts to black, no slide transitions, no split screens"
  ],
  "sound": [
   "Instruments: tuned mallets (marimba, vibraphone, glockenspiel, glass), a round bass, a short synthetic kick and small dry percussion.…",
   "Foley is the material: hollow plastic clacks for keycaps or housings, a switch click with a low thock, dry taps for boards, inharmonic…"
  ]
 },
 "telestrator": {
  "name": "Sports Telestrator",
  "cat": "Edit & Documentary",
  "line": "Down 3–0 at half-time, Fenerbahçe scored three in 12 minutes: freeze, draw, split screen, shot map.",
  "uses": [
   "Sports analysis",
   "Match recaps",
   "Coaching"
  ],
  "quote": "The TV football analysis segment: play the clip at full speed, rewind, freeze it, and draw on the broadcast picture — rings under players' feet, marker arrows for the ball, a red patch for the space nobody covered — then play on, switch angles, count the frames, and flatten the pitch into a board. R",
  "essence": "Not Visual Investigation (that is restrained, synchronised multi-camera evidence where the timeline is the protagonist; this is a pundit's show with packaging and enthusiasm). Not a highlight reel (no montage of goals to music; each clip is analysed). Not Data Storytelling or an infographic: charts are not the film; the top-down board appears once, as a summary, and is reached by flattening the real picture.",
  "nots": "Visual Investigation (that is restrained, synchronised multi-camera evidence where the timeline is the protagonist; this is a pundit's show with packaging and enthusiasm). Not a highlight reel (no montage of goals to music; each clip is analysed). Not Data Storytelling or an infographic: charts are ",
  "material": [
   "Wikimedia Commons (search \"goal\", the match, the player): many clips are cut from broadcasters' own YouTube uploads under CC BY. Fine: CC0, public domain, CC BY. Not…",
   "Facts (scores, minutes, how a goal was scored): the league's or broadcaster's own match page or video description, then established newspapers; quote them in FACTS.md.…",
   "Photos of players: Commons (CC BY / CC0); state the year when the photo isn't from the match"
  ],
  "colour": [
   "One colour, one identity, throughout the film: a label's left bar takes the colour of what it names. Change the hues if the show needs to, never the three roles."
  ],
  "motion": [
   "Spotlight: everything outside a focus ellipse darkens to 0.42 (even-odd hole), 0.3 s fade",
   "Slow motion: source frames at 0.6–0.85×, neighbours cross-blended (no stutter)",
   "Trails: in screen space keep only the last ~0.6 s (ball 0.24 s) — the camera pans, so long trails land in the wrong place"
  ],
  "camera": [],
  "sound": [
   "Score: sampled band (drum kit, electric bass, staccato trumpet and trombone, timpani, horn, cellos, glockenspiel), about 120 BPM. The…",
   "Foley: marker squeak (2–5 kHz band-passed noise with flutter) for each line, pops for rings, a tick per landed label, whoosh on every wipe,…"
  ]
 },
 "tilt-shift": {
  "name": "Tilt-Shift Miniature",
  "cat": "Materials & 3D",
  "line": "Morning rush hour in a town that looks like a model: traffic, trains and tiny people.",
  "uses": [
   "City promos",
   "Real estate",
   "Transport"
  ],
  "quote": "A real-looking place photographed from high above with a tilted lens and a time-lapse camera, so the whole world reads as a tabletop model.",
  "essence": "A place seen from high up through a tilt-shift lens: only a thin horizontal strip of the frame is sharp, everything above and below melts into blur. The eye reads that as a macro shot of something small, so the world becomes a model. Two more things make the trick work: saturated, sunny colour (model-railway paint) and time-lapse (vehicles and people move in fast, jittery steps like wind-up toys).",
  "nots": "a toy or clay render (the world is photoreal, only the lens and the clock make it small), not a game's top-down view (no UI, no clean flat shading), not drone footage (the band, the saturation and the stutter are mandatory).",
  "material": [
   "Vantage: always high. Oblique views at roughly 45–55° pitch from 100–200 m with a moderately long lens (~27–30° vertical FOV); straight top-down for the most \"board…",
   "Grade: neutral tone mapping, strong saturation boost, soft added contrast, slightly warm highlights, a vignette. Lower saturation at night",
   "Light: a hard sun with sharp shadows (a big shadow map fitted to each shot), a low hemisphere fill with warm ground bounce so shadows stay blue but not murky, a…",
   "Model-like detail (what separates \"filmed miniature\" from \"game CG\"): facades with several window types, 1.6–3 m bays, dark reveals, world-space grime, sky-reflective…"
  ],
  "colour": [
   "Saturated, sunny, \"freshly painted model\": a pale warm ground of buildings with a few candy accents, very saturated greens, dark ground surfaces so white…",
   "Shadows stay blue and clean, never grey. Night and dawn are the only low-saturation states; dawn must read as early morning (a warm low fill from the sunrise…",
   "The subject you want found should be the one saturated thing in the sharp band, or move against the flow"
  ],
  "motion": [
   "Systems run on simple simulations pre-computed per clip (car-following, signal cycles, crowds gathering and surging), with cycle offsets chosen so changes land…",
   "Hero actors get art-directed timing (scripted paths fitted through beat times), never a hope that the sim hits a beat"
  ],
  "camera": [],
  "sound": [
   "Ensemble: tuned percussion carries the style (marimba, glockenspiel, vibraphone, woodblocks, kalimba, celesta), pulse-based and minimalist…",
   "Techniques, as options: world events gate the notes of a fixed phrase skeleton (vehicles crossing a line, lights changing, crowds moving…"
  ]
 },
 "transit-map": {
  "name": "Transit Map",
  "cat": "Information & Keynote",
  "line": "A printed metro map grows from one 6 km line in 1993 to 21 lines and 906 km.",
  "uses": [
   "Transport",
   "Growth over time",
   "Networks"
  ],
  "quote": "A metro schematic printed on a physical sheet: lines held to eight directions, white stops, black-outlined interchange capsules, water as a flat blue band. The network is drawn on by glowing pen tips while a real perspective camera moves over the paper: it rides a tip, drops low where a line dives u",
  "essence": "Eight directions only. Every line segment, river edge and coastline is horizontal, vertical or at 45°; every corner is one fillet radius. A line never wiggles Growth is drawing. A line exists as far as its pen tip has travelled; stops light when the tip passes; an interchange appears only when the second line actually arrives, and it lands with weight",
  "nots": "Data Storytelling (even a time chart is drawn as two lines with stops), not Blueprint (no white-on-blue linework), not Isometric Infographic (the map is flat; depth comes from the camera), not a 3D city map (no extruded buildings, no terrain), not a keynote (no slides, header bars, centred titles or",
  "material": [
   "Interchange shape follows the station. Points side by side make a horizontal stadium, stacked points a vertical one; lines that cross at one point make a circle r 0.13…",
   "Paper: warm off-white, procedural and tileable, sampled in world coordinates so it never slides. Three layers: a cloud of value at about 9 G period with detail down to…",
   "Light: one raking light from one corner of the sheet (north-west in our demo), about 33° above the paper, neutral in colour and fixed for the whole film; it lifts that…",
   "The sheet edge sits on a near-black warm table (about #1B1918) with a contact shadow that fades over about 0.2 G. Far away the table goes into a warm dark haze so the…"
  ],
  "colour": [
   "Neutral ground: warm off-white paper; ink near-black for text and interchange outlines; secondary text in warm grey; water one pale blue with a darker edge,…",
   "Line colours carry identity and nothing else. A real network uses its published colours; an invented one picks hues spaced around the wheel at similar weight,…",
   "Mode is carried by line form, never by hue. Each line keeps its colour whatever kind of vehicle runs on it:"
  ],
  "motion": [
   "Stops pop from 0.6× with a small overshoot in about 0.28 s and a ring in the line colour that spreads from 0.10 to 0.42 G and fades in 0.6 s. Minor stops pop…",
   "Interchanges scale down from 2× in 0.22 s with an ink ring spreading to 0.64 G. A major interchange falls from above in about 0.4 s (from 3.4× its size, its…",
   "Line bullets spring in with a back ease and carry the opening year; they fade when the story moves past their chapter"
  ],
  "camera": [],
  "sound": [
   "Tuned percussion for drawing and stops: glockenspiel, marimba, vibraphone; a stop is a pluck, an interchange a pop with a low thump",
   "A two-note station chime as the motif, returning at the turns of the story"
  ]
 },
 "ukiyoe": {
  "name": "Ukiyo-e",
  "cat": "East Asian Traditions",
  "line": "A traveller walks toward a distant mountain; every shot is a woodblock print, a great wave at the climax, the mountain and the whole scroll at the end.",
  "uses": [
   "Travel",
   "Japanese culture",
   "Poetry"
  ],
  "quote": "Edo-period woodblock prints brought to life: flat colour blocks, carved ink lines, bokashi skies, paper you can feel, and a camera that moves over the print like an unrolling handscroll.",
  "essence": "Every shot is a complete woodblock print: a sheet of washi, a thin double ink border, flat areas of colour printed from separate blocks, a black key-block line on top, a vertical title cartouche and a red seal. The world is flat on purpose. Depth comes from stacked horizontal layers, mist bands and bold cropping, never from perspective rendering, lighting or shading.",
  "nots": "a flat vector illustration with a paper overlay (no woodgrain, no misregistration), not Chinese ink wash (no bleeding washes, colour is printed, not painted), not anime cel shading (no light and shadow on forms).",
  "material": [
   "The sheet is the frame: the print fills the screen at zoom 1, inside a thick + thin ink border, with a paper margin beyond. Sheets can sit on a long mounting scroll…",
   "Motifs of the medium: mist as long rounded flat bands (suyari-gasumi) fading at both ends; pines with flat-topped needle pads; fields as high, flat, parallel layers…"
  ],
  "colour": [
   "A pigment set, not a colour wheel: 6–9 flat hues, each printed from its own block, over the paper ground. No gradients except bokashi, no shading on forms",
   "Sumi key line over everything; paper is the white (no white pigment for foam, snow, mist, blank sky)",
   "One dominant hue family carries sky and water (in the 19th-century prints, Prussian blue); red is rare: seals, a sun, one garment or tab"
  ],
  "motion": [
   "Prints are still. Most of the frame does not move; each view has one or two small actions (steam, rain, a lantern, a falling leaf)",
   "A native move needs a held beat of about a second to be read; a peak flashed in under a second reads as noise"
  ],
  "camera": [],
  "sound": [
   "Modes: miyako-bushi (in scale), yō, ritsu; long breathy tones with a slide into each note and meri drops at phrase ends suit the…"
  ]
 },
 "urban-sketch": {
  "name": "Urban Sketch · Pen & Wash",
  "cat": "Hand-drawn & Painting",
  "line": "A park that is only a pen sketch; wherever the wind carries her straw hat, colour follows.",
  "uses": [
   "City & travel",
   "Architecture",
   "Lifestyle brands"
  ],
  "quote": "A sketchbook page drawn on location: fine sepia fineliner lines that wobble, overshoot and never quite close, with loose transparent watercolour dropped on top. The colour sits slightly off the lines, spills over them, and dissolves into cream cold-press paper at the page edge.",
  "essence": "Reportage drawing, made on location in a few minutes. Two layers that stay visibly separate:",
  "nots": "Watercolor Brush (no line-free wet-in-wet painting, no painterly edges without ink), not Whiteboard (no marker, no explainer diagrams), not Chinese Ink Wash (no brush calligraphy, no monochrome ink tones). Line and wash, both, always.",
  "material": [
   "Paper: two octaves of fbm mottling (a few %), a tooth tile multiplied over everything, figures included",
   "Colour arrival field: every pixel has a time at which colour reaches it. The wash is revealed through it with a ragged wet front (darkened band just behind the front)…",
   "Foliage: pale base wash, then light and shadow masses, then small leaf dabs coloured by light direction, holes at the rim, scalloped ink only on the outline",
   "Sky: a few big soft washes at low alpha, fading upward; clouds are reserves with a tinted belly"
  ],
  "colour": [
   "Ink is one colour (dark sepia or warm black); it never changes",
   "Wash is local colour, lightly: few pigments, mixed on the page; shadows are the local colour mixed toward one shared cool violet; distance mixes toward one haze",
   "Paper white is the brightest value; it is reserved, never painted"
  ],
  "motion": [
   "Performance: anticipation, action, follow-through; footsteps on the beat",
   "Invisible forces are drawn: wind as ink curls that draw on and erase from the tail, trailing dabs; sound as ink lines; heat as wavy strokes",
   "Colour never snaps: it blooms from a point or arrives through the field"
  ],
  "camera": [],
  "sound": [
   "Ambience from the place: paper room tone first, then the location once it has colour (birds, traffic, harbour gulls, market chatter). J-cut…",
   "Pen on cold-press paper: band-passed noise (~1.6–7.5 kHz) with a fibre texture and grain clicks, one burst per real stroke; thousands…"
  ]
 },
 "visual-investigation": {
  "name": "Visual Investigation",
  "cat": "Edit & Documentary",
  "line": "Newsreel, photos, testimony and the 1937 inquiry on one clock: five sources point to the same spot.",
  "uses": [
   "Reconstructions",
   "Fact-checks",
   "Incident reports"
  ],
  "quote": "A cold investigation desk: footage, photographs, documents, sound and maps from one real event, laid out on one shared clock so they check each other. The clock lives inside the picture — timestamps on the evidence, a playhead on a data chart, a stopwatch over the decisive seconds; frozen frames are",
  "essence": "",
  "nots": "Satellite Briefing (no orbital imagery, no zoom from space). Not Archive Light Table (no paper on glass, loupes or hands: documents are flat evidence frames). Not Halftone Dossier (no print texture, stamps or collage). Not a newsreel package (no channel bug, ticker or anchor voice). Not a keynote: n",
  "material": [
   "Drawn evidence (plan, side schematic, charts, dot matrix) is thin line work on the panel colour, marked schematic when it is not measured",
   "Remove channel bugs, watermarks and the source's own title cards; never generate an image to stand in for a historical one"
  ],
  "colour": [
   "Sources are greyscale; red is the only colour and it only ever points: circles, the chart playhead, sync lines, highlights, ✓ badges (a drawn tick in a red box, no words), the zone everything converges on, the unresolved column, a…"
  ],
  "motion": [
   "Only things that are drawn are progressive: circles drawn clockwise in 0.5 s (ease-out cubic), leaders and links 0.4–0.8 s, plans stroke by stroke, highlights…",
   "Something changes at least every second; holds are for verdicts only"
  ],
  "camera": [],
  "sound": []
 },
 "watercolor": {
  "name": "Watercolor Brush",
  "cat": "Hand-drawn & Painting",
  "line": "Follow the rain from Australia's red desert heart to its green coast in one unbroken painted walk.",
  "uses": [
   "Nature documentary",
   "Travel",
   "Science explainers"
  ],
  "quote": "A hand-painted journal page that paints itself: translucent brush strokes with dry-brush flying white on warm cotton paper, hand-written notes beside what is painted, nothing drawn with a vector line.",
  "essence": "One sheet of warm, fibrous paper under everything; it is also the eraser (paper-coloured mist washes things away) Everything is individual brush strokes: a variable-width ribbon at partial opacity plus a few thin bristle tracks that break into dashes (flying white). Strokes overlap and darken where they cross, like…",
  "nots": "ink wash (colour, not ink tones; no calligraphic brush-as-gesture), not impasto (no thick paint, no knife), not a children's picture book (no crayon, no cute outlines), not vector illustration with a watercolour texture laid on top.",
  "material": [
   "Paper: a pre-generated image (warm base, three octaves of smooth noise ±3.5 %, a few thousand short curved fibres, fine grain, light vignette), drawn first every frame",
   "Wash: the same polygon painted in 3 passes with jittered vertices at a third of the opacity each, so edges darken where passes disagree (a pooled watercolour edge)",
   "Cache finished objects as sprites; draw stroke by stroke only what is being painted or transformed"
  ],
  "colour": [
   "Paper is the white. Never paint pure white; light is unpainted paper",
   "Ink (a warm near-black and a lighter brown) for lines, text, edges and stems only",
   "Colour may carry the data or the mood: blend sky, ground and background by position or time so the palette itself changes with the subject. Map ramps quantised…"
  ],
  "motion": [
   "Brush-edge wipes: a wavy vertical clip reveals a whole scene; lines grow by stroke progress; labels open with a left-to-right clip",
   "Mist erases: paper-coloured layers with a wavy rising edge",
   "Animated creatures and events may be phased to the music's beat grid so landings hit the beat"
  ],
  "camera": [],
  "sound": [
   "Music: acoustic and gentle: felt piano, fingerpicked guitar, woodwinds, light strings, glockenspiel, kalimba, soft pads. A licensed track…",
   "Foley made from the scene's matter: a paper brush rustle for each painting-in (band-passed noise, light tremolo, a panned sweep); pencil…"
  ]
 },
 "white-model": {
  "name": "Projection on White Model",
  "cat": "Evidence Films",
  "line": "A projector paints Rotterdam's white model layer by layer, from the 1940 gap to today's towers.",
  "uses": [
   "Urban planning",
   "Exhibitions",
   "City data"
  ],
  "quote": "A pure white massing model of a real place stands on a plinth in a dark room, and a projector paints data onto it as light: one layer at a time, falling on the surfaces that face it, spilling a little past the plate. The model never changes; only the light on it does.",
  "essence": "The model is real geometry of a real place: building footprints and heights from open data (§2), extruded at a stated scale (1:1000, 1:2000…). Nothing on the model is invented or \"representative\", and no… The model is white; data is light. Colour is never painted into the material: it is projected, so it brightens surfaces that face the projector, fades on walls turned away, stops at the edge of the throw and…",
  "nots": "Isometric Infographic (no diorama or icons), not Low-poly Island (no invented terrain), not Sci-fi Hologram HUD (no wireframes; light lands on matter), not Satellite Briefing (no imagery), not a laser-scan or point-cloud film (no scan lines; light is projected, not measured).",
  "material": [
   "Layers depend on what exists. Construction years per building are a Dutch luxury; elsewhere they are often missing. Substitute what the data does hold and the medium can…",
   "The sun is a real directional light with shadow maps, computed from the place's latitude and a real date and time (NOAA/Meeus solar position). The projector can trace…",
   "Post: physical depth of field (stronger on close shots), bloom only above the projection highlights, vignette, light grain in ffmpeg. GTAO only on close shots: on wide…",
   "Keep a FACTS.md in the project folder (claim, source URL, quoted wording, or the measurement method) and deliver it with the film; every number on screen is computed by…"
  ],
  "colour": [
   "Neutral ground: white model, dark room (near black), dark plinth. Projector black level is a cool near-black on the plate",
   "The sun is warm, its shade is a projected deep blue; data colours are put away when the sun arrives",
   "Never colour the model in the house light; never use more than two layer palettes on screen at once"
  ],
  "motion": [
   "The camera moves continuously and slowly; it changes speed with the layers, never stops dead",
   "Light is the actor. Each layer arrives by a soft-edged gesture of light: a wash spreading from the projector axis, buildings switching on one by one with a…",
   "Counters roll while the light moves and land when it lands; measured lines grow from A to B with ticks"
  ],
  "camera": [],
  "sound": [
   "Light as sound: mallets and glass for things switching on, bowed vibraphone for held light, a rising mallet line and air riser for a…",
   "Weight: timpani, gran cassa, gong, low brass for a heavy fact; warm low brass for a turn"
  ]
 },
 "whiteboard": {
  "name": "Whiteboard Explainer",
  "cat": "Hand-drawn & Painting",
  "line": "How your phone knows where you are: GPS, atomic clocks, and the 38 microseconds relativity adds every day.",
  "uses": [
   "Explainers",
   "Online courses",
   "Science"
  ],
  "quote": "An explainer drawn live on one glossy dry-erase board: single-line handwriting that is actually written stroke by stroke, floating markers with no hand, magnets that can move, an eraser that can rewind, and a camera that travels across the board instead of cutting.",
  "essence": "One physical whiteboard. Everything the viewer learns is drawn in dry-erase marker in front of them, in real handwriting order Real marker, not animated text: ink pools where the nib lands, dry streaks and speckle, strokes overshoot and don't quite close, ghosts of old lessons remain, a glossy sheen drifts slower than the board, and…",
  "nots": "draw a hand, an arm or a cursor.",
  "material": [
   "Board: a warm white gradient, a faint scuff and micro-scratch tile, a few dozen ghost marks (old words, circles, arrows) at 5–10 % in grey or pale blue, and a soft…",
   "Dry-marker texture: a speckle-and-streak tile subtracted from the ink layer (destination-out), locked to board space, faded out when the camera is wide",
   "Props: dry-erase markers (white barrel, colour band and cap in the ink colour, felt nib), a felt eraser, magnets (glossy, with specular highlight and soft cast shadow).…"
  ],
  "colour": [
   "Three marker colours at most, each with a meaning held for the whole film: one dark ink for things and structure, one for signals / measurement / process, one…",
   "Monochrome variant: everything in the dark ink, one element in the accent (the \"only colour\")",
   "Ghost marks and board stay neutral; the accent never appears on props except its own marker cap and the hero magnet"
  ],
  "motion": [
   "Pen hops between strokes lift in proportion to distance (shadow slides and blurs); long gaps send the pen off-frame to park and back shortly before its next…",
   "Magnet: drop with a shrinking shadow; slide with a small lift; lift-off and sink possible",
   "Eraser: constant speed along a path, a wide band at ~90 % strength (a ghost always remains)"
  ],
  "camera": [],
  "sound": [
   "Room: low room tone; a single diegetic ticker (a wall clock, a fridge hum, a projector fan) can own a silence",
   "Music options: a solo piano figure; a small jazz trio with brushes; plucked strings and kalimba; a synth arpeggio for tech topics;…"
  ]
 },
 "woodcut": {
  "name": "Woodcut Print",
  "cat": "Print & Printmaking",
  "line": "A village spends a whole winter casting one bell; the first time it rings, the snow stops.",
  "uses": [
   "Folk tales",
   "Craft brands",
   "Book trailers"
  ],
  "quote": "A relief print that carves itself: every frame is a black wood block, and light only exists where a knife has cut it away. One colour at most, and only for the thing that burns.",
  "essence": "Each shot is one printed plate: black ink on laid paper, framed by a paper margin. It follows three rules of real relief printing:",
  "nots": "copperplate engraving (no swelling burin lines on white, no crosshatch built up from white ground), not linocut poster art (no flat colour areas), not a black-and-white photo run through a threshold filter (the cuts must follow the form).",
  "material": [
   "Print frame: the printed image area sits inside a paper margin; the wider bottom margin holds captions. The image edge is the block edge: ragged ink, never a clean…",
   "Knife classes (widths in 1080p pixels at 1× camera):"
  ],
  "colour": [
   "Two values carry everything: near-black ink and warm laid-paper white. The raw wood colour appears only in shots that show the block itself",
   "At most one colour plate, printed only where white has been carved, so it glows out of the cuts and never sits on the black. A colour plate over ink is nearly…",
   "The colour is reserved for the one thing that matters (a flame, molten metal, a heart, a signal lamp). It can spread at a peak and shrink to a single highlight…"
  ],
  "motion": [
   "What never moves: the paper margin"
  ],
  "camera": [],
  "sound": [
   "Options: withhold the timbre of the story's object until it appears; a metric modulation instead of a tempo jump; a modal shift inside a…",
   "Silence is a tool: near-silence with one faint ambience, or true digital silence before the loudest moment; the first sound after it is…"
  ]
 }
}


# Looks added for AVOS after the upstream library was extracted (see filmstyles_extra.py for their sources).
from .filmstyles_extra import EXTRA  # noqa: E402

STYLES.update(EXTRA)
