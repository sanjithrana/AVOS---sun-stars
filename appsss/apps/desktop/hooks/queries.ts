"use client";

import { useQuery } from "@tanstack/react-query";
import { directorApi, gpuApi, jobsApi, modelsApi, projectsApi, qaApi, shotsApi } from "@/lib/api";
import { ACTIVE_PROJECT_STATUSES, TERMINAL_JOB_STATUSES } from "@/types";

// Query keys are shared with useLiveProject so SSE events can
// invalidate / update exactly the right cache entries.
export const queryKeys = {
  projects: ["projects"] as const,
  project: (id: string) => ["project", id] as const,
  jobs: (projectId: string) => ["jobs", projectId] as const,
  job: (jobId: string) => ["job", jobId] as const,
  gates: (projectId: string) => ["gates", projectId] as const,
  trace: (projectId: string) => ["trace", projectId] as const,
  shots: (projectId: string) => ["shots", projectId] as const,
  shot: (shotId: string) => ["shot", shotId] as const,
  qa: (shotId: string) => ["qa", shotId] as const,
  models: ["models"] as const,
  gpu: ["gpu"] as const,
  gpuJobs: (projectId?: string) => ["gpu-jobs", projectId ?? "all"] as const,
};

/** The AVOS model catalog with readiness (Models page, New Project pickers). */
export function useModels() {
  return useQuery({ queryKey: queryKeys.models, queryFn: modelsApi.list, staleTime: 30_000, retry: false });
}

/** GPU page: workers' live status (VRAM, loaded models, queue), limits, recent runs. Workers report by polling. */
export function useGpu() {
  return useQuery({ queryKey: queryKeys.gpu, queryFn: gpuApi.overview, refetchInterval: 3_000, retry: false });
}

/** Generation runs (one per picture / clip), optionally for one project; GPU_JOB_* events refresh it live. */
export function useGpuJobs(projectId?: string, refetchMs: number | false = 5_000) {
  return useQuery({ queryKey: queryKeys.gpuJobs(projectId), queryFn: () => gpuApi.jobs(projectId, 100),
                    refetchInterval: refetchMs, retry: false });
}

// Safety net only: live updates arrive over SSE. If the SSE connection
// drops, active work still refreshes every few seconds.
const ACTIVE_REFRESH_MS = 5_000;

export function useProjects() {
  return useQuery({ queryKey: queryKeys.projects, queryFn: projectsApi.getAll });
}

export function useProject(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.project(projectId ?? ""),
    queryFn: () => projectsApi.getById(projectId as string),
    enabled: Boolean(projectId),
    refetchInterval: (query) =>
      ACTIVE_PROJECT_STATUSES.includes(query.state.data?.status ?? "") ? ACTIVE_REFRESH_MS : false,
  });
}

export function useProjectJobs(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.jobs(projectId ?? ""),
    queryFn: () => projectsApi.getJobs(projectId as string),
    enabled: Boolean(projectId),
    refetchInterval: (query) => {
      const latest = query.state.data?.[0];
      return latest && !TERMINAL_JOB_STATUSES.includes(latest.status) ? ACTIVE_REFRESH_MS : false;
    },
  });
}

export function useJob(jobId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.job(jobId ?? ""),
    queryFn: () => jobsApi.getById(jobId as string),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status && TERMINAL_JOB_STATUSES.includes(status) ? false : ACTIVE_REFRESH_MS;
    },
  });
}

export function useProjectGates(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.gates(projectId ?? ""),
    queryFn: () => projectsApi.getGates(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useTrace(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.trace(projectId ?? ""),
    queryFn: () => directorApi.getTrace(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useProjectShots(projectId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.shots(projectId ?? ""),
    queryFn: () => shotsApi.listByProject(projectId as string),
    enabled: Boolean(projectId),
  });
}

export function useShot(shotId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.shot(shotId ?? ""),
    queryFn: () => shotsApi.getById(shotId as string),
    enabled: Boolean(shotId),
  });
}

export function useShotQA(shotId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.qa(shotId ?? ""),
    queryFn: () => qaApi.getShotState(shotId as string),
    enabled: Boolean(shotId),
  });
}
