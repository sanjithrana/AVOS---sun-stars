export interface DecisionTraceEntry {
  id: string;
  agent_decision: string;
  tool_name: string;
  status: "success" | "error";
  duration_ms: number;
  cost: number;
  model: string;
  error: string | null;
  created_at: string;
}
