import { expect, test } from "@playwright/test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

/**
 * Settings page (shared by Explainer and Animations), against the real API.
 * Adds models of its own (ids starting with e2e-) and removes them at the end.
 */

const WORKFLOW = { "1": { class_type: "LoadImage", inputs: { image: "{{IMAGE}}" } }, "2": { class_type: "CLIPTextEncode", inputs: { text: "{{PROMPT}}" } } };

test.afterAll(async ({ request, baseURL }) => {
  const api = `${new URL(baseURL!).protocol}//${new URL(baseURL!).hostname}:8001/api/v1`;
  for (const id of ["e2e-flux", "e2e-wan", "e2e-deepseek"]) await request.delete(`${api}/settings/models/${id}`);
  await request.put(`${api}/settings/keys`, { data: { E2E_DEEPSEEK_KEY: null } });
  await request.put(`${api}/settings/gpu`, { data: { comfyui_url: "" } });
});

test("Settings: keys, GPU server, add models (fal, ComfyUI with workflow upload, text), shared with Animations", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/explainer");
  await page.getByRole("link", { name: /Settings/ }).first().click();
  await expect(page).toHaveURL(/\/settings$/);
  await expect(page.getByRole("heading", { name: "Settings", exact: true })).toBeVisible();

  // API keys: a custom key name
  const keys = page.getByTestId("settings-keys");
  await expect(keys.locator('[data-key="FAL_KEY"]')).toBeVisible();
  await keys.getByLabel("New key name").fill("e2e deepseek key");
  await expect(keys.getByLabel("New key name")).toHaveValue("E2E_DEEPSEEK_KEY");
  await keys.getByLabel("New key value").fill("sk-e2e-123456789");
  await keys.getByRole("button", { name: "Add key" }).click();
  await expect(keys.locator('[data-key="E2E_DEEPSEEK_KEY"]')).toContainText("E2E_DEEPSEEK_KEY");
  await expect(keys.locator('[data-key="E2E_DEEPSEEK_KEY"] input')).toHaveAttribute("placeholder", /6789/);   // masked

  // GPU server
  await page.getByTestId("gpu-url").fill("http://127.0.0.1:9");
  await page.getByTestId("settings-gpu").getByRole("button", { name: "Save" }).click();
  await page.getByTestId("gpu-test").click();
  await expect(page.getByTestId("gpu-msg")).toContainText("Can't reach");

  // add a fal.ai image model
  const add = page.getByTestId("add-model");
  await add.getByTestId("add-name").fill("E2E Flux");
  await add.getByTestId("add-id").fill("e2e-flux");
  await add.getByTestId("add-endpoint").fill("fal-ai/flux-pro/v1.1");
  await expect(add.getByTestId("add-inputs")).toHaveValue(/\{\{prompt\}\}/);
  await add.getByTestId("add-save").click();
  await expect(add.getByTestId("add-msg")).toContainText("Added");
  await expect(page.locator('[data-model="e2e-flux"]')).toContainText("yours");

  // a ComfyUI video model: ready only after its workflow is uploaded
  await add.getByTestId("add-task").selectOption("video");
  await add.getByTestId("add-kind").selectOption("comfyui");
  await add.getByTestId("add-name").fill("E2E Wan LoRA");
  await add.getByTestId("add-id").fill("e2e-wan");
  await add.getByTestId("add-save").click();
  await expect(page.locator('[data-model="e2e-wan"]')).toContainText("Upload its ComfyUI workflow");
  const dir = mkdtempSync(join(tmpdir(), "wf-"));
  writeFileSync(join(dir, "regular.json"), JSON.stringify({ nodes: [], links: [] }));
  writeFileSync(join(dir, "api.json"), JSON.stringify(WORKFLOW));
  await page.getByTestId("wf-file-e2e-wan").setInputFiles(join(dir, "regular.json"));
  await expect(page.getByTestId("wf-msg-e2e-wan")).toContainText("Export (API)");
  await page.getByTestId("wf-file-e2e-wan").setInputFiles(join(dir, "api.json"));
  await expect(page.getByTestId("wf-msg-e2e-wan")).toContainText("Workflow uploaded");
  await expect(page.locator('[data-model="e2e-wan"]')).toContainText("Ready on your GPU server");

  // an OpenAI-compatible text model using the key added above
  await add.getByTestId("add-task").selectOption("llm");
  await add.getByTestId("add-name").fill("E2E DeepSeek");
  await add.getByTestId("add-id").fill("e2e-deepseek");
  await add.getByTestId("add-base").fill("https://api.deepseek.com/v1");
  await add.getByTestId("add-model-name").fill("deepseek-chat");
  await add.getByTestId("add-key").fill("E2E_DEEPSEEK_KEY");
  await add.getByTestId("add-save").click();
  await expect(page.locator('[data-model="e2e-deepseek"]')).toContainText("Ready");

  // Animations: the text model is a crew; the image model is a backdrop choice
  await page.goto("/animations");
  await page.getByTestId("ai-settings-btn").click();
  await expect(page.getByTestId("ai-settings")).toContainText("E2E DeepSeek");
  await expect(page.locator('[data-testid="image-model"] option[value="e2e-flux"]')).toHaveCount(1);
  expect(errors).toEqual([]);
});
