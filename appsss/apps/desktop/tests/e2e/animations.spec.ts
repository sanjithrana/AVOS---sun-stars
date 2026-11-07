import { expect, test, type Page, type Route } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * Animations tab = ReelMimic's UI ported natively into AVOS, backed by the Animation Studio service
 * (apps/animation_studio). The service is mocked here (page.route on /studio-api and /studio-files), so the
 * spec runs without it: it checks the UI wiring, not the AI crew.
 */

// ---------- fixtures ----------
const ago = (s: number) => new Date(Date.now() - s * 1000).toISOString();

type InfoOver = Partial<{ pulls: Record<string, unknown>; groqKey: boolean; falKey: boolean; comfyui: string; imageModel: string }>;
function agentsInfo(over: InfoOver = {}) {
  return {
    default: "ollama",
    agents: [
      { id: "ollama", label: "Ollama (local)", tier: "local", ready: true, detail: "qwen2.5:7b on http://127.0.0.1:11434", model: "qwen2.5:7b", models: ["qwen2.5:7b", "llama3.2:3b"], url: "http://127.0.0.1:11434", vision: false },
      { id: "groq", label: "Groq", tier: "free", ready: !!over.groqKey, detail: over.groqKey ? "llama-3.3-70b-versatile" : "No API key yet", fix: "Get a free key at console.groq.com and paste it in AI settings", model: "llama-3.3-70b-versatile", models: ["llama-3.3-70b-versatile"], needsKey: true, hasKey: !!over.groqKey },
      { id: "gemini", label: "Gemini", tier: "free", ready: true, detail: "gemini-2.0-flash", model: "gemini-2.0-flash", needsKey: true, hasKey: true, vision: true },
      { id: "openai", label: "OpenAI", tier: "paid", ready: false, detail: "No API key yet", fix: "Paste an OpenAI API key", needsKey: true, hasKey: false },
      { id: "claude", label: "Claude Code", tier: "paid", ready: false, detail: "CLI not found", fix: "Install Claude Code and log in" },
    ],
    pulls: over.pulls ?? {},
    render: { quality: "720p", images: "drawn", imagesReady: false, imagesDetail: "AI images need a Gemini key", imageModel: over.imageModel ?? "free" },
    models: {
      images: [
        { id: "z-image", name: "Z-Image Turbo", ready: !!over.falKey, backend: over.falKey ? "fal" : null, why: over.falKey ? null : "Add a fal.ai key", bestFor: "Characters, scenes", license: "Apache-2.0", commercial: "yes" },
        { id: "qwen-image", name: "Qwen-Image", ready: !!over.falKey, backend: over.falKey ? "fal" : null, why: over.falKey ? null : "Add a fal.ai key", bestFor: "Pictures with readable text", license: "Apache-2.0", commercial: "yes" },
        { id: "flux-schnell", name: "FLUX.1 schnell", ready: true, backend: "cloudflare", why: null, bestFor: "Fast drafts", license: "Apache-2.0", commercial: "yes" },
      ],
      finish: [
        { id: "wan-vace", name: "Wan VACE 14B", ready: !!over.falKey, backend: over.falKey ? "fal" : null, why: over.falKey ? null : "Add a fal.ai key (AI settings or FAL_KEY).", license: "Apache-2.0", commercial: "yes", price: "$0.08 per video second (720p)" },
        { id: "wan-2.2-animate", name: "Wan 2.2 Animate 14B", ready: !!over.falKey, backend: over.falKey ? "fal" : null, why: over.falKey ? null : "Add a fal.ai key", license: "Apache-2.0", commercial: "yes" },
        { id: "scail-2", name: "SCAIL-2", ready: false, backend: null, why: "SCAIL-2 isn't set up yet. comfyui: Set your GPU server's ComfyUI address.", license: "MIT", commercial: "yes" },
        { id: "ltx-2.3", name: "LTX-2.3 22B", ready: !!over.falKey, backend: over.falKey ? "fal" : null, why: over.falKey ? null : "Add a fal.ai key", license: "LTX-2 Community License", commercial: "conditional" },
      ],
      fal: !!over.falKey, comfyui: over.comfyui ?? "", catalog: true,
    },
  };
}

const ROUNDS = { values: { castRounds: 3, chunkRounds: 3, finalRounds: 2 }, defaults: { castRounds: 3, chunkRounds: 3, finalRounds: 2 }, min: 1, max: 10 };
const PLAN = {
  title: "Rainy Day Cat", version: 2, logline: "A cat who hates water learns to dance in the rain.", style: "flat 2D cartoon", engine: "motion-canvas",
  format: { width: 1280, height: 720, duration_s: 12 },
  look: { palette: ["#2B2D42", "#8D99AE", "#EF233C", "#EDF2F4"], medium: "Flat vector shapes, soft grain", color_arc: "grey to warm" },
  borrowed_from_reference: ["Whip-pan transitions on the beat", "Hold the last frame for one beat"],
  music: { file: "inputs/song.mp3", source: "user", bpm: 112, license: "user provided", section: { start_s: 0, end_s: 12 } },
  style_frames: ["plan/frames/f1.png"],
  characters: [{ id: "cat", name: "Miso", design: "Round grey cat with a yellow raincoat", arc: "scared to joyful" }],
  shots: [
    { id: "S1", start_s: 0, end_s: 4, summary: "Miso stares at the rain", action: "Ears droop", camera: { move: "dolly_in", lens: 35, from: { fill: 0.3 }, to: { fill: 0.6 } }, ref_shot: 1, transition_out: "whip pan" },
    { id: "S2", start_s: 4, end_s: 8, summary: "A puddle reflects a rainbow", camera: "static", transition_in: "whip pan" },
    { id: "S3", start_s: 8, end_s: 12, summary: "Miso dances", camera: { move: "orbit" }, reads: ["joy"] },
  ],
  assets: [{ id: "A1", file: "assets/rain.png", kind: "image", purpose: "rain overlay", status: "drawn_in_code" }, { id: "A2", file: "inputs/song.mp3", kind: "music", purpose: "soundtrack", status: "user", license: "user provided" }],
  open_questions: ["Should Miso talk?"],
  changelog: ["v1", "v2: shorter intro"],
};
const REPORT = { video: { duration: 12.4, width: 1280, height: 720, fps: 24 }, audio: { bpm: 112, present: true }, pacing: { count: 6, mean_shot_s: 2.1, mean_shot_beats: 4 } };
const ROUTE = { engine: "motion-canvas", style: "Flat cartoon", medium: "2D vector", confidence: 0.82, why: ["Flat colours", "No 3D lighting"] };

function job(id: string, stage: string, extra: Record<string, unknown> = {}) {
  return {
    id, title: "Rainy day cat", agent: "ollama", lang: "en", reference: { type: "url", src: "https://example.com/v.mp4" }, settings: {},
    stage, sessionId: null, sessions: {}, createdAt: ago(600), updatedAt: ago(30),
    chat: [
      { role: "user", text: "Make it about a cat who loves rain", ts: ago(590) },
      { role: "agent", who: "director", text: "Here is the **plan**. Approve it or tell me what to change.", ts: ago(60) },
    ],
    log: [
      { type: "turn", state: "start", phase: "plan", who: "director", ts: ago(300) },
      { type: "tool", name: "Read", detail: "analysis/report.json", who: "director", ts: ago(290) },
      { type: "tool", name: "Bash", detail: "python analyze.py ref.mp4", who: "director", ts: ago(200) },
      { type: "text", text: "Here is the **plan**. Approve it or tell me what to change.", who: "director", ts: ago(61) },
      { type: "turn", state: "end", phase: "plan", ok: true, who: "director", ts: ago(59) },
    ],
    needs: [], waived: [], pipeline: {},
    ...extra,
  };
}
function planSnapshot(id: string, songStatus: "missing" | "waived" | "provided" = "missing") {
  return {
    job: job(id, "plan_review", { waived: songStatus === "waived" ? ["song"] : [] }),
    brief: "A 12-second cartoon about a cat who loves rain", report: REPORT, styleMd: "# Style\n- flat colours", route: ROUTE, plan: PLAN,
    storyboard: null, assetsMd: "| asset | license |\n|---|---|\n| song | user |", checks: [], video: null, critique: null,
    cast: { sheets: [], review: null }, shots: [], production: null, lyrics: null,
    requiredInputs: [
      { id: "song", kind: "audio", label: "Your song", why: "the dance is cut to it", status: songStatus, files: songStatus === "provided" ? ["inputs/song.mp3"] : [] },
      { id: "logo", kind: "image", label: "Logo", status: "provided", files: ["inputs/logo.png"] },
    ],
    rounds: ROUNDS, inputs: [], engine: { id: "motion-canvas", label: "Motion Canvas" },
  };
}
function doneSnapshot(id: string) {
  return {
    ...planSnapshot(id, "provided"),
    job: job(id, "done", {
      pipeline: {
        phase: "final", final: { round: 1 },
        cast: { round: 1, pass: true, state: "passed", chars: { cat: { state: "passed", round: 1 } } },
        chunks: { C1: { shots: ["S1", "S2"], state: "passed", round: 1 }, C2: { shots: ["S3"], state: "passed", round: 2 } },
      },
    }),
    video: "out/video.mp4",
    critique: { pass: false, summary: "Good energy; the ending is rushed.", scores: { 開場: 4, 節奏: 3 }, must_fix: [{ shot: "S3", time: 9.5, issue: "Dance ends too abruptly", fix: "Hold the pose 0.5 s" }] },
    cast: { sheets: ["cast/cat_sheet.png"], review: { pass: true, issues: [] } },
    shots: ["review/S1.png", "review/S2.png"],
    production: { characters: [{ id: "cat", name: "Miso" }] },
  };
}
const SUMMARIES = [
  { id: "p-plan", title: "Rainy day cat", stage: "plan_review", agent: "ollama", updatedAt: ago(30), needs: 1, thumb: null },
  { id: "p-done", title: "Finished cat", stage: "done", agent: "gemini", updatedAt: ago(3600), needs: 0, thumb: null },
];
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==", "base64");

let mp4: Buffer | null = null;
test.beforeAll(() => {
  try {
    const dir = mkdtempSync(join(tmpdir(), "avos-anim-"));
    const out = join(dir, "v.mp4");
    execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=12:d=12", "-c:v", "libx264", "-pix_fmt", "yuv420p", out]);
    if (existsSync(out)) mp4 = readFileSync(out);
  } catch { mp4 = null; }
});

type Call = { method: string; path: string; body: string; contentType: string };
interface FinishState { model: string; name: string; state: string; done: number; total: number; shots: Record<string, unknown>; video: string | null; error: string | null; polls: number }
interface Studio { calls: Call[]; info: ReturnType<typeof agentsInfo>; song: "missing" | "waived" | "provided"; offline: boolean; over: InfoOver; finish: FinishState | null }

async function mockStudio(page: Page): Promise<Studio> {
  const st: Studio = { calls: [], info: agentsInfo(), song: "missing", offline: false, over: {}, finish: null };
  const json = (route: Route, body: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });
  // the live stream is opened straight at the service: unreachable here, so the page falls back to polling
  await page.route(/:8020\/api\/projects\/.*\/events/, (route) => route.abort());
  await page.route("**/studio-files/**", (route) => {
    const u = route.request().url();
    if (/\.mp4/.test(u)) return mp4 ? route.fulfill({ status: 200, contentType: "video/mp4", body: mp4 }) : route.fulfill({ status: 404 });
    if (/\.(png|jpe?g)/.test(u)) return route.fulfill({ status: 200, contentType: "image/png", body: PNG });
    return route.fulfill({ status: 404, body: "" });
  });
  await page.route("**/studio-api/**", async (route) => {
    const req = route.request(), url = new URL(req.url()), path = url.pathname.replace(/^\/studio-api/, ""), method = req.method();
    st.calls.push({ method, path, body: req.postDataBuffer()?.toString("latin1") ?? "", contentType: (await req.allHeaders())["content-type"] ?? "" });
    if (st.offline) return route.fulfill({ status: 502, contentType: "text/plain", body: "Bad Gateway" });
    if (path === "/agents/info") return json(route, st.info);
    if (path === "/agents") return json(route, { ollama: "qwen2.5:7b", gemini: "gemini-2.0-flash" });
    if (path === "/agents/settings") {
      const body = JSON.parse(req.postData() || "{}");
      if (body.agent === "groq" && body.key) st.over.groqKey = true;
      if (body.models?.falKey !== undefined) st.over.falKey = !!body.models.falKey;
      if (body.models?.comfyuiUrl !== undefined) st.over.comfyui = body.models.comfyuiUrl;
      if (body.render?.imageModel) st.over.imageModel = body.render.imageModel;
      st.info = agentsInfo({ ...st.over, pulls: st.info.pulls });
      return json(route, st.info);
    }
    if (path === "/agents/pull") {
      const { model } = JSON.parse(req.postData() || "{}");
      st.info = { ...st.info, pulls: { [model]: { status: "pulling manifest", done: false, pct: 42 } } };
      return json(route, { ok: true });
    }
    if (path === "/config") return json(route, { castRounds: 3, chunkRounds: 3, finalRounds: 2, builders: 2, maxAgentsGlobal: 4 });
    if (path === "/projects" && method === "POST") return json(route, { id: "p-new" });
    if (path === "/projects") return json(route, SUMMARIES);
    const m = path.match(/^\/projects\/([\w-]+)(?:\/(\w+))?$/);
    if (m) {
      const [, id, action] = m;
      if (st.finish && id === "p-done" && !action) {   // the AI finish advances one shot per poll
        const f = st.finish;
        f.done = Math.min(3, f.done + 1);
        f.shots = Object.fromEntries(["S1", "S2", "S3"].slice(0, f.done).map((k) => [k, k === "S2" ? { ok: false, error: "fal.ai: error 422" } : { ok: true }]));
        if (f.done === 3) Object.assign(f, { state: "done", video: "out/video_ai.mp4" });
        return json(route, { ...doneSnapshot(id), finish: { ...f } });
      }
      const snap = () => (id === "p-done" ? doneSnapshot(id) : id === "p-new" ? { ...planSnapshot(id), job: job(id, "analyzing", { chat: [], log: [] }), plan: null, report: null, route: null, requiredInputs: [] } : planSnapshot(id, st.song));
      if (!action) return json(route, snap());
      if (action === "waive") { st.song = "waived"; return json(route, snap()); }
      if (action === "unwaive") { st.song = "missing"; return json(route, snap()); }
      if (action === "approve") return st.song === "missing" ? json(route, { error: "missing inputs", open: ["song"] }, 409) : json(route, { ok: true });
      if (action === "finish") {
        st.finish = { model: "wan-vace", name: "Wan VACE 14B", state: "running", done: 0, total: 3, shots: {}, video: null, error: null, polls: 0 };
        return json(route, { ok: true, finish: st.finish });
      }
      return json(route, { ok: true });
    }
    return json(route, { error: "not mocked: " + path }, 404);
  });
  return st;
}

// ---------- tests ----------
test("sidebar: Explainer and Animations tabs, /dashboard still redirects to /explainer", async ({ page }) => {
  await mockStudio(page);
  await page.goto("/dashboard");
  await expect(page).toHaveURL(/\/explainer$/);
  await expect(page.getByTestId("explainer-create")).toBeVisible();
  await page.getByRole("link", { name: /Animations/ }).first().click();
  await expect(page).toHaveURL(/\/animations$/);
  await expect(page.getByTestId("composer")).toBeVisible();
});

test("home: AVOS layout; a suggestion fills the brief in the chosen language; Create asks for a missing reference", async ({ page }) => {
  await mockStudio(page);
  await page.goto("/animations");
  await expect(page.getByRole("heading", { name: "Animations", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your Projects" })).toBeVisible();
  await page.getByRole("button", { name: /about love, with a funny twist/ }).click();
  await expect(page.getByTestId("brief")).toHaveValue(/about love, with a funny twist/);  // English, not the Chinese source
  // Create without a reference video opens the file chooser and says why
  const chooser = page.waitForEvent("filechooser");
  await page.getByTestId("create-animation").click();
  await chooser;
  await expect(page.getByTestId("need-reference")).toContainText("Choose a reference video");
});

test("home: composer, crew picker defaults to Ollama, AI settings", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const st = await mockStudio(page);
  await page.goto("/animations");
  await expect(page.getByRole("heading", { name: "New animation" })).toBeVisible();
  await expect(page.getByTestId("composer")).toBeVisible();
  await expect(page.getByText("Break down the style")).toBeVisible();            // "how it works" row
  await expect(page.getByTestId("animation-card")).toHaveCount(2);                 // project list
  await expect(page.getByTestId("crew-capsule")).toContainText("Ollama (local)");  // header capsule

  const picker = page.getByTestId("crew-picker");
  await expect(picker).toContainText("Ollama (local)");
  await picker.click();
  const menu = page.getByTestId("crew-menu");
  await expect(menu).toContainText("Local (free, runs on your PC)");
  await expect(menu).toContainText("Free cloud");
  await expect(menu).toContainText("Paid");
  await expect(menu.locator('[data-agent="ollama"]')).toHaveAttribute("aria-selected", "true");
  await expect(menu.locator('[data-agent="ollama"]')).toContainText("Default");
  await expect(menu.locator('[data-agent="groq"]')).toBeDisabled();
  await expect(menu.locator('[data-agent="groq"]')).toContainText("console.groq.com");
  await menu.locator('[data-agent="gemini"]').click();
  await expect(picker).toContainText("Gemini");

  // AI settings: per-provider model / key / default / download
  await page.getByTestId("ai-settings-btn").click();
  const sheet = page.getByTestId("ai-settings");
  await expect(sheet.getByRole("heading", { name: "AI settings" })).toBeVisible();
  await expect(sheet).toContainText("Drawn by the engine (offline)");
  await expect(sheet).toContainText("AI images need a Gemini key");
  const ollama = sheet.locator('[data-provider="ollama"]');
  await expect(ollama.getByLabel("Downloaded models")).toHaveValue("qwen2.5:7b");
  await expect(ollama.getByTestId("vision-model")).toBeVisible();   // optional model that looks at frames
  await ollama.getByPlaceholder("Model name to download").fill("llama3.2:1b");
  await ollama.getByTestId("pull-model").click();
  await expect(ollama.getByTestId("pull-progress")).toContainText("Downloading 42%");
  await expect.poll(() => st.calls.some((c) => c.path === "/agents/pull" && c.body.includes("llama3.2:1b"))).toBe(true);

  const groq = sheet.locator('[data-provider="groq"]');
  await groq.getByRole("button", { name: /Groq/ }).click();
  await groq.getByPlaceholder("Paste the API key").fill("gsk_test");
  await groq.getByRole("button", { name: "Save" }).click();
  await expect(groq).toContainText("Saved");
  await expect.poll(() => st.calls.some((c) => c.path === "/agents/settings" && c.body.includes('"key":"gsk_test"') && c.body.includes('"agent":"groq"'))).toBe(true);
  await sheet.getByRole("tab", { name: "1080p" }).click();
  await expect.poll(() => st.calls.some((c) => c.path === "/agents/settings" && c.body.includes('"quality":"1080p"'))).toBe(true);
  await page.keyboard.press("Escape");
  await expect(sheet).toBeHidden();
  expect(errors).toEqual([]);
});

test("create: multipart POST to /studio-api/projects, then the project page opens", async ({ page }) => {
  const st = await mockStudio(page);
  await page.goto("/animations");
  await expect(page.getByTestId("crew-picker")).toContainText("Ollama (local)");
  await page.getByRole("button", { name: "Paste link" }).click();
  await page.getByPlaceholder("Paste a YouTube or video link").fill("https://www.youtube.com/watch?v=dQw4w9WgXcQ");
  await page.getByTestId("brief").fill("A 10-second cartoon about a cat who loves rain");
  await page.getByTestId("create-animation").click();
  await expect(page).toHaveURL(/\/animations\/p-new$/);
  const post = st.calls.find((c) => c.method === "POST" && c.path === "/projects");
  expect(post?.contentType).toContain("multipart/form-data");
  expect(post?.body).toContain('name="url"');
  expect(post?.body).toContain("dQw4w9WgXcQ");
  expect(post?.body).toMatch(/name="agent"\r\n\r\nollama/);
  expect(post?.body).toMatch(/name="lang"\r\n\r\nen/);
  await expect(page.getByText("Analyzing the reference…").first()).toBeVisible();
});

test("plan review: tabs, required inputs, approve blocked until the input is skipped", async ({ page }) => {
  const st = await mockStudio(page);
  await page.goto("/animations/p-plan");
  await expect(page.getByRole("heading", { name: "Rainy Day Cat", level: 1 })).toBeVisible();
  await expect(page.getByRole("tab", { name: "Plan" })).toBeVisible();
  await expect(page.getByRole("tab", { name: /Reference analysis/ })).toBeVisible();
  const req = page.locator("#required-inputs");
  await expect(req).toContainText("Needs 1 input(s) from you");
  await expect(req).toContainText("Your song");
  const approve = page.getByRole("button", { name: "Approve and start" });
  await expect(approve).toBeDisabled();
  await expect(page.getByText("1 inputs missing")).toBeVisible();
  // plan details: shots expand, "comment on S3" tags the conversation
  await page.locator(".shot-li").filter({ hasText: "Miso dances" }).click();
  await page.getByRole("button", { name: "Comment on S3" }).click();
  await expect(page.locator(".ctx-tag")).toContainText("On S3");
  // skip the song -> approve unlocks
  await req.getByRole("button", { name: "Skip" }).click();
  await expect.poll(() => st.calls.some((c) => c.path === "/projects/p-plan/waive" && c.body.includes('"input":"song"'))).toBe(true);
  await expect(approve).toBeEnabled();
  await approve.click();
  await expect.poll(() => st.calls.some((c) => c.path === "/projects/p-plan/approve")).toBe(true);
  // reference analysis tab
  await page.getByRole("tab", { name: /Reference analysis/ }).click();
  await expect(page.getByText("Detected style")).toBeVisible();
  await expect(page.getByText("Flat cartoon")).toBeVisible();
});

test("done project: Final tab with player, notes and critique; Production line; Log", async ({ page }) => {
  const st = await mockStudio(page);
  await page.goto("/animations/p-done");
  await expect(page.getByRole("tab", { name: /Final/ })).toHaveAttribute("aria-selected", "true");
  await expect(page.getByTestId("final-video")).toBeVisible();
  await expect(page.getByText("Independent critic")).toBeVisible();
  await expect(page.getByText("Dance ends too abruptly")).toBeVisible();
  await page.getByTestId("note-input").fill("Make the rain heavier here");
  await page.getByRole("button", { name: "Add note" }).click();
  await page.getByRole("button", { name: "Send 1 notes" }).click();
  await expect.poll(() => st.calls.find((c) => c.path === "/projects/p-done/message")?.body ?? "").toContain("Make the rain heavier here");

  await page.getByRole("tab", { name: /Production line/ }).click();
  await expect(page.getByText("Character sheets")).toBeVisible();
  await expect(page.locator(".chunk").filter({ hasText: "C2" })).toContainText("Passed");

  await page.getByRole("tab", { name: "Log" }).click();
  await expect(page.locator(".lg-row").first()).toBeVisible();
  await page.getByPlaceholder("Search log").fill("analyze.py");
  await expect(page.locator(".lg-row")).toHaveCount(1);
});

test("open models: AI settings pick the backdrop model and save the fal.ai key / GPU server; AI finish on a done film", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const st = await mockStudio(page);
  await page.goto("/animations");
  await page.getByTestId("ai-settings-btn").click();
  const box = page.getByTestId("open-models");
  await expect(box).toBeVisible();
  await expect(box.locator('[data-model="scail-2"]')).toHaveCount(0);                    // finish models aren't listed here
  await expect(box.locator('[data-model="z-image"]')).toContainText("Add a fal.ai key");
  // fal.ai key
  await page.getByTestId("fal-key").fill("fal-secret");
  await box.getByRole("button", { name: "Save" }).first().click();
  await expect(box.locator('[data-model="z-image"]')).toContainText("fal.ai (paid)");
  expect(st.calls.some((c) => c.path === "/agents/settings" && c.body.includes('"falKey":"fal-secret"'))).toBe(true);
  // backdrop model
  await page.getByTestId("image-model").selectOption("best");
  await expect.poll(() => st.calls.some((c) => c.body.includes('"imageModel":"best"'))).toBe(true);
  await expect(page.getByTestId("image-model")).toHaveValue("best");
  // GPU server address
  await page.getByTestId("comfyui-url").fill("http://203.0.113.5:8188");
  await box.getByRole("button", { name: "Save" }).nth(1).click();
  await expect.poll(() => st.calls.some((c) => c.body.includes('"comfyuiUrl":"http://203.0.113.5:8188"'))).toBe(true);
  await page.keyboard.press("Escape");

  // AI finish on a finished film
  await page.goto("/animations/p-done");
  const fin = page.getByTestId("ai-finish");
  await expect(fin).toBeVisible();
  await expect(page.getByTestId("finish-model")).toHaveValue("wan-vace");               // first ready model
  await page.getByTestId("finish-model").selectOption("scail-2");
  await expect(fin).toContainText("GPU server");                                          // why it can't run
  await expect(page.getByTestId("finish-start")).toBeDisabled();
  await page.getByTestId("finish-model").selectOption("ltx-2.3");
  await expect(fin).toContainText("LTX-2 Community License");
  await page.getByTestId("finish-model").selectOption("wan-vace");
  await page.getByTestId("finish-start").click();
  await expect(page.getByTestId("finish-video")).toBeVisible({ timeout: 20_000 });       // progress polled to the end
  await expect(fin).toContainText("1 shot(s) kept the engine version");
  expect(st.calls.some((c) => c.path === "/projects/p-done/finish" && c.body.includes('"model":"wan-vace"'))).toBe(true);
  expect(errors).toEqual([]);
});

test("language menu switches the interface to Traditional Chinese", async ({ page }) => {
  await mockStudio(page);
  await page.goto("/animations");
  await expect(page.getByRole("heading", { name: "New animation" })).toBeVisible();
  await page.getByTestId("lang-menu").click();
  await page.getByRole("option", { name: "繁體中文" }).click();
  await expect(page.getByRole("heading", { name: "新動畫" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "New animation" })).toHaveCount(0);
  await page.getByTestId("lang-menu").click();
  await page.getByRole("option", { name: "简体中文" }).click();
  await expect(page.getByText("丢一支喜欢的影片，")).toBeVisible();
});

test("engine offline: friendly card with how to start it, then recovers by itself", async ({ page }) => {
  const st = await mockStudio(page);
  st.offline = true;
  await page.goto("/animations");
  const card = page.getByTestId("studio-offline");
  await expect(card).toBeVisible({ timeout: 30_000 });
  await expect(card).toContainText("docker compose up -d animation-studio");
  await expect(card).toContainText("start-animations.bat");
  await expect(card).toContainText("ollama pull qwen2.5:7b");
  st.offline = false;
  await expect(page.getByTestId("composer")).toBeVisible({ timeout: 15_000 });
});

// Visual check, off by default: ANIM_SHOTS_DIR=/some/dir writes light/dark x desktop/phone screenshots there.
test("screenshots (ANIM_SHOTS_DIR)", async ({ page }) => {
  const dir = process.env.ANIM_SHOTS_DIR;
  test.skip(!dir, "set ANIM_SHOTS_DIR to capture screenshots");
  test.setTimeout(300_000);
  await mockStudio(page);
  for (const theme of ["light", "dark"]) {
    for (const [w, h, tag] of [[1440, 900, "desktop"], [390, 844, "phone"]] as const) {
      await page.setViewportSize({ width: w, height: h });
      await page.addInitScript((t) => { try { localStorage.setItem("avos-theme", t); } catch {} }, theme);
      for (const [path, name] of [["/animations", "home"], ["/animations/p-plan", "plan"], ["/animations/p-done", "done"]] as const) {
        await page.goto(path);
        await page.waitForTimeout(1500);
        await page.screenshot({ path: `${dir}/${name}-${theme}-${tag}.png`, fullPage: false });
        // English mode: any Chinese left in the UI is a missing translation
        const cjk = (await page.locator(".rm").allInnerTexts()).join("\n").split("\n").filter((l) => /[\u4e00-\u9fff]/.test(l));
        if (cjk.length) console.log(`[${name}] untranslated:`, cjk);
      }
      await page.goto("/animations");
      await page.getByTestId("crew-picker").click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${dir}/crew-${theme}-${tag}.png` });
      await page.locator(".crew-foot").click();
      await page.waitForTimeout(500);
      await page.screenshot({ path: `${dir}/settings-${theme}-${tag}.png` });
    }
  }
});
