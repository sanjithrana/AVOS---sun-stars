import { expect, test } from "@playwright/test";

/**
 * Series, the way a person drives it: create a series → approve each character (sheet + voice) → AI outline in parts
 * → approve → edit a line of part 1's script → approve and render → watch → redo one shot → approve → part 2's
 * script is written. Needs the Animation Studio and a GPU worker (E2E_GPU_WORKER_URL; the mock backend is enough:
 * `WORKER_MOCK=1 WORKER_ADAPTERS=mock python -m worker` in apps/gpu_worker), so pictures and voices work offline.
 */
const WORKER_URL = process.env.E2E_GPU_WORKER_URL;
test.skip(!WORKER_URL, "set E2E_GPU_WORKER_URL to a running GPU worker");
test.setTimeout(600_000);

// a small style picture (a 64×36 PNG) to draw the characters in
const STYLE_PNG = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAEAAAAAkCAIAAAC2bqvFAAAACXBIWXMAAAABAAAAAQBPJcTWAAAByUlEQVR4nO2Wu0oDURCG/wdQGwtRIRZeQIugEMUmKSyCjQiidlEECyWgL+AlikS8oE3USiwsLUUQ7O20sFRsFMTSF0jin524ns2ak5uIhIGvmJ2ze3Y+djInWEfmR9KACzI20mkbJR524B4WkM3aqBOBACIFRAAXRGyEwzZKPOxg3SCcq8WCCqjALwqE0EjeE/3kI9FBxgDSOZDjaa/dRTLFBKaGcrwlW8jrZoi0ocFFMma+WOnjaCKPO30uXaFmF8kUCtxspVj9HBAHKPCwMS8CR+fTrHuxFYQBL+0CV8dRVp/swQTAQi92T6VWBrxk0sxbBO5W9lnlcgCEweHZmlTPQPL5QSnfUiao+XXNyWoumJmlIO4PgoSBvFlWzRby7GNslL/TuXcWeF6dIQwk8/WW74bx1uMk61AgBrwkRkjMKxDtxvXJMGFgCvi/vayK2O32wqB3H14yaeaLtZCsjvbiMjVJGJj7SL4eBSptIZk5Qi0tJDNH+NPfgMwcUrsAZw6pXoATk3OT0zNeyRj1C1Q3Rv0CFY9RObbkCCv/IPO3UHUHmb+FyjrITIFi/Ou/EiqgAiqgAiqgAiqgAiqgAiqgAiqgAtUJfALCDDldZvX0fgAAAABJRU5ErkJggg==", "base64");

const api = (baseURL: string) => `${new URL(baseURL).protocol}//${new URL(baseURL).hostname}:8001/api/v1`;

test.beforeAll(async ({ request, baseURL }) => {
  await request.post(`${api(baseURL!)}/gpu/workers`, { data: { id: "e2e-series", name: "E2E series GPU", url: WORKER_URL } });
});
test.afterAll(async ({ request, baseURL }) => {
  await request.delete(`${api(baseURL!)}/gpu/workers/e2e-series`);
});

test("Series: approve characters, then each part", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/animations");
  await page.getByTestId("series-link").click();
  await expect(page).toHaveURL(/\/animations\/series$/, { timeout: 60_000 });

  const form = page.getByTestId("new-series");
  await form.getByTestId("series-title").fill(`E2E Ghar ${Date.now() % 100000}`);
  await form.getByTestId("series-language").selectOption("hi");
  await expect(form).toContainText("Voices: Chatterbox, IndicF5");
  await form.getByTestId("series-premise").fill("A noisy family in a small flat.");
  await form.getByTestId("series-cast").fill("Bunty - a 12-year-old boy, messy hair, green t-shirt\nMummy - his mother, purple saree, round glasses");
  await form.getByTestId("series-plan").fill("0.25");
  await form.getByTestId("series-refs").setInputFiles({ name: "style.png", mimeType: "image/png", buffer: STYLE_PNG });
  await expect(form.getByAltText("style 1")).toBeVisible();
  await form.getByTestId("series-crew").selectOption("builtin");
  await form.getByTestId("series-create").click();
  await expect(page).toHaveURL(/\/animations\/series\/[\w-]+$/, { timeout: 60_000 });   // the dev server may compile the page first

  // each character: a sheet and a voice, then you approve it
  for (const id of ["bunty", "mummy"]) {
    const card = page.getByTestId(`character-${id}`);
    await expect(card.getByTestId("approve-character")).toBeVisible({ timeout: 180_000 });
    await expect(card.getByTestId("sheet")).toBeVisible();
    await expect(card.getByTestId("voice")).toBeVisible();
    await expect(card).toContainText("look: Qwen-Image-Edit");
  }
  await page.getByTestId("character-bunty").getByTestId("approve-character").click();
  await expect(page.getByTestId("character-bunty").getByTestId("status-chip")).toHaveText("Approved");
  await page.getByTestId("character-mummy").getByTestId("approve-character").click();
  await expect(page.getByTestId("character-mummy").getByTestId("status-chip")).toHaveText("Approved");

  // an episode, outlined in parts
  const ne = page.getByTestId("new-episode");
  await ne.getByTestId("episode-brief").fill("Bunty breaks the TV remote before the cricket final");
  await ne.getByTestId("episode-minutes").fill("0.5");
  await ne.getByTestId("episode-start").click();
  const outline = page.getByTestId("outline-review");
  await expect(outline).toBeVisible({ timeout: 60_000 });
  await expect(outline).toContainText("Part 2");
  await outline.getByTestId("approve-outline").click();

  // part 1: edit a line, approve, render
  const p1 = page.getByTestId("part-1");
  const review = p1.getByTestId("script-review");
  await expect(review).toBeVisible({ timeout: 60_000 });
  await review.getByTestId("line-text").first().fill("रिमोट कहाँ है?");
  await review.getByTestId("save-script").click();
  await expect(review.getByTestId("save-script")).toHaveCount(0);
  await review.getByTestId("approve-script").click();
  // the storyboard: frames first, nothing moves until it's approved
  const board = p1.getByTestId("storyboard");
  await expect(board).toBeVisible({ timeout: 300_000 });
  await expect(board.getByTestId("storyboard-collage")).toBeVisible();
  await board.getByTestId("approve-board").click();
  await expect(p1.getByTestId("part-video")).toBeVisible({ timeout: 300_000 });
  await expect(p1.getByTestId("shots")).toContainText("रिमोट कहाँ है?");

  // redo one shot's picture
  const tiles = p1.getByTestId("shots").locator("[data-testid^='shot-']");
  const first = tiles.first();
  await first.locator("button").first().click();
  await p1.getByTestId("redo-shot-note").fill("make the room darker");
  await p1.getByTestId("redo-shots").click();
  await expect(p1.getByTestId("part-status")).toHaveText(/Queued|Rendering/, { timeout: 30_000 });
  await expect(p1.getByTestId("approve-part")).toBeVisible({ timeout: 300_000 });
  await expect(first).toContainText("make the room darker");

  // Director: open the shot, change the camera move, add a timed action, preview it, save → only this shot is redone
  await first.getByTestId("open-shot").click();
  const tools = page.getByTestId("shot-tools");
  await expect(tools.getByTestId("shot-key")).toBeVisible();
  await tools.getByTestId("open-director").click();
  const dir = page.getByTestId("director");
  await expect(dir.getByTestId("director-canvas").or(dir.getByTestId("director-no-webgl"))).toBeVisible();
  await dir.getByTestId("director-move").selectOption("orbit_right");
  await dir.getByTestId("view-top").click();
  await dir.getByTestId("director-add-key").click();
  await dir.getByTestId("director-key-action").last().fill("jumps with joy");
  await dir.getByTestId("director-play").click();
  await expect(dir.getByTestId("director-scrub")).not.toHaveValue("0", { timeout: 5_000 });
  await dir.getByTestId("director-save").click();
  await expect(dir).toHaveCount(0);
  await expect(p1.getByTestId("part-status")).toHaveText(/Queued|Rendering/, { timeout: 30_000 });
  await expect(p1.getByTestId("approve-part")).toBeVisible({ timeout: 300_000 });
  await first.getByTestId("open-shot").click();
  await tools.getByTestId("shot-prompts").locator("summary").click();
  await expect(tools.getByTestId("shot-prompts")).toContainText("arcs around to the right");
  await expect(tools.getByTestId("shot-prompts")).toContainText("jumps with joy");

  // Modify shot: change one thing, keep the rest
  await tools.getByTestId("modify-instruction").fill("make the sofa red");
  await tools.getByTestId("modify-go").click();
  await expect(page.getByTestId("shot-tools")).toHaveCount(0);
  await expect(p1.getByTestId("part-status")).toHaveText(/Queued|Rendering/, { timeout: 30_000 });
  await expect(p1.getByTestId("approve-part")).toBeVisible({ timeout: 300_000 });
  await expect(first).toContainText("edited: make the sofa red");

  // the Design DNA and the agents' skills
  await page.getByTestId("dna-panel").locator("button").first().click();
  await expect(page.getByTestId("skills")).toContainText("avos-scene-director");
  await page.getByTestId("dna-line").fill("thick wobbly outlines");
  await page.getByTestId("dna-save").click();
  await page.getByTestId("dna-panel").locator("button").first().click();
  await expect(page.getByTestId("dna-panel")).toContainText("thick wobbly outlines");

  // approve → part 2 is written and waits for you
  await p1.getByTestId("approve-part").click();
  await expect(page.getByTestId("part-2").getByTestId("script-review")).toBeVisible({ timeout: 120_000 });
  await expect(p1.getByTestId("part-status")).toHaveText("Approved");

  expect(errors).toEqual([]);
});
