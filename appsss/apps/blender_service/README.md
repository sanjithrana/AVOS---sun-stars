# AVOS Blender engine (video provider "blender")

Every shot of a project becomes a real 3D scene, rendered by Blender:

1. The shot's description (from the script) goes to your LLM (Groq / Ollama / OpenAI,
   whatever the project uses). It returns a **scene plan**: environment, characters,
   what each one does, props, and the camera. It can only choose things this service
   actually has (`GET /catalog`). Without an LLM, a keyword planner does it.
2. This service builds the scene in Blender and renders the shot to MP4.
3. AVOS joins the shots with the narration, captions, music and whooshes.

Free per video. Speed depends on your hardware (see below).

## What's built in

| | |
|---|---|
| Environments | `grid_studio` (light-blue tiled studio), `desert`, `space` (Moon surface + Earth), `night_city_floor` (neon grid) |
| Characters | a 3D mannequin in 6 variants: `man`, `woman`, `giant`, `kid`, `robot`, `astronaut` |
| Actions | idle, walk, run, punch, push, jump, wave, fall, celebrate, dance, point, shocked, fight_idle |
| Props | box, sphere, ball, gold_bar, balloon, wall, pillar, rock, tree, bullet, coin, car_block, planet, moon, sun_orb (motions: spin, float, fall, bounce, shake, fly) |
| Camera | wide / medium / close; static, push_in, pull_out, orbit, pan, low_angle, track |

## Realistic people: add Mixamo characters and animations (free)

1. Go to **mixamo.com** and sign in with a free Adobe account.
2. **Characters** tab → pick a character (e.g. *Remy*, *Kaya*; *Mutant* or
   *Brute* work as a "giant"). **Download**: Format **FBX Binary (.fbx)**, Pose **T-pose**.
   Save it into `apps/blender_assets/characters/` and **name the file after what it is**:
   `man.fbx`, `woman.fbx`, `giant.fbx`, `kid.fbx` ... (those names replace the mannequin
   automatically; any other name, e.g. `remy.fbx`, becomes a character the LLM can pick).
3. **Animations** tab → search e.g. *Punching*, *Walking*, *Running*, *Jump*, *Idle*,
   *Falling Back Death*, *Victory*, *Hip Hop Dancing*, *Waving*. Tick **In Place** when the
   option exists. **Download**: Format **FBX Binary**, Skin **Without Skin**, 30 fps.
   Save into `apps/blender_assets/animations/`, named by the action: `punch.fbx`,
   `walk.fbx`, `run.fbx`, `jump.fbx`, `idle.fbx`, `fall.fbx`, `celebrate.fbx`, `dance.fbx`,
   `wave.fbx` ... Any other name (e.g. `flying_kick.fbx`) becomes an action the LLM can use.
4. Done - new files are picked up on the next render (the folder is mounted live).

Mixamo animations work on any Mixamo character (they share the same skeleton). A Mixamo
character asked for an action you haven't downloaded uses the closest one you have
(an idle, if nothing matches) - never a T-pose. Props: any `.glb` / `.fbx` / `.obj` in
`blender_assets/props/` (e.g. a free gorilla or car model from Sketchfab / Poly Haven)
becomes a prop the LLM can place by its file name.

Mixamo's licence lets you use the characters and animations in your videos (including
monetised ones); you just can't redistribute the raw files.

## Running it

**Option A - Docker (CPU, works anywhere):**

```
cd apps
docker compose up -d --build blender
```

Renders with Cycles on the CPU. On a typical 8-core laptop expect very roughly 1-3 s per
frame at the default 540x960, 16 samples, 24 fps - so several minutes per shot. For
faster test runs set in `apps/.env`: `BLENDER_FPS=15`, `BLENDER_SAMPLES=8`, or
`BLENDER_ENGINE=workbench` (flat preview look, seconds per shot).

**Option B - your own Blender on Windows with a GPU (much faster):**

1. Install Blender **5.0** from blender.org.
2. Start the service with your Blender (keep this window open):

   ```
   "C:\Program Files\Blender Foundation\Blender 5.0\blender.exe" -b --python D:\star\apps\blender_service\server.py
   ```

   For the best quality/speed on an NVIDIA/AMD GPU, set these first in the same window:
   `set BLENDER_ENGINE=eevee` (or `set BLENDER_GPU=1` for Cycles on the GPU).
3. In `apps/.env`: `BLENDER_RENDER_URL=http://host.docker.internal:8090`, then
   `docker compose up -d --force-recreate api worker`. (Stop the Docker one:
   `docker compose stop blender`.)

## Check it

```
curl http://127.0.0.1:8090/health
curl http://127.0.0.1:8090/catalog
```

`/catalog` lists your Mixamo files under `library_characters` / `library_animations`.

Tests (inside the container): `docker compose exec blender python -m pytest /app/blender_service/tests -q`

Note: `BLENDER_SERVICE_URL` (physics proxy passes) is a different, older setting - leave
it empty; this service is `BLENDER_RENDER_URL`.
