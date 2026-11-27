# apps/skills

**Start with [SKILLS-GUIDE.md](SKILLS-GUIDE.md)** — what every skill takes, needs, does, returns, and still needs doing.

Two kinds of thing live here, and the difference matters.

## 1. AVOS instruction files (`avos-*`)

Markdown that AVOS itself reads at run time - what its writers, directors and checkers are told before they write. They
show in the desktop under **Skills → Instruction files**. Edit one and the next run follows it; no rebuild, no restart.

| File | What it steers |
|---|---|
| `avos-paper-art` | the handcrafted paper-cut look, shared by every skill that offers it |
| `avos-company-story` · `-writer` · `-pictures` · `-check` | the Company Story skill, end to end |
| `avos-asmr-cooking` | the ASMR Cooking skill |
| `avos-asmr-cutting` | the ASMR Cutting skill |
| `avos-motion-graphics` | the JSON spec behind the four code-drawn animations |
| `avos-film-style` | the 66-look Film Style skill: the prompt budget, what is stripped, how to add a style |
| `avos-prompt-to-video` | how to write prompts for every hop: prompt→image, image→video, image+storyboard→video, plus the measured model limits |
| `avos-camera` | shot sizes, angles and moves; which ones a video model honours and when to leave the camera locked |
| `avos-house-director` | the eight film rules every director shares - Explainer, Stickman, every Film Style, ASMR Cooking, Company Story |
| `avos-when-it-fails` | a bad run diagnosed: symptom, cause, and the one thing to change |
| `avos-reach` | the hook, the aspect variants, the words around the video, and planning a series rather than one-offs |

Takes (every version of a shot kept, so you can redo one and go back) and the Maestro comparison are both in the guide.

## 2. Agent skills (everything else)

Skills for an agent session - Claude Code on your PC - not for the AVOS container. They are listed in the panel too, so
you can read them from the desktop, but AVOS does not run them.

| Folder | What it is | Needs |
|---|---|---|
| `avos-wingman` | the production-bible + hard-cut character short pattern | nothing: it is a way of writing prompts |
| `stylized-3d-animation` | 3D animated feature-film look prompts for ads and B-roll | an image/video model |
| `song-style-ad` | a sung product ad | a music model |
| `animation-skills/` | six MIT code-rendered animation skills by Artem Novitckii | Node + headless Chrome |
| `faceless-shorts/` | six narrated-short styles, free and fully local | Node 22, Chrome, ~1 GB of voice models |
| `lemo-opuscar/` | 66 code-rendered film style prompts by Lemomo (prompts only; install the plugin to run them) | Node 20+, ffmpeg 7+, Python 3.11+ |

`animation-skills` and `faceless-shorts` keep their own `README-AVOS.md` saying exactly what they need and why they are
not Skills-tab skills. Four of the six animation skills have already been ported to pure Python and live in the Skills
tab as **Motion Graphics**, which needs none of that toolchain.

## The Skills tab, for comparison

It is a cover grid now — search, category chips and a thumbnail per skill — because a sidebar list built for five
skills does not work for seventy-one. Covers live at `apps/desktop/public/skills/<skill-id>.jpg`.


These run inside the container, with stages you can watch: Mechanical Toy, Company Story, ASMR Cooking, ASMR Cutting,
Motion Graphics, and **66 Film Style skills** (`film-art-deco`, `film-risograph`, …). Of those, **Motion Graphics and ASMR Cutting use no model at all** - every frame is drawn in code and
every sound synthesised - so they cost nothing to run and give the same result twice.
