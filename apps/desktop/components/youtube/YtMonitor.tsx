"use client";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RefreshCw } from "lucide-react";
import { autoclip, type YtTab } from "@/lib/autoclip";
import { Card, btn } from "@/components/autoclip/ui";
import { num, thumbUrl, when } from "./util";

/** The numbers: totals per channel and every posted video with its views, likes and comments. Refreshed from YouTube every 10 minutes. */
export function YtMonitor({ tab, channel }: { tab: YtTab; channel?: string }) {
  const qc = useQueryClient();
  const refresh = useMutation({ mutationFn: () => autoclip.yt(true), onSuccess: (t) => qc.setQueryData(["yt"], t) });
  const posted = tab.posts.filter((p) => p.status === "posted" && (!channel || p.channel === channel)).sort((a, b) => (b.posted_at ?? "").localeCompare(a.posted_at ?? ""));
  const sum = (k: "views" | "likes" | "comments") => tab.channels.filter((c) => !channel || c.id === channel).reduce((n, c) => n + c[k], 0);
  const checked = posted.map((p) => p.stats?.at).filter(Boolean).sort().pop();
  return (
    <Card title="Posted and numbers" hint={checked ? `Last read ${when(checked, tab.tz_offset_minutes)}.` : "Numbers appear a few minutes after the first post (YouTube only)."}
      right={<button type="button" className={btn} disabled={refresh.isPending} onClick={() => refresh.mutate()}><RefreshCw className={`h-4 w-4 ${refresh.isPending ? "animate-spin" : ""}`} />Refresh</button>}>
      <dl className="grid grid-cols-2 gap-3 text-center sm:grid-cols-4">
        {([["Posted", posted.length], ["Views", num(sum("views"))], ["Likes", num(sum("likes"))], ["Comments", num(sum("comments"))]] as const).map(([k, v]) => (
          <div key={k} className="border border-border p-3"><dd className="text-2xl font-semibold">{v}</dd><dt className="text-xs text-muted-foreground">{k}</dt></div>
        ))}
      </dl>
      {posted.length === 0 ? <p className="text-sm text-muted-foreground">Nothing posted yet.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-left text-sm">
            <thead className="text-xs uppercase tracking-wide text-muted-foreground"><tr><th className="py-2 pr-3">Video</th><th className="pr-3">Channel</th><th className="pr-3">Posted</th><th className="pr-3 text-right">Views</th><th className="pr-3 text-right">Likes</th><th className="pr-3 text-right">Comments</th><th>State</th></tr></thead>
            <tbody>
              {posted.map((p) => {
                const img = thumbUrl(p.thumb);
                const gone = p.stats?.removed;
                return (
                  <tr key={p.id} className="border-t border-border">
                    <td className="py-2 pr-3"><div className="flex items-center gap-2">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      {img ? <img src={img} alt="" className="h-12 w-7 object-cover" /> : <div className="h-12 w-7 bg-muted" />}
                      <a href={p.url ?? "#"} target="_blank" rel="noreferrer" className="inline-flex max-w-[260px] items-center gap-1 truncate underline">{p.title}<ExternalLink className="h-3 w-3 shrink-0" /></a>
                    </div></td>
                    <td className="pr-3">{p.channel_title}</td>
                    <td className="pr-3 text-xs text-muted-foreground">{when(p.posted_at, tab.tz_offset_minutes)}</td>
                    <td className="pr-3 text-right">{num(p.stats?.views)}</td><td className="pr-3 text-right">{num(p.stats?.likes)}</td><td className="pr-3 text-right">{num(p.stats?.comments)}</td>
                    <td className={gone ? "text-red-400" : "text-muted-foreground"}>{gone ? "Removed or blocked: check YouTube Studio" : p.stats?.privacy ?? p.privacy}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
