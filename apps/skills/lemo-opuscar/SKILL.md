---
name: lemo-opuscar
description: Reference library of 66 code-rendered film styles by Lemomo - art deco, rubber hose, risograph, silent film, liminal found footage and 62 more, each a full style prompt for building that look in code with no video model. Use when choosing or writing a visual style for a film, or when AVOS needs a new code-rendered look.
---

# Lemo-Opuscar — 66 film styles, rendered in code

Start at **[INDEX.md](INDEX.md)**: all 66 styles by category, with what each looks like and what it suits.

Every style folder holds a `STYLE.md` — the full style prompt covering essence and what the style is *not*, materials
and rendering, colour logic, type and subtitles, and motion quality — plus `style.json` with its metadata. The three
guides beside this file are the upstream ones: `DIRECTOR.md` (direction), `TECHNIQUE.md` (building), `MY-STYLES.md`
(making a style your own).

**This library is prompts, not a runner.** The demo films and their renderer code are not vendored. To actually make
films with it you install the plugin, which needs Node 20+, ffmpeg 7+ and Python 3.11+ on your PC — it does not run
in the `animation-studio` container:

```bash
claude plugin marketplace add lemomo-ai/lemo-opuscar
claude plugin install lemo-opuscar@lemolab
```

See `README-AVOS.md` for what was and was not vendored, and why these prompts are worth reading even if you never run
the plugin. MIT; films you make are yours.
