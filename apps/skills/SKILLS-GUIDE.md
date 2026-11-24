# AVOS skills — what each one takes, what it needs, how it works, what it gives back

Updated 9 November 2026.

## Where the prompts actually live

Worth knowing before anyone tries to improve them: **most of the prompt engineering is in Python, not in the
instruction files.** The `skills/avos-*/SKILL.md` files steer the AI writers. The prompts that reach a picture or
video model are built in code:

| What | Where |
|---|---|
| The ASMR Cooking director's brief | `studio/skilllab/asmr_cooking.py` → `RECIPE` |
| Its look lock, hands, light, surfaces | same file → `HANDS`, `BARE`, `SURFACES`, `LIGHT`, `NEVER`, `look_for()` |
| Its picture, edit and motion prompts | same file → `image_prompt()`, `edit_prompt()`, `motion_prompt()`, `peak_of()` |
| Its negative list | same file → `NEGATIVE` |
| The paper-cut look shared by several skills | `studio/paper.py` → `LOOK_SHORT`, `TAIL`, `NEGATIVE`, `ART` |
| Company Story's scene prompts | `studio/skilllab/company_story.py` → `scene_prompt()`, `NEGATIVE`, `BRIGHTER` |
| Motion Graphics' spec brief | `studio/skilllab/motion_graphics.py` → `SPEC` |
| ASMR Cutting's object brief | `studio/skilllab/asmr_cutting.py` → `SPEC` |

Anyone improving prompts needs `animation_studio/studio/` as well as `skills/`.
 Everything here is read off the code in this zip, not from memory. Where something is
untested, it says so.

---

## The three kinds of skill, because they are not interchangeable

| | Runs where | Appears where | Started how |
|---|---|---|---|
| **Skill Lab skills** | inside the `animation-studio` container | **Skills** tab, with stages you watch | type a subject, press run |
| **Instruction files** (`avos-*`) | nowhere — they are read | Skills → **Instruction files** | AVOS loads them during a run |
| **Agent skills** | on your PC, in a Claude Code session | Instruction files (read-only) | you ask the agent |

A Skill Lab skill has `ID`, `INFO`, `STAGES`, `LABELS`, `RUN`, `last_stage`, `reset` and a line in
`skilllab/pipeline.py`. Nothing without those can appear in the Skills tab, however good its `SKILL.md` is. That is
why the six vendored animation skills and the six faceless-shorts styles are listed but not runnable there.

---

## Cost, which is the thing that decides most of this

| Skill | Picture model | Video model | Cost of one run |
|---|---|---|---|
| **ASMR Cutting** | none | none | **₹0** |
| **Motion Graphics** | none | none | **₹0** |
| ASMR Cooking | 1 per shot | 1 per shot | ~₹2 of images + the video model |
| Company Story | 1–2 per scene | 1 per scene | images ~₹2; **video is the whole bill** |
| Mechanical Toy | 2 | 1 | small |

Video is essentially the entire cost. Seedance 2.0 Mini is about $0.155 a second, so a 60-second Company Story is
roughly **$9.30**. Wan 2.2 at about $0.08 a second would halve it, but the Skill Lab is hardwired to the Seedance
endpoint — see *Improvements needed* at the end.

Both free skills draw every frame in Python and synthesise every sound. They need no key, cannot run out of credit,
and give the same output twice. When fal.ai ran out of credit mid-run (your Paneer Butter Masala run), those two would
have been unaffected.

---

# Skill Lab skills

## 1. ASMR Cutting — `asmr-cutting`

**Input.** The object and the number of cuts, in one line: `papaya, 50 cuts`, `Object = Papaya, Cuts = 50`,
`a bar of blue soap, 24 cuts`. Add `@yourhandle` anywhere in the line to get a watermark; leave it out and there is
none. The count is taken exactly — 50 means 50.

**Needs.** Nothing. No key, no model, no GPU, no Blender. Python, Pillow, numpy and ffmpeg, all already in the
container.

**How it works.**

| Stage | What happens |
|---|---|
| `plan` | An AI writer, if you have one, returns one small JSON spec: object, shape, skin/flesh/seed colours, sound texture. With no writer it falls back to a built-in table of 20 objects. The cut count and the beat are worked out in code, never by the AI. |
| `render` | `cutscene.py` draws every frame with Pillow; `foley.py` synthesises one knife stroke per impact; `mgfx.encode` pipes raw RGB into ffmpeg. |

The object is drawn once into two layers — skin and flesh — and every slice is a crop of those layers. That is what
keeps fifty pieces consistently lit and lets a cut face appear the instant two slices part.

Timing follows the source workflow: intro 1.2 s, one stroke every 0.25 s, a 0.9 s beat, a 1.9 s fall, 1.4 s to end.
50 cuts lands on 17.7 seconds. The **Length** control sets the beat between strokes, not the number of them; it is
clamped to 0.12–0.60 s, and if a count will not fit the length at a watchable pace the video gets longer and the run
says so rather than dropping cuts.

**Output.** `final.mp4`, 1080×1920, H.264 + AAC, plus `cuts.wav` and a thumbnail. About 45 seconds to render 50 cuts.

**Verified.** Renderer checked by eye across all four shapes; 7 of 9 tests pass here (`tests/test_asmr_cutting.py`);
the pipeline-wiring test and the ffmpeg run test need the full repo.

**Improvements needed.**
- Only four silhouettes (round / long / bar / tall). A layered object — a cake with visible sponge and cream — would
  need a new silhouette and a layered flesh layer.
- The knife is the same knife every time. A cleaver for soap and a paring knife for fruit would read better.
- No juice, no crumbs, no steam. A particle pass on impact would add a lot for little code.
- The fan at the end always falls to the right.

---

## 2. Motion Graphics — `motion-graphics`

**Input.** One line of what to show. `0 to 100K followers in 9 months: 1.2K, 2.1K, 5K, 24K, 100K` ·
`every step feels small until you look back` · `home to the gym, 2.8 km, 9 minutes` · `my phone, every part labelled`.

**Needs.** Nothing. Same as above.

**How it works.** Pick one of four animations (or let it guess from your words): `graph`, `lineart`, `route`,
`breakdown`. Stage `spec` turns your line into a small JSON spec — **only numbers you actually wrote**; it never
invents one. Stage `render` draws it: `mgfx.py` supersamples at 2× and pipes raw RGB to ffmpeg, `mgscenes.py` draws
the four scenes. Isometric projection in code replaces the three.js the originals used.

**Output.** `final.mp4` at 1080×1920 or 1920×1080, 5–12 s, silent. About 8–10 seconds to render.

**Verified.** The four renderers were checked by eye and timed. **The glue that wires them into the Skill Lab has
never been executed** — it is written from the AVOS APIs and has not run against the real `base.py`/`store.py`. This
is the one outstanding risk in this zip.

**Improvements needed.**
- No sound at all. The `foley.py` engine is right there and these four scenes would carry a tick, a whoosh and a
  thud well.
- `breakdown` labels can still collide on a device with many parts.
- Ported from the MIT skills by Artem Novitckii; `stick-figure` and `zach-d-films` are **not** ported — they need
  a voiceover and about 1 GB of voice models.

---

## 3. ASMR Cooking — `asmr-cooking`

**Input.** A dish: `paneer butter masala`, `cheese corn nuggets`, `garlic butter prawns`. Length 30 s to 180 s;
hands bare or gloved; 9:16 or 16:9.

**Needs.** An **AI writer** (Groq or another crew) — it will not run without one, because the recipe has to be real.
A **picture model** for the shots. A **video model** optionally: without one it falls back to macro camera moves made
in ffmpeg, which is what happened on your run when fal.ai ran out of credit.

**How it works.**

| Stage | What happens |
|---|---|
| `recipe` | The writer returns a real recipe and a shot list. Each shot carries `title`, `stage`, `where`, `state`, `gone`, `subject`, `action`, `physics`, `asmr`, `camera`. |
| `pictures` | One picture per shot. Some drawn fresh from words, some drawn **from the shot before** so the board stays continuous. |
| `motion` | Each still becomes a clip — a video model if you have one, otherwise a macro camera move. The ASMR sound for each shot is synthesised in code from its own `asmr` line. |
| `finish` | The clips joined, no music. |

**Output.** `final.mp4` at 720×1280, plus every shot PNG and every prompt.

### What went wrong on your Paneer Butter Masala run, measured

I pulled a frame from the middle of each of the eleven shots and measured them.

| Problem | The measurement |
|---|---|
| Shots repeating | Shots 3→4, 4→5, 8→9 and 10→11 scored **0.95–0.98 alike** on a 16×16 thumbprint. Shots that genuinely moved on scored 0.71–0.91. Four of ten pairs were the same photograph. |
| Black bands | **Ten of eleven frames** had a black band, 6%–20% of the frame. |
| Nine shots of a chopping board | Two of eleven shots reached the pan. The whole mise en place sat in frame throughout. |
| The knife never cut | The blade hovers over the board in every prep shot, touching nothing. |

**The causes, and what is now fixed in this zip.**

1. **The chain of edits collapsed.** Every shot was drawn from the one before. An edit model's safest answer is its own
   input, so an eleven-long chain drifts to no change at all. Fixed three ways: `MAX_CHAIN = 2`, so no shot is more
   than two edits from a fresh drawing; `compose.too_same()` compares each chained result against its reference and
   **redraws it fresh from words** when they are 94% alike or more — run against your actual eleven shots it flags
   exactly the four bad pairs and passes the six good ones; and the chain breaks whenever the cooking moves.
2. **One banded shot banded all the rest.** The clip filter was already cropping correctly, so the bands were baked
   into the pictures: shot 2 picked one up and every later edit copied it. `compose.fill()` now cuts black bands off
   and cover-crops every picture the moment it arrives, before anything else sees it. Run against your eleven frames
   it cleans ten of them; the eleventh has a genuinely dark background and is correctly left alone.
3. **The shot list was nine-tenths prep.** `balance()` now puts a floor under the cooking: at least 30% of shots at
   the stove or the plate, and the last shot is always the finished dish. A writer that already got it right is left
   alone.
4. **The prompts described ingredients, not cooking.** `peak_of()` now names the instant to photograph — *"the blade
   is already buried halfway through, the cut piece has fallen away, the knife is in contact with the board. Not
   hovering, not finished"* — and what has already been used is named as **out of frame** so the board actually
   empties. The negative list gained `knife hovering above the food`, `full mise en place`, `every ingredient laid out
   at once`, `silken tofu`, `white rubbery cubes`.

**Verified.** 8 of 8 new tests pass (`tests/test_asmr_cooking.py`). The gate and the band-cutter were both measured
against your real video. **Not yet verified against a live run** — that needs a picture model and credit.

**Improvements needed.**
- The paneer still reads as tofu. The fix is in the writer's "show, do not name" rule, which needs a worked Indian
  example in `RECIPE`, not more negative terms.
- The black gloves plus a white worktop read clinical. A dark wood or slate surface would suit the food better; the
  surface is in `SURFACES`, one line to change.
- Sound is synthesised per shot from its `asmr` line, so it is a texture, not a performance. It will never beat a
  recorded foley library.
- `fal.ai: no credit left` is caught and the run carries on, which is right, but the Models tab should warn
  **before** a run starts, not after shot 1.

---

## 4. Company Story — `company-story`

**Input.** A company or an industry: `Toyota`, `Nvidia`, `Zomato`, `the airline industry`. 30 s to 600 s, 16:9 or
9:16 reel.

**Needs.** An AI writer, a picture model, and a video model for motion. Research needs web access.

**How it works.** Seven stages: `research` (reads the Wikipedia article, keeps only researched numbers) → `script`
(act-by-act, 8 scenes at a time) → `cast` (founder characters) → `scenes` (backdrops, with characters placed **in
code** by `compose.py` so the same face appears in every scene) → `animate` → `voice` → `finish`.

Pacing is fixed: 10 s a scene up to 90 s, 12 s to 300 s, 15 s beyond. Narration is 2.6 words a second.

**Output.** `final.mp4`, narrated, with sources listed.

**Improvements needed.**
- The backdrop sometimes comes back as a dark empty room. There is a `too_dull()` gate that rejects and redraws, and
  the prompt appends `BRIGHTER` on the second try, but it is still the weakest stage.
- A 600-second story is ~40 scenes of video. At Seedance Mini that is around $90. There should be a warning.
- The video model is hardwired to Seedance — see below.

---

## 5. Mechanical Toy — `mechanical-toy`

**Input.** An object that transforms: `a seven-headed hydra`, `a vintage steam locomotive`.

**How it works.** Four stages: `design` locks the form in words → `compact` draws the folded state → `transformed`
draws the open state **from the compact picture**, so it is recognisably the same object → `video` animates between
them as a key-pose animatic.

**Output.** `transformation.mp4` plus both stills and all three prompts.

**Improvements needed.** It is the oldest skill and predates the paper-cut look, the `fill()` band-cutter and the
sameness gate. All three would help it.

## 6. Film Style — 66 skills (`film-art-deco`, `film-risograph`, …)

**Input.** What the film is about, in one line: `a student shipping her first app at 3am`. 15 s / 30 s / 45 s / 60 s,
16:9, 9:16 or 1:1.

**Needs.** An AI writer for the shot plan (without one it falls back to a plain three-beat plan and still finishes),
a picture model for the shots, a video model optionally — without one each shot gets a slow camera move and sound
synthesised from the style's own sound palette.

**How it works.** Each of the 66 Lemo-Opuscar styles is its own Skills-tab entry, all built at import time from one
implementation. Four stages — `plan`, `pictures`, `motion`, `finish` — mirroring ASMR Cooking, with the chain cap, the
sameness gate, the band cutter and takes. The style is a **lock on every prompt**: the same look sentence, colour rule
and list of what the style is not goes into every shot of a run, which is what makes six shots hold one look.

Shot counts: 15 s → 3, 30 s → 6, 45 s → 9, 60 s → 12, at 4–6 seconds each.

**The hard part was the 900-character budget.** A style's look alone is about a thousand characters. The first version
led with the look and let it take everything — every shot of a film came out with an identical prompt and no subject
in it. `_fit()` now reserves the shot first and gives the look what is left. There is a test per style for it: the
subject and the action must both survive at 900 characters, in all 66.

**Two things are stripped on the way in.** Real artist, director and building names, which the library uses as grammar
and which have no place in a prompt sent to a picture model. And build notes — canvas channels, blend modes, shader
maths — which mean nothing to a picture model and would crowd out the budget. `filmstyles.py` is generated by
`tools/extract_styles.py`; never hand-edit it.

**Output.** `final.mp4` at 1280×720, 720×1280 or 960×960, plus every shot picture and every prompt.

**Verified.** 75 of 76 tests pass here (`tests/test_film_style.py`), including the prompt budget for every one of the
66 styles. The 76th needs the full repo. **Not verified against a live run** — that needs a picture model with credit.

**Improvements needed.**
- The look is as close as a prompt can hold it. Upstream renders these in code and gets them exactly; this gets them
  approximately. That gap will not close with better prompts.
- The Skills tab is now a cover grid with search and category chips, and every skill has a cover image. The 66 film
  covers are the upstream posters resized to 480x270 — **stills by Lemomo, CC BY 4.0**, credited on each skill's page.
- No per-style negative list yet. Each style knows what it is *not*; only the first sentence of that reaches the prompt.

---

# Takes — redo one shot without losing the one it replaced

Borrowed from Maestro's Director, which keeps *"plans, prompts and takes together so you can revise individual
shots"*. AVOS could already redo a single shot, but the redo **overwrote** the old picture, so a second attempt that
came out worse lost the first. That is the wrong way round: the common case is a run where most shots are fine and
three are not — your Paneer run had four the picture model had collapsed into their own reference.

**How it works.** Every picture and every clip is now a *take*. `shot["picture"]` still holds a plain file name, so
everything that reads a shot is unchanged and knows nothing about any of this; it just always points at the chosen
take. Files are named `S04.png`, `S04b.png`, `S04c.png`, so a redo never lands on the last take's file.

| | |
|---|---|
| `GET /api/skills/{id}/takes/{n}` | every take of shot n, newest first, with its model and prompt |
| `POST /api/skills/{id}/takes/{n}` `{kind, take}` | use that take instead — nothing regenerated, nothing thrown away |
| `POST /api/skills/{id}/redo` `{step, n}` | make shot n again; the previous take stays on file |

A reset now clears the *pointer* and keeps the takes. Picking a take by hand also marks it **kept**, and a kept take
is never pruned — without that, going back to an early take and then trying a few more would quietly delete the very
one you went back to. (Found by a test, not by reasoning.) The limit is 8 per shot per kind.

**Verified.** 10 of 11 tests pass here (`tests/test_takes.py`); the eleventh imports the rest of the repo and will
run there. The flow was walked end to end against a stubbed eleven-shot cooking run: redo shot 4, the other ten
untouched, second attempt worse, one call back to the first.

**Still missing:** no UI for it yet. The endpoints work; the Skills tab has no take strip under a shot. That is the
next piece of front-end work and it is where the feature actually becomes usable.

---

# What else Maestro has that AVOS does not

Read off the Maestro repository, not the marketing page. Maestro is a local CUDA pipeline built on WanGP, running
open weights on your own RTX card. AVOS calls hosted models. That difference explains most of the rest.

| Maestro | AVOS today | Worth taking? |
|---|---|---|
| **Takes** on every shot | **done, above** | — |
| **Auto vs Manual mode** — run the whole production, or stop at each stage for review | Company Story has a review pause; nothing else does | **Yes, and cheap.** One `pause_after` list in the pipeline generalises it to every skill |
| **Studio bench** — pick workflow + model + prompt + refs + LoRAs, queue jobs, browse a gallery | Prompt to Video is close, but it is a skill with fixed stages, not a free bench | **Yes.** The most-missed thing for anyone who just wants one image |
| **Saved characters** with appearance references and an optional voice, reusable across projects | `characters/` holds ready-made 2D cut-outs; you cannot make your own | Yes, but a real piece of work |
| **Non-destructive multi-track editor** — trim, transitions, speed, volume, titles, send a shot back through AI | a Timeline view, no editing | Not soon. This is a video editor |
| **Local open weights** — LTX-2.3, Wan 1/2, Hunyuan, Flux 2 Klein, Qwen Image Edit, ACE-Step, MMAudio | hosted models, GPU tab for your own worker | **Partly.** Your GPU worker is the hook; LTX-2.3 Distilled and Wan 2 GGUF would run on it |
| **MCP server** so an agent can drive it | REST API | Yes, small, and it would let Claude Code drive AVOS directly |
| **Song-first direction** — analyse a track, cut visuals to its sections | nothing | Interesting, and `song-style-ad` already has half the thinking |

**The honest comparison.** Maestro is a generation studio: its strength is breadth of models and a real editor.
AVOS is a set of opinionated recipes: its strength is that a skill knows what a *good* company story or cutting reel
looks like and enforces it — the paper-cut look, the pacing table, the cooking floor, the exact cut count. Maestro
will not make you an ASMR cutting video for free in forty-five seconds, and AVOS will not let you trim a clip.

The three worth copying, in order: **manual mode** (cheap, immediately useful), **a Studio bench** (most asked for),
**local weights on your GPU worker** (it would make Company Story free instead of $9.30).

---

# Instruction files (`avos-*`)

Markdown AVOS reads at run time. Edit one and the next run follows it — no rebuild, no restart.

| File | Steers |
|---|---|
| `avos-paper-art` | the handcrafted paper-cut look, shared by every skill that offers it |
| `avos-company-story` · `-writer` · `-pictures` · `-check` | Company Story, end to end |
| `avos-asmr-cooking` | the ASMR Cooking director |
| `avos-asmr-cutting` | the ASMR Cutting spec |
| `avos-motion-graphics` | the JSON spec behind the four animations |
| `avos-prompt-to-video` | every hop: prompt→image, image→video, image+storyboard→video, and the measured model limits |
| `avos-camera` | shot sizes, angles, moves, and why the default is a locked camera |
| `avos-house-director` | the eight house rules sent with every shot plan, and the free plan check that follows it |
| `avos-when-it-fails` | the failure catalogue: repeating shots, a style that loses to its subject, actions that never finish, mimed hands, black bands, default sound |
| `avos-reach` | the hook, one film into several shapes, the words around it, and planning a series |

Hard limits worth knowing, all measured: **Pollinations cuts a prompt at 900 characters** · FLUX about 256 tokens ·
Seedance clamps duration to **4–15 s**, takes `images[:9]`, aspect 16:9 / 9:16 / 1:1 · **FLUX.2 klein takes at most 4
references, each under 512×512** · video reference files must be under **8 MB**. They are all written up, with what
each one means for a prompt, in `avos-prompt-to-video`.

**Duration and aspect ratio are parameters, not prompt text.** They are passed to the model beside the prompt, so
writing "5 seconds" or "9:16" into the words sets nothing and spends budget the craft lines need. `motion_prompt()`
keeps them out.

---

# Agent skills — your PC, not the container

| Folder | What it is | Needs |
|---|---|---|
| `avos-wingman` | the production-bible + hard-cut character short pattern | nothing — it is a way of writing prompts |
| `disney-pixar-animation` | Pixar-look prompts for ads and B-roll | an image/video model |
| `song-style-ad` | a sung product ad | a music model |
| `animation-skills/` | six MIT code-rendered skills by Artem Novitckii | Node + headless Chrome |
| `faceless-shorts/` | six narrated-short styles, free and fully local | **Node 22, Chrome, ~1 GB of voice models** |
| `lemo-opuscar/` | **66 code-rendered film style prompts** by Lemomo — prompts and guides only | Node 20+, ffmpeg 7+, Python 3.11+ |

### The three code-rendered libraries, compared

All three draw every frame rather than generating one, which is why none of them costs anything to run and why none
of them runs in the container (**no Node, no browser**).

| | Styles | Length | Narration | Vendored |
|---|---|---|---|---|
| `animation-skills` | 6 | ~10 s | 2 of 6 | in full, and 4 ported to Python as **Motion Graphics** |
| `faceless-shorts` | 6 | 30–45 s | yes, local Kokoro | in full |
| `lemo-opuscar` | **66** | ~60 s | yes, local Kokoro | **prompts and guides only** — see its `README-AVOS.md` |

Lemo-Opuscar is vendored as prompts because the full repository is 191 MB, of which 50 MB is posters and 8 MB is
per-style renderer code that needs Node anyway. The 66 `STYLE.md` files are 0.9 MB and stand on their own. The proper
way to *run* it is the plugin: `claude plugin marketplace add lemomo-ai/lemo-opuscar`.

Worth reading even if you never run it: these are a written vocabulary for what a code-rendered look *is*, at about
twelve pages each. `avos-paper-art` is AVOS's only document of that kind and it is one page. If Motion Graphics grows
past its four scenes, this is where the next looks should come from.

Neither vendored collection runs in the container — it has **no Node and no browser**. Each keeps its own
`README-AVOS.md` saying exactly what it needs.

---

# The scripts you need

**Install an update** (the zips are cumulative, so this is always the same):

```bash
cd /d/star/apps && unzip -o ~/Downloads/avos-latest.zip -d /d/star/apps && docker compose up -d --build animation-studio
```

`restart` alone is not enough — the build step is what picks up changed Python.

**Check it came up:**

```bash
docker compose ps animation-studio && docker compose logs --tail=40 animation-studio
```

**Run the tests:**

```bash
docker compose exec animation-studio python -m pytest tests -q
```

**Commit** (the no-reply address — GitHub rejects the private one):

```bash
git config user.email "141348079+sanjithrana@users.noreply.github.com"
git add -A && git commit -m "ASMR Cutting, cooking fixes, skills guide" && git push
```

**Faceless Shorts, once, on your PC** (not in the container):

```bash
unzip -o ~/Downloads/faceless-shorts.zip -d /d/star/apps
bash skills/faceless-shorts/scripts/setup.sh      # until it prints "All set"
bash skills/faceless-shorts/scripts/selftest.sh   # must print "SELFTEST PASSED"
```

---

# Improvements needed, in the order I would do them

1. **Run the test suite against the full repo.** Motion Graphics' Skill Lab glue has never executed. Everything else
   in this list is cosmetic next to that. Send `apps.zip` and it takes one pass.
2. **Make the video model selectable.** The Skill Lab is hardwired to the Seedance endpoint, so the cheaper Wan 2.2
   cannot be picked there. This roughly halves the cost of every Company Story and ASMR Cooking run, and it is the
   single highest-value change on this list for a student paying per second.
3. **Warn about credit and cost before a run, not during it.** Your Paneer run spent its images and then failed at
   the video. A pre-flight check in the Models tab would have caught it.
4. **A take strip in the Skills tab.** The takes endpoints work; there is no UI. Without it the feature exists only
   over curl, which is not where you are working.
5. **Apply `fill()`, `too_same()` and takes everywhere.** All three are in place and measured, but only ASMR Cooking
   uses them. Company Story and Mechanical Toy have the same failure modes.
6. **Manual mode for every skill** — stop after each stage so a bad shot list is caught before it is paid for.
7. **Give Motion Graphics sound.** `foley.py` already exists.
8. **Fix the paneer.** Add a worked Indian example to the `RECIPE` "show, do not name" rule.
9. **Port `stick-figure` and `zach-d-films`**, or decide not to and say so in the README. They need voice models,
   which is a different kind of project.

## The house director (one director for everything)

Every section used to have its own director. They shared the AI connection and nothing else: the Explainer knew camera
words, Stickman checked its plans, Film Style fitted prompts to the model's limit. `studio/house.py` is the shared part.

| Piece | What it does | Cost |
|---|---|---|
| `house.rules()` | eight film rules added to every shot-planning call (`writers.directed`). Edit them in `avos-house-director/SKILL.md` | about 200 tokens per plan |
| `house.review()` | reads the finished plan: two actions in one shot, a thought instead of a picture, an opening with nothing moving, the same framing twice | free, no AI call |
| `house.unrepeat_framing()` | when two shots in a row have the same distance and the same camera move, changes the second one's move | free |
| `house.fit()` | sizes a picture prompt to the model's limit and never cuts the shot itself | free |

Who uses it: Explainer (rules, check, fix, and findings feed its prompt library), Stickman (rules on the story and
each clip, check on the story, fix between clips), all 66 Film Styles and ASMR Cooking (rules and check), Company
Story (rules, check, and scenes in one setting no longer all push in). Animations only gets the check as a note,
because that breakdown is your own prompt and is kept as written. ASMR Cutting, Motion Graphics and Mechanical Toy
plan no shots, so they are unchanged.

What it reports shows up as a note on the plan step (skills) or a line in Activity (Explainer, Stickman, Animations).
