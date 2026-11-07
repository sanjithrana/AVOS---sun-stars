import { api } from "./core";
import type { GenerationLimits, GpuJobRow, GpuOverview, GpuWorker, LearnedRow, RoutePlan } from "@/types";

/** GPU compute: your GPU workers, the Model Router, generation limits and every run (api/src/routes/gpu.py). */
export const gpuApi = {
  overview: () => api.get<GpuOverview>("/gpu"),
  workers: (force = false) => api.get<GpuWorker[]>(`/gpu/workers${force ? "?force=true" : ""}`),
  saveWorker: (w: { id?: string; name: string; url: string; cost_per_hour?: number | string | null; enabled?: boolean }) =>
    api.post<GpuWorker[]>("/gpu/workers", w),
  deleteWorker: (id: string) => api.delete<GpuWorker[]>(`/gpu/workers/${encodeURIComponent(id)}`),
  testWorker: (id: string) => api.post<GpuWorker>(`/gpu/workers/${encodeURIComponent(id)}/test`),
  loadModel: (id: string, body: { model: string; adapter: string; precision?: string }) =>
    api.post<unknown>(`/gpu/workers/${encodeURIComponent(id)}/load`, body),
  unloadModel: (id: string, body: { model: string; adapter: string }) =>
    api.post<unknown>(`/gpu/workers/${encodeURIComponent(id)}/unload`, body),
  pushWorkflows: (id: string) =>
    api.post<{ sent: string[]; failed: string[]; dir: string }>(`/gpu/workers/${encodeURIComponent(id)}/workflows`),
  jobs: (projectId?: string, limit = 50) =>
    api.get<GpuJobRow[]>(`/gpu/jobs?limit=${limit}${projectId ? `&project_id=${encodeURIComponent(projectId)}` : ""}`),
  learned: () => api.get<{ min_runs: number; rows: LearnedRow[] }>("/gpu/performance"),
  setLimits: (l: Partial<GenerationLimits>) => api.put<GenerationLimits>("/gpu/limits", l),
  route: (body: {
    task: "image" | "video" | "avatar";
    seconds?: number;
    prompt?: string;
    has_audio?: boolean;
    continuity?: boolean;
    model?: string;
    limits?: Partial<GenerationLimits>;
  }) => api.post<RoutePlan>("/gpu/route", body),
  setProjectLimits: (projectId: string, l: Partial<GenerationLimits> | null) =>
    api.put<{ project_id: string; generation_policy: Partial<GenerationLimits> | null; effective: GenerationLimits }>(
      `/gpu/projects/${encodeURIComponent(projectId)}/limits`, l),
};
