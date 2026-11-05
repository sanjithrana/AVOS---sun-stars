import { expect, test, type Page } from "@playwright/test";

/**
 * The whole point of the pipeline, through the real UI and real stack:
 * topic -> script (approved by a human) -> narration -> shots -> an
 * image + clip per shot -> ONE final MP4 with narration and captions
 * that plays in the project page and downloads as a file.
 *
 * Provider under test (defaults to the free one that needs no key/GPU):
 *   E2E_VIDEO_PROVIDER=motion|replicate|comfyui|local|""   (default motion)
 *   E2E_IMAGE_PROVIDER=pollinations|local|...              (default: form default)
 *   E2E_RENDER_TIMEOUT_MS                                   (default 10 min)
 */

const VIDEO_PROVIDER = process.env.E2E_VIDEO_PROVIDER ?? "motion";
const IMAGE_PROVIDER = process.env.E2E_IMAGE_PROVIDER;
const RENDER_TIMEOUT = Number(process.env.E2E_RENDER_TIMEOUT_MS || 600_000);

function trackErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") errors.push(`console: ${msg.text()}`);
  });
  page.on("pageerror", (err) => errors.push(`pageerror: ${err.message}`));
  return errors;
}

test("topic to a finished, playable, downloadable video", async ({ page }) => {
  test.setTimeout(RENDER_TIMEOUT + 120_000);
  const errors = trackErrors(page);
  const topic = `The Sun ${Date.now()}`;

  // 1. Create the project with the chosen providers.
  await page.goto("/facts");
  await page.getByRole("button", { name: "New Project" }).first().click();
  await page.getByLabel("Topic").fill(topic);
  await page.getByLabel("Duration (sec)").fill("30");
  if (IMAGE_PROVIDER !== undefined) await page.locator("#image-provider").selectOption(IMAGE_PROVIDER);
  await page.locator("#video-provider").selectOption(VIDEO_PROVIDER);
  await expect(page.getByTestId("video-provider-hint")).not.toBeEmpty();
  await page.getByRole("button", { name: "Create Project" }).click();
  await expect(page).toHaveURL(/\/project\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  const projectUrl = page.url();

  // 2. Generate, then approve the script in the Studio.
  await page.getByTestId("generate-button").click();
  const review = page.getByRole("link", { name: /Review in Studio/ });
  await expect(review).toBeVisible({ timeout: 60_000 });
  await review.click();
  await page.getByTestId("script-approval").getByRole("button", { name: "Approve" }).click();

  // 3. Shots get their visuals automatically (no manual Generate clicks).
  const cards = page.getByTestId("shot-card");
  await expect(cards.first()).toBeVisible({ timeout: 60_000 });
  await expect(cards.first()).toHaveAttribute("data-status", "QA_PENDING", { timeout: RENDER_TIMEOUT });
  await expect(cards.first().locator("img, video")).toHaveCount(1);

  // 4. The final video appears on the project page - live, no reload.
  await expect(page.getByRole("link", { name: "Watch video" })).toBeVisible({ timeout: RENDER_TIMEOUT });
  await page.goto(projectUrl);
  const card = page.getByTestId("final-video");
  await expect(card).toBeVisible();
  await expect(page.locator("[data-step=render]")).toHaveAttribute("data-state", "done");

  // It's a real, playable MP4: the browser reads its duration. (Chrome
  // and Edge play H.264; Playwright's open-source Chromium build ships
  // without that codec, so there only the file itself is checked.)
  const video = card.locator("video");
  const canPlayH264 = await video.evaluate(
    (el: HTMLVideoElement) => el.canPlayType('video/mp4; codecs="avc1.64001F, mp4a.40.2"') !== ""
  );
  const duration = !canPlayH264 ? Number.NaN : await video.evaluate(
    (el: HTMLVideoElement) =>
      new Promise<number>((resolve, reject) => {
        if (el.readyState >= 1) return resolve(el.duration);
        el.addEventListener("loadedmetadata", () => resolve(el.duration), { once: true });
        el.addEventListener("error", () => reject(new Error("video failed to load")), { once: true });
        el.load();
      })
  );
  if (canPlayH264) expect(duration).toBeGreaterThan(5);
  else test.info().annotations.push({ type: "note", description: "browser lacks H.264; playback not checked" });

  const src = await video.getAttribute("src");
  const media = await page.request.get(src!);
  expect(media.status()).toBe(200);
  expect(media.headers()["content-type"]).toContain("video/mp4");
  const bytes = await media.body();
  expect(bytes.subarray(4, 8).toString()).toBe("ftyp"); // an MP4 container
  expect(bytes.length).toBeGreaterThan(100_000);

  // Download gives an attachment named after the project.
  const href = await page.getByTestId("download-video").getAttribute("href");
  const download = await page.request.get(href!);
  expect(download.headers()["content-disposition"]).toMatch(/attachment; filename=.*the-sun-\d+\.mp4/);

  expect(errors).toEqual([]);
});
