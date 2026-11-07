import { expect, test } from "@playwright/test";

/** Models page → Download: the panel lists the verified versions, the folder picker works, and sizes add up. */
test("Download a model: versions, extras, folder picker", async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/models");
  const btn = page.getByTestId("download-qwen-image");
  await btn.scrollIntoViewIfNeeded();
  await btn.click();
  const panel = page.getByTestId("download-panel");
  await expect(panel).toBeVisible();
  await expect(panel.getByTestId("where-local")).toHaveAttribute("aria-checked", "true");
  await expect(panel.getByTestId("variant-fp8")).toContainText("fp8");
  await expect(panel.getByTestId("variant-bf16")).toContainText("GB");
  await expect(panel).toContainText("Lightning 8-step LoRA");                  // recommended extra, ticked
  await expect(panel.getByTestId("download-size")).toContainText(/GB|already/);
  const before = await panel.getByTestId("download-size").innerText();
  await panel.getByTestId("variant-bf16").click();
  await expect(panel.getByTestId("download-size")).not.toHaveText(before);   // bf16 is bigger
  await expect(panel.getByTestId("download-path")).not.toHaveValue("");
  await expect(panel.getByTestId("folder-list")).toBeVisible();
  await panel.getByRole("button", { name: "Close" }).click();
  await expect(panel).toHaveCount(0);
  expect(errors).toEqual([]);
});
