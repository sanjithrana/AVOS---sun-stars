import { expect, test } from "@playwright/test";

/** Explainer Studio, with the studio service mocked: one idea in, the plan to approve, the final video out. */
const SHOT = (i: number, extra: object = {}) => ({
  id: `S0${i}`, index: i, shot_type: i === 3 ? "scientific_cutaway" : "presenter", seconds: 3, narration: `Line ${i}`, action: `Action ${i}`,
  characters: i === 3 ? [] : ["host"], props: ["thing"], camera: { type: "medium", movement: "push_in", lens_mm: 35 }, physics: false,
  visualization: { cross_section: i === 3, force_arrows: i === 3 }, sfx: "", engine: i === 3 ? "blender" : "ai_video", engine_why: "test", status: "pending", version: 1, ...extra,
});
const PROJECT = (over: object = {}) => ({
  id: "x1", brief: "Why can a straw go through a potato?", title: "Straw and potato", seconds: 30, aspect: "9:16", language: "en", crew: "builtin", auto: false, voice: "male",
  status: "waiting", stage: "plan", error: null, assets: {}, log: [{ t: "", kind: "info", text: "Plan ready" }], busy: false, totalSeconds: 9, caps: { ai_video: true, blender: true },
  stages: [["plan", "Script and shot list"], ["design", "Presenter, props and set"], ["board", "Storyboard"], ["shoot", "Voice and shots"], ["finish", "Captions and final video"]].map(([id, label]) => ({ id, label })),
  plan: { title: "Straw and potato", hook: "", music: "", aspect: "9:16", characters: [{ id: "host", name: "Host", look: "friendly" }], props: [{ id: "thing", name: "Potato", look: "brown" }],
    world: { name: "Studio", look: "cyan" }, shots: [SHOT(1), SHOT(2), SHOT(3)] },
  createdAt: "", updatedAt: "1", ...over,
});

test("Explainer: one idea creates a project; the script is approved; the finished video appears", async ({ page }) => {
  let project = PROJECT();
  await page.route("**/studio-api/explainer**", async (route) => {
    const u = new URL(route.request().url()), m = route.request().method(), path = u.pathname.replace("/studio-api/explainer", "");
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: "application/json", body: JSON.stringify(b) });
    if (path === "/capabilities") return json({ ai_video: true, blender: true, voice: true, music: false, hint: null, aspects: ["9:16"], languages: [] });
    if (path === "" && m === "GET") return json([]);
    if (path === "" && m === "POST") { expect(route.request().postDataJSON()).toMatchObject({ brief: "Why can a straw go through a potato?", seconds: 30, aspect: "9:16", auto: false }); return json(project); }
    if (path === "/x1/approve") { project = PROJECT({ status: "done", stage: "finish", final: "final.mp4", finalSeconds: 9 }); return json(project); }
    if (path === "/x1") return json(project);
    return json({ error: "not mocked " + path }, 404);
  });
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/explainer");
  await page.getByTestId("explainer-brief").fill("Why can a straw go through a potato?");
  await page.getByTestId("explainer-create").click();
  await expect(page).toHaveURL(/\/explainer\/x1$/);
  await expect(page.getByTestId("explainer-title")).toHaveText("Straw and potato");
  await expect(page.getByTestId("shot-S01")).toBeVisible();
  await expect(page.getByTestId("shot-S03")).toContainText("3D (Blender)");
  await page.getByTestId("explainer-approve").click();
  await expect(page.getByTestId("explainer-final")).toBeVisible();
  expect(errors).toEqual([]);
});

test("Explainer: an error keeps the work and offers Continue", async ({ page }) => {
  await page.route("**/studio-api/explainer**", (route) => {
    const path = new URL(route.request().url()).pathname.replace("/studio-api/explainer", "");
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(path === "/x1" ? PROJECT({ status: "error", stage: "board", error: "provider down" }) : []) });
  });
  await page.goto("/explainer/x1");
  await expect(page.getByRole("alert")).toContainText("provider down");
  await expect(page.getByRole("button", { name: "Continue" })).toBeVisible();
});
