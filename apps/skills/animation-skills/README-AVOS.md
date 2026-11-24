# Animation skills, vendored into AVOS

Six animation skills by **Artem Novitckii**, MIT licensed, from
<https://github.com/artemnovitckii/claude-animation-skills>. The upstream README is kept beside this file as
`UPSTREAM-README.md`, and the licence as `LICENSE`. Nothing here has been modified.

## What they are

They render **in code** - three.js, GSAP and HyperFrames driving a headless browser, then ffmpeg. There is no picture
model and no video model anywhere in them, so they cost nothing to run and give the same result every time.

| Skill | Makes | Needs three.js |
|---|---|---|
| `graph` | a line that draws itself while a number counts up | no |
| `minimalistic-graphics` | black-and-white line art, a dot hopping up steps | no |
| `map-route` | a 3D white city with a route drawing itself, pin drop, ETA | yes |
| `breakdown` | a 3D exploded view with leader lines and labels | yes |
| `stick-figure` | a full stick-figure explainer reel, voiced and captioned | no (needs the voice models) |
| `zach-d-films` | a 3D cartoon "what if" explainer | yes (needs the voice models) |

All output 1080x1920 at 30 fps - reels shape.

The first four take a small JSON spec and render in about 10 seconds (2D) or 1.5 minutes (3D). The last two are
full projects: they want a working session, a voiceover and about 1 GB of voice models.

## They are Claude Code skills, not Skill Lab skills

Each one is a `SKILL.md` plus a `build.py`, written to be run by an agent as `/graph`, `/map-route` and so on. They
have no `STAGES`/`RUN`, so they do **not** appear in the AVOS Skills tab and cannot be started from it as things stand.

**To use them today**, install them the way upstream intends, on the machine where you run Claude Code:

```bash
git clone https://github.com/artemnovitckii/claude-animation-skills.git ~/claude-animation-skills
cd ~/claude-animation-skills && ./install.sh          # add --voice for stick-figure and zach-d-films
```

Then in Claude Code: `/graph 0 to 100K followers in 9 months: 1.2K, 2.1K, 5K, 24K, 100K`

## What running them inside AVOS would need

`kit/anim.py` shells out at render time. For the `animation-studio` container to render these, it needs:

- **ffmpeg and ffprobe** on PATH - already there.
- **Node.js and npx** on PATH - *not* in the Python image today, as far as I can tell.
- **`npx hyperframes@0.8.34`** at render time, so either outbound access to the npm registry from the container, or
  hyperframes installed into the image at build time.
- **`kit/vendor/gsap.min.js`** - fetched once from cdnjs by `kit/setup.sh`.
- **`kit/node_modules/three`** - only for `map-route`, `breakdown` and `zach-d-films`.
- A headless Chromium for HyperFrames to drive.

Once those exist, one Skill Lab skill can cover the four quick ones: the AI writes the JSON spec from the subject,
the skill runs that skill's `build.py`, and the mp4 comes back - free, and with no model keys involved.
