import { expect, test } from "@playwright/test";

/**
 * Models page and the open-model pickers in New Project, against the real API (GET /api/v1/models reads
 * agentic_core/models/catalog.json and the server's settings).
 */

test("Models page: every task, the best model first, readiness and licences", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/explainer");
  await page.getByRole("link", { name: /Models/ }).first().click();
  await expect(page).toHaveURL(/\/models$/);
  await expect(page.getByRole("heading", { name: "Models" })).toBeVisible();
  for (const task of ["image", "video", "avatar", "control"]) await expect(page.getByTestId(`task-${task}`)).toBeVisible();
  // best first in each task
  await expect(page.getByTestId("task-image").locator('[data-testid^="model-"]').first()).toHaveAttribute("data-testid", "model-z-image");
  await expect(page.getByTestId("task-video").locator('[data-testid^="model-"]').first()).toHaveAttribute("data-testid", "model-wan-2.2");
  await expect(page.getByTestId("task-avatar").locator('[data-testid^="model-"]').first()).toHaveAttribute("data-testid", "model-longcat-avatar");
  await expect(page.getByTestId("model-z-image")).toContainText("Best");
  // licences: LTX-2.3 has conditions, the rest are open
  await expect(page.getByTestId("license-ltx-2.3")).toContainText("conditions");
  await expect(page.getByTestId("license-wan-2.2")).toContainText("commercial OK");
  // SCAIL-2 only on a GPU server; Vista4D listed for reference
  await expect(page.getByTestId("model-scail-2")).toContainText("Not set up");
  await expect(page.getByTestId("model-vista4d")).toContainText("research code");
  await expect(page.getByTestId("models-settings")).toBeVisible();
  expect(errors).toEqual([]);
});
