// The top bar's feed (apps/animation_studio/studio/activity.py): what runs, what waits for you and what finished, across every studio.
export type ActivityState = "running" | "waiting" | "error" | "done" | "stopped";
export interface ActivityItem {
  studio: string; kind: string; id: string; title: string; state: ActivityState; stage: string; updatedAt: string; href: string; thumb: string | null; needs: number; error: string;
}
export interface Activity { jobs: ActivityItem[]; recent: ActivityItem[]; counts: { running: number; waiting: number; error: number } }
export interface Capabilities { ai_video: boolean; blender: boolean; voice: boolean; music: boolean; hint: string | null }

export const EMPTY_ACTIVITY: Activity = { jobs: [], recent: [], counts: { running: 0, waiting: 0, error: 0 } };

export async function fetchActivity(): Promise<Activity> {
  const r = await fetch("/studio-api/activity", { cache: "no-store" });
  if (!r.ok) throw new Error(`activity ${r.status}`);
  return (await r.json()) as Activity;
}

export async function fetchCaps(): Promise<Capabilities> {
  const r = await fetch("/studio-api/explainer/capabilities", { cache: "no-store" });
  if (!r.ok) throw new Error(`capabilities ${r.status}`);
  return (await r.json()) as Capabilities;
}

/** "just now", "5 min ago", "3 h ago", "2 d ago" from an ISO time. */
export function ago(iso: string, now = Date.now()): string {
  const t = Date.parse(iso);
  if (!Number.isFinite(t)) return "";
  const s = Math.max(0, Math.round((now - t) / 1000));
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  return `${Math.round(s / 86400)} d ago`;
}
