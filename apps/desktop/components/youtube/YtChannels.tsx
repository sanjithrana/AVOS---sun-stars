"use client";
import { AlertTriangle } from "lucide-react";
import type { YtTab } from "@/lib/autoclip";
import { when, num } from "./util";

/** One card per connected channel: the quick glance (waiting, posted, views, next post). */
export function YtChannels({ tab }: { tab: YtTab }) {
  if (!tab.channels.length) return null;
  return (
    <section aria-label="Channels" className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
      {tab.channels.map((c) => (
        <div key={c.id} className="rounded-2xl border border-border bg-card p-4">
          <div className="flex items-center gap-3">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            {c.thumb ? <img src={c.thumb} alt="" className="h-10 w-10 rounded-full" /> : <div className="h-10 w-10 rounded-full bg-muted" />}
            <div className="min-w-0"><div className="truncate font-medium">{c.title}</div><div className="text-xs text-muted-foreground">{c.platform && c.platform !== "youtube" ? <span className="capitalize">{c.platform}</span> : "YouTube"} · {num(c.subs)} {c.platform && c.platform !== "youtube" ? "followers" : "subscribers"}</div></div>
          </div>
          {c.needs_login && <p className="mt-3 flex items-center gap-2 border border-amber-400/70 px-2 py-1.5 text-xs"><AlertTriangle className="h-3.5 w-3.5" />Sign in again in Connections. Its posts are on hold.</p>}
          <dl className="mt-3 grid grid-cols-4 gap-2 text-center text-xs">
            {([["Waiting", c.queued], ["Posted", c.posted], ["Failed", c.failed], ["Views", num(c.views)]] as const).map(([k, v]) => (
              <div key={k}><dd className="text-base font-semibold">{v}</dd><dt className="text-muted-foreground">{k}</dt></div>
            ))}
          </dl>
          <p className="mt-3 text-xs text-muted-foreground">Next post: {c.next ? when(c.next, tab.tz_offset_minutes) : "nothing scheduled"}</p>
        </div>
      ))}
    </section>
  );
}
