// Thin client for the Animation Studio service (ReelMimic's HTTP API + multi-provider crews).
// Calls go through this Next server (/studio-api/* and /studio-files/*, see next.config.ts), so the browser stays
// same-origin. Only the live event stream is opened directly at the service (it sends CORS headers).
import type {
  AgentInfo, AgentKind, AgentSettingsBody, AgentStatus, AgentsInfo, Config, FinishModel, FinishStatus, MessageMeta, ProjectSummary, RoundKey, ServerEvent, Snapshot,
} from "./types";

type Ok = { ok: true };

// ---------- engine online / offline ----------
// Any network failure or a 5xx without a JSON body means the service is not running (the Next rewrite could not
// reach it). The flag is shared so one gate can show "how to start it" and recover by itself.
export class StudioOfflineError extends Error {
  constructor() {
    super("The animation service is not running.");
    this.name = "StudioOfflineError";
  }
}
let offline = false;
const subs = new Set<() => void>();
const setOffline = (v: boolean) => { if (offline !== v) { offline = v; subs.forEach((f) => f()); } };
export const engineStatus = {
  get: () => offline,
  server: () => false,
  subscribe: (f: () => void) => { subs.add(f); return () => { subs.delete(f); }; },
  set: setOffline,
};

const j = async <T,>(r: Response): Promise<T> => {
  const text = await r.text().catch(() => "");
  let d: unknown = {};
  let isJson = false;
  try { d = text ? JSON.parse(text) : {}; isJson = !!text; } catch { d = {}; }
  if (!r.ok) {
    const msg = (d as { error?: string }).error;
    if (r.status >= 500 && !msg && (!isJson || [502, 503, 504].includes(r.status))) { setOffline(true); throw new StudioOfflineError(); }
    setOffline(false);
    const err = new Error(msg || r.statusText || `HTTP ${r.status}`) as Error & { status?: number; body?: unknown };
    err.status = r.status; err.body = d;
    throw err;
  }
  setOffline(false);
  return d as T;
};
const call = async <T,>(path: string, init?: RequestInit): Promise<T> => {
  let r: Response;
  try { r = await fetch(`/studio-api${path}`, init); } catch { setOffline(true); throw new StudioOfflineError(); }
  return j<T>(r);
};
const post = <T,>(path: string, body?: unknown) =>
  call<T>(path, body === undefined ? { method: "POST" } : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });

// where the browser opens the SSE stream: NEXT_PUBLIC_ANIMATION_STUDIO_URL, else the service on this host's :8020
export const studioUrl = () => {
  const env = process.env.NEXT_PUBLIC_ANIMATION_STUDIO_URL;
  if (env) return env.replace(/\/$/, "");
  if (typeof location !== "undefined" && location.hostname) return `http://${location.hostname}:8020`;
  return "http://localhost:8020";
};

export type LiveEvent = ServerEvent | { type: "poll" };

export const api = {
  agents: () => call<AgentStatus>("/agents"),
  agentsInfo: () => call<AgentsInfo>("/agents/info"),
  agentSettings: (body: AgentSettingsBody) => post<AgentsInfo>("/agents/settings", body),
  pull: (model: string) => post<Ok>("/agents/pull", { model }),
  projects: () => call<ProjectSummary[]>("/projects"),
  project: (id: string) => call<Snapshot>(`/projects/${id}`),
  create: (form: FormData) => call<{ id: string }>("/projects", { method: "POST", body: form }),
  addInputs: (id: string, form: FormData, to?: string | null, forInput?: string) =>
    call<Snapshot & { saved: string[] }>(`/projects/${id}/inputs?${new URLSearchParams({ ...(to ? { to } : {}), ...(forInput ? { for: forInput } : {}) })}`, { method: "POST", body: form }),
  message: (id: string, text: string, meta?: MessageMeta) => post<Ok>(`/projects/${id}/message`, { text, meta }),
  approve: (id: string) => post<Ok>(`/projects/${id}/approve`),
  retry: (id: string) => post<Ok>(`/projects/${id}/retry`),
  lyrics: (id: string, text: string) => post<{ ok: boolean; aligned: boolean; report?: unknown }>(`/projects/${id}/lyrics`, { text }),
  unwaive: (id: string, input: string) => post<Snapshot>(`/projects/${id}/unwaive`, { input }),
  waive: (id: string, input: string) => post<Snapshot>(`/projects/${id}/waive`, { input }),
  config: () => call<Config>("/config"),
  settings: (id: string, body: Partial<Record<RoundKey, number | "">>) => post<Snapshot>(`/projects/${id}/settings`, body),
  accept: (id: string) => post<Ok>(`/projects/${id}/accept`),
  resume: (id: string) => post<Ok>(`/projects/${id}/resume`),
  cancel: (id: string) => post<Ok>(`/projects/${id}/cancel`),
  critique: (id: string) => post<Ok>(`/projects/${id}/critique`),
  finish: (id: string, model: FinishModel) => post<{ ok: boolean; finish: FinishStatus }>(`/projects/${id}/finish`, { model }),
  // Live updates: SSE straight from the service; while it is not connected, poll every 3 s instead.
  events: (id: string, fn: (ev: LiveEvent) => void) => {
    let poll: ReturnType<typeof setInterval> | null = null;
    const startPoll = () => { if (!poll) poll = setInterval(() => fn({ type: "poll" }), 3000); };
    const stopPoll = () => { if (poll) { clearInterval(poll); poll = null; } };
    let es: EventSource | null = null;
    try {
      es = new EventSource(`${studioUrl()}/api/projects/${encodeURIComponent(id)}/events`);
      es.onopen = () => stopPoll();
      es.onmessage = (m: MessageEvent<string>) => { try { fn(JSON.parse(m.data) as ServerEvent); } catch { /* keep-alive or junk */ } };
      es.onerror = () => startPoll();
    } catch { startPoll(); }
    return () => { es?.close(); stopPoll(); };
  },
  // encode each path segment ('#' would start the fragment, '%' makes a malformed URI); agents on Windows may write '\'
  file: (id: string, p: string, bust?: number) => `/studio-files/${id}/${p.split(/[\\/]/).map(encodeURIComponent).join("/")}${bust ? `?v=${bust}` : ""}`,
};

// ---------- crews ----------
export const agentLabel = (id: AgentKind | string | undefined, info?: AgentsInfo | null) =>
  (id && info?.agents.find((a) => a.id === id)?.label) || FALLBACK_LABEL[id as AgentKind] || id || "";
const FALLBACK_LABEL: Partial<Record<AgentKind, string>> = {
  ollama: "Ollama (local)", groq: "Groq", gemini: "Gemini", openrouter: "OpenRouter", openai: "OpenAI", anthropic: "Anthropic API", claude: "Claude Code", codex: "Codex",
};
export const findAgent = (info: AgentsInfo | null | undefined, id: AgentKind | string | null | undefined): AgentInfo | undefined =>
  info?.agents.find((a) => a.id === id);
