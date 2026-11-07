import { api } from "./core";
import type { ContinuityReport, RegenStatus, Shot, ShotDetail, ShotEdit, WorldStateResponse } from "@/types";

export const shotsApi = {
  listByProject: (projectId: string) => api.get<Shot[]>(`/projects/${projectId}/shots`),
  /** Director: one ShotSpec per semantic beat (409 until audio exists). */
  plan: (projectId: string) => api.post<Shot[]>(`/projects/${projectId}/shots/plan`),
  getById: (shotId: string) => api.get<ShotDetail>(`/shots/${shotId}`),
  validate: (shotId: string) => api.post<ContinuityReport>(`/shots/${shotId}/validate`),
  worldState: (projectId: string) => api.get<WorldStateResponse>(`/projects/${projectId}/world-state`),
  /** Video agent: 3 candidates from the shot's current physics proxy
   * (409 until the Blender stage has run). Idempotent - safe to retry. */
  generate: (shotId: string) => api.post<ShotDetail>(`/shots/${shotId}/generate`),
  /** The stubbed final gate (Week 3 Day 15): 409 unless the shot's
   * latest QA result is PASS. */
  approve: (shotId: string) => api.post<ShotDetail>(`/shots/${shotId}/approve`),
  /** Studio: save edits (or a new take) as a new version and regenerate this shot + the final video. */
  edit: (shotId: string, edit: ShotEdit) =>
    api.post<{ shot_id: string; version: number; regen: RegenStatus }>(`/shots/${shotId}/edit`, edit),
  regenStatus: (shotId: string) => api.get<RegenStatus>(`/shots/${shotId}/regenerate`),
};
