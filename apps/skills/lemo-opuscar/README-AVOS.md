# Lemo-Opuscar, vendored into AVOS — the style prompts only

66 film styles by Lemomo (LemoLab), every one rendered **in code with no video model** — canvas and WebGL pages
captured frame by frame, narrated with a local voice. Closest thing in spirit to AVOS's own Motion Graphics and
ASMR Cutting, which also draw every frame rather than generating one.

Upstream: <https://github.com/lemomo-ai/lemo-opuscar> · MIT for code and docs.

## What is here, and what is not

| Vendored | Not vendored | Why |
|---|---|---|
| All 66 `STYLE.md` style prompts | the 66 demo films and their renderer code | 8 MB of per-style JS/Python that needs Node to run |
| All 66 `style.json` | the full-size posters and styleframes | 50 MB; the covers below are made from them instead |
| 66 cover stills at 480x270, in `desktop/public/skills/film-*.jpg` | — | 1.5 MB in all, so each skill has a card in the Skills tab |
| `INDEX.md`, generated from the metadata | `docs/`, `styleboard/`, `core/`, `tools/` | they come with the plugin install, below |
| `DIRECTOR.md`, `TECHNIQUE.md`, `MY-STYLES.md`, `AGENTS.md`, `LICENSE` | the six restricted voice tracks | the README asks that those not be reused |

A `STYLE.md` stands on its own: it describes the look, the materials, the colour logic, the typography, the motion
quality and what the style is *not*, in enough detail for an agent to build it. That is the part worth having in the
repo. The demos are what you install the real thing for.

## This does not run in the container

Like `animation-skills` and `faceless-shorts`: **no Node and no browser in `animation-studio`.** Lemo-Opuscar needs
**Node 20+, ffmpeg 7+ and Python 3.11+**, and it is built to run inside Claude Code on Claude Opus 5.5 — its README
warns that "other models may not reproduce them well." A film takes 30–60 minutes and a fair number of tokens.

## To actually use it, install the plugin

Vendoring the prompts is for reference. The proper install is two commands, and it is strictly better than copying
the repo in, because it keeps itself up to date:

```bash
claude plugin marketplace add lemomo-ai/lemo-opuscar
claude plugin install lemo-opuscar@lemolab
```

On first use it downloads the guides, tools and style prompts to `~/lemo-opuscar`. Films land in `films/<name>/`.
Ask for a storyboard of the key shots before committing to a full film — it is much cheaper to change your mind there.

## How it sits beside AVOS

| You want | Use |
|---|---|
| A 60-second narrated film in one of 66 looks, free, on your PC | **Lemo-Opuscar** (plugin install) |
| A 30–45 s narrated explainer in one of 6 looks, free, on your PC | **Faceless Shorts** |
| A stat, journey or device animation in 10 s, free, in the container | **Motion Graphics** |
| A cutting reel, free, in the container | **ASMR Cutting** |
| A cooking reel, a brand story, a transformation toy | the model-driven Skill Lab skills |

**Why the prompts are worth reading even if you never run it.** AVOS's code-rendered skills have one look each.
These 66 are a written vocabulary for what a code-rendered look *is* — `art-deco` on gold keylines and airbrushed
volumes, the "characters step on twos at 12 fps while camera and light run on ones" rule, the one-saturated-accent
colour discipline. `avos-paper-art` is AVOS's only document of that kind, and it is a page long. These are twelve.

If Motion Graphics ever grows beyond its four scenes, this is where the next looks should come from.

## Licence

MIT for the code and docs vendored here; `LICENSE` is included.

The 66 cover images in `apps/desktop/public/skills/film-*.jpg` are the upstream posters, resized to 480x270. They are
**stills from Lemomo's demo films, used under CC BY 4.0**, which asks for attribution: every film skill carries
"cover still by Lemomo, CC BY 4.0" in its `credit`, shown on the skill's page. If you publish anything that shows
these covers, keep that credit with them. The six restricted voice tracks are not vendored and must not be reused.

Films you make with the library are yours.
