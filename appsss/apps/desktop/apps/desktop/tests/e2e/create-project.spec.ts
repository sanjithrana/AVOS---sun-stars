import { expect, test, type Page } from "@playwright/test";

// These specs drive the manual QA / repair UI, so the workflow's automatic QA agent (v12) is turned off while they
// run and turned back on afterwards (GPU page → generation limits).
test.beforeAll(async ({ request }) => {
  await request.put(`${process.env.E2E_API_URL || "http://localhost:8001/api/v1"}/gpu/limits`, { data: { auto_qa: false } });
});
test.afterAll(async ({ request }) => {
  await request.put(`${process.env.E2E_API_URL || "http://localhost:8001/api/v1"}/gpu/limits`, { data: { auto_qa: true } });
});


/**
 * Week 1 Day 3 smoke test + Week 2 Day 10 integration checkpoint demo,
 * driven through the real UI:
 *   1. create a project from the Dashboard
 *   2. Generate -> Director researches + writes a script
 *   3. script approval gate appears in the Studio; approve it
 *   4. workflow resumes -> narration + timestamps + beats appear
 *   5. every agent step is audited (GET /agents/trace); a shot can be edited and regenerated in the Studio
 *   6. (Week 3) shots are planned per beat and run through the Blender
 *      stage; the ShotEditor shows the selected shot's real ShotSpec
 * and fails on any console error or unhandled promise rejection.
 */

const API_URL = process.env.E2E_API_URL || "http://localhost:8001/api/v1";

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return errors;
}

async function createProject(page: Page, topic: string) {
  await page.goto("/facts");
  await expect(page.getByRole("heading", { name: "Facts" })).toBeVisible();

  await page.getByRole("button", { name: "New Project" }).first().click();
  await page.getByLabel("Topic").fill(topic);
  await page.getByLabel("Duration (sec)").fill("30");
  // No per-shot clips: keeps this spec offline/deterministic (mock
  // images); final-video.spec.ts covers the video providers.
  await page.locator("#image-provider").selectOption("");   // deterministic placeholder pictures (the QA checks agree by construction)
  await page.locator("#video-provider").selectOption("");
  await page.getByRole("button", { name: "Create Project" }).click();

  await expect(page).toHaveURL(/\/project\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  await expect(page.getByTestId("project-name")).toHaveText(topic);
}

test("create project -> appears on dashboard after reload", async ({ page }) => {
  const errors = trackErrors(page);
  const topic = `Playwright smoke ${Date.now()}`;

  await createProject(page, topic);

  await page.goto("/facts");
  await page.reload();
  await expect(page.getByTestId("project-card").filter({ hasText: topic })).toBeVisible();

  expect(errors).toEqual([]);
});

test("studio storyboard empty state is graceful for a new project", async ({ page }) => {
  const errors = trackErrors(page);
  const topic = `Empty storyboard ${Date.now()}`;
  await createProject(page, topic);

  const projectId = page.url().split("/").pop();
  const shots = await page.request.get(`${API_URL}/projects/${projectId}/shots`);
  expect(shots.status()).toBe(200);
  expect(await shots.json()).toEqual([]);

  await page.goto(`/studio/${projectId}`);
  await expect(page.getByTestId("storyboard-empty")).toBeVisible();
  await expect(page.getByTestId("storyboard-empty")).toContainText("Start generation");
  await expect(page.getByTestId("shot-card")).toHaveCount(0);
  await expect(page.getByTestId("plan-shots")).toHaveCount(0);
  await expect(page.getByTestId("shot-editor")).toHaveCount(0);

  expect(errors).toEqual([]);
});

test("full Week 2 flow: generate -> approve script -> audio + live trace", async ({ page }) => {
  test.setTimeout(300_000);
  const errors = trackErrors(page);
  const topic = `Flowers for Kids ${Date.now()}`;

  await createProject(page, topic);

  // Generate: job goes RUNNING and the Director starts working.
  await page.getByTestId("generate-button").click();
  await expect(page.getByTestId("job-status")).toHaveText(/RUNNING/, { timeout: 15_000 });

  // Script gate opens (pushed over SSE - no reload).
  const review = page.getByRole("link", { name: /Review in Studio/ });
  await expect(review).toBeVisible({ timeout: 30_000 });
  await review.click();

  const approval = page.getByTestId("script-approval");
  await expect(approval).toBeVisible();
  await expect(page.getByTestId("storyboard").getByRole("button")).not.toHaveCount(0);

  // Audited trace so far: memory, research, script.
  const projectId = page.url().split("/").pop();
  const traceTools = async () =>
    ((await (await page.request.get(`${API_URL}/agents/trace?project_id=${projectId}`)).json()) as { tool_name: string }[]).map((t) => t.tool_name);
  expect(await traceTools()).toContain("generate_script");

  // The workflow is genuinely paused: nothing proceeds for a few seconds.
  await page.waitForTimeout(2_000);
  await expect(approval).toBeVisible();
  await expect(page.getByTestId("timeline")).toHaveCount(0);

  await approval.getByRole("button", { name: "Approve" }).click();

  // Workflow resumes: audio, timestamps and beats arrive live. The
  // timeline reads the finished job's output, which now also waits for the
  // visuals + final render stages.
  await expect(page.getByTestId("timeline")).toBeVisible({ timeout: 180_000 });
  await expect(page.getByTestId("script-approval")).toHaveCount(0);
  expect(await traceTools()).toContain("generate_audio");
  // Complete now means the final video is rendered too.
  await expect(page.getByText("Complete").first()).toBeVisible({ timeout: 180_000 });
  await expect(page.getByTestId("live-indicator")).toHaveText(/Live/);

  // Generated narration is a real, playable asset.
  const src = await page.locator("[data-testid=timeline] audio").getAttribute("src");
  expect(src).toBeTruthy();
  const audio = await page.request.get(src!);
  expect(audio.status()).toBe(200);
  // WAV with the offline mock voice, MP3 with the real (Edge) voice.
  expect(audio.headers()["content-type"]).toMatch(/audio\/(wav|mpeg)/);

  // Week 3: one shot per beat, continuity-checked, Blender stage, then
  // its visuals generated automatically (physics before pixels).
  const cards = page.getByTestId("shot-card");
  await expect(cards.first()).toBeVisible({ timeout: 30_000 });
  const count = await cards.count();
  expect(count).toBeGreaterThan(0);
  for (let i = 0; i < count; i++) {
    await expect(cards.nth(i)).toHaveAttribute("data-status", "QA_PENDING");
  }
  expect(await traceTools()).toContain("run_blender_proxy");

  // ShotEditor shows the selected shot's ShotSpec (GET /shots/{id}).
  await cards.first().click();
  const editor = page.getByTestId("shot-editor");
  await expect(editor).toBeVisible();
  await expect(editor.getByText("Shot 01")).toBeVisible();
  await expect(editor.getByTestId("shot-narration")).not.toBeEmpty();
  await expect(editor.getByTestId("shot-continuity")).toContainText("Passed");

  await editor.getByTestId("shot-tab-camera").click();
  await expect(editor.getByTestId("shot-type")).toHaveText("Wide"); // first shot of a scene
  await editor.getByTestId("shot-tab-environment").click();
  await expect(editor.getByTestId("shot-location")).toContainText("main setting");
  await editor.getByTestId("shot-tab-prompt").click();
  await expect(editor.getByTestId("shot-prompt")).toContainText("Wide shot");

  // Edit the shot's prompt and regenerate just this shot (and the final video)
  await expect(editor.getByTestId("physics-assets")).toHaveCount(0);           // no Blender passes in the UI
  await editor.getByTestId("edit-prompt").fill("A bright storybook garden full of tulips, close up, morning light");
  await editor.getByTestId("edit-save").click();
  await expect(editor.getByTestId("regen-status")).toContainText("is ready", { timeout: 180_000 });
  await expect(editor.getByText(/v2 ·/)).toBeVisible({ timeout: 15_000 });
  await editor.getByTestId("shot-tab-prompt").click();
  await expect(editor.getByTestId("shot-prompt")).toContainText("tulips");

  if (count > 1) {
    await cards.nth(1).click();
    await expect(editor.getByText("Shot 02")).toBeVisible();
  }

  expect(errors).toEqual([]);
});
