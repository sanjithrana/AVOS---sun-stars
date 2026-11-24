"use client";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { autoclip } from "@/lib/autoclip";
import { Card, Note, btn } from "./ui";

/** Views, likes and (for Partner Programme channels) the last 28 days of estimated earnings. */
export function ResultsCard() {
  const q = useQuery({ queryKey: ["autoclip", "stats"], queryFn: () => autoclip.stats(false), refetchInterval: 120000, retry: false });
  const d = q.data;
  const rev = d?.revenue_28d as { estimatedRevenue?: number; currency?: string } | number | null | undefined;
  const money = rev == null ? null : typeof rev === "number" ? rev : rev.estimatedRevenue ?? null;
  return (
    <Card title="Results" hint="What the posted clips earned." right={<button className={btn} onClick={() => q.refetch()} disabled={q.isFetching}><RefreshCw className={`h-4 w-4 ${q.isFetching ? "animate-spin" : ""}`} />Refresh</button>}>
      {q.isError && <Note tone="err">{(q.error as Error).message}</Note>}
      {d && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="border border-border p-3"><div className="text-xs text-muted-foreground">Posted</div><div className="text-2xl font-semibold">{d.posted.length}</div></div>
            <div className="border border-border p-3"><div className="text-xs text-muted-foreground">Views</div><div className="text-2xl font-semibold">{d.views.toLocaleString()}</div></div>
            <div className="border border-border p-3"><div className="text-xs text-muted-foreground">Estimated earnings, 28 days</div><div className="text-2xl font-semibold">{money == null ? "n/a" : money.toFixed(2)}</div></div>
          </div>
          <p className="text-xs text-muted-foreground">{d.note}</p>
          {d.posted.length > 0 && (
            <ul className="divide-y divide-border border border-border text-sm">
              {d.posted.slice(0, 20).map((p) => (
                <li key={p.youtube_id} className="flex items-center justify-between gap-3 px-3 py-2">
                  <a className="truncate underline" href={`https://youtube.com/shorts/${p.youtube_id}`} target="_blank" rel="noreferrer">{p.title}</a>
                  <span className="shrink-0 text-xs text-muted-foreground">{p.views ?? "–"} views · {p.likes ?? "–"} likes · {p.privacy ?? ""}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </Card>
  );
}
