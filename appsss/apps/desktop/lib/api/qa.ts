import { api } from "./core";
import type { RepairPlanRecord, QAResultRecord, ShotQAState } from "@/types";

export const qaApi = {
  getShotState: (shotId: string) => api.get<ShotQAState>(`/shots/${shotId}/qa`),
  /**
   * QA agent: score the shot's candidate 0 (409 until it's generated).
   *
   * forceFail (Week 3 Day 15 integration checkpoint): still runs the
   * real evaluation, then deliberately, visibly overrides the verdict
   * to FAIL - the mock Video generator and the geometry check agree by
   * construction, so this is the only way to prove the repair ladder
   * fires through the live UI rather than only in a backend test
   * fixture. Never sent unless a human explicitly asks for it.
   */
  runCommittee: (shotId: string, forceFail = false) =>
    api.post<QAResultRecord>(`/shots/${shotId}/qa${forceFail ? "?force_fail=true" : ""}`),
  /** Repair agent: advance the ladder one attempt (409 unless the latest QA result is FAIL). */
  repair: (shotId: string) => api.post<RepairPlanRecord>(`/shots/${shotId}/repair`),
};
