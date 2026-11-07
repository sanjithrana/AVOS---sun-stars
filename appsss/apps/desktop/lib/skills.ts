// Client for the Skill Lab (apps/animation_studio/studio/skilllab) through the Next rewrite (/studio-api/skills/*).
export type RunStatus = "working" | "done" | "error" | "stopped";
export type StepId = string;

export interface SkillInfo {
  id: string; name: string; group: string; kind: string; made_for: string; about: string; input: string; outputs: string[];
  aspect: string; seconds: number[]; default_seconds: number; native_audio: boolean; examples: string[]; credit: string; make?: [string, string][];
}
export interface Lock { subject: string; form: string; finish: string; palette: string; shell: string; hidden: string[]; anatomy: string; torso: string; sequence: string[]; reveal: string }
export interface Source { title: string; url: string }
export interface Card { type: "title" | "stat" | "caption" | "year" | "vs"; text?: string; value?: string; unit?: string; kicker?: string; years?: string; accent?: string; left?: string; right?: string }
export interface Scene { n: number; purpose: string; narration: string; visual: string; setting: string; move: string; rival: boolean; cards: Card[]; dropped: number; warning: string; picture?: string | null; video?: string | null; voice?: string | null; version?: number }
export interface Research {
  name: string; kind: "company" | "industry"; founded: string; founder: string; origin: string; home: string; sources: Source[];
  milestones: { year: string; event: string; source?: Source | null }[]; numbers: { value: string; label: string; year?: string; source?: Source | null }[];
  how_it_works: string[]; rivals: string[]; turning_points: string[]; unknowns: string[];
}
export interface Run {
  id: string; skill: string; subject: string; title: string; aspect: string; seconds: number; media: "media" | "prompts"; status: RunStatus; stage: StepId;
  error?: string | null; lock?: Lock; prompts?: { compact: string; transformed: string; video: string }; compact?: string; transformed?: string; video?: string; engine?: string;
  steps: Partial<Record<string, { status: "working" | "done" | "error"; model?: string; note?: string }>>; log: { t: string; kind: string; text: string }[];
  research?: Research; script?: { title: string; scenes: Scene[] }; cast?: Record<string, string>; finalSeconds?: number;
  busy: boolean; stages: { id: StepId; label: string }[]; version?: number; updatedAt: string; thumb?: string;
}
export interface RunSummary { id: string; skill: string; title: string; subject: string; status: RunStatus; stage: StepId; aspect: string; video?: string; thumb?: string; error?: string; media: string; updatedAt: string }

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let r: Response;
  try {
    r = await fetch(`/studio-api/skills${path}`, { ...init, headers: init?.body ? { "Content-Type": "application/json" } : undefined });
  } catch {
    throw new Error("The studio service is not running. Start it with: docker compose up -d animation-studio");
  }
  const text = await r.text();
  let data: unknown = null;
  try { data = text ? JSON.parse(text) : null; } catch { /* not JSON */ }
  if (!r.ok) throw new Error((data as { error?: string } | null)?.error || (r.status === 404 ? "The studio doesn't know Skills yet: install the update and restart animation-studio." : `The studio answered ${r.status}.`));
  return data as T;
}
const post = <T,>(path: string, body?: unknown) => call<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const skills = {
  list: () => call<{ skills: SkillInfo[]; runs: RunSummary[] }>(""),
  get: (id: string) => call<Run>(`/${id}`),
  create: (b: { skill: string; subject: string; media: "media" | "prompts"; aspect: string; seconds: number; voice?: "male" | "female"; models?: Record<string, { model: string }>; local_only?: boolean; crew?: string }) => post<Run>("", b),
  editPrompts: (id: string, prompts: Partial<Record<"compact" | "transformed" | "video", string>>) => call<Run>(`/${id}`, { method: "PATCH", body: JSON.stringify({ prompts }) }),
  redo: (id: string, step: StepId, n?: number) => post<Run>(`/${id}/redo`, { step, n }),
  editNarration: (id: string, narration: Record<string, string>) => call<Run>(`/${id}`, { method: "PATCH", body: JSON.stringify({ narration }) }),
  resume: (id: string) => post<Run>(`/${id}/continue`),
  cancel: (id: string) => post<{ ok: true }>(`/${id}/cancel`),
  remove: (id: string) => call<{ ok: true }>(`/${id}`, { method: "DELETE" }),
  file: (id: string, name: string, v?: string | number) => `/studio-api/skills/${id}/files/${name}${v !== undefined ? `?v=${encodeURIComponent(String(v))}` : ""}`,
};
