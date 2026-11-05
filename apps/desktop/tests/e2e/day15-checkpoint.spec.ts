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
 * Week 3 Day 15 - the integration checkpoint. The whole AVOS-18 s6.3
 * pipeline, driven live through the real UI, no manual DB/Temporal
 * intervention:
 *
 *   1. create project (topic + duration + aspect ratio)
 *   2. Generate -> Director researches + writes a script (mock LLM)
 *   3. human approves the script via the UI
 *   4. TTS + Whisper + semantic beats -> real audio + timing
 *   5. ShotSpecs per beat, continuity-checked against the WorldState
 *   6. Blender stage (mock) - physics-before-pixels enforced by the Gateway
 *   7. Prompt Compiler + idempotent generation -> a video asset per shot
 *   8. QA Committee evaluates; one shot is forced to FAIL on purpose and
 *      the repair ladder is driven Micro -> Macro -> Human across 3
 *      forced failures, escalating correctly on the 3rd
 *   9. Storyboard, GenerationMonitor, Agent Chat and QADashboard all
 *      reflect every step live over SSE - no page reload anywhere below
 *  10. a second, passing shot is approved at the stubbed final gate
 *
 * "Force a deliberate QA FAIL" is done through ?force_fail= on the real
 * run_qa_committee endpoint (see agentic_core/pipelines/qa/committee.py
 * and RUNBOOK.md's Day 15 section for why: the mock Video generator and
 * the geometry QA dimension agree by construction, so there's no
 * naturally-occurring FAIL to drive the ladder with in a live demo).
 * That override is itself real Gateway traffic - audited, SSE'd, and
 * visible in the UI as a "forced" badge - not a DB backdoor.
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

async function createProject(page: Page, topic: string, durationSeconds: string) {
  await page.goto("/facts");
  await page.getByRole("button", { name: "New Project" }).first().click();
  await page.getByLabel("Topic").fill(topic);
  await page.getByLabel("Duration (sec)").fill(durationSeconds);
  // No per-shot clips: keeps this spec offline/deterministic (mock
  // images); final-video.spec.ts covers the video providers.
  await page.locator("#image-provider").selectOption("");   // deterministic placeholder pictures (the QA checks agree by construction)
  await page.locator("#video-provider").selectOption("");
  await page.getByRole("button", { name: "Create Project" }).click();
  await expect(page).toHaveURL(/\/project\/[0-9a-f-]{36}$/, { timeout: 30_000 });
  return page.url().split("/").pop()!;
}

test("Day 15 integration checkpoint: script -> audio -> shots -> physics -> generation -> forced QA fail -> repair ladder escalation -> approve", async ({
  page,
}) => {
  test.setTimeout(300_000);
  const errors = trackErrors(page);
  const topic = `Day 15 checkpoint ${Date.now()}`;

  // Steps 1-4: create, generate, approve script, real audio + timing.
  const projectId = await createProject(page, topic, "40"); // longer duration -> multiple beats/shots
  await page.getByTestId("generate-button").click();
  const review = page.getByRole("link", { name: /Review in Studio/ });
  await expect(review).toBeVisible({ timeout: 30_000 });
  await review.click();
  await page.getByTestId("script-approval").getByRole("button", { name: "Approve" }).click();
  await expect(page.getByTestId("timeline")).toBeVisible({ timeout: 180_000 });

  // Step 5-6: ShotSpecs per beat, continuity-checked, Blender stage run
  // automatically by the Director's own pipeline - BLENDER_READY, no
  // pixels yet (physics-before-pixels).
  const cards = page.getByTestId("shot-card");
  await expect(cards.first()).toBeVisible({ timeout: 30_000 });
  const shotCount = await cards.count();
  expect(shotCount).toBeGreaterThanOrEqual(2); // need a "fails" shot and a "passes" shot
  for (let i = 0; i < shotCount; i++) {
    await expect(cards.nth(i)).toHaveAttribute("data-status", /BLENDER_READY|GENERATING|QA_PENDING/);
  }

  // Step 7: Prompt Compiler + idempotent generation - one candidate set
  // per shot, live via SSE (VIDEO_GENERATED), no reload.
  const monitor = page.getByTestId("generation-monitor");
  const rows = monitor.getByTestId("generation-row");
  await expect(rows).toHaveCount(shotCount);
  for (let i = 0; i < shotCount; i++) {
    // Generated by the pipeline's visuals stage itself (no clicks).
    await expect(rows.nth(i)).toHaveAttribute("data-shot-status", "QA_PENDING", { timeout: 120_000 });
  }

  // Step 8: shot A is deliberately, repeatedly forced to FAIL through
  // the QADashboard's "Force fail (test)" toggle, driving the repair
  // ladder Micro -> Macro -> Human across exactly 3 forced failures.
  await cards.first().click();
  const dashboard = page.getByTestId("qa-dashboard");
  await expect(dashboard).toBeVisible();

  await dashboard.getByTestId("force-fail-toggle").check();

  // Attempt 1: forced FAIL -> MICRO repair.
  await dashboard.getByTestId("run-qa").click();
  await expect(dashboard.getByTestId("qa-verdict")).toHaveAttribute("data-verdict", "FAIL", { timeout: 15_000 });
  await expect(dashboard.getByTestId("qa-forced-badge")).toBeVisible();
  await dashboard.getByTestId("repair-shot").click();
  await expect(dashboard.getByTestId("repair-rung")).toHaveAttribute("data-rung", "MICRO", { timeout: 15_000 });

  // Attempt 2: force it to fail again (the repaired candidate would
  // otherwise pass by construction) -> MACRO repair.
  await dashboard.getByTestId("run-qa").click();
  await expect(dashboard.getByTestId("qa-verdict")).toHaveAttribute("data-verdict", "FAIL", { timeout: 15_000 });
  await dashboard.getByTestId("repair-shot").click();
  await expect(dashboard.getByTestId("repair-rung")).toHaveAttribute("data-rung", "MACRO", { timeout: 15_000 });

  // Attempt 3: forced FAIL a third time -> escalates to HUMAN_REQUIRED,
  // no further "Repair" affordance offered.
  await dashboard.getByTestId("run-qa").click();
  await expect(dashboard.getByTestId("qa-verdict")).toHaveAttribute("data-verdict", "FAIL", { timeout: 15_000 });
  await dashboard.getByTestId("repair-shot").click();
  await expect(dashboard.getByTestId("repair-rung")).toHaveAttribute("data-rung", "HUMAN_REQUIRED", {
    timeout: 15_000,
  });
  await expect(dashboard.getByTestId("repair-shot")).toHaveCount(0);
  await expect(dashboard).toContainText("Escalated to human review");
  // A shot stuck at HUMAN_REQUIRED has no passing QA result, so it can't
  // be approved at the final gate.
  await expect(dashboard.getByTestId("approval-panel")).toHaveCount(0);

  // Step 9 (agent chat/trace): every forced QA + repair dispatch is
  // audited and shows up in the live decision trace, not just the DB.
  const traceId = page.url().split("/").pop();
  const trace = (await (await page.request.get(`${API_URL}/agents/trace?project_id=${traceId}`)).json()) as { tool_name: string }[];
  expect(trace.map((t) => t.tool_name)).toEqual(expect.arrayContaining(["run_qa_committee", "repair_shot"]));

  // Step 10: shot B (a different shot, untouched by the forced failures
  // above) genuinely passes QA and is approved at the stubbed final
  // gate - live, no reload.
  await cards.nth(1).click();
  await expect(dashboard.getByTestId("force-fail-toggle")).not.toBeChecked(); // fresh per-shot state
  await dashboard.getByTestId("run-qa").click();
  await expect(dashboard.getByTestId("qa-verdict")).toHaveAttribute("data-verdict", "PASS", { timeout: 15_000 });
  await expect(dashboard.getByTestId("qa-forced-badge")).toHaveCount(0);
  await expect(dashboard.getByTestId("repair-panel")).toHaveCount(0);

  await dashboard.getByTestId("approve-shot").click();
  await expect(dashboard.getByTestId("approval-panel")).toContainText("Approved at the final gate.", {
    timeout: 15_000,
  });
  await expect(cards.nth(1)).toHaveAttribute("data-status", "APPROVED", { timeout: 15_000 });

  // Independent confirmation straight from the API: the ladder's escalation
  // and the approval both really persisted, not just in the UI's cache.
  const shots = await (await page.request.get(`${API_URL}/projects/${projectId}/shots`)).json();
  expect(shots[1].status).toBe("APPROVED");
  const qaStateA = await (await page.request.get(`${API_URL}/shots/${shots[0].id}/qa`)).json();
  expect(qaStateA.repairs.map((r: { rung: string }) => r.rung)).toEqual(["MICRO", "MACRO", "HUMAN_REQUIRED"]);

  expect(errors).toEqual([]);
});
