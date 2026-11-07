import { expect, test } from "@playwright/test";

/**
 * GPU page (Model Fabric) against the real API: add / test / remove a GPU worker, save generation limits, ask the
 * router. With E2E_GPU_WORKER_URL pointing at a running GPU worker (e.g. `WORKER_MOCK=1 WORKER_ADAPTERS=mock
 * python -m worker` in apps/gpu_worker) it also checks the worker reports its GPU and the router picks it.
 */
const WORKER_URL = process.env.E2E_GPU_WORKER_URL;

test.afterAll(async ({ request, baseURL }) => {
  const api = `${new URL(baseURL!).protocol}//${new URL(baseURL!).hostname}:8001/api/v1`;
  for (const id of ["e2e-offline", "e2e-live"]) await request.delete(`${api}/gpu/workers/${id}`);
  await request.put(`${api}/gpu/limits`, { data: { preference: "balanced", max_cost_per_shot: null, auto_qa: true, review_shots: false } });
});

test("GPU page: workers, limits and the router", async ({ page, request, baseURL }) => {
  const api = `${new URL(baseURL!).protocol}//${new URL(baseURL!).hostname}:8001/api/v1`;
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("/explainer");
  await page.getByRole("link", { name: /GPU/ }).first().click();
  await expect(page).toHaveURL(/\/gpu$/);
  await expect(page.getByRole("heading", { name: "GPU", exact: true })).toBeVisible();
  await expect(page.getByTestId("gpu-stats")).toContainText("Workers online");

  // a worker that isn't running: added, explained, removed
  await request.post(`${api}/gpu/workers`, { data: { id: "e2e-offline", name: "E2E offline", url: "http://127.0.0.1:9" } });
  await page.reload();
  const off = page.getByTestId("worker-e2e-offline");
  await expect(off.getByTestId("worker-state")).toHaveText("offline");
  await expect(off.getByTestId("worker-error")).toContainText("Can't reach");
  page.once("dialog", (d) => d.accept());
  await off.getByRole("button", { name: "Remove E2E offline" }).click();
  await expect(page.getByTestId("worker-e2e-offline")).toHaveCount(0);

  // the add form validates the address
  const add = page.getByTestId("add-worker");
  await add.getByTestId("worker-url").fill("ftp://nope");
  await add.getByTestId("worker-add").click();
  await expect(add).toContainText("must look like");

  // limits: preference + max cost per shot
  const limits = page.getByTestId("gpu-limits");
  await limits.getByTestId("pref-cost").click();
  await limits.getByTestId("limit-cost").fill("0.25");
  await limits.getByTestId("limits-save").click();
  await expect(limits).toContainText("Saved");
  const saved = await (await request.get(`${api}/gpu`)).json();
  expect(saved.limits.preference).toBe("cost");
  expect(saved.limits.max_cost_per_shot).toBe(0.25);
  expect(saved.limits.auto_qa).toBe(true);
  await expect(limits.getByTestId("limit-review")).not.toBeChecked();

  if (WORKER_URL) {
    await request.post(`${api}/gpu/workers`, { data: { id: "e2e-live", name: "E2E live", url: WORKER_URL } });
    await page.reload();
    const live = page.getByTestId("worker-e2e-live");
    await expect(live.getByTestId("worker-state")).toHaveText(/ready|generating|loading/);
    await expect(live).toContainText("NVIDIA");
    await live.getByTestId("worker-test").click();
    await expect(live.getByTestId("worker-msg")).toContainText("can run");
  }

  // ask the router
  await page.getByTestId("route-task").selectOption("video");
  await page.getByTestId("route-run").click();
  const result = page.getByTestId("route-result");
  await expect(result).toBeVisible();
  if (WORKER_URL) await expect(result.locator("tr").nth(1)).toContainText(/GPU|RTX|NVIDIA|E2E live|at home|RunPod/);

  expect(errors).toEqual([]);
});
