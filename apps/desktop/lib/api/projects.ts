import { api } from "./core";
import type { GenerateResponse, HumanGate, Job, Project, ProjectCreate } from "@/types";

export const projectsApi = {
  getAll: () => api.get<Project[]>("/projects"),
  getById: (id: string) => api.get<Project>(`/projects/${id}`),
  create: (data: ProjectCreate) => api.post<Project>("/projects", data),

  /** Starts the production workflow (research -> script -> approval -> audio).
   *  Calling it while a job is running returns that same job. */
  generate: (projectId: string) =>
    api.post<GenerateResponse>(`/projects/${projectId}/generate`, { generation_type: "video" }),

  getJobs: (projectId: string) => api.get<Job[]>(`/projects/${projectId}/jobs`),
  getGates: (projectId: string) => api.get<HumanGate[]>(`/projects/${projectId}/gates`),
  getPendingGate: (projectId: string) =>
    api.get<HumanGate | null>(`/projects/${projectId}/gates/pending`),
};
