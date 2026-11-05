import { api } from "./core";
import type { HumanGate, HumanGateDecisionInput } from "@/types";

export const gatesApi = {
  getById: (gateId: string) => api.get<HumanGate>(`/gates/${gateId}`),
  approve: (gateId: string, decision: HumanGateDecisionInput) =>
    api.post<HumanGate>(`/gates/${gateId}/approve`, decision),
  reject: (gateId: string, decision: HumanGateDecisionInput) =>
    api.post<HumanGate>(`/gates/${gateId}/reject`, decision),
};
