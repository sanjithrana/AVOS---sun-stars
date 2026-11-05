import { expect, test } from "@playwright/test";

/**
 * Films (prompt → animation), the way a person drives it: paste a timed prompt → check and edit the breakdown →
 * approve → approve each character (one saved to the library) → the storyboard (frames + collage, a camera change on
 * one shot, the compiled prompts, the timeline) → approve → every shot animated → approve → the film and the project
 * files. Needs the Animation Studio and a GPU worker (E2E_GPU_WORKER_URL; the mock backend is enough).
 */
const WORKER_URL = process.env.E2E_GPU_WORKER_URL;
test.skip(!WORKER_URL, "set E2E_GPU_WORKER_URL to a running GPU worker");
test.setTimeout(600_000);

const api = (baseURL: string) => `${new URL(baseURL).protocol}//${new URL(baseURL).hostname}:8001/api/v1`;
const PROMPT = `Create a 7-second cinematic 3D animated comedy, Pixar style.

SETTING
A lush forest road after rain, puddles, golden sunlight.

CHARACTERS
Wolf: a cheerful grey wolf in a yellow tropical shirt, driving a small red convertible.
Rabbit: a tiny white rabbit in blue overalls.

0–3 SECONDS
Wide tracking shot: the wolf sings while driving and splashes the rabbit. Wolf sings "La la la!"

3–5 SECONDS
Close-up, static: the rabbit wipes water from his face. Rabbit says "Oh, it's on."

5–7 SECONDS
Low angle, slow push-in: the rabbit's giant truck rolls through a puddle and drenches the wolf. Final plop.

AUDIO
forest ambience, playful orchestral music, splashes, a final plop`;

test.beforeAll(async ({ request, baseURL }) => {
  await request.post(`${api(baseURL!)}/gpu/workers`, { data: { id: "e2e-films", name: "E2E films GPU", url: WORKER_URL } });
});
test.afterAll(async ({ request, baseURL }) => {
  await request.delete(`${api(baseURL!)}/gpu/workers/e2e-films`);
});

test("Films: prompt → breakdown → characters → storyboard → film → project files", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/animations");
  await page.getByTestId("films-link").click();
  await expect(page).toHaveURL(/\/animations\/films$/, { timeout: 60_000 });
  const form = page.getByTestId("new-film");
  await form.getByTestId("film-prompt").fill(PROMPT);
  await expect(form).toContainText("3 timed sections found");
  await form.getByTestId("film-title").fill(`E2E Puddle ${Date.now() % 100000}`);
  await form.getByTestId("film-crew").selectOption("builtin");
  await form.getByTestId("film-create").click();
  await expect(page).toHaveURL(/\/animations\/films\/[\w-]+$/, { timeout: 60_000 });

  // 1. the breakdown: detected, editable, approved
  const bd = page.getByTestId("breakdown");
  await expect(bd.getByTestId("bd-shots")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("stage-breakdown")).toHaveAttribute("data-state", "yours");
  await expect(bd).toContainText("3 timed shots · 7s");
  await expect(bd).toContainText("2 characters");
  await bd.getByTestId("bd-shot-1").getByTestId("bd-camera").selectOption("orbit_left");
  await bd.getByTestId("save-breakdown").click();
  await expect(bd.getByTestId("save-breakdown")).toHaveCount(0);
  await bd.getByTestId("approve-breakdown").click();

  // 2. characters & world: approve each, save one to the library
  for (const id of ["wolf", "rabbit"]) {
    const card = page.getByTestId(`character-${id}`);
    await expect(card.getByTestId("approve-character")).toBeVisible({ timeout: 180_000 });
    await card.getByTestId("approve-character").click();
    await expect(card.getByTestId("status-chip")).toHaveText("Approved");
  }
  await page.getByTestId("character-wolf").getByTestId("save-library").click();
  await expect(page.getByTestId("character-wolf").getByTestId("save-library")).toHaveText(/Update in library/);
  await page.getByTestId("make-storyboard").click();

  // 3-5. the storyboard: collage + frames, a camera change on one shot, the compiled prompts, the timeline
  const board = page.getByTestId("storyboard");
  await expect(board.getByTestId("storyboard-collage")).toBeVisible({ timeout: 300_000 });
  await expect(board.getByTestId("frames").locator("[data-testid^='frame-']")).toHaveCount(3);
  await expect(board.getByTestId("frames")).toContainText("orbit left");
  await board.getByTestId("frames").locator("[data-testid^='frame-'] button").first().click();
  await board.getByTestId("cam-move").selectOption("handheld");
  await board.getByTestId("cam-apply").click();
  await expect(page.getByTestId("storyboard").getByTestId("frames")).toContainText("handheld", { timeout: 120_000 });
  await page.getByTestId("storyboard").getByTestId("prompts").locator("summary").click();
  await expect(page.getByTestId("storyboard").getByTestId("prompts")).toContainText("exact visual reference");
  await expect(page.getByTestId("timeline")).toBeVisible();
  await expect(page.getByTestId("timeline")).toContainText("Sound FX");
  await page.getByTestId("storyboard").getByTestId("approve-board").click();

  // 6-7. every shot animated → approve → the film and the project files
  await expect(page.getByTestId("part-video")).toBeVisible({ timeout: 300_000 });
  await page.getByTestId("approve-part").click();
  await expect(page.getByTestId("film-video")).toBeVisible({ timeout: 120_000 });
  await expect(page.getByTestId("stage-edit")).toHaveAttribute("data-state", "done");
  const href = await page.getByTestId("export-project").getAttribute("href");
  const zip = await page.request.get(href!);
  expect(zip.status()).toBe(200);
  expect((await zip.body()).subarray(0, 2).toString()).toBe("PK");

  // the library shows the saved wolf on the next film
  await page.goto("/animations/films");
  await expect(page.getByTestId("library-picker")).toContainText("Wolf", { timeout: 60_000 });
  expect(errors).toEqual([]);
});
