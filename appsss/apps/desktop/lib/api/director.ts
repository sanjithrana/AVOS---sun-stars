import { api } from "./core";
import type { DecisionTraceEntry } from "@/types";

export const directorApi = {
  getTrace: (projectId: string) =>
    api.get<DecisionTraceEntry[]>("/agents/trace", { project_id: projectId }),
};
