# AVOS — Runbook (Weeks 1–3, complete; Week 4: real video output)

Everything here was verified end to end: 292 Python tests (unit + real
Postgres / Redis / Temporal + live API) and 6 Playwright browser tests,
including the Week 3 Day 15 integration checkpoint - one project going
from a typed topic to a QA-evaluated, repaired-where-forced, approved
set of shots, entirely through the real architecture, zero console
errors, zero manual DB/Temporal intervention - plus Week 3 Day 16's
per-project Ollama/Groq/free-image/self-hosted-video provider routing
and its multi-provider daily-quota fallback chain (see those sections
below), also verified against the real stack, live, with real
credentials (Ollama, Groq and Pollinations all confirmed working
end-to-end against real APIs).

## Services

| Service       | Where                          | What it does                                  |
|---------------|--------------------------------|-----------------------------------------------|
| `api`         | http://localhost:8001          | FastAPI; runs DB migrations on every start    |
| `worker`      | (no port)                      | Temporal worker — executes the video workflow |
| `postgres`    | localhost:5435                 | App DB (+ Temporal's DBs)                     |
| `redis`       | localhost:6380                 | Event bus (live UI updates over SSE)          |
| `temporal`    | localhost:7233                 | Durable workflows                             |
| `temporal-ui` | http://localhost:8233          | Temporal Web UI                               |
| `desktop`     | http://localhost:3000          | Next.js UI (run on your machine, see below)   |

## Start it

```bash
cd apps
docker compose up -d --build      # first time, or after changing requirements.txt
docker compose ps                 # api should be "healthy", worker "running"

cd desktop
npm install
npm run dev                       # http://localhost:3000
```

Use `docker compose` (with a space). Migrations run automatically when the
`api` container starts — no manual `alembic upgrade head` needed.

**Opening the UI from another device** (e.g. `http://192.168.1.12:3000`)
works out of the box: the UI calls the API on the same host at port 8001,
the dev server allows all of this machine's IPs, and the API accepts
private-network origins (192.168.x.x, 10.x, 172.16–31.x, 100.64–127.x,
`*.local`). For anything else, add it to `CORS_ORIGINS` in
`docker-compose.yml`. To pin the API address, copy `desktop/.env.example`
to `desktop/.env.local`.

## The demo (Week 1 + Week 2 checkpoint)

1. Dashboard → **New Project** → topic "Flowers for Kids", 30 s, 9:16 → Create.
2. On the project page click **Generate Video**. Job goes **RUNNING**.
3. The Director checks memory, researches and writes the script — watch it
   live in Studio → *Agent Activity* (no page refresh; SSE).
4. **Review in Studio** appears. The workflow is now genuinely paused in
   Temporal (no polling) — nothing happens until you decide.
5. **Approve** → the workflow resumes: narration audio, word/sentence
   timestamps and semantic beats. Storyboard, Timeline (playable audio)
   and Scene Info fill in; job **COMPLETED**, project **Complete**.
   **Reject** instead → job stopped, project "Script rejected"; click
   Generate again for a new script.
6. **Week 3:** after audio the project shows **Planning shots**: the
   Director creates one ShotSpec per semantic beat (`create_shot_spec`),
   checks each against the WorldState (`validate_shot_spec`), then the
   Physics agent runs the Blender stage per shot (`run_blender_proxy`).
   The Storyboard fills with shot cards (**Physics ready**); click one to
   open the **ShotEditor** (Narrative / Camera / Character / Environment /
   Prompt, read-only) with its depth / normal / canny / mask passes.
7. Every tool call is in the audit trail:
   `GET http://localhost:8001/api/v1/agents/trace?project_id=<id>`

Pipeline: `CreateVideoWorkflow` = research → script → **human gate** →
audio → shot planning → **Blender stage** → finalize. Every tool call goes through the Tool Gateway (schema →
permission → constitution check → execute) and writes exactly one
`audit_records` row, increments `budget_spent`, and emits
`BUDGET_WARNING` at 80% / `BUDGET_EXCEEDED` at 100% of an optional
per-project budget.

## Week 3 — shots, continuity, physics before pixels

| Endpoint | What |
|---|---|
| `GET  /api/v1/projects/{id}/shots` | Storyboard: every shot + its current ShotSpec version |
| `POST /api/v1/projects/{id}/shots` | Create a shot, or a new version (`shot_index` given) |
| `POST /api/v1/projects/{id}/shots/plan` | Director: plan missing shots from beats (+ Blender) |
| `GET  /api/v1/shots/{id}` | ShotEditor: shot, all versions, physics assets |
| `POST /api/v1/shots/{id}/validate` | Continuity check (doesn't advance the WorldState) |
| `POST /api/v1/shots/{id}/blender` | Blender stage for one shot (409 unless PLANNED) |
| `GET  /api/v1/projects/{id}/world-state` | Current WorldState |

Tables (migration 08): `shots` (stable identity), `shot_versions`
(immutable versioned ShotSpecs: version / parent_version / content_hash /
continuity / physics_proxy_asset_id), `world_states` (versioned snapshots).

**Blender is a MOCK by default** (no GPU here). `MockBlenderClient` is
deterministic (same ShotSpec → same bytes), returns real PNG depth /
normal / canny / mask passes, tags every asset `renderer: "MOCK"`
(`source: blender_mock`) and logs `[MOCK] Blender stage: …` in the worker
log. Assets: one `physics_proxy` (JSON) plus `blender_depth|normal|canny|mask`
with `parent_asset` = the proxy and `content_hash` = sha256 of the bytes.
For real renders set `BLENDER_SERVICE_URL` (a headless Blender service
that answers `POST /render` with base64 passes) and restart api + worker.

**Physics before pixels** is enforced by the Tool Gateway, not by
convention: `generate_video_shot` is rejected with `MISSING_DEPENDENCY`
(before the executor runs, and audited) unless the shot's *current*
version has completed the Blender stage and the call names exactly that
proxy — a made-up id, another shot's proxy, or a stale proxy from before
an edit are all rejected. Proven by `api/tests/test_physics_before_pixels.py`.

## Week 3 Day 13 — idempotent generation, Prompt Compiler, live monitor

| Endpoint | What |
|---|---|
| `POST /api/v1/shots/{id}/generate` | Video agent: 3 candidates from the shot's physics proxy (409 unless Blender is done). Optional `?idempotency_key=` |

`plan_shots` (both the `POST /shots/plan` route and the Director's own
call) now also runs the generation stage automatically for every shot
that reaches `BLENDER_READY`, so a fully-planned project lands on
`QA_PENDING` with 3 candidates per shot with no extra clicks. The
Temporal `CreateVideoWorkflow` deliberately still stops at the Blender
stage for its own activities (generation is reachable through the two
routes above, not baked into the workflow) — that keeps physics and
pixels as clearly separable stages, matching Day 12's own boundary.

**Idempotency (AVOS-03 v1.1 §9.5).** Every `generate_video_shot` call
carries an idempotency key: the caller's own (`?idempotency_key=`, or the
tool input's `idempotency_key`), or, if omitted, one derived from
`shot_id + version + content_hash + physics_proxy_asset_id`. A second
call with the same key — a UI double-click, a retried request — returns
the *first* call's `video_generations` row and candidate asset ids
unchanged: no new database row, no new Asset Registry writes. An edited
ShotSpec always gets a fresh physics proxy (Day 12), which changes the
default key too, so re-generating after an edit is correctly a new job,
not a stale cache hit. Proven directly by
`api/tests/test_video_generation_idempotency.py` (fires the same request
twice and asserts the asset/row counts don't move), independent of the
Playwright e2e test that exercises the same guarantee through the UI.

**Prompt Compiler** (`agentic_core/pipelines/shot/prompt_compiler.py`,
AVOS-03 v1.1 §10) is a pure function: `ShotContent` → `CompiledPrompt`
(prompt text, negative prompt, seed, resolution, camera/style params,
physics conditioning, `params_hash`). No randomness beyond a caller-given
seed — the same ShotSpec always compiles to the same output, proven by
`agentic_core/tests/test_prompt_compiler.py`. `VideoGenerationService`
calls it once per candidate (3 different `candidate_index` values, so 3
different deterministic seeds) before generating.

**Generation is a MOCK by default**, same shape as Blender: each
candidate is a `video_candidate` JSON asset (the compiled prompt) plus a
real, deterministic `video_thumbnail` PNG (reusing the Day 12 encoder),
both tagged `renderer: "MOCK"` (`source: video_mock`), with lineage
`video_generation` (root) → `video_candidate` → `video_thumbnail`. Swap in
a real generator by giving `VideoGenerationService` a real client the
same way `BlenderStageService` takes one.

**GenerationMonitor** (`desktop/components/studio/GenerationMonitor.tsx`)
shows a live progress row per shot — no polling: `VIDEO_GENERATED` (and
`BLENDER_RENDERED`) events invalidate the shots query over the existing
SSE connection (`hooks/useLiveProject.ts`), the same pattern the
Storyboard/ShotEditor already use. A manual "Generate" button covers any
shot that reaches `BLENDER_READY` outside the automatic pipeline (added
after the fact, or re-rendered after an edit).

## Week 3 Day 14 — QA committee + the repair ladder

| Endpoint | What |
|---|---|
| `GET  /api/v1/shots/{id}/qa` | Latest QA result + full repair history for the shot |
| `POST /api/v1/shots/{id}/qa?candidate_index=0` | QA agent: score one candidate (409 unless it's generated) |
| `POST /api/v1/shots/{id}/repair` | Repair agent: advance the ladder one attempt (409 unless latest QA result is FAIL) |

Tables (migration 10, on top of Day 2's `qa_results`/`repair_plans`
scaffolding): `qa_results` gains `confidence` + `evidence` (JSONB);
`repair_plans` gains `shot_id`, `attempt`, `rung` — the durable ladder
state, indexed by `shot_id`.

**QA committee** (`agentic_core/pipelines/qa/committee.py`, AVOS-03 v1.1
§15) scores 6 dimensions per candidate. Two are real this week:
*visual* decodes the candidate's PNG thumbnail and checks it's a
plausible frame (real dimensions, non-degenerate pixel data); *geometry*
compares the physics proxy's subject bounding box against the
shot-type-to-scale mapping (`SHOT_TYPE_SCALE`) the same way a human would
sanity-check a wide vs. close-up composition. The other four
(temporal / identity / audio / prompt_adherence) return
`score=1.0, confidence=0.5` with `diagnostics.todo=True` — clearly marked
placeholders, not silently-passing real checks. A shot PASSES when every
real dimension clears `REAL_PASS_THRESHOLD=0.6`; run through the Tool
Gateway (`run_qa_committee`, permission `qa`) and persisted via
`QARepository`, emitting `QA_PASSED` / `QA_FAILED`.

**The repair ladder** (`agentic_core/agents/repair/classifier.py` +
`api/src/services/repair_service.py`, AVOS-03 v1.1 §14) is the single
riskiest piece of the system — an infinite or forgotten repair loop — so
its attempt counter is **read fresh from Postgres on every call**,
never held in memory:
`attempt = COUNT(repair_plans WHERE shot_id = ?) + 1`.
That's what makes it durable across a worker restart, a deploy, or two
requests racing — there's no process-local state to lose. Attempt 1 is
classified `MICRO` (a small seed nudge), attempt 2 `MACRO` (a corrective
prompt suffix appended to — not replacing — the compiled prompt, re-using
the shot's own description/camera/lighting), attempt 3+ always
`HUMAN_REQUIRED`, at which point `repair_shot` stops dispatching new
generations and emits `REPAIR_ESCALATED` instead. The ladder only
advances forward: `RepairService.repair()` requires the shot's latest QA
result to be `FAIL`, so it can never be called speculatively or run past
`HUMAN_REQUIRED`. Proven directly against the database by
`api/tests/test_repair_ladder.py` (5 tests): a forced 3-failure sequence
escalates Micro → Macro → Human on exactly attempt 3, not before; and the
counter is proven durable by opening a **second, independent** SQLAlchemy
session mid-sequence (the strongest single-process proxy for "the worker
restarted") and confirming it derives the identical next attempt from the
same rows.

**QADashboard** (`desktop/components/studio/QADashboard.tsx`) shows the
selected shot's latest verdict and all 6 dimension scores (placeholders
labeled `(TODO)`), and — only on a `FAIL` — a repair affordance: the
current attempt number and rung (Micro/Macro/Human) as a badge plus a
3-step ladder tracker, a `Repair` button (hidden once escalated to
Human), and the full attempt history. Live via SSE
(`QA_PASSED`/`QA_FAILED`/`REPAIR_STARTED`/`REPAIR_ESCALATED` invalidate
`["qa", shotId]` in `hooks/useLiveProject.ts`) — no polling, no reload,
the same pattern as `GenerationMonitor`.

Because the mock Video generator and the QA geometry check share the
same `SHOT_TYPE_SCALE` mapping, a mock-generated shot always earns a real
PASS end-to-end — by construction, not by luck. That's why the Playwright
e2e test (`tests/e2e/qa-dashboard.spec.ts`) exercises the reachable-through-the-UI
PASS path (Run QA → live dimensions, no repair panel), while the forced-FAIL
repair-ladder guarantee is proved at the strongest layer available: directly
against the durable Postgres counter in `test_repair_ladder.py`, independent
of whatever a mock renderer happens to agree with this week.

## Week 3 Day 15 — integration checkpoint & first full video

| Endpoint | What |
|---|---|
| `POST /api/v1/shots/{id}/approve` | The stubbed final gate: a human signs off on a QA-PASSED shot (409 unless it is one) |
| `POST /api/v1/shots/{id}/qa?force_fail=true` | Same QA committee endpoint, with a deliberate, visible verdict override (see below) |

**The DoD, run for real:** create a project → Director researches +
writes a script (mock LLM) → human approves it in the UI → real audio
(TTS/Whisper mock) + timestamps + semantic beats → one ShotSpec per
beat, continuity-checked against the WorldState → Blender stage (mock)
→ Prompt Compiler + idempotent generation → QA committee → repair
ladder → the stubbed final gate. Every step goes through the Tool
Gateway (schema → permission → constitution → idempotency), is audited,
and shows up live in the UI over SSE with no polling and no reload.
Proven both as a Playwright test that drives the actual browser
(`tests/e2e/day15-checkpoint.spec.ts`) and as a backend integration test
that drives the same calls directly (`api/tests/test_day15_integration.py`).

**Forcing a QA FAIL, honestly.** The mock Video generator and the QA
committee's geometry dimension share the same `SHOT_TYPE_SCALE` mapping
(Day 14), so a mock-generated candidate always earns a genuine PASS -
there's no naturally-occurring FAIL in this stack to drive the repair
ladder with in a live demo. `run_qa_committee` now takes an optional
`force_fail` (query param on the route, a checkbox on QADashboard
labeled "Force fail (test)"). It still runs the *real* evaluation, then
deliberately overrides the two real dimensions to FAIL - loudly:
`evidence.forced=true` on the result, a dedicated `forced_failure` issue
on each overridden dimension carrying the original (real) score it
overrode, and a "forced" badge next to the verdict in the UI. This goes
through the exact same Gateway/audit/SSE path as a real verdict - it is
not a database backdoor - so the whole FAIL → repair → escalate chain
(proven with a seeded fixture on Day 14) is now also provably reachable
from a human clicking buttons in the live app.

**The stubbed final gate** (`api/src/services/approval_service.py`,
`agentic_core/tool_gateway/tools/qa_tools.py`'s `approve_shot`,
permission `approval`, dispatched as the Director - the one role scoped
for it, unused until now). A shot can only be approved once its current
version's latest QA result is a genuine PASS (first-try or after a
repair resolves it); already-approved is rejected; every other role is
denied by the same permission check as any other tool. Final
Assembly/FFmpeg doesn't exist yet (see the ticket list below) - approval
*is* the whole final stage for now, and it's real: audited, and it
flips the shot to `APPROVED` live over SSE (`SHOT_APPROVED`, a Day 2
event type that had never been wired to anything until today).

**A real bug the live path caught that a fixture couldn't.** Day 14's
repair-ladder tests seeded a failing `qa_results` row directly, which
never advances `shot.status` past `QA_PENDING`. Driving a real FAIL
through the live QA endpoint moves the shot to `FAILED` (correctly),
but the physics Gateway's `POST_BLENDER_STATUSES` allowlist - the set of
statuses `generate_video_shot` is permitted to run against - didn't
include `FAILED`, so every repair attempt's regeneration step was
rejected with `MISSING_DEPENDENCY`. Fixed by adding `FAILED` to that
set (`api/src/services/physics_gate.py`) - regenerating against the
shot's existing physics proxy is exactly what a repair is for. This is
the textbook case for why Day 15 exists: an integration test using the
real endpoints surfaces exactly the class of bug a well-meaning fixture
papers over by skipping the state transition the real caller depends on.

**No frontend code path touches infra directly** (Eng 3 + Eng 1
spot-check, Day 15 EOD checklist). Verified by code review, not just
convention: every `desktop/` data path is one of two functions -
`lib/api/core.ts`'s `fetch()` to the FastAPI base URL, or
`lib/events.ts`'s `EventSource` against `GET /events/stream` on that
same API. `grep`ing the whole `desktop/` tree for Postgres, Redis,
Temporal, Blender or ComfyUI turns up only comments, UI labels, and the
QA dimension literally named `"temporal"` - no client library for any of
them is even a dependency in `package.json`.

## Week 3 Day 16 — per-project generation providers (Ollama, Groq, free image/video)

Every project can now pick its own text/image/video backend at creation
time, instead of the whole deployment being stuck on one choice. This
doesn't replace the mocks above — it's the opt-in real path next to them.

| Field (New Project form / `ProjectCreate`) | What it selects | Values |
|---|---|---|
| `llm_provider` | Director research + script writing | `""`/`mock`/`openai`/`ollama`/`groq` |
| `image_provider` | Video candidate thumbnails | `""`/`mock`/`pollinations`/`cloudflare`/`local`/`chain` |
| `video_provider` | Video candidate renders | `""`/`mock`/`local` |

`""` (the form's default, and every project created before Day 16
existed, since the column is nullable) means "no explicit choice" — LLM
falls through to the `LLM_PROVIDER` env default, then auto-detects from
whichever API key is set, then the offline mock; image/video with no
explicit choice or env default stay on the existing deterministic mock
(no auto-detect, so old projects/tests keep byte-identical output).
`agentic_core/models/{llm,image,video}/factory.py`'s `get_*_provider()`
functions are the router; `ProjectService.create_project` validates the
three fields against those factories' `KNOWN_PROVIDERS` (plus the
literal `"mock"`) and 422s on an unknown name.

**Text — Ollama and Groq.** Both are wired in behind the same
`LLMProvider` interface as the existing mock/OpenAI providers
(`agentic_core/models/llm/ollama_provider.py`, `groq_provider.py`):

- **Ollama** — runs on your own machine (`ollama serve` + `ollama pull
  llama3.1`), genuinely free, no key. `OLLAMA_BASE_URL` defaults to
  `http://host.docker.internal:11434` so the `api`/`worker` containers
  reach a host-machine Ollama on Docker Desktop (Windows/Mac); on Linux,
  point it at the host's real IP or run Ollama as its own container on
  this compose network instead. `OLLAMA_MODEL` defaults to `llama3.1`.
- **Groq** — hosted, free tier, no card: get a key at
  console.groq.com/keys, set `GROQ_API_KEY`. `GROQ_MODEL` defaults to
  `openai/gpt-oss-20b` (Groq's own recommended free-tier replacement for
  the now-deprecated `llama-3.1-8b-instant`, retired 2026-08-16 — see
  console.groq.com/docs/deprecations if this happens again; override
  with `GROQ_MODEL`). Selecting `groq`/`openai` without their key
  set raises a clear error rather than silently degrading to the mock.

**Image — genuinely free, not "free tier."** Researched specifically
for this: Hugging Face's Inference API and Pollinations' newer
key-gated `gen.pollinations.ai` "Pollen credits" endpoint were both
rejected as free-*trial*, not free. What's wired in instead:

- **Pollinations.ai** (`pollinations`) — the older, no-key, no-signup
  `image.pollinations.ai/prompt/{prompt}` endpoint. No account, no
  card, no expiring credits; rate-limited per IP and carries no uptime
  guarantee, which is the honest cost of "actually free." No env var
  needed beyond the optional `POLLINATIONS_MODEL` (default `flux`).
- **Cloudflare Workers AI** (`cloudflare`) — a real, *renewing* free
  daily allowance: 10,000 "neurons"/day on Cloudflare's free Workers
  plan, no credit card for that allocation. Runs FLUX.1 [schnell]
  (`@cf/black-forest-labs/flux-1-schnell`), ~4.8 neurons/512×512 image,
  so 10,000 neurons/day ≈ 2,000 images. Needs a free Cloudflare account:
  `CLOUDFLARE_ACCOUNT_ID` (dashboard sidebar) and `CLOUDFLARE_API_TOKEN`
  (My Profile → API Tokens → the "Workers AI" template).
- **Self-hosted** (`local`) — your own Automatic1111/SD-WebUI-compatible
  server (`IMAGE_SERVICE_URL`, `POST /sdapi/v1/txt2img`). Genuinely free
  and unlimited because it's your GPU, not a vendor's — the tradeoff is
  you have to run it.
- **Replicate** (`replicate`) — **paid**, pay-per-use, not free. Runs
  FLUX.1 [schnell] via `POST /v1/models/black-forest-labs/flux-schnell/predictions`.
  ~$0.003/image (estimate, see `REPLICATE_IMAGE_COST_USD`). `REPLICATE_API_TOKEN` required.
- **Stability AI** (`stability`) — **paid**, credit-based, not free
  (the one-time signup credit grant is a trial, not a renewing tier).
  Runs the "core" tier of the Stable Image API. ~$0.03/image (estimate,
  see `STABILITY_IMAGE_COST_USD`). `STABILITY_API_KEY` required.
- **Auto fallback chain** (`chain`) — see the next section. Tries every
  free provider first (Pollinations → Cloudflare → self-hosted), then
  Replicate/Stability only as a last resort, under a hard shared spend
  cap.

Every other hosted image API from the original research pass (Leonardo.ai,
Fal.ai, Clipdrop) is likewise pay-per-use, not free — not wired in for
the same reason as Replicate/Stability weren't going to be at first:
adding a paid API by default would silently start charging a card. They
*were* explicitly requested as a **paid last-resort fallback with a
hard spend cap**, which is what `replicate`/`stability` now are — see
below. Runway, Luma, Kling, Pika and Haiper (the video equivalents from
that same request) were **not** added: several require an approval
process or waitlist rather than self-serve API access, and per the
"self-hosted only" decision already made for video (Ollama physically
cannot generate video — see below), a paid video API wasn't the ask
that got confirmed. Say the word if you want one of those wired in
specifically once you've confirmed you have API access to it.

**Auto fallback chain (`image_provider=chain`).** Ask was: "if one
provider's daily limit is over, use another one automatically" — and
then, once every genuinely-free option was confirmed too limited or
unreliable to rely on alone: "add paid providers as a last resort, with
a hard spend cap." `agentic_core/models/image/chain.py`'s
`ImageProviderChain` does both. It holds an ordered list of
`ChainMember`s of two kinds:

- `free_member(provider, daily_request_limit=None)` — gated by a call
  count today (`None` = no renewing quota to track, e.g. Pollinations
  or self-hosted, so only a failure moves the chain past it).
- `paid_member(provider, cost_per_call_usd, daily_spend_cap_usd)` —
  gated by a **shared dollar total** across every paid member combined
  (`PAID_SPEND_KEY = "paid_total"`), not a separate allowance per
  vendor: the ask was a real ceiling on total spend, so Replicate using
  most of today's budget correctly makes Stability unavailable too,
  rather than each getting its own pool.

A member whose limit (request count or spend) is already hit today is
skipped without even being called; one that raises (network error,
etc.) is also skipped in favor of the next. The chain is built in this
fixed order — free tier first, paid tier only after every free member —
so the paid providers are only ever reached once Pollinations,
Cloudflare and self-hosted have all failed or run out for the day.
Only members that are actually configured are included: with nothing
set beyond the code itself, `image_provider=chain` behaves exactly
like plain `pollinations`; add `CLOUDFLARE_*`/`IMAGE_SERVICE_URL` and it
grows the free tier; add `REPLICATE_API_TOKEN`/`STABILITY_API_KEY` and
it grows the paid last-resort tier — nothing paid is ever reachable
without its key present.

Daily counts and spend both live in Redis
(`agentic_core/models/quota.py`, `avos:quota:image:<provider>:<UTC
date>` for counts, `avos:quota:spend:image:<key>:<UTC date>` for
dollars, 2-day TTL either way) so they survive an api/worker restart
and are shared across processes — the same already-required service
`EventBus` uses (see its ADR), reused rather than adding new infra. If
Redis is unreachable, both fall back to an in-process in-memory count
instead of blocking generation entirely (a brief undercount — of
requests or of dollars — is a far smaller problem than every image
request failing, though it does mean the spend cap is a *best-effort*
ceiling under a Redis outage, not an absolute guarantee; budget
accordingly if that matters for your account). Cloudflare's free slot
defaults to `CLOUDFLARE_DAILY_IMAGE_LIMIT=1500` (comfortably under the
~2,000/day the free neuron allowance gives); the paid tier defaults to
`IMAGE_PAID_DAILY_SPEND_CAP_USD=0.50` total per day across both paid
providers combined — all overridable per deployment. Cost-per-call
estimates (`REPLICATE_IMAGE_COST_USD`, `STABILITY_IMAGE_COST_USD`) are
not fetched live from either vendor's billing API; they're reasonable
estimates at the time this was written, so check actual usage on each
vendor's dashboard occasionally and adjust if pricing drifts.

**Video — self-hosted only, and here's why Ollama can't do this.**
Ollama is an LLM runtime; it serves text models, not image/video
models, so no model pulled through it can generate a frame or a clip —
this is a hard capability gap, not a config option. Researched and
found **no genuinely free hosted video-generation API** exists today
(every option is either a paid API or a shrinking trial credit).  The
only "fully free" video path is **self-hosted** (`local`,
`VIDEO_SERVICE_URL`, a thin `POST /generate` → `{"video": "<base64
mp4>"}` contract — there's no Automatic1111-style standard for video,
so this is this repo's own small contract; adapt a ComfyUI HTTP wrapper
to match it, or adjust the client to match a workflow you already run).

**Wiring.** `DirectorService.research()`/`write_script()` resolve
`get_llm_provider(project.llm_provider)` and pass it into
`ResearchTopicTool`/`GenerateScriptTool`. `VideoGenerationService.generate()`
resolves both `get_image_provider`/`get_video_provider` from the
project, and — only when a real provider is configured — generates a
real thumbnail/render instead of the deterministic mock PNG, tags the
asset's `renderer`/`source` metadata with the real provider's name
instead of `"MOCK"`, and (for video) stores a new `video_render` asset
(`render_asset_id` on the candidate, `None` when no video provider
ran). A provider call that fails raises rather than silently falling
back to the mock, so a broken real config is visible, not masked.

**Env vars** (all optional; unset = mock/offline, exactly Day 1–15's
behavior):

```
LLM_PROVIDER=            # deployment-wide default; a project's own llm_provider wins
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=llama3.1
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
IMAGE_PROVIDER=          # deployment-wide default; a project's own image_provider wins
POLLINATIONS_MODEL=flux
IMAGE_SERVICE_URL=       # only used when image_provider=local or chain
CLOUDFLARE_ACCOUNT_ID=   # only used when image_provider=cloudflare or chain
CLOUDFLARE_API_TOKEN=    # only used when image_provider=cloudflare or chain
CLOUDFLARE_IMAGE_MODEL=@cf/black-forest-labs/flux-1-schnell
CLOUDFLARE_DAILY_IMAGE_LIMIT=1500   # chain's cap for Cloudflare's slot
REPLICATE_API_TOKEN=     # PAID - only used when image_provider=replicate or chain
REPLICATE_IMAGE_MODEL=black-forest-labs/flux-schnell
REPLICATE_IMAGE_COST_USD=0.003      # estimate used against the spend cap
STABILITY_API_KEY=       # PAID - only used when image_provider=stability or chain
STABILITY_IMAGE_COST_USD=0.03       # estimate used against the spend cap
IMAGE_PAID_DAILY_SPEND_CAP_USD=0.50 # hard ceiling, shared across Replicate+Stability combined
VIDEO_PROVIDER=          # deployment-wide default; a project's own video_provider wins
VIDEO_SERVICE_URL=       # only used when video_provider=local
```

Migration 11 (`11_generation_provider_selection`) adds the three
nullable `projects` columns. Tests:
`agentic_core/tests/test_llm_factory.py`,
`agentic_core/tests/test_image_video_factory.py` (routers, in
isolation, including `cloudflare`/`replicate`/`stability`/`chain`
selection and the paid tier's spend-cap wiring),
`agentic_core/tests/test_quota.py` (the Redis-backed daily counter and
spend tracker, incl. their in-memory fallback),
`agentic_core/tests/test_image_chain.py` (the fallback chain's
skip/fall-through logic for both the free and paid tiers, including
the shared spend cap, against fake providers), and
`api/tests/test_video_generation_real_provider.py` (the service wiring,
with the providers' own HTTP calls monkeypatched so tests don't hit the
real network).

## Studio tabs: Facts and Animations

The sidebar has two studios (the old Dashboard is now **Facts**; `/dashboard`
redirects there):

- **Facts** (`/facts`) - everything above and below: topic -> script -> voice ->
  shots -> visuals -> final MP4.
- **Animations** (`/animations`) - **ReelMimic's workflow, rebuilt in Python**
  (`apps/animation_studio`; the original repo is kept in `apps/reelmimic`, upstream commit in
  `AVOS_UPSTREAM.txt`). Give it a reference video (file, screen recording or link) and a one-line
  brief. The crew breaks the reference down (cuts, pacing, BPM, camera moves, colours), picks a style
  from ReelMimic's style registry, writes a plan with you (storyboard, characters, assets, style frames;
  chat to change it, then approve), and produces it through review gates: every character, every shot
  is checked by an independent reviewer and fixed with before/after proof, then a final critic checks
  seams, continuity and pacing. Leave timed notes on the finished video and it revises those moments.
  Every tab and button of ReelMimic's web app is in the Animations tab (plan, reference analysis,
  production line, final video, chat with live steps, log, review rounds, required inputs and lyrics,
  stop / retry / accept / resume, three languages).

### Series (Animations → Series)

An animated series with you approving every step. Code: `animation_studio/studio/series/`; full description in the
architecture docs (`12-series.md`).

1. **New series**: title, the language the characters speak (Hindi, Hinglish, English, Tamil, Telugu, … any
   language), premise, your characters (`Name - who they are, how they look`, one per line), art style + up to 3
   style pictures, frame (16:9 / 9:16), part lengths (`1,3` = 1 min, then 3 min each), the AI writers, optional
   theme music.
2. **Characters**: each gets a character sheet (Qwen-Image-Edit from your style pictures, or your own drawing) and a
   voice sample (Indic Parler-TTS from the voice description, or your recording). Approve each one, or redo the look
   or the voice with a note.
3. **Episode**: a brief + length (the AI outlines it in parts) or paste your own script. Approve the outline.
4. **Each part**: read and edit the script (lines in the series' language) → approve → it renders on your GPU
   workers → watch it → approve (the next part is written) or select shots and redo their picture / motion / voice.
   After the last part the episode is joined (`episode.mp4` + subtitles).

What runs it: GPU workers with `comfyui` or `diffusers` (Qwen-Image-Edit, Wan 2.2 / LTX-2.3, InfiniteTalk,
ACE-Step), `speech` (`pip install -r requirements-speech.txt`: Chatterbox, IndicF5, Indic Parler-TTS) and `foley`
(HunyuanVideo-Foley). The Series page's **Models** panel shows what each step will use; without them it falls back
(text-only pictures, Edge voices, still pictures with camera moves) and says so on every shot. Try the whole flow
without a GPU: `cd gpu_worker && WORKER_MOCK=1 WORKER_ADAPTERS=mock python -m worker`, add it on the GPU page.

Stopped, failed or interrupted by a restart: press **Resume** on the episode; finished shots are reused.

**v14: how a shot is made now.** Each shot is data, not a prompt: a *scene graph* (who stands where, props, light,
camera position / target / lens), a *motion blueprint* (camera move + ease, timed actions, background motion) and
the series' *Design DNA* (look, camera and motion grammar, sound). The prompt compiler turns them into each model's
prompt (open a shot → "What the models were told"). Before you see a part, a vision crew (e.g. Ollama
`qwen2.5vl`, Gemini, GPT-4o) checks every picture and clip against the character sheets and redraws once with its fix
(Settings `shotQA`, on by default; skipped when the crew can't see).

In the part review, **Open** a shot for: **Director** (a 3D stage with the place and the characters, the camera and a
timeline you can play and edit; Save redoes only that shot), **Modify shot** (change one thing, keep the rest and
the motion), **Animate my image**, **Motion from a video**, **Reset**. The **Design DNA** panel on the series page
edits the look; **Agent skills** lists the SKILL.md files in `apps/skills` — edit them to change how the writers,
the scene director, the sound designer and QA work (no restart needed).

**v15: storyboard first.** Each part's frames are drawn first (one per shot + a numbered `storyboard.png`) and nothing
is animated until you press **Approve the storyboard and animate**. On the storyboard: redraw single frames with a
note, open one (Director / Modify / your own picture), or change the camera (move, ease, lens, angle) on all or the
selected shots. Turn it off per series with "Approve a storyboard before animating". Approved characters can be
saved to your **character library** and cast in any other series or film. Episode → **Project files (.zip)**.

### Films (Animations → Films): prompt → animation

One prompt → a short film, made the "lock the look, storyboard, animate each frame, design the sound, assemble"
way, with your approval at every stage. Code: `animation_studio/studio/series/film.py` (a film is a series of kind
`film` with one episode of one part); full description in `14-films.md`.

1. **New film**: paste the prompt — story, SETTING, CHARACTERS, then timed sections (`0–3 SECONDS: …`,
   `SHOT 4 (3.00–4.00s) – close-up, low angle: …`), AUDIO, RULES — or a JSON prompt. Optional: title, dialogue
   language, frame, style pictures, music, characters from your library.
2. **Breakdown**: the prompt analyst (skill `avos-prompt-analyst`) turns it into timed shots (framing, angle, camera
   move, lens, timed actions, dialogue word for word, timed sounds), characters, world, audio and rules. Edit it as a
   table or JSON, or read the prompt again with a note → approve.
3. **Characters & world**: each character's sheet + voice (or the library's), the world references → approve or
   redesign → **Lock the look and draw the storyboard**.
4. **Storyboard**: frames + collage with the prompt's exact timing and camera; motion timeline (camera, each
   character, effects, dialogue, sound, ambience, music); the compiled prompt for each shot → approve.
5. **Render** (one clip per shot; a wide line is played over an action clip, close lines are lip-synced) → approve.
6. **Edit bay**: the master, the music / ambience / timed sound effects, and **Project files (.zip)**: `script.json`,
   `breakdown.json`, `consistency_manifest.json`, `storyboard/collage_master.png` + `frames/`, `motion_blueprint.json`,
   `prompts/shot_NN.txt`, `renders/clip_NN.mp4`, `audio/`, `final/final_master.mp4` + `audio_mix.wav`.

### Your own PC as the GPU (v16): ComfyUI in one click, workflows without placeholders, CPU mode

- `apps\tools\setup-comfyui.bat`: installs ComfyUI portable next to AVOS (`D:\star\ComfyUI_windows_portable`) and
  writes its `extra_model_paths.yaml` so it reads `apps\models` (where the Models page downloads).
- NVIDIA card: `apps\tools\start-gpu.bat` (ComfyUI + the GPU worker in Docker). No NVIDIA card (Intel / AMD):
  `apps\tools\start-cpu.bat` (ComfyUI `--cpu` + the worker in ComfyUI's own Python). Then GPU page → add
  `http://host.docker.internal:8700`.
- Workflows: in ComfyUI run the model's template once → **Workflow → Export (API)** → Settings → Models → Upload. AVOS
  wires the prompt / image / audio / seed / size / frames / fps itself and sends it to your workers.
- **CPU mode** (optional — only when you start `start-cpu.bat` or set `WORKER_DEVICE=cpu`; Intel PC, e.g. 16 GB RAM): the worker reports RAM + page file as its memory; pictures and clips are
  drawn at ≤512 px and ≤5 s (`WORKER_CPU_MAX_SIDE`, `WORKER_CPU_MAX_SECONDS`) and AVOS scales them up; the smallest
  weights are chosen (fp8). Z-Image Turbo: minutes per picture. LTX-2.3 22B fp8: needs a page file of ~48 GB
  (`powershell -ExecutionPolicy Bypass -File apps\tools\set-pagefile.ps1 -Drive D: -SizeGB 48` as Administrator, then
  restart) and takes a long time per clip — everything beyond your RAM is read from the SSD at every step.
- **Colibrì** (github.com/JustVugg/colibri, huge MoE text models from SSD on a CPU): run `coli serve --model <path>`
  (port 8000) and pick **Colibrì (local MoE)** as the AI crew (Facts: `LLM_PROVIDER=colibri`). `COLIBRI_URL` changes
  the address.

### Choosing models yourself (v17)

- **Films / Series → Models panel**: for each step (pictures, action shots, lip-sync, voices, sound, music) pick the
  model and where it runs: *Auto* (your GPU worker → your ComfyUI → free tiers → paid APIs), or e.g. LTX-2.3 on
  **your GPU** (files you downloaded on the Models page), or on **fal.ai** / **Cloudflare** with your API key
  (Settings → API keys). ✓ / ✗ show what's ready and why not. Music and sound can be turned off; voices can be Edge.
  Saved choices apply to what's made next (redo shots to re-make finished ones).
- **Models page**: a model you downloaded shows *Downloaded on this PC* (and an unfinished `.part` download says so).
  Files alone don't run a model: start ComfyUI + the worker (`tools\start-gpu.bat`, or `tools\start-cpu.bat` without
  an NVIDIA card — optional CPU mode) and upload the workflow.
- **A provider with no credit or a refused key** (e.g. fal.ai "Exhausted balance") is skipped for an hour (a new key
  retries at once; Models page → *Try it again now*): AVOS falls through to your GPU, free tiers or the next model, and
  a shot that can't be animated anywhere becomes the frame with its camera move instead of failing.

### The AI crew: local first

Pick it in the composer (gear button = AI settings). Settings apply to new projects.

| Crew | Cost | What you need |
|---|---|---|
| **Ollama** (default) | free, runs on your PC | [ollama.com](https://ollama.com), then `ollama pull qwen2.5:7b`. Optional vision model so reviewers can *look* at frames: `ollama pull qwen2.5vl:7b` and set it in AI settings. |
| Built-in rules | free, offline | nothing - plans and reviews come from the engine's rules (no story writing); good for testing |
| Groq / Gemini / OpenRouter | free tier | a key pasted in AI settings |
| OpenAI / Anthropic API | paid | a key pasted in AI settings |
| Claude Code / Codex | your plan | the CLI installed and logged in on the PC running the service |

The video itself is always drawn on your PC by the built-in 2D engine, in ReelMimic's seven looks:
vector / motion graphics, hand-painted watercolor, crayon picture book, pixel art, paper cut-out,
whiteboard doodle, anime cel. 2D only, original characters (or your own uploaded designs), no real people.
Narration uses free Microsoft Edge voices when online. Your own music/lyrics: upload them; lyrics are timed
to your song automatically (`requirements-lyrics.txt`).

### Start it (pick one)

- **Docker** (from `apps\`): `docker compose up -d --build animation-studio`
- **Without Docker**: double-click `apps\start-animations.bat` (first run installs its Python packages into
  `apps\animation_studio\.venv`; needs Python 3.10-3.12 and FFmpeg). Keep the window open.

Either way it runs on http://127.0.0.1:8020; the Animations tab finds it by itself (override with
`ANIMATION_STUDIO_URL` for the Next server and `NEXT_PUBLIC_ANIMATION_STUDIO_URL` for the live event stream).
Projects live in `apps/animation_studio/projects` (native) or the `animation_projects` volume (Docker).
A 20-30 s animation takes a few minutes with the built-in rules and roughly 10-40 minutes with a local
7B model on a CPU (much faster with a GPU or a cloud crew).

### Tests

- `cd apps\animation_studio && .venv\Scripts\python -m pytest -q` - analysis, renderer (all 7 looks),
  every pipeline step with the built-in crew and with a stand-in Ollama server, the HTTP API.
- `cd apps\desktop && npx playwright test tests/e2e/animations.spec.ts` - the UI with a mocked service.
- `set STUDIO_LIVE=1 && npx playwright test tests/e2e/animations-live.spec.ts` - the UI against the real
  service, from upload to revised video (`STUDIO_LIVE_AGENT=ollama` to use your local model).

## Week 4 — real video output (voice, clips, final MP4)

Before this, "Complete" meant *planned*: the narration was silent (mock
TTS), no shot ever got pixels, and nothing joined the shots into a file.
Now every run ends in a real MP4:

    ... -> Blender stage -> Visuals (image + clip per shot) -> Final render -> complete

- **Voice**: `TTS_PROVIDER=edge` (docker-compose default) uses Microsoft
  Edge's free neural voices (`edge-tts`, no key; needs internet). Real
  per-word timings come back with the audio and drive the captions and
  shot cuts. `TTS_VOICE` picks the voice (`en-US-ChristopherNeural`,
  `en-US-AndrewNeural`, `en-GB-RyanNeural`, `en-IN-PrabhatNeural`...);
  `TTS_RATE=+10%` speeds it up. `TTS_PROVIDER=mock` = silent/offline.
- **Visuals**: the workflow generates every shot itself (one Temporal
  activity per shot, committed per shot). Each shot gets 3 image
  candidates and, if the project picked a video provider, **one** clip
  (candidate 1; clips are the slow/paid part). If one shot's provider
  call fails after retries, that shot falls back to its animated still
  and the warning is shown on the project page; a misconfiguration
  (missing key/URL) fails the job straight away with the reason.
- **Final render** (`assemble_video`, Video agent, audited): each shot's
  clip (scaled/cropped, trimmed or slowed+held to its exact length) or
  its still with a camera move, cut on the narration's beats, narration
  mixed in, word-by-word captions burned in (spoken word highlighted).
  Output: H.264/AAC MP4 in Full HD, 1080×1920 for 9:16 (`RENDER_SIZE=720x1280`
  renders faster on a slow PC), stored as a `final_video` asset; `VIDEO_ASSEMBLED` updates the
  UI live. The project page plays it and has **Download MP4**.

### Video providers (New Project → Video)

| Choice | What each shot looks like | Needs | Cost |
|---|---|---|---|
| **Free: AI image + camera motion** (`motion`, form default) | AI image with a smooth zoom/pan | nothing (images: the `free` chain — Cloudflare Workers AI if `CLOUDFLARE_ACCOUNT_ID`/`CLOUDFLARE_API_TOKEN` are set, then Pollinations — unless you pick another) | free |
| **Real 3D animation – Blender** (`blender`) | a real 3D scene per shot: characters acting out the line, props, moving camera | the Blender service running (Docker or your own Blender) | free |
| **AI video clips – fal.ai / Kling** (`fal`) | real AI motion (Kling 2.1), image-to-video from the shot's image | `FAL_KEY` in `apps/.env` | paid, ~$0.25 per clip |
| **AI video clips – Replicate** (`replicate`) | real AI motion, image-to-video from the shot's image | `REPLICATE_API_TOKEN` in `apps/.env` (a real `r8_...` token, with billing set up) | paid per clip; ~6 clips per 30 s video. `REPLICATE_VIDEO_COST_USD` (default 0.15, an estimate) is added to the project budget per clip — check replicate.com/account/billing for the real amount |
| **AI video clips – ComfyUI on your GPU** (`comfyui`) | real AI motion (LTX-Video, Wan 2.x...) | ComfyUI running + `apps/comfyui_workflows/video.json` — see `comfyui_workflows/README.md` | free (your GPU; minutes per clip) |
| **Custom self-hosted API** (`local`) | whatever your service returns | `VIDEO_SERVICE_URL` (POST `/generate`, now also receives `image` as base64) | free |
| **None** | the final render animates each image itself | — | free |
| **Open models** (`best`, `wan-2.2`, `ltx-2.3`, `wan-vace`, `avatar`, `longcat-avatar`, `infinitetalk`) | Wan 2.2 / LTX-2.3 clips, or a talking presenter lip-synced to the narration | your GPU server (ComfyUI + workflow) or `FAL_KEY` — see **Open AI models** below | free on your GPU; fal.ai per second |

**fal.ai** (`fal`, paid per clip): `FAL_KEY` from fal.ai/dashboard/keys. Default model
`FAL_VIDEO_MODEL=fal-ai/kling-video/v2.1/standard/image-to-video` (~$0.25 per 5 s clip
on fal's price list, so ~$1.50 per 30 s video); `.../v2.1/pro/image-to-video` moves better
and costs more. `FAL_VIDEO_COST_USD` is what gets added to the project budget per clip.

### Blender engine (`blender`, free, real 3D animation)

Each shot's description is planned into a 3D scene by the project's LLM (environment,
characters, actions, props, camera - only from what the service has) and rendered by
the Blender service (`blender_service/`, `docker compose up -d --build blender`, or your
own Blender 5.0 with a GPU - see `blender_service/README.md`). Built in: grid studio /
desert / space / neon floor, a 3D mannequin (man, woman, giant, kid, robot, astronaut)
with 13 animations, 15 props, 7 camera moves. Drop Mixamo characters/animations into
`apps/blender_assets/` for realistic people. `BLENDER_RENDER_URL` points the worker at
the service; `BLENDER_ENGINE` / `BLENDER_SAMPLES` / `BLENDER_FPS` trade quality for speed.

### Style presets (New Project → Style)

| Style | Script | Look | Music folder | Captions |
|---|---|---|---|---|
| **Viral 3D facts** (`viral_3d`, default) | hook first line, short punchy facts, twist ending, every scene one concrete action | photorealistic 3D render, realistic humans, light-blue grid studio | `music/suspense` | 2 words |
| **Storybook explainer** (`storybook`) | calm explainer | illustrated storybook | `music/uplifting` | 3 words |

Presets live in `agentic_core/styles.py` (DB column `projects.style_preset`, migration 12).

### Music and sound effects

Put royalty-free tracks in `apps/music/suspense/` and `apps/music/uplifting/`
and a whoosh in `apps/music/sfx/` (see `music/README.md`). The render loops
the track, ducks it under the voice, fades it in/out, and plays the whoosh
on every cut. `MUSIC_VOLUME`, `SFX_VOLUME`, `MUSIC=off`, `SFX=off`.

Replicate model: `REPLICATE_VIDEO_MODEL` (default `bytedance/seedance-1-lite`;
Kling, Minimax/Hailuo and Wan model names are mapped too; community models as
`owner/name:version`). Resolution: `REPLICATE_VIDEO_RESOLUTION` (`480p`
default, `720p`). Any extra model input: `REPLICATE_VIDEO_INPUT_JSON`.

Tests: `agentic_core/tests/test_video_render.py` (voice timing alignment,
all providers — Replicate and ComfyUI against simulated servers — captions,
the ffmpeg render), `api/tests/test_final_render.py` (motion clips → final
MP4 through the DB, audit + budget), `api/tests/test_create_video_workflow.py`
(whole workflow on real Temporal, now through visuals + render), and
`desktop/tests/e2e/final-video.spec.ts` (topic → watch → download in the UI;
`E2E_VIDEO_PROVIDER=motion|replicate|comfyui`).

## Settings page (keys, GPU server, your own models)

Sidebar → **Settings**. One place for both Facts and Animations; saved in `avos_settings` (Docker volume, file
`/data/settings/avos.json`; without Docker `apps/.avos/settings.json`). The API, the worker and the Animation Studio
read the same file, so a key saved once works in both tabs. A value saved here wins over the same name in `apps/.env`;
**Clear** falls back to `.env` again.

- **API keys**: OpenAI, Groq, Gemini, OpenRouter, Anthropic, fal.ai, Replicate, Stability, Cloudflare, Pollinations,
  Ollama address, your image server, and **any other NAME** (for example `DEEPSEEK_API_KEY`) for your own models.
  Secrets are shown masked.
- **GPU server**: your ComfyUI address (RunPod / Vast.ai pod, port 8188), **Test connection** (shows the GPU), and
  "Run models on": Auto / only my GPU server / only fal.ai.
- **Models**: every catalog model with its readiness; **Upload workflow** puts a ComfyUI API export in place for that
  model (checked: API format, `{{PROMPT}}` present). **Add a model**:
  - *fal.ai* or *Replicate*: endpoint (`fal-ai/flux-pro/v1.1`, `owner/name[:version]`) and an input template in JSON with
    placeholders `{{prompt}} {{width}} {{height}} {{aspect_ratio}} {{seed}} {{duration}} {{num_frames}} {{image_url}}
    {{audio_url}} {{video_url}}` (files go as data URIs; fields whose placeholder has no value are left out).
  - *ComfyUI*: then upload its workflow; it runs on your GPU server.
  - *OpenAI-compatible text model* (DeepSeek, Together, Groq models, LM Studio `http://host.docker.internal:1234/v1`,
    vLLM…): base URL, model name, key name (empty for a local server). **Test** sends one short request.

  What you add appears in Facts → New video (Text AI / Pictures / Video pickers, under "Your models"), in Animations →
  AI settings (backdrop model, AI finish, and text models as an AI crew under "Your models"), and on the Models page.
  Avatar-type models get the presenter portrait and each shot's narration, like LongCat.

API: `GET /api/v1/settings`, `PUT /settings/keys`, `PUT /settings/gpu`, `POST /settings/gpu/test`,
`POST /settings/models`, `DELETE /settings/models/{id}`, `PUT|DELETE /settings/models/{id}/workflow`,
`POST /settings/models/{id}/test`.

**Facts → New video** is now an inline card (like Animations): topic, style, length, shape, budget, and the Text AI /
Pictures / Video model chips with readiness and licence notes; the header's **New Project** button jumps to it.

## Open AI models (Models page)

One list, `agentic_core/models/catalog.json`, says which open model does which job, where it can run and its
licence. The Facts tab, the Animations tab and the **Models** page (sidebar) all read it; `GET /api/v1/models`
returns it with what is ready right now.

| Job | Best (default) | Top 2 | Fallback | Where it's used |
|---|---|---|---|---|
| Image | **Z-Image Turbo** (Apache-2.0) | **Qwen-Image** (Apache-2.0), picked automatically when the picture must show text | **FLUX.1 schnell** (Apache-2.0; also free on Cloudflare) | Facts image `best` / `z-image` / `qwen-image` / `flux-schnell`; Animations AI backdrops; the presenter portrait |
| Video (shot from its picture) | **Wan 2.2 I2V A14B** (Apache-2.0) | **LTX-2.3 22B** (LTX-2 Community License: free commercially only under $10M revenue and not in a competing product) for shots over 10 s or to follow the narration audio | **Wan VACE 14B** (Apache-2.0) for continuity | Facts video `best` / `wan-2.2` / `ltx-2.3` / `wan-vace`; Animations AI finish |
| Talking presenter | **LongCat Avatar** (MIT) | **InfiniteTalk** (Apache-2.0) for long takes and dialogue | **Wan 2.2 Animate** (Apache-2.0) for full-body motion | Facts video `avatar` / `longcat-avatar` / `infinitetalk`; Animations AI finish (`wan-2.2-animate`) |
| Character animation from a driving video | **Wan 2.2 Animate** | **SCAIL-2** (MIT, your GPU server only) | – | Animations AI finish |
| Re-shoot with a new camera | **Vista4D** (Apache-2.0) | – | – | listed only: no hosted API or ComfyUI nodes yet |

**Where they run.** Not on a laptop GPU (Intel Iris Xe can't): each needs 24–80 GB of GPU memory (less with fp8 / int8 /
int4). Three ways, all optional:

0. **Your GPU workers (recommended, the GPU page).** Run `apps/gpu_worker` on each GPU machine (your RTX PC, a RunPod /
   Vast.ai pod, a cloud VM: `pip install -r requirements.txt && python -m worker`, or its Docker file), set the same
   `GPU_WORKER_TOKEN` there and in **Settings → API keys**, and add its address on the **GPU** page. The Model Router
   then picks model, GPU, backend (ComfyUI / Wan2GP / Diffusers) and precision for every picture and clip, by quality,
   speed, cost and VRAM, keeps models loaded between shots, and falls through to the next option if a run fails. The GPU
   page shows each worker's VRAM, loaded models and queue, every run, generation limits (priority, max cost / time per
   shot, max generations) and "Ask the router". No GPU at hand? `WORKER_MOCK=1 WORKER_ADAPTERS=mock python -m worker`
   gives stand-in output so you can try it. Details: `gpu_worker/README.md`.
1. **Your GPU server (free per call, used first).** Rent an A100/H100 on RunPod, Vast.ai or Lambda, run ComfyUI with
   `--listen`, put its address in **Settings → GPU server**, and upload each model's workflow (exported with the
   placeholders from `comfyui_workflows/README.md`) in **Settings → Models**. A model is used on your server only when
   its workflow is there.
2. **fal.ai (paid per use).** Paste the key in **Settings → API keys** (or `FAL_KEY` in `.env`). Prices are on the Models page.

`MODEL_BACKEND=gpu`, `fal` or `comfyui` (Settings → "Run models on") forces one backend. With neither set up, `best` image falls back to the free chain and
`best` video to the free camera motion, so a project never stops because a paid model isn't configured.

**Download the models (Models page → Download).** Each open model has a Download button: pick **where** (This PC,
or one of your GPU workers: straight into its ComfyUI models folder), the **version** (fp8 / bf16 …, with the one that
fits your GPU marked), extras and the **folder**; the files come from Hugging Face into `<folder>/diffusion_models`,
`/text_encoders`, `/vae`, `/loras`… Progress, speed and ETA show on the Models page; an interrupted download resumes.
"This PC" in Docker means `AVOS_MODELS_HOST_DIR` (default `apps/models`; e.g. `AVOS_MODELS_HOST_DIR=D:/AI/models`
in `apps/.env`). Gated repos need `HF_TOKEN` (Settings → API keys).

**Speed (GPU Scheduler).** Shots generate in parallel (`VISUAL_CONCURRENCY`, auto = 2 per online GPU), a shot's
pictures in parallel and its clip as soon as its picture is ready; the project's models are loaded on the GPUs while
physics runs; Studio edits jump the GPU queues. Every shot is then QA-checked and failures repaired automatically
(GPU page → limits: "QA every shot…"); tick **Review shots first** in New video to check the shots before the final
video. Outputs can live in S3-compatible storage: start the bundled store with
`docker compose --profile storage up -d` (SeaweedFS on :8333) and set `ASSETS_STORAGE=s3` in `apps/.env`, or point
`S3_ENDPOINT` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` at your own MinIO / AWS S3 / R2. A small local text model: run llama.cpp's `llama-server -m <model>.gguf --port 8080`
and pick **llama.cpp** as the Text AI.

**Facts, presenter (`avatar`).** One presenter portrait is made per project with the project's image model and reused in
every shot; each shot sends that portrait plus its own part of the narration (cut from the narration audio by the
shot's start/end) so the lips follow the voice. Override the portrait prompt with `AVATAR_PRESENTER_PROMPT`.

**Animations, AI finish.** On a finished film (Final tab): pick Wan VACE (re-style, keeps motion and framing), Wan 2.2
Animate or SCAIL-2 (each shot's first frame performs the engine's motion) or LTX-2.3 (re-animate from the first frame)
and press Start. Each shot is sent with its first frame; results are fitted back to the shot's exact length and joined
with the film's own soundtrack into `out/video_ai.mp4` (the engine's `out/video.mp4` is kept). A shot that fails keeps
the engine's version.

Per-model fal input can be tuned with `<MODEL>_FAL_INPUT_JSON` (e.g. `WAN_2_2_FAL_INPUT_JSON={"resolution":"480p"}`)
and `<MODEL>_RESOLUTION` (e.g. `LONGCAT_AVATAR_RESOLUTION=720p`).

## Tickets — Weeks 4+ (every mock/stub still standing)

Nothing below is an accident; each was a deliberate, visible mock so
Weeks 1–3 could prove the *architecture* (Gateway, audit, idempotency,
durability, live UI) without waiting on GPU infrastructure or a second
model integration. Owners are placeholder engineer numbers (Eng 1/2/3
from this sprint's rotation) - assign for real at Week 4 planning.

| # | Ticket | Currently | Owner | Rough estimate |
|---|---|---|---|---|
| 1 | Real Blender rendering | `MockBlenderClient` (deterministic placeholder PNG passes) | Eng 2 | 1 wk (headless Blender service + `BLENDER_SERVICE_URL` wiring already exists as the seam) |
| 2 | Real video generation (ComfyUI or equivalent) | **Done (Week 4)**: `motion` (free), `replicate` (paid, hosted), `comfyui` (your GPU, native API), `local` — per project, run automatically by the workflow | Eng 3 | — |
| 3 | 4 of 6 QA dimensions (temporal, identity, audio, prompt_adherence) | `score=1.0, confidence=0.5, diagnostics.todo=True` placeholders | Eng 2 | 2–3 wk total (temporal + identity likely need a real video model in place from #2 first; audio needs the TTS output compared against the candidate; prompt_adherence wants a VLM judge) |
| 4 | Memory / long-term learning search | `search_memory` tool returns an empty/static result - `LEARNING_AGENT` role exists, nothing populates it yet | Eng 1 | 1 wk for a first pass (embed + retrieve past decisions/QA outcomes) |
| 5 | Policy layer depth (shadow → activate → deprecate) | `POLICY_*` event types exist (Day 2 scaffolding); no policy engine reads or writes them | Eng 1 | 2 wk (this is genuinely new work, not wiring an existing seam) |
| 6 | Final Assembly / FFmpeg | **Done (Week 4)**: `assemble_video` renders clips/stills + narration + captions to an MP4 after the visuals stage. Not yet gated on QA/human shot approval (it uses candidate 1 of each shot) | Eng 3 | follow-up: render from QA-approved candidates |
| 7 | Real LLM by default | Offline `MockLLMProvider` unless a key/provider is set — Day 16 added Ollama (free, local) and Groq (free tier) alongside OpenAI, selectable per-project | Eng 1 | Already switchable three ways; ticket is "decide the default for staging/prod," not new code |
| 8 | Real TTS/Whisper | **TTS done (Week 4)**: Edge neural voices with real word timings (no Whisper pass needed for them); Whisper is still the mock for other TTS | Eng 3 | — |
| 9 | Auth / multi-user | None - every request acts as an implicit single operator | Eng 1 | 1–1.5 wk for a first pass (this blocks "decided_by" on gates/approvals meaning anything) |
| 10 | Human-required repair resolution UI | `HUMAN_REQUIRED` shows in QADashboard as a dead end ("Escalated to human review") - no workflow to actually resolve it | Eng 3 | 3–4 days (an edit-and-regenerate action, or a manual override to re-open the ladder) |

## Sprint retro (Weeks 1–3) & Week 4+ re-baseline

**What worked.** The Tool Gateway pattern (schema → permission →
constitution → execute, wrapped by `dispatch_and_audit`) paid for
itself repeatedly - every new capability (Blender, generation, QA,
repair, approval) was "write an executor + a ToolSchema + register it,"
and got audit/budget/live-trace for free. Deterministic, clearly-tagged
MOCK implementations (`renderer: "MOCK"`, `[MOCK]` log lines) let every
week's DoD be proven against a live, running stack instead of just
unit tests - which is exactly what caught Day 15's physics-gate bug.
Building the durable, DB-derived repair counter from day one (rather
than "add durability later") meant Day 15's live-path test needed zero
extra work to trust.

**What didn't.** Two features (`SHOT_APPROVED` the event type, `qa`/
`repair` DB columns) were scaffolded on Day 2 for use days or weeks
later - useful foresight, but it meant Day 15 had to first *discover*
that `SHOT_APPROVED` already existed and had never been wired to
anything, rather than that being visible up front. Estimating "2 real
QA dimensions, 4 placeholders" as a one-day task undersold how much of
Day 14 that mapping-reuse constraint (mock generator and geometry check
agreeing by construction) would end up shaping Day 15's testing
strategy too - it's a recurring cost of every mock, not a one-time one,
and future estimates should account for "how do we force the failure
path" as part of building any mock, not as an afterthought once
integration testing starts.

**Velocity observed.** Days 11–15 (5 working days) shipped: shots +
continuity + WorldState + physics-before-pixels (Day 11–12), idempotent
generation + Prompt Compiler + live monitor (Day 13), QA committee (2
real dimensions) + repair ladder with durable state (Day 14), and the
integration checkpoint + stubbed final gate (Day 15) - roughly one
substantial subsystem with full test coverage per day, holding steady
across the week rather than slowing down as the codebase grew. That's
the number Week 4+ should be paced against, not a generic "story
points" estimate.

**Re-baselined Week 4+ (AVOS-18 §10 Phases 7–9), given that pace and
the ticket list above:**

- **Week 4 — real generation stack**: tickets #1 (Blender) and #2
  (video generation) in parallel across two engineers, since they're
  independent seams; #7/#8 (real LLM/TTS default decision) folded in as
  they're config, not code. This is the week the "MOCK" tags start
  coming off for real, so it should also produce the first genuinely
  non-mock end-to-end video.
- **Week 5 — QA depth + Final Assembly**: ticket #3 (remaining QA
  dimensions) now that #1/#2 give real artifacts to judge, plus ticket
  #6 (Final Assembly/FFmpeg) so `approve_shot` has something real to be
  the last step before. Ticket #10 (human-required resolution UI) rides
  along since it's small and blocks a clean demo of a shot that
  actually needed a human.
- **Week 6 — memory, policy, hardening**: tickets #4 (memory search) and
  #5 (policy layer) are the two genuinely new subsystems, not wiring
  existing seams, so they get their own week rather than being
  squeezed into Week 4/5's estimates. Ticket #9 (auth) starts here too,
  since "who approved this shot" only means something once more than
  one operator exists.

This assumes Weeks 4–6 hold the same one-subsystem-per-day pace Weeks
1–3 actually showed; the real Blender/generation integrations in Week 4
are the biggest unknown (external services, not just internal wiring),
so that week's estimate carries the most risk of slipping.

## Real LLM vs offline mock

With no key/provider chosen, a deterministic offline mock LLM writes
research and scripts (so everything works without credentials). Three
real options exist now (Day 16), selectable per-project in the New
Project form or deployment-wide via env — see the Day 16 section above
for the full list of env vars:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...
# or Groq (free tier, no card)
export GROQ_API_KEY=gsk-...
# or Ollama (free, runs on your own machine - `ollama serve` first)
export OLLAMA_BASE_URL=http://host.docker.internal:11434
docker compose up -d api worker
```

TTS/Whisper are still the offline mock providers (real WAV bytes, silent
audio, correct timing) — plug real ones into
`agentic_core/pipelines/audio/tts.py` / `whisper.py`.

## Tests

```bash
# All Python suites (contracts, tool gateway, agents, api) from the repo root.
# Tests that need Postgres/Redis/Temporal skip automatically if unreachable.
cd apps
export TEST_DATABASE_URL=postgresql+psycopg://solunex:solunex@localhost:5435/solunex_test
export REDIS_URL=redis://localhost:6380/0 TEMPORAL_HOST=localhost:7233
export LIVE_API_URL=http://localhost:8001      # enables live end-to-end API tests
pip install -r api/requirements.txt
pytest

# Or inside Docker (API suite):
docker compose exec api pytest

# Frontend
cd desktop
npm test            # typecheck + lint
npm run build
npm run test:e2e    # Playwright; needs the stack + `npx playwright install chromium`
# just the video flow, against a given provider:
E2E_VIDEO_PROVIDER=motion npx playwright test tests/e2e/final-video.spec.ts
```

The test database (`solunex_test`) is created automatically.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Animations tab: "The animation engine isn't running" | Start it: `docker compose up -d animation-studio` or `apps\start-animations.bat`. Check http://127.0.0.1:8020/api/health |
| Animations: Ollama shows a red dot | Start Ollama (`ollama serve`, or open the Ollama app) and download the model (`ollama pull qwen2.5:7b`, or Download in AI settings). In Docker the service reaches it at `host.docker.internal:11434`. |
| Animations: a step fails with "took too long" on a slow PC | Use a smaller model (`llama3.2:3b`), a free cloud crew, or fewer review rounds. Click "Try again" - finished files are kept. |
| Animations: no narration voice | Narration uses free Edge voices and needs internet; offline the lines show as captions. |
| Animations: lyrics aren't timed | Install the optional package: `apps\animation_studio\.venv\Scripts\pip install -r requirements-lyrics.txt` (Docker images include it). |
| Dashboard shows an error "Cannot reach the API at …" | `docker compose ps` — is `api` healthy? `docker compose logs api` |
| Job stays RUNNING, nothing in Agent Activity | `docker compose logs worker` — the worker must be running |
| Page stuck on grey skeleton cards via a LAN IP | Restart `npm run dev` (dev origins are read at start); check the browser console |
| CORS error in the browser console | Add your exact origin to `CORS_ORIGINS` in `docker-compose.yml`, `docker compose up -d api` |
| Want to see workflows | http://localhost:8233 (Temporal UI) |
| Badge says **Offline** but `docker compose ps` is healthy, and `curl localhost:8001/...` hangs or "Connection reset" while `curl 127.0.0.1:8001/health` works | Another program holds port 8001 on IPv6 (`[::1]:8001`) and `localhost` resolves to IPv6 first on Windows. `netstat -ano \| findstr :8001` → stop the PID that isn't Docker (Git Bash: `taskkill //PID <pid> //F`), or open the UI at http://127.0.0.1:3000 |
| Every page 404s; `npm run dev` warns "multiple lockfiles ... selected D:\star\package-lock.json" | A stray lockfile above `apps/`. `desktop/next.config.ts` pins `turbopack.root` now; deleting the stray `package-lock.json` is also fine |
| Job fails at "visuals" with "REPLICATE_API_TOKEN is not set" / "COMFYUI_URL" | Set it in `apps/.env`, then `docker compose up -d` (env changes need a container restart) |
| Shots show **"No visual"**, warnings say Pollinations "402 Payment Required" or "failed after 3 attempts" | Pollinations' anonymous tier is refusing/timing out. Set `CLOUDFLARE_ACCOUNT_ID` + `CLOUDFLARE_API_TOKEN` (free Workers AI allowance) in `apps/.env` and `docker compose up -d`; the `free` image chain uses Cloudflare first. Or pick another image provider |
| Narration is silent | `TTS_PROVIDER` is `mock`, or the worker has no internet for Edge TTS — `docker compose logs worker` |
| Models page: a model says "Not set up" | It lists what's missing: `FAL_KEY`, or `COMFYUI_URL` plus the exported workflow file `apps/comfyui_workflows/<model id>.json`. Env changes need `docker compose up -d` |
| Facts warning "fal.ai …: error 402" / "balance" | Your fal.ai balance is empty: add credit at fal.ai/dashboard/billing. Shots fall back to an animated still |
| Facts warning "… speaks the narration, but project … has no narration audio yet" | The avatar models need the narration: keep `TTS_PROVIDER` on `edge` (or any real voice) |
| ComfyUI: "… expects {{AUDIO}} but none was given" / "saved no video" | The workflow file is for a different job, or doesn't end with Save Video (MP4). See `comfyui_workflows/README.md` |
| Final video won't play in Playwright's Chromium | That build has no H.264 codec; Chrome/Edge/phones play the MP4 fine |

## What was fixed in this pass

Backend
- `GET /projects` didn't exist (405) — the dashboard could never load its list.
- Every gate endpoint (`/plan`, `/gates/pending`, `/gates/{id}`) returned **500**:
  UUID ids weren't coerced to strings in `HumanGateResponse`.
- No Temporal **worker** in docker-compose — workflows were never executed.
- Approving a script never produced audio: `/plan` didn't run through the
  workflow. Generate now runs the real `CreateVideoWorkflow` (Day 8).
- The workflow narrated the bare topic instead of the approved script.
- Job/worker race: the job row wasn't committed before the workflow
  started, so jobs could stay RUNNING forever; status writes could also
  overwrite a finished job. Both fixed (commit first, guarded transitions).
- Research activity never committed — audit rows and budget were lost.
- Events were published before the DB commit (UI re-fetched and missed
  data); now committed-then-published via an outbox helper.
- Budget warning never fired at exactly 80% (float rounding); now exact decimals.
- Double-click on Generate started two pipelines; double Approve raced.
- Day 4 `/internal/temporal/hello` hung forever (missing workflow argument).
- Mock LLM answered every prompt with script JSON, so research "notes"
  were a JSON blob; research notes also leaked into every narration line.
- Asset cache hits were written permanently into asset metadata.
- `requirements.txt` unpinned → fresh builds pulled SQLAlchemy 2.1 without
  `greenlet` and the API crashed on start. Now pinned.
- `alembic` ignored `DATABASE_URL`; naive vs timezone-aware timestamps
  (migration 07); Docker image didn't contain `packages/`, `agentic_core/`,
  `tool_gateway/`; conflicting / duplicate test folders.

Frontend
- Types described fields the API never returns (`progress`, `totalShots`,
  `target_duration`…) — now mirror the backend contracts exactly.
- New Project form sent fields the API rejects (every create was a 422).
- Requests could hang forever (no timeout); API errors weren't parsed.
- API base URL hardcoded to `localhost:8000` (wrong port; breaks on LAN).
- Home page was a static mockup with dead buttons → now the Dashboard.
- Studio rebuilt as the Day 10 3-panel workspace on real data: live agent
  trace, script approval, storyboard from the real script, playable
  narration with sentence/beat timeline, scene timing from word timestamps.
- Font fell back to serif (self-referencing CSS variable).

## Explainer Studio (idea -> finished video)

Sidebar -> **Explainer** (`/explainer`). The old Facts tab is gone; its links open this page.

1. Type one idea (length and shape are buttons). Everything else is chosen for you.
2. The writer drafts the script and shot list (`skills/avos-explainer-director`). You can edit any line or pick how a shot is made.
3. **Approve** -> the presenter, props and set are drawn, then one storyboard picture per shot. **Approve** again -> voice, shots, captions, `final.mp4`.
   Tick "Do everything without asking me" to skip both approvals.

How each shot is made is decided per shot by the router (`animation_studio/studio/explainer/router.py`): science cutaways and exact object
contact -> Blender (`BLENDER_RENDER_URL`); people, reactions, macro looks -> AI video (fal.ai Wan / LTX with a key and credit, ComfyUI, or a GPU
worker); nothing available -> the picture with a camera move, so a video always comes out. Each shot says which it used and why.

API: `/api/explainer` on the studio service (port 8020, `docker compose restart animation-studio` after code changes).
Files: `<STUDIO_EXPLAINER>/<id>/` (default next to the projects folder). Continue after any error skips finished work.

## Stickman Studio (history in flat 2D stickman clips)

Sidebar -> **Stickman** (`/stickman`). Follows the "Historical Stickman Video Instructions" sheet:

1. Name an event, or leave it empty and pick from **eight specific ideas** (one is recommended). Defaults: English narration, 9:16, **six 10-second clips = 60 s**.
2. The studio writes a **fact brief** (what is well-established, what to check, which kinds of sources to check, where sources disagree, what is staging).
   **It does not check sources itself: the brief is always marked "verification pending". Confirm claims before you publish.**
3. Story and narration by clip (18-24 spoken words per clip), a roster of 1-3 characters with a fixed **identity paragraph**, a **reference-sheet prompt** per character,
   a standalone **character consistency agent** prompt, and for every clip a scene-image prompt, a 10-second animation prompt with four timed beats (0-2, 2-5, 5-8, 8-10 s),
   sound notes and the outgoing continuity state. Prompts are composed by code, so identity paragraphs are repeated verbatim.
4. You approve the **character sheets**, then it draws the scene images (with the sheets attached where the image model accepts references), animates each clip
   (AI video if a model is ready, else the picture with a camera move), records the voiceover, burns word-by-word captions, and joins six clips into `final.mp4`.
5. Download the video, and the **written package** (Markdown, in the sheet's delivery order) to paste into Google Flow or any other tool.

It needs an AI writer (Groq etc.); the built-in crew refuses rather than write history from rules. API: `/api/stickman` on the studio service.

