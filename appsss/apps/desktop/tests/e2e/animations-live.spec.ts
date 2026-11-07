import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * The Animations tab against the REAL Animation Studio service (apps/animation_studio), end to end:
 * create from a reference video → plan → chat changes the plan → approve → production → video →
 * a timed note on the video → revision → done.
 *
 *   STUDIO_LIVE=1 npx playwright test tests/e2e/animations-live.spec.ts
 *
 * Needs the service running (start-animations.bat / docker compose up -d animation-studio) and FFmpeg here.
 * STUDIO_LIVE_AGENT picks the crew (default "builtin": no AI needed, fully offline; "ollama" uses your local model).
 * STUDIO_URL is where the service runs (default http://127.0.0.1:8020).
 */
test.skip(!process.env.STUDIO_LIVE, "set STUDIO_LIVE=1 to run against the real Animation Studio service");
test.setTimeout(20 * 60_000);

const STUDIO = (process.env.STUDIO_URL || "http://127.0.0.1:8020").replace(/\/$/, "");
const AGENT = process.env.STUDIO_LIVE_AGENT || "builtin";

type Snap = { job: { stage: string; error?: string | null }; plan?: { version?: number; title?: string } | null; video?: string | null };
const snap = async (id: string): Promise<Snap> => (await fetch(`${STUDIO}/api/projects/${id}`)).json();
async function until(id: string, stages: string[], ms: number): Promise<Snap> {
  const t0 = Date.now();
  for (;;) {
    const s = await snap(id);
    if (stages.includes(s.job.stage)) return s;
    if (s.job.stage === "error") throw new Error(`project failed: ${s.job.error}`);
    if (Date.now() - t0 > ms) throw new Error(`timed out waiting for ${stages.join("/")} (now ${s.job.stage})`);
    await new Promise((r) => setTimeout(r, 2000));
  }
}

test("live: reference → plan → chat → approve → video → timed note → revised", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  // a 6-second reference with a few cuts and a tone
  const dir = mkdtempSync(join(tmpdir(), "avos-live-"));
  const ref = join(dir, "reference.mp4");
  execFileSync("ffmpeg", ["-hide_banner", "-loglevel", "error", "-y",
    "-f", "lavfi", "-i", "testsrc2=s=640x360:r=24:d=2", "-f", "lavfi", "-i", "smptebars=s=640x360:r=24:d=2", "-f", "lavfi", "-i", "mandelbrot=s=640x360:r=24",
    "-f", "lavfi", "-i", "sine=f=440:d=6", "-filter_complex", "[2:v]trim=duration=2[m];[0:v][1:v][m]concat=n=3:v=1:a=0[v]",
    "-map", "[v]", "-map", "3:a", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-shortest", ref]);

  await page.goto("/animations");
  await expect(page.getByTestId("composer")).toBeVisible({ timeout: 30_000 });
  // pick the crew for this run
  await page.getByTestId("crew-picker").click();
  await page.getByTestId("crew-menu").locator(`[data-agent="${AGENT}"]`).click();
  await page.getByTestId("reference-file").setInputFiles(ref);
  await page.getByTestId("brief").fill("A 12-second story about a shy cat who learns to dance at a party");
  await page.getByTestId("create-animation").click();
  await expect(page).toHaveURL(/\/animations\/[\w-]+$/, { timeout: 60_000 });
  const id = page.url().split("/").pop()!;

  // plan review
  let s = await until(id, ["plan_review"], 6 * 60_000);
  await expect(page.getByRole("tab", { name: /^Plan/ })).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("button", { name: /Approve and start/ })).toBeVisible();
  const v1 = s.plan?.version ?? 1;

  // a chat message revises the plan
  await page.locator(".compose textarea").fill("Make it vertical 9:16 please");
  await page.locator(".compose textarea").press("Enter");
  await expect.poll(async () => (await snap(id)).plan?.version ?? 0, { timeout: 5 * 60_000 }).toBeGreaterThan(v1);
  s = await until(id, ["plan_review"], 5 * 60_000);

  // approve → production → final video
  await page.getByRole("button", { name: /Approve and start/ }).click();
  s = await until(id, ["done", "needs_input"], 15 * 60_000);
  if (s.job.stage === "needs_input") {
    await page.reload();
    await page.getByRole("button", { name: /Good enough|Characters are fine|Continue production/ }).first().click();
    s = await until(id, ["done"], 10 * 60_000);
  }
  expect(s.video).toBe("out/video.mp4");
  await page.reload();
  await expect(page.getByTestId("final-video")).toBeVisible({ timeout: 30_000 });

  // a timed note on the video → revision → done again
  await page.evaluate(() => { const v = document.querySelector("video"); if (v) v.currentTime = 3; });
  await page.getByTestId("note-input").fill("make the cat bigger here");
  await page.getByRole("button", { name: /Add note/ }).click();
  await page.getByRole("button", { name: /Send 1 note/ }).click();
  await expect.poll(async () => (await snap(id)).job.stage, { timeout: 60_000 }).not.toBe("done");
  await until(id, ["done", "needs_input"], 10 * 60_000);
  await page.getByRole("tab", { name: /^Log/ }).click();
  await expect(page.locator(".logview")).toBeVisible();
  expect(errors).toEqual([]);
});
