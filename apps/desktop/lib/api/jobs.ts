import { api } from "./core";
import type { Job } from "@/types";

export const jobsApi = {
  getById: (jobId: string) => api.get<Job>(`/jobs/${jobId}`),
};
