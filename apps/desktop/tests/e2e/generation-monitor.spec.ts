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
 * Week 3 Day 13 - GenerationMonitor, driven through the real UI:
 * a BLENDER_READY shot's "Generate" button dispatches
 * generate_video_shot through the audited + physics-gated Gateway, and
 * the row updates live (SSE VIDEO_GENERATED, no reload) to show 3
 * candidates once QA_PENDING.
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
  await page.getByRole("button", { name: "New Project" }).first().click();
  await page.getByLabel("Topic").fill(topic);
  await page.getByLabel("Duration (sec)").fill("30");
  // No per-shot clips: keeps this spec offline/deterministic (mock
  // images); final-video.spec.ts covers the video providers.
  await page.locator("#image-provider").selectOption("");   // deterministic placeholder pictures (the QA checks agree by construction)
  await page.locator("#video-provider").selectOption("");
  await page.getByRole("button", { name: "Create Project" }).click();
  await expect(page).toHaveURL(/\/project\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  return page.url().split("/").pop()!;
}

test("generation monitor: the pipeline generates 3 live candidates per shot", async ({ page }) => {
  const errors = trackErrors(page);
  const topic = `Generation monitor ${Date.now()}`;

  const projectId = await createProject(page, topic);

  await page.getByTestId("generate-button").click();
  const review = page.getByRole("link", { name: /Review in Studio/ });
  await expect(review).toBeVisible({ timeout: 30_000 });
  await review.click();

  await page.getByTestId("script-approval").getByRole("button", { name: "Approve" }).click();

  // Shots go PLANNED -> BLENDER_READY -> QA_PENDING by themselves: the
  // Temporal pipeline's visuals stage generates every shot (no clicks).
  const cards = page.getByTestId("shot-card");
  await expect(cards.first()).toBeVisible({ timeout: 30_000 });

  const monitor = page.getByTestId("generation-monitor");
  await expect(monitor).toBeVisible();
  const rows = monitor.getByTestId("generation-row");
  const firstRow = rows.first();

  // Live update over SSE: no reload, the row moves to QA_PENDING with
  // 3 candidates and a full progress bar.
  await expect(firstRow).toHaveAttribute("data-shot-status", "QA_PENDING", { timeout: 120_000 });
  await expect(firstRow.getByTestId("candidate")).toHaveCount(3);
  await expect(firstRow.getByTestId("generation-progress")).toHaveAttribute("data-progress", "100");
  await expect(firstRow.getByTestId("generate-shot")).toHaveCount(0); // no longer BLENDER_READY

  // The backend idempotency guarantee (api/tests/test_video_generation_idempotency.py)
  // means this state is stable: re-fetching still shows exactly 3
  // candidates, not 6.
  const detail = await page.request.get(`${API_URL}/projects/${projectId}/shots`);
  const shots = await detail.json();
  expect(shots[0].spec.video_generation.candidates).toHaveLength(3);

  expect(errors).toEqual([]);
});
