# Faceless Shorts, vendored into AVOS

A complete narrated-shorts skill with six styles: `deep-dive`, `night-file`, `inside-out`, `stick-story`,
`paper-atlas`, `tall-tale`. Upstream `SKILL.md`, `README.md`, the scripts and all six style folders are unchanged;
this file is the only thing added.

## Read this before you try to run it

**It does not run in the `animation-studio` container, and it is not a Skills tab skill.** It is a Claude Code skill
that runs on your Windows machine, and it needs things the container does not have:

| Needs | The container has | Your PC |
|---|---|---|
| Node 22+ | no Node at all | install from nodejs.org |
| Chrome (headless capture) | no browser | you already have it |
| ffmpeg | yes | comes with the setup script's checks |
| Python venv + Kokoro voice, ~340 MB | no | downloaded on first setup |
| Whisper small.en, ~0.5 GB | no | downloaded on first setup |

So about **1 GB of model downloads once**, then every short after that is free: no picture model, no video model, no
API key, no credits. Everything is canvas drawing, headless Chrome capture, ffmpeg and numpy sound.

## Running it

In a Claude Code session on your PC, in `/d/star/apps`:

```bash
bash skills/faceless-shorts/scripts/setup.sh     # until it prints "All set"
bash skills/faceless-shorts/scripts/selftest.sh  # must print "SELFTEST PASSED"
```

Then ask for a short and name a style, or just a topic and let it choose. Projects land in `~/faceless-shorts/<name>/`.

If `setup.sh` stops on Node, that is the one thing you have to install by hand. Everything else it fetches itself.

## How it relates to what AVOS already does

These six styles overlap with AVOS skills but are not duplicates - they are the *narrated 30-45 second explainer*
shape, where AVOS's own skills are shorter and model-driven:

| You want | Use |
|---|---|
| A narrated 30-45 s explainer with word-synced captions, free | **Faceless Shorts** (this, on your PC) |
| A stat, a journey, a device coming apart, in 10 seconds, free | **Motion Graphics** (Skills tab) |
| A cutting reel, free | **ASMR Cutting** (Skills tab) |
| A cooking reel with synthesised foley | **ASMR Cooking** (Skills tab) |
| A brand or founder story with AI pictures and video | **Company Story** (Skills tab) |

The styles' `style-sheet.png` files are worth opening on their own - each is the look of that style in one image, and
they are useful reference even when you are writing prompts for a model instead.

## Could it be ported to Python, like the animation skills were?

Four of the animation skills were ported because each was one scene with a fixed look. These are not: each style is a
full rendering engine (`src/core/engine.js`, `human.js`, `sdf.js`, `sets3d.js`, `captions.js`) plus a voice model and a
word-timing model. Porting six of those is a project in its own right, not a tidy-up, and the result would be worse
than what is here. Left as it is, deliberately.
