"""Four more looks for Film Style, written for AVOS from the style guides of four open-source explainer skills.

They run on the same engine as the other 66: your writer plans the shots, your picture and video models draw and move them,
ffmpeg joins them. No Claude, no Node, no Chrome. Only the style knowledge was taken, as notes in our own words:

  explainer-collage   CK42BB/vox-explainer-skill (MIT): the five-beat explainer arc and the paper-collage look
  watercolour-mv      lintsinghua/paint-mv-skills (MIT): the lyrics-to-storyboard rules and the painted look
  stroke-story        hi-nikola/hand-drawn-explainer-video-nikola (Apache-2.0): drawn-on-screen story, exact text kept out of pictures
  minimal-black-line  the same repo's sparse black-line style on white
  cutout-cartoon, press-collage, catalogue-grid, engraving-explainer
                      bangtutorial/bang-motion (MIT): its explainer surfaces and its camera-never-static, no-slide rules
  layered-motion      haidrrrry/claude-remotion-skill (MIT): layered backgrounds, grain, springs and stagger, hit-hold-build pacing
  product-promo       Vincentwei1021/video-shotcraft (Apache-2.0): one motion idea per shot, the product's own look, riser-impact-sparkle sound

Same record shape as filmstyles.py. The prompt budget is tight (see that file), so every line is short.
"""
from __future__ import annotations

EXTRA: dict[str, dict] = {
 "explainer-collage": {
  "name": "Editorial Collage Explainer",
  "cat": "Explainers",
  "line": "In 1969 a single phone call between two computers crashed after two letters; that is how the internet began.",
  "uses": ["Explainers", "History and science topics", "Channel intros"],
  "quote": "A mixed-media editorial collage that reads as designed, not generated: torn paper cutouts with white sticker borders and soft shadows on an aged cream textured ground.",
  "essence": ("Dot-screen accents, strips of washi tape at the corners, one or two flat geometric shapes. One accent colour, fixed for the whole film. "
              "Story arc: shot 1 is a cold open on one concrete surprising fact; shot 2 zooms out to context; the middle shots escalate one idea "
              "step by step with numbers and everyday comparisons; the next to last shot is the complication or irony; the last shot returns to the "
              "opening image with a new meaning."),
  "nots": "photorealism, 3D render, gradients, glossy light, anime, a movie still, text baked into the picture.",
  "material": [
   "Paper cutouts with a white sticker edge and a soft drop shadow, layered over cream paper grain",
   "Dot-screen accents and washi tape; one or two flat geometric accents; headings, if any, are bold condensed capitals"
  ],
  "colour": [
   "Cream ground, charcoal ink, one accent colour chosen once and never changed",
   "No gradients anywhere; flat fills only"
  ],
  "motion": [
   "A slow 2D push-in of 3 to 5 percent, parallax between the paper layers, one element drifting (cloud, smoke, water)",
   "Pieces slide in and settle. No 3D camera moves, no morphing or dissolves, no shake, nothing flies apart, faces never move"
  ],
  "camera": ["Flat front-on, as if the collage lies under a camera", "Vary the framing by zooming on one cutout, never by tilting"],
  "sound": ["Light percussion and a soft bass pulse under a clear voice; swell on the reframe, then settle"],
 },
 "watercolour-mv": {
  "name": "Watercolour Music Video",
  "cat": "Music & Story",
  "line": "A lighthouse keeper sends a paper boat down the stairs every night; by the last chorus the whole harbour is full of them.",
  "uses": ["Music videos", "Lyric stories", "Children's songs"],
  "quote": "A hand-painted watercolour storybook: soft wet colour washes, a rough textured sheet, a loose dark brush outline, playful and colourful, something happens in every shot.",
  "essence": ("One concept from the song escalates and ends on a twist; the first and last pictures rhyme. A very small cast: one or two lead characters, "
              "drawn large, the same silhouette, colours and face every time, plus one recurring symbol that grows each chorus. One set per song section; "
              "chorus sets are bigger than verse sets. Transitions are motivated by action, not by wipes. Almost no words in the picture."),
  "nots": "photorealism, 3D render, glossy digital gradients, a text caption, a title card, a logo.",
  "material": [
   "Watercolour washes bleeding at the edges over a rough textured sheet, with a loose brush-drawn dark outline",
   "Pigment blooms, dry-brush streaks and a few paint splatters; the white of the sheet shows through the light areas"
  ],
  "colour": [
   "A bold, saturated palette that shifts with the mood of the song (cooler in the verse, warmer and brighter in the chorus)",
   "Every shot has one clear focal action that reads at a glance"
  ],
  "motion": [
   "Every shot has a camera move: a slow push, a drift or a pan with the action",
   "Instrumental moments become dance or action shots; the character changes expression with the feeling of the line"
  ],
  "camera": ["Lead character large in frame", "Each shot hands off to the next by matching its exit with the next entry"],
  "sound": ["The song carries the film: cut on the beat, hold a shot for the long vowel, land the last image on the last note"],
 },
 "stroke-story": {
  "name": "Hand-Drawn Stroke Story",
  "cat": "Explainers",
  "line": "A tea merchant sketches the road to the sea one line at a time and every line is a day of the journey.",
  "uses": ["Biographies", "History", "Human stories"],
  "quote": "A hand-drawn ink story that seems to draw itself: friendly rounded characters in confident ink linework, natural skin tones, clear age and clothing, flat colour fills, on a warm white ground.",
  "essence": ("Each shot is one drawn scene. Characters keep the same body shape, age and clothing in every shot. Drawing follows meaning: the main figure first, "
              "then the objects around it. Exact words, dates, names and numbers are never part of the picture; they come later as subtitles. "
              "Where two ideas are compared, the left half is drawn first and stays on screen while the right half is drawn."),
  "nots": "photorealism, 3D render, gradients, glossy light, writing or numbers inside the picture, a real person's likeness, a logo.",
  "material": [
   "Confident ink contour lines of even weight, flat colour fills that stay inside the lines, a little pen wobble",
   "Warm white ground with generous empty space around each figure"
  ],
  "colour": [
   "Natural skin tones, two or three supporting colours per film, black ink lines",
   "Colour is filled only after the outline is drawn"
  ],
  "motion": [
   "The picture draws itself: outline first, then fill; the camera barely moves, a slow push at most",
   "Earlier drawn parts stay on screen while the next part is drawn"
  ],
  "camera": ["Eye-level medium shots, one scene per picture", "Split left and right when comparing"],
  "sound": ["A light acoustic bed under a warm voice; a soft pen scratch as lines appear"],
 },
 "minimal-black-line": {
  "name": "Minimal Black Line",
  "cat": "Explainers",
  "line": "A workflow with five steps is drawn as five dots and four lines, and the one slow step is the only thing in red.",
  "uses": ["Methods and systems", "States and metaphors", "Teaching an idea"],
  "quote": "A pure white page with sparse black line art and generous empty space; a few small accents in red, orange or blue say what matters.",
  "essence": ("Simple stick-like figures and plain shapes, drawn with a thin black line, never filled except by a single accent. One idea per shot. "
              "Metaphor over detail: a bridge for a link, a knot for a problem. Words and numbers are kept out of the picture."),
  "nots": "gradients, shading, a coloured background, detailed realism, 3D, clutter, text in the picture.",
  "material": [
   "Thin black line art on pure white; no texture, no shadow",
   "Accent marks only: a red circle, an orange arrow, a blue underline"
  ],
  "colour": [
   "White ground, black line, at most two accent colours in a shot",
   "The accent marks the one thing the viewer must see"
  ],
  "motion": [
   "Lines draw on one after another; the accent colour arrives last, as the answer",
   "Nothing else moves; whitespace stays empty"
  ],
  "camera": ["Fixed, frontal, centred", "Push in slowly only on the accent"],
  "sound": ["Near silence with a soft tick as each line lands; a single low tone on the accent"],
 },
 "cutout-cartoon": {
  "name": "Cutout Cartoon Explainer",
  "cat": "Explainers",
  "line": "A baker explains why bread rises, and every ingredient is a paper character who walks on and settles.",
  "uses": ["Friendly explainers", "Kids and general audiences", "How things work"],
  "quote": "A playful cutout cartoon on cream grainy paper with faint stains: bright paper characters and props with pill-shaped colour labels, annotations that draw themselves.",
  "essence": ("The camera is never still: it enters the scene, settles, looks around, then leaves; each new idea is a new camera move, never a fade. "
              "No two shots in a row share the same size, entry direction or text position. Never three shots in a row from the same viewpoint. "
              "At most two levels of text in a shot. Words appear one at a time."),
  "nots": "slide-deck layouts, a flat single-colour background, photorealism, 3D render, all-capitals centred titles.",
  "material": [
   "Cream paper grain with faint stains; cutout illustrations with a slight paper edge",
   "Pill-shaped colour labels; hand-drawn arrows, circles and underlines"
  ],
  "colour": [
   "Warm cream ground, a bright cheerful palette of three or four colours, chosen fresh for each film",
   "Dark text on light areas only"
  ],
  "motion": [
   "The whole world moves with the camera: push through, pan, settle; things enter from different sides at different speeds",
   "Movement looks hand-made: a slight bounce on landing, annotations drawn on rather than faded in"
  ],
  "camera": ["Vary size and angle every shot", "Push-through and pan, never a static frame"],
  "sound": ["Bouncy light percussion, soft pops as pieces land, a clear friendly voice"],
 },
 "press-collage": {
  "name": "Press Collage Explainer",
  "cat": "Explainers",
  "line": "Four newspaper-style cutouts and one yellow highlighter show how a rumour travelled across a town in a day.",
  "uses": ["News and current affairs explainers", "Investigations", "Analysis"],
  "quote": "A dark, grainy editorial collage: cut-out press-style pictures with small source tags, torn edges and dashed annotation lines, on near-black.",
  "essence": ("Evidence-style storytelling. Each shot pins one or two cut-out pieces to the dark board and marks the one that matters with a yellow or red highlighter. "
              "The camera travels across the collage and settles on the detail; never a static frame, never a slide. Source tags are plain labels, not names of real people or outlets."),
  "nots": "a real person's likeness, a logo, a real outlet name, a flat background, photorealism of a live scene.",
  "material": [
   "Near-black board with film grain; cut-out pieces with torn edges and tiny source tags",
   "Dashed annotation lines and highlighter strokes in yellow or red"
  ],
  "colour": [
   "Black ground, off-white pieces, one highlighter colour used for the single key detail",
   "Text area stays very dark or very light, never mid-grey"
  ],
  "motion": [
   "A collage camera: slide across the board, settle on the detail, push through to the next",
   "Annotations draw on in dashed strokes"
  ],
  "camera": ["Travelling over a flat board", "A new move for every segment change"],
  "sound": ["Low tense pulse, paper rustle, a short riser into each reveal"],
 },
 "catalogue-grid": {
  "name": "Catalogue Grid Explainer",
  "cat": "Explainers",
  "line": "A museum shop lays out twelve objects on a faint grid and the film explains the one that is not like the others.",
  "uses": ["Product explainers", "Collections", "Comparisons"],
  "quote": "A clean white catalogue page with a faint grid: tidy cutout objects, bold display type, a yellow highlighter on the one thing that matters.",
  "essence": ("Objects sit on a visible grid like a catalogue spread; the camera moves across the page to each one. One idea per shot, one object in focus, "
              "everything else quiet. Comparisons put two objects side by side on the same grid."),
  "nots": "clutter, gradients, a dark background, photorealism of a live scene, a brand logo.",
  "material": [
   "White page with a faint light-grey grid; cutout objects with a very soft shadow",
   "Bold display lettering for labels, a hand-written note beside the key object"
  ],
  "colour": [
   "White ground, black type, one yellow highlighter used once per shot",
   "Objects keep their own natural colours"
  ],
  "motion": [
   "The camera slides across the page and settles on one object; the others stay still",
   "Highlighter strokes draw on from left to right"
  ],
  "camera": ["Flat overhead on the page", "Move from object to object, never a static frame"],
  "sound": ["Clean light taps and a soft hum; a small chime on each highlight"],
 },
 "engraving-explainer": {
  "name": "Vintage Engraving Explainer",
  "cat": "Explainers",
  "line": "An old naturalist's plate of the bee comes alive one engraved part at a time while the voice explains the hive.",
  "uses": ["History", "Science and nature", "Museums"],
  "quote": "An old-book explainer on sepia paper: engraved cutout figures with fine cross-hatched shading, rust and gold accents, ornate serif lettering.",
  "essence": ("Each shot is a plate from a worn natural-history book. Engraved cutouts multiply into the sepia paper so the paper texture shows through. "
              "The camera travels across the plate and settles on one figure at a time; never a slide, never a fade between shots."),
  "nots": "colour photography, gradients, neon, a modern interface, 3D render, a real person's likeness.",
  "material": [
   "Sepia paper with foxing and fold marks; engraved figures in fine cross-hatching",
   "Gold leaf details and a rust-red accent; ornate serif capitals"
  ],
  "colour": [
   "Sepia, warm brown ink, rust and gold accents only",
   "Light paper behind dark ink, always"
  ],
  "motion": [
   "The camera travels over the plate; parts of the engraving appear stroke by stroke",
   "A slow settle on each figure"
  ],
  "camera": ["Travelling over a flat plate", "Close on the engraved detail, then pull back to the whole"],
  "sound": ["Soft strings, a quiet page turn between plates, a warm unhurried voice"],
 },
 "layered-motion": {
  "name": "Layered Motion Film",
  "cat": "Motion & Type",
  "line": "A launch film where a single orange shape hits, holds, builds and hits again on the beat.",
  "uses": ["Launch films", "Promos", "Title sequences"],
  "quote": "A richly layered motion-graphics film: a coloured gradient-mesh background, crisp flat graphics and type, a colour grade over everything, fine grain and a soft vignette.",
  "essence": ("Never a flat background: five layers, back to front: background mesh, assets, graphics and type, colour grade, grain and vignette. "
              "The hero colour appears on only one element per frame. Rhythm is hit, hold, build, hit: a short still beat, then something new lands. "
              "Something moves at once in the first second, and no shot goes long without a new element."),
  "nots": "a flat solid background, emoji used as icons, linear fades only, everything entering at the same time, photorealism of a live scene.",
  "material": [
   "Soft gradient-mesh background, flat vector shapes, bold clean type",
   "A colour grade over the content with fine grain and a vignette on top"
  ],
  "colour": [
   "One hero colour on one element per frame; a dark, rich supporting palette",
   "Dim text stays readable against the grade"
  ],
  "motion": [
   "Entrances use a springy ease with two or three properties together (fade, rise, scale), staggered a few frames apart; exits are quicker than entrances",
   "Anything on screen longer than two seconds has a slight floating drift; stills get a slow push of about eight percent"
  ],
  "camera": ["Flat front-on graphic frames", "Slow push on stills"],
  "sound": ["Whoosh on entrances, a pop on landing, a kick on the hit and a soft pad underneath; never silent"],
 },
 "product-promo": {
  "name": "Product Promo Showcase",
  "cat": "Motion & Type",
  "line": "A planner app is shown as one hero card that rises, floats, settles, and then a stack of cards deals out across the frame.",
  "uses": ["App and product promos", "Launch teasers", "Feature highlights"],
  "quote": "A polished product-promo film: clean interface cards (invented, never a real brand) floating in soft 3D space, drawn in the product's own simple design language.",
  "essence": ("Every shot has exactly one motion idea: a hero card's full arc (spotlight, push in, float, settle), a deck of cards dealing out, or a slow side-angle orbit. "
              "No two shots repeat a motion or a tagline. The wordmark lands and holds for at least a second. Anything sensitive or personal is made up. "
              "The opening subject moves for at least three seconds, and timing is unhurried: longer holds are better than faster cuts."),
  "nots": "a real product or brand name, a real person's data, a logo, clutter, photorealism of a live scene, a generic stock promo look.",
  "material": [
   "Clean interface cards with rounded corners and soft shadows in a gentle 3D perspective",
   "One consistent set of fonts, colours and corner radii across the whole film"
  ],
  "colour": [
   "A restrained palette taken from one interface style, one accent colour",
   "Plenty of empty space around the hero card"
  ],
  "motion": [
   "A hero arc: spotlight, push in, float, settle; or cards dealing out with a little physics; or a slow orbit",
   "At most three full-frame camera slams in the whole film; let animations rest half a second at the end"
  ],
  "camera": ["Slight 3D perspective on the cards", "Slow push-ins and orbits"],
  "sound": ["Riser into an impact, then a sparkle; keep the sound effects even in the version without music"],
 },
}
