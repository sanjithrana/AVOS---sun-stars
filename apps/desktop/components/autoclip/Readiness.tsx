"use client";
import { useQuery } from "@tanstack/react-query";
import { AlertCircle, AlertTriangle, CheckCircle2, Loader2, RefreshCw } from "lucide-react";
import { autoclip } from "@/lib/autoclip";
import { Note, btn } from "./ui";

const ICON = { ok: <CheckCircle2 className="h-4 w-4 text-primary" />, warn: <AlertTriangle className="h-4 w-4 text-amber-400" />, fail: <AlertCircle className="h-4 w-4 text-red-400" /> };

/** "Is everything ready?": ffmpeg filters, disk space, the AI helper, Ollama and every YouTube login, tried in a second or two. Only runs when you press the button. */
export function Readiness() {
  const q = useQuery({ queryKey: ["autoclip", "readiness"], queryFn: () => autoclip.readiness(), enabled: false, retry: false, staleTime: 0 });
  const rows = q.data?.rows ?? [];
  return (
    <details className="border border-border p-3">
      <summary className="cursor-pointer text-sm">Is everything ready? {q.data && <span className="ml-2 text-xs text-muted-foreground">{q.data.ok ? "All good" : q.data.blocking ? "Something needs fixing" : "A few warnings"}</span>}</summary>
      <div className="mt-3 space-y-3">
        <button type="button" className={btn} disabled={q.isFetching} onClick={() => q.refetch()}>{q.isFetching ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Check now</button>
        {q.isError && <Note tone="err">{(q.error as Error).message}</Note>}
        {rows.length > 0 && (
          <ul className="space-y-2">{rows.map((r) => (
            <li key={r.id} className="flex items-start gap-2 text-sm">{ICON[r.status]}
              <span><span className="font-medium">{r.label}</span>{r.detail && <span className="text-muted-foreground"> · {r.detail}</span>}{r.fix && r.status !== "ok" && <span className="block text-xs text-muted-foreground">→ {r.fix}</span>}</span>
            </li>))}</ul>
        )}
        <p className="text-xs text-muted-foreground">A stopped or failed video carries on from its last finished step: the download, the transcript, the chosen moments and clips already cut are kept.</p>
      </div>
    </details>
  );
}
