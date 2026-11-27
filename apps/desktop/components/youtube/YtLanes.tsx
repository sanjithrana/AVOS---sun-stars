"use client";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Plus } from "lucide-react";
import { autoclip, type YtChannel, type YtPlan, type YtTab } from "@/lib/autoclip";
import { Card, Label, Note, btn, btnPrimary, field } from "@/components/autoclip/ui";
import { Row } from "./YtQueue";
import { num, when } from "./util";

const fmt = (h: number) => `${String(h % 24).padStart(2, "0")}:00`;
const hoursList = Array.from({ length: 25 }, (_, i) => i);

/** Everything for ONE channel: its numbers, its posting times, its queue, and a picker that drops Library clips (or your own upload) into just that queue. */
export function Lane({ c, tab }: { c: YtChannel; tab: YtTab }) {
  const qc = useQueryClient();
  const base: YtPlan = c.plan ?? tab.plan;
  const [f, setF] = useState({ per_day: base.per_day, gap: base.min_gap_minutes, a: base.hours[0], b: base.hours[1], privacy: base.privacy, ahead: base.ahead_hours ?? 0 });
  useEffect(() => setF({ per_day: base.per_day, gap: base.min_gap_minutes, a: base.hours[0], b: base.hours[1], privacy: base.privacy, ahead: base.ahead_hours ?? 0 }),
    [base.per_day, base.min_gap_minutes, base.hours, base.privacy, base.ahead_hours]);
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [mode, setMode] = useState<"auto" | "schedule">("auto");
  const [at, setAt] = useState("");
  const [ack, setAck] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const done = (t: YtTab) => qc.setQueryData(["yt"], t);
  const save = useMutation({ mutationFn: () => autoclip.ytPlan({ channel: c.id, per_day: f.per_day, min_gap_minutes: f.gap, hours: [f.a, f.b], privacy: f.privacy, ahead_hours: f.ahead }), onSuccess: done });
  const grant = useMutation({ mutationFn: (jid: string) => autoclip.confirmPermission(jid), onSuccess: () => qc.invalidateQueries({ queryKey: ["yt"] }) });
  const upload = useMutation({
    mutationFn: (fl: File) => { const fd = new FormData(); fd.append("file", fl); fd.append("ack", String(ack)); return autoclip.ytUpload(fd); },
    onSuccess: (u) => { qc.invalidateQueries({ queryKey: ["yt"] }); setSel((s) => new Set(s).add(`u:${u.id}`)); if (file.current) file.current.value = ""; },
  });
  const add = useMutation({
    mutationFn: () => autoclip.ytAdd({ items: [...sel].map((k) => (k.startsWith("u:") ? { upload: k.slice(2) } : { jid: k.split(":")[0], n: +k.split(":")[1] })), channels: [c.id], mode,
      at: mode === "schedule" && at ? new Date(Date.parse(at + ":00Z") - tab.tz_offset_minutes * 60_000).toISOString() : undefined }),
    onSuccess: (t) => { done(t); setSel(new Set()); setOpen(false); },
  });
  const dirty = f.per_day !== base.per_day || f.gap !== base.min_gap_minutes || f.a !== base.hours[0] || f.b !== base.hours[1] || f.privacy !== base.privacy || f.ahead !== (base.ahead_hours ?? 0);
  const queue = tab.posts.filter((p) => p.channel === c.id && ["queued", "posting", "failed"].includes(p.status)).sort((a, b) => (a.at ?? "").localeCompare(b.at ?? ""));
  const free = tab.library.filter((x) => x.allowed && !x.queued);
  const locked = [...new Map(tab.library.filter((x) => !x.allowed).map((x) => [x.jid, x])).values()];
  const social = !!c.platform && c.platform !== "youtube";
  const canGo = sel.size > 0 && (mode === "auto" || !!at);
  const stat = (k: string, v: string | number) => <div key={k}><dd className="text-xl font-semibold">{v}</dd><dt className="text-xs text-muted-foreground">{k}</dt></div>;
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {c.thumb ? <img src={c.thumb} alt="" className="h-12 w-12 rounded-full" /> : <div className="h-12 w-12 rounded-full bg-muted" />}
          <div><div className="text-lg font-semibold">{c.title}</div><div className="text-xs capitalize text-muted-foreground">{c.platform || "youtube"}{c.subs != null ? ` · ${num(c.subs)} ${social ? "followers" : "subscribers"}` : ""}</div></div>
        </div>
        <dl className="flex gap-6 text-center">{[stat("Waiting", c.queued), stat("Posted", c.posted), stat("Failed", c.failed), ...(!social ? [stat("Views", num(c.views))] : [])]}</dl>
        <button type="button" className={btnPrimary} onClick={() => setOpen(!open)}><Plus className="h-4 w-4" />{open ? "Close" : "Add clips"}</button>
      </div>
      {c.needs_login && <Note tone="warn">Sign in again in Connections. Posts for this account are on hold.</Note>}

      {open && (
        <Card title="Add to this queue" hint={`Only ${c.title} gets these.`}>
          {locked.length > 0 && (
            <div className="space-y-2 border border-amber-400/60 p-3 text-sm">
              <p>Some clips are locked until you confirm you may use their source video (your own, with permission, or licensed for reuse).</p>
              {locked.map((x) => (
                <div key={x.jid} className="flex flex-wrap items-center gap-2"><span className="min-w-0 flex-1 truncate">{x.job_title || x.jid}</span>
                  {x.permission === "blocked" ? <span className="text-xs text-amber-300">Marked as not allowed</span> : <button type="button" className={btn} disabled={grant.isPending} onClick={() => grant.mutate(x.jid)}>I have permission</button>}</div>
              ))}
            </div>
          )}
          {free.length === 0 && tab.uploads.length === 0 ? <p className="text-sm text-muted-foreground">No clips are ready yet.</p> : (
            <>
              <div className="flex items-center justify-between text-xs text-muted-foreground"><span>{sel.size} picked</span>
                {free.length > 0 && <button type="button" className="underline" onClick={() => setSel(new Set(free.map((x) => `${x.jid}:${x.n}`)))}>Select all {free.length}</button>}</div>
              <ul className="grid grid-cols-4 gap-2 sm:grid-cols-6 lg:grid-cols-8">
                {free.map((x) => { const k = `${x.jid}:${x.n}`; const on = sel.has(k); return (
                  <li key={k}>
                    <button type="button" aria-pressed={on} onClick={() => { const n = new Set(sel); on ? n.delete(k) : n.add(k); setSel(n); }}
                      className={`relative block w-full border text-left ${on ? "border-signal/95" : "border-border"}`}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      {x.thumb ? <img src={autoclip.file(x.jid, x.thumb)} alt="" className="aspect-[9/16] w-full object-cover" /> : <div className="aspect-[9/16] w-full bg-muted" />}
                      {on && <CheckCircle2 className="absolute right-1 top-1 h-4 w-4 text-primary" />}
                      <span className="block truncate px-1 py-0.5 text-[10px]">{x.title || `Clip ${x.n}`}</span>
                    </button>
                  </li>); })}
                {tab.uploads.map((u) => { const k = `u:${u.id}`; const on = sel.has(k); return (
                  <li key={k}>
                    <button type="button" aria-pressed={on} onClick={() => { const n = new Set(sel); on ? n.delete(k) : n.add(k); setSel(n); }}
                      className={`relative block w-full border text-left ${on ? "border-signal/95" : "border-border"}`}>
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      {u.thumb ? <img src={autoclip.uploadCover(u.id)} alt="" className="aspect-[9/16] w-full object-cover" /> : <div className="aspect-[9/16] w-full bg-muted" />}
                      {on && <CheckCircle2 className="absolute right-1 top-1 h-4 w-4 text-primary" />}
                      <span className="block truncate px-1 py-0.5 text-[10px]">{u.title} (upload)</span>
                    </button>
                  </li>); })}
              </ul>
            </>
          )}
          <div className="space-y-2 border border-dashed border-border p-3">
            <div className="text-sm font-medium">…or upload your own video</div>
            <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} />I made this, or have permission to post it.</label>
            <input ref={file} type="file" accept="video/*" className={field + " py-1.5"} disabled={!ack || upload.isPending} onChange={(e) => { const fl = e.target.files?.[0]; if (fl) upload.mutate(fl); }} />
            {upload.isPending && <p className="text-xs text-muted-foreground">Uploading…</p>}
            {upload.isError && <Note tone="err">{(upload.error as Error).message}</Note>}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex items-center gap-2 text-sm"><input type="radio" checked={mode === "auto"} onChange={() => setMode("auto")} />Pick the times for me</label>
            <label className="flex items-center gap-2 text-sm"><input type="radio" checked={mode === "schedule"} onChange={() => setMode("schedule")} />Start at</label>
            {mode === "schedule" && <input type="datetime-local" className={field + " !w-auto"} value={at} onChange={(e) => setAt(e.target.value)} />}
            <button type="button" className={btnPrimary} disabled={!canGo || add.isPending} onClick={() => add.mutate()}>{add.isPending ? "Adding…" : `Add ${sel.size} to ${c.title}`}</button>
          </div>
          {add.isError && <Note tone="err">{(add.error as Error).message}</Note>}
          {grant.isError && <Note tone="err">{(grant.error as Error).message}</Note>}
        </Card>
      )}

      <Card title={`Queue (${queue.length})`} hint={queue[0]?.at ? `Next: ${when(queue[0].at, tab.tz_offset_minutes)}` : "Nothing waiting yet. Press Add clips."}>
        {queue.length === 0 ? <p className="text-sm text-muted-foreground">Empty.</p> : <ul className="space-y-2">{queue.map((p) => <Row key={p.id} p={p} tz={tab.tz_offset_minutes} />)}</ul>}
        <details className="border border-border p-3">
          <summary className="cursor-pointer text-sm">Posting times for this {social ? "account" : "channel"}: {f.per_day} a day, {fmt(f.a)} to {f.b === 24 ? "24:00" : fmt(f.b)}, {f.privacy}{f.ahead ? `, upload ${f.ahead} h ahead` : ""}</summary>
          <div className="mt-3 space-y-3">
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <Label text="Posts per day"><input type="number" min={1} max={20} className={field} value={f.per_day} onChange={(e) => setF({ ...f, per_day: +e.target.value })} /></Label>
              <Label text="Gap (minutes)"><input type="number" min={10} max={1440} step={10} className={field} value={f.gap} onChange={(e) => setF({ ...f, gap: +e.target.value })} /></Label>
              <Label text="From"><select className={field} value={f.a} onChange={(e) => setF({ ...f, a: +e.target.value })}>{hoursList.slice(0, 24).map((h) => <option key={h} value={h}>{fmt(h)}</option>)}</select></Label>
              <Label text="To"><select className={field} value={f.b} onChange={(e) => setF({ ...f, b: +e.target.value })}>{hoursList.map((h) => <option key={h} value={h}>{h === 24 ? "24:00" : fmt(h)}</option>)}</select></Label>
              <Label text="Visibility"><select className={field} value={f.privacy} onChange={(e) => setF({ ...f, privacy: e.target.value })}><option value="private">Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option></select></Label>
              {c.can_schedule && <Label text="Upload ahead (hours)"><input type="number" min={0} max={720} className={field} value={f.ahead} onChange={(e) => setF({ ...f, ahead: +e.target.value })} /></Label>}
            </div>
            <p className="text-xs text-muted-foreground">These are used when you choose &quot;Pick the times for me&quot;. {c.can_schedule ? "Upload ahead sends public videos early and the platform publishes them itself, so the computer can be off at posting time. 0 = upload at the posting time." : "This platform can't publish later by itself, so the studio must be running at the posting time."}</p>
            <button type="button" className={btn} disabled={!dirty || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : "Save"}</button>
            {save.isError && <Note tone="err">{(save.error as Error).message}</Note>}
          </div>
        </details>
      </Card>
    </div>
  );
}
