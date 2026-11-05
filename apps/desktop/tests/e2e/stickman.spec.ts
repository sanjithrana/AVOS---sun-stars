import { expect, test } from "@playwright/test";

/** Stickman Studio with the studio service mocked: eight ideas → pick one → approve the reference sheets → the finished video. */
const TOPIC = (i: number) => ({ title: `Event ${i}`, date_place: `18${i}0, Somewhere`, premise: "A thing happened.", opening_visual: "a stickman stares", conflict: "x vs y", ending: "it ended", duration_s: 60, clips: 6, difficulty: "easy" });
const STAGES = ["topics", "brief", "story", "roster", "clips", "refs", "scenes", "animate", "voice", "finish"].map((id) => ({ id, label: id }));
const BASE = {
  id: "h1", title: "Event 2", event: "Event 2", aspect: "9:16", status: "waiting", stage: "topics", error: null, auto: false, clip_count: 6, seconds: 60, project: null, brief: null, story: null,
  roster: null, clips: [], assets: {}, log: [], busy: false, stages: STAGES, updatedAt: "1", topics: { topics: [0, 1, 2, 3, 4, 5, 6, 7].map(TOPIC), recommended: 2, why: "visual" },
};
const FULL = {
  ...BASE, stage: "refs", topics: null, project: { title: "Event 2", date_place: "1802, Somewhere", premise: "" },
  brief: { event: "Event 2", date: "1802", location: "Somewhere", people: [], cause: "c", turning_point: "t", outcome: "o", facts: [{ claim: "It happened in 1802.", confidence: "well-established" }], disputed: [], sources_to_check: ["a national archive"], dramatization_notes: [], verification: "pending" },
  story: { title: "Event 2", hook: "", clips: [{ n: 1, t0: 0, t1: 10, purpose: "hook", narration: "A stickman stares at the river.", main_action: "stares" }] },
  roster: [{ id: "CHAR_01", name: "Ada", role: "lead", age_presentation: "adult", head_shape: "round", height_heads: 5, proportions: "slim", eyes: "dots", brows: "b", mouth: "m", hair_or_headwear: "red hat", clothing: "blue coat", footwear: "boots", accents: [{ name: "blue", hex: "#2a5db0" }], signature_prop: "lantern", distinguishing_feature: "notch", planned_damage: "none" }],
  clips: [{ n: 1, t0: 0, t1: 10, location: "a river street", time_of_day: "dusk", chars: [], opening_setup: "o", beats: { hook: "h", main: "m", reaction: "r", outcome: "o" }, camera_move: "static", sfx: [], music: "", transition: "match", transition_note: "", outgoing: { summary: "ends" }, scene_prompt: "SCENE PROMPT TEXT", animation_prompt: "ANIM PROMPT TEXT", words: { scene: 150, animation: 200 }, narration_warning: "" }],
  continuity: { issues: [] }, consistency: "CHARACTER CONSISTENCY AGENT INSTRUCTIONS ...",
};

test("Stickman: pick one of eight ideas, approve the sheets, get the video and the package", async ({ page }) => {
  let project: Record<string, unknown> = BASE;
  await page.route("**/studio-api/stickman**", (route) => {
    const path = new URL(route.request().url()).pathname.replace("/studio-api/stickman", ""), m = route.request().method();
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (path === "" && m === "GET") return json([]);
    if (path === "" && m === "POST") { expect(route.request().postDataJSON()).toMatchObject({ aspect: "9:16", auto: false }); return json(project); }
    if (path === "/h1/pick") { expect(route.request().postDataJSON()).toEqual({ index: 3 }); project = FULL; return json(project); }
    if (path === "/h1/approve") { project = { ...FULL, status: "done", stage: "finish", final: "final.mp4", finalSeconds: 60 }; return json(project); }
    if (path === "/h1") return json(project);
    return json({ error: "not mocked " + path }, 404);
  });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/stickman");
  await page.getByTestId("stickman-create").click();
  await expect(page).toHaveURL(/\/stickman\/h1$/);
  await expect(page.getByTestId("stickman-topics")).toContainText("Event 2");
  await expect(page.getByTestId("stickman-topics")).toContainText("RECOMMENDED");
  await page.getByTestId("pick-3").click();
  await expect(page.getByTestId("verification-banner")).toContainText("Verification pending");
  await expect(page.getByTestId("clip-1")).toContainText("C01");
  await page.getByText("Scene-image prompt").click();
  await expect(page.getByText("SCENE PROMPT TEXT")).toBeVisible();
  await page.getByTestId("stickman-approve").click();
  await expect(page.getByTestId("stickman-final")).toBeVisible();
  await expect(page.getByRole("link", { name: /written package/ })).toBeVisible();
  expect(errors).toEqual([]);
});
