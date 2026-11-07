export type PolicyCategory =
  | "style"
  | "pacing"
  | "composition"
  | "narrative"
  | "audio"
  | "generation";

export interface PolicyRule {
  id: string;
  category: PolicyCategory;
  description: string;
  condition: string; // e.g., "topic == 'physics'"
  action: string; // e.g., "use_style 'clean_3d'"
  confidence: number;
  source: "human" | "agentic_learning" | "default";
  created_at: string;
  updated_at: string;
}

export interface CreativePolicy {
  policy_id: string;
  name: string;
  rules: PolicyRule[];
  version: number;
  updated_at: string;
}