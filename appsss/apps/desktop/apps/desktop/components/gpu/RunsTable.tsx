"use client";

// Generation runs (gpu_jobs): where each picture / clip ran, at which precision, how long and what it cost.
import type { GpuJobRow } from "@/types";

export const fmtS = (s: number | null | undefined) =>
  s == null ? "—" : s < 90 ? `${s.toFixed(s < 10 ? 1 : 0)} s` : s < 5400 ? `${(s / 60).toFixed(1)} min` : `${(s / 3600).toFixed(1)} h`;
export const fmtUsd = (c: number | null | undefined) => (c == null ? "—" : c === 0 ? "free" : c < 0.01 ? `$${c.toFixed(4)}` : `$${c.toFixed(2)}`);
export const BACKEND_LABEL: Record<string, string> = { gpu: "GPU worker", comfyui: "Your ComfyUI", cloudflare: "Cloudflare", fal: "fal.ai", replicate: "Replicate" };

export function RunsTable({ jobs, compact = false }: { jobs: GpuJobRow[]; compact?: boolean }) {
  if (!jobs.length) return <p className="text-sm text-muted-foreground">No runs yet. Every picture and clip AVOS generates appears here with where it ran.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px] text-left text-sm" data-testid="runs-table">
        <thead className="text-xs uppercase text-muted-foreground">
          <tr><th className="py-1 pr-3">Model</th><th className="pr-3">Where</th><th className="pr-3">Status</th><th className="pr-3">GPU time</th><th className="pr-3">Cost</th>{!compact && <th className="pr-3">QA</th>}<th>When</th></tr>
        </thead>
        <tbody>
          {jobs.map((j) => (
            <tr key={j.id} className="border-t border-border align-top" data-testid="run-row">
              <td className="py-2 pr-3"><span className="font-medium text-foreground">{j.model}</span><span className="block text-xs text-muted-foreground">{j.task}{j.warm ? " · already loaded" : ""}</span></td>
              <td className="pr-3 text-foreground">
                {j.backend === "gpu" ? <>{j.worker_name}<span className="block text-xs text-muted-foreground">{j.gpu} · {j.adapter} · {j.precision}{j.attention && j.attention !== "sdpa" ? ` · ${j.attention}` : ""}</span></> : BACKEND_LABEL[j.backend] ?? j.backend}
              </td>
              <td className="pr-3">
                {j.status === "done" ? <span className="text-emerald-600 dark:text-emerald-400">done</span>
                  : j.status === "error" ? <span className="text-red-500" title={j.error ?? ""}>failed</span>
                    : (
                      <span className="block w-28">
                        <span className="text-amber-600 dark:text-amber-400">{j.step || j.status}</span>
                        <span className="mt-1 block h-1.5 overflow-hidden rounded-full bg-muted"><span className="block h-full bg-amber-500" style={{ width: `${Math.round((j.progress || 0) * 100)}%` }} /></span>
                      </span>
                    )}
                {j.status === "error" && j.error && <span className="block max-w-[260px] text-xs text-muted-foreground [overflow-wrap:anywhere]">{j.error}</span>}
              </td>
              <td className="pr-3">{fmtS(j.gpu_seconds ?? (j.status === "done" ? j.wall_seconds : null))}</td>
              <td className="pr-3">{fmtUsd(j.cost_usd ?? (j.status === "done" ? 0 : null))}</td>
              {!compact && <td className="pr-3">{j.qa_score != null ? j.qa_score.toFixed(2) : "—"}</td>}
              <td className="text-xs text-muted-foreground">{j.created_at ? new Date(j.created_at).toLocaleTimeString() : ""}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

