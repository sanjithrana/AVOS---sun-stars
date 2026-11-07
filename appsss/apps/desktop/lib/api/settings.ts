import { api } from "./core";
import type { AppSettings, CustomModelDef } from "@/types";

/** Settings shared by Explainer and Animations: API keys, GPU server, models you add, ComfyUI workflows. */
export const settingsApi = {
  get: () => api.get<AppSettings>("/settings"),
  setKeys: (keys: Record<string, string | null>) => api.put<AppSettings>("/settings/keys", keys),
  setGpu: (body: { comfyui_url?: string; model_backend?: string }) => api.put<AppSettings>("/settings/gpu", body),
  testGpu: () => api.post<{ ok: boolean; detail: string }>("/settings/gpu/test"),
  saveModel: (m: Omit<Partial<CustomModelDef>, "inputs"> & { inputs?: unknown }) => api.post<AppSettings>("/settings/models", m),
  deleteModel: (id: string) => api.delete<AppSettings>(`/settings/models/${encodeURIComponent(id)}`),
  testModel: (id: string) => api.post<{ ok: boolean; detail: string }>(`/settings/models/${encodeURIComponent(id)}/test`),
  uploadWorkflow: (id: string, json: string) => api.put<AppSettings>(`/settings/models/${encodeURIComponent(id)}/workflow`, json),
  retryProvider: (p: string) => api.post<{ ok: boolean }>(`/settings/providers/${encodeURIComponent(p)}/retry`),
  deleteWorkflow: (id: string) => api.delete<AppSettings>(`/settings/models/${encodeURIComponent(id)}/workflow`),
};
