"use client";

// Downloads in progress and finished, on this PC and on every GPU worker (Models page).
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Download, HardDrive, Loader2, Server, X, XCircle } from "lucide-react";

import { downloadsApi } from "@/lib/api";
import type { DownloadJob } from "@/types";
import { gb } from "./DownloadPanel";

const eta = (s: number | null) => (s == null ? "" : s < 90 ? `${s} s left` : s < 5400 ? `${Math.round(s / 60)} min left` : `${(s / 3600).toFixed(1)} h left`);

export function useDownloads() {
  return useQuery({
    queryKey: ["downloads"],
    queryFn: downloadsApi.list,
    retry: false,
    refetchInterval: (q) => ((q.state.data as DownloadJob[] | undefined)?.some((j) => j.status === "running" || j.status === "queued") ? 1500 : 10_000),
  });
}

export function DownloadsList() {
  const qc = useQueryClient();
  const { data } = useDownloads();
  const jobs = data ?? [];
  if (!jobs.length) return null;
  const cancel = async (j: DownloadJob) => {
    await downloadsApi.cancel(j.where, j.id).catch(() => undefined);
    qc.invalidateQueries({ queryKey: ["downloads"] });
  };
  return (
    <section className="border border-border bg-card/40 p-5" data-testid="downloads">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground"><Download className="h-5 w-5 text-amber-500" />Downloads</h2>
      <div className="mt-3 space-y-3">
        {jobs.slice(0, 12).map((j) => {
          const active = j.status === "running" || j.status === "queued";
          return (
            <div key={`${j.where}-${j.id}`} className="border border-border p-3" data-testid="download-row" data-status={j.status}>
              <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                <span className="flex min-w-0 items-center gap-2">
                  {j.where === "local" ? <HardDrive className="h-4 w-4 shrink-0 text-muted-foreground" /> : <Server className="h-4 w-4 shrink-0 text-muted-foreground" />}
                  <span className="truncate font-medium text-foreground">{j.label}</span>
                  <span className="truncate text-xs text-muted-foreground">→ {j.where_name} · {j.dest}</span>
                </span>
                <span className="flex items-center gap-2 text-xs">
                  {j.status === "done" && <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400"><CheckCircle2 className="h-4 w-4" />Done · {gb(j.total)}</span>}
                  {j.status === "error" && <span className="flex items-center gap-1 text-red-500"><XCircle className="h-4 w-4" />Failed</span>}
                  {j.status === "cancelled" && <span className="text-muted-foreground">Cancelled (start again to resume)</span>}
                  {active && <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400"><Loader2 className="h-3.5 w-3.5 animate-spin" />{gb(j.done)} / {gb(j.total)}{j.speed ? ` · ${gb(j.speed)}/s · ${eta(j.eta)}` : ""}</span>}
                  <button className="text-muted-foreground hover:text-red-400" onClick={() => cancel(j)} aria-label={active ? "Cancel download" : "Clear"} title={active ? "Cancel" : "Clear"}><X className="h-4 w-4" /></button>
                </span>
              </div>
              {(active || j.status === "error") && (
                <div className="mt-2 h-1.5 overflow-hidden bg-muted"><div className={`h-full ${j.status === "error" ? "bg-red-500" : "bg-amber-500"} transition-all`} style={{ width: `${Math.round(j.progress * 100)}%` }} /></div>
              )}
              {j.error && <p className="mt-1 text-xs text-red-400 [overflow-wrap:anywhere]">{j.error}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
