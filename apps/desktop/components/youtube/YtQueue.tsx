"use client";
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RotateCcw, X, Zap } from "lucide-react";
import { autoclip, type YtPost, type YtTab } from "@/lib/autoclip";
import { Card, Note, btn, field } from "@/components/autoclip/ui";
import { thumbUrl, when } from "./util";

export function Row({ p, tz }: { p: YtPost; tz: number }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState(p.title);
  const done = (t: YtTab) => qc.setQueryData(["yt"], t);
  const edit = useMutation({ mutationFn: (b: Parameters<typeof autoclip.ytEdit>[1]) => autoclip.ytEdit(p.id, b), onSuccess: done });
  const cancel = useMutation({ mutationFn: () => autoclip.ytCancel(p.id), onSuccess: done });
  const retry = useMutation({ mutationFn: () => autoclip.ytRetry(p.id), onSuccess: done });
  const now = useMutation({ mutationFn: () => autoclip.ytNow(p.id), onSuccess: done });
  const waiting = p.status === "queued";
  const img = thumbUrl(p.thumb);
  const err = (edit.error || cancel.error || retry.error || now.error) as Error | null;
  return (
    <li className="grid grid-cols-[56px_1fr] gap-3 border border-border p-2 sm:grid-cols-[56px_1fr_auto]">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      {img ? <img src={img} alt="" className="aspect-[9/16] w-14 object-cover" /> : <div className="aspect-[9/16] w-14 bg-muted" />}
      <div className="min-w-0 space-y-1">
        {waiting ? <input className={field + " !h-8"} value={title} maxLength={95} onChange={(e) => setTitle(e.target.value)} onBlur={() => title !== p.title && edit.mutate({ title })} aria-label="Title" /> : <div className="truncate text-sm font-medium">{p.title}</div>}
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{p.channel_title}</span>
          {waiting ? <select aria-label="Visibility" className={field + " !h-7 !w-auto !px-2 text-xs"} value={p.privacy} onChange={(e) => edit.mutate({ privacy: e.target.value as "private" | "unlisted" | "public" })}><option value="private">Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option></select> : <span>{p.privacy}</span>}
          <span className={p.status === "failed" ? "text-red-400" : p.status === "posted" ? "text-primary" : ""}>
            {p.status === "queued" ? (p.hold ? "On hold: sign in again" : `Waiting · ${when(p.at, tz)}`) : p.status === "posting" ? "Posting now…" : p.status === "posted" ? (p.scheduled_for && Date.parse(p.scheduled_for) > Date.now() ? `Uploaded. Goes public ${when(p.scheduled_for, tz)}` : `Posted ${when(p.posted_at, tz)}`) : p.status === "failed" ? "Failed" : "Cancelled"}
          </span>
          {p.status === "posted" && p.thumb_status && <span>{p.thumb_status === "set" ? "cover set" : p.thumb_status.startsWith("not") ? "YouTube didn't take the cover (normal for Shorts)" : ""}</span>}
        </div>
        {waiting && !p.hold && (
          <label className="flex items-center gap-2 text-xs text-muted-foreground">Time
            <input type="datetime-local" className={field + " !h-8 !w-auto"} defaultValue={p.at ? new Date(Date.parse(p.at) + tz * 60_000).toISOString().slice(0, 16) : ""}
              onBlur={(e) => { const v = e.target.value; if (v) edit.mutate({ at: new Date(Date.parse(v + ":00Z") - tz * 60_000).toISOString() }); }} />
          </label>
        )}
        {p.error && <p className="text-xs text-red-400">{p.error}</p>}
        {p.note && <p className="text-xs text-amber-300">{p.note}</p>}
        {err && <p className="text-xs text-red-400">{err.message}</p>}
      </div>
      <div className="col-span-2 flex flex-wrap items-center gap-2 sm:col-span-1 sm:justify-end">
        {waiting && <button type="button" className={btn + " !h-8 !px-3 text-xs"} onClick={() => now.mutate()} disabled={now.isPending}><Zap className="h-3 w-3" />Post now</button>}
        {(p.status === "failed" || p.status === "cancelled") && <button type="button" className={btn + " !h-8 !px-3 text-xs"} onClick={() => retry.mutate()}><RotateCcw className="h-3 w-3" />Retry</button>}
        {(waiting || p.status === "failed") && <button type="button" className={btn + " !h-8 !px-3 text-xs"} onClick={() => cancel.mutate()} aria-label="Cancel"><X className="h-3 w-3" />Cancel</button>}
        {p.url && <a href={p.url} target="_blank" rel="noreferrer" className={btn + " !h-8 !px-3 text-xs"}>Open <ExternalLink className="h-3 w-3" /></a>}
      </div>
    </li>
  );
}

/** What is waiting to go out, in time order, with edit / post now / cancel / retry. Posted items move to the monitor below. */
export function YtQueue({ tab }: { tab: YtTab }) {
  const qc = useQueryClient();
  const clear = useMutation({ mutationFn: () => autoclip.ytClear(), onSuccess: (t) => qc.setQueryData(["yt"], t) });
  const pub = useMutation({ mutationFn: (v: string) => autoclip.ytPrivacy(v), onSuccess: (t) => qc.setQueryData(["yt"], t) });
  const drip = useMutation({ mutationFn: () => autoclip.ytDrip(), onSuccess: (t) => qc.setQueryData(["yt"], t) });
  const live = tab.posts.filter((p) => p.status === "queued" || p.status === "posting" || p.status === "failed")
    .sort((a, b) => (a.at ?? "").localeCompare(b.at ?? ""));
  const dead = tab.posts.filter((p) => p.status === "cancelled").length;
  return (
    <Card title={`Queue (${live.length})`} hint="Posts go out by themselves while the studio is running." right={<div className="flex flex-wrap gap-2">
      {live.some((p) => p.status === "queued") && <button type="button" className={btn} disabled={drip.isPending} onClick={() => { if (window.confirm("Post everything that is waiting, one by one, starting now with 3 to 5 minutes between posts?")) drip.mutate(); }}><Zap className="h-3 w-3" />{drip.isPending ? "Starting…" : "Post one by one now (3–5 min apart)"}</button>}
      {live.some((p) => p.status === "queued" && p.privacy !== "public") && <button type="button" className={btn} disabled={pub.isPending} onClick={() => pub.mutate("public")}>{pub.isPending ? "Saving…" : "Make all waiting public"}</button>}
      {dead > 0 && <button type="button" className={btn} onClick={() => clear.mutate()}>Clear {dead} cancelled</button>}</div>}>
      {tab.posts.some((p) => p.status === "posted" && p.note) && <Note tone="warn">{tab.posts.find((p) => p.status === "posted" && p.note)?.note}</Note>}
      {drip.isError && <Note tone="err">{(drip.error as Error).message}</Note>}
      {live.length === 0 ? <p className="text-sm text-muted-foreground">Nothing waiting. Add videos above.</p> : <ul className="space-y-2">{live.map((p) => <Row key={p.id} p={p} tz={tab.tz_offset_minutes} />)}</ul>}
      <Note>Posting happens inside the studio service: if Docker or the computer is off at a post&apos;s time, it goes out when the studio is next running.</Note>
    </Card>
  );
}
