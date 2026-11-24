"use client";
import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, Trash2, Upload } from "lucide-react";
import { autoclip, type YtTab } from "@/lib/autoclip";
import { Card, Label, Note, btn, btnPrimary, field } from "@/components/autoclip/ui";

type Mode = "auto" | "schedule" | "now";
const key = (i: { jid?: string; n?: number; upload?: string }) => (i.upload ? `u:${i.upload}` : `c:${i.jid}:${i.n}`);

/** Pick any number of videos (Library clips or your own uploads) and any number of channels, choose when, queue them. */
export function YtAdd({ tab }: { tab: YtTab }) {
  const qc = useQueryClient();
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [chans, setChans] = useState<Set<string>>(() => new Set(tab.channels.length === 1 ? [tab.channels[0].id] : []));
  const [mode, setMode] = useState<Mode>("auto");
  const [at, setAt] = useState("");
  const [privacy, setPrivacy] = useState("");
  const [ack, setAck] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const toggle = <T,>(s: Set<T>, v: T, set: (x: Set<T>) => void) => { const n = new Set(s); n.has(v) ? n.delete(v) : n.add(v); set(n); };

  const upload = useMutation({
    mutationFn: (f: File) => { const fd = new FormData(); fd.append("file", f); fd.append("ack", String(ack)); return autoclip.ytUpload(fd); },
    onSuccess: (u) => { qc.invalidateQueries({ queryKey: ["yt"] }); setSel((s) => new Set(s).add(`u:${u.id}`)); if (file.current) file.current.value = ""; },
  });
  const delUp = useMutation({ mutationFn: (id: string) => autoclip.ytUploadDelete(id), onSuccess: () => qc.invalidateQueries({ queryKey: ["yt"] }) });
  const grant = useMutation({
    mutationFn: (jid: string) => autoclip.confirmPermission(jid),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["yt"] }),
  });
  const add = useMutation({
    mutationFn: () => autoclip.ytAdd({
      items: [...sel].map((k) => { const p = k.split(":"); return p[0] === "u" ? { upload: p[1] } : { jid: p[1], n: +p[2] }; }),
      channels: [...chans], mode, at: mode === "schedule" && at ? new Date(at).toISOString() : undefined, privacy: privacy || undefined,
    }),
    onSuccess: (t) => { qc.setQueryData(["yt"], t); setSel(new Set()); },
  });

  const lib = tab.library;
  const locked = [...new Map(lib.filter((c) => !c.allowed).map((c) => [c.jid, c])).values()];
  const usable = lib.filter((c) => c.allowed && !c.queued);
  const needTime = mode === "schedule" && !at;
  const ready = sel.size > 0 && chans.size > 0 && !needTime;
  const total = sel.size * chans.size;
  const tz = tab.tz_offset_minutes;
  return (
    <Card title="Add many at once" hint="Several videos to several channels in one go. For one channel at a time, use its card above."
      right={usable.length > 0 && <button type="button" className={btn} onClick={() => setSel(new Set(usable.map((c) => key(c))))}>Select all ready</button>}>
      <div>
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">1 · Videos ({sel.size} picked)</span>
        {lib.length === 0 && tab.uploads.length === 0 && <p className="mt-2 text-sm text-muted-foreground">No finished clips yet. Make some in Auto Clip, or upload a video below.</p>}
        {locked.length > 0 && (
          <div className="mt-2 space-y-2 border border-amber-400/60 p-3 text-sm">
            <p>These clips are greyed out because you haven&apos;t confirmed you may use the source video. Confirm only if you own it, have the owner&apos;s permission, or it is licensed for reuse.</p>
            {locked.map((c) => (
              <div key={c.jid} className="flex flex-wrap items-center gap-2">
                <span className="min-w-0 flex-1 truncate">{c.job_title || c.jid}</span>
                {c.permission === "blocked"
                  ? <span className="text-xs text-amber-300">Marked as not allowed, can&apos;t be unlocked</span>
                  : <button type="button" className={btn} disabled={grant.isPending} onClick={() => grant.mutate(c.jid)}>I have permission</button>}
              </div>
            ))}
            {grant.isError && <Note tone="err">{(grant.error as Error).message}</Note>}
          </div>
        )}
        <ul className="mt-2 grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8">
          {lib.map((c) => {
            const k = key(c);
            const on = sel.has(k);
            const off = !c.allowed || c.queued;
            return (
              <li key={k}>
                <button type="button" disabled={off} aria-pressed={on} onClick={() => toggle(sel, k, setSel)} title={!c.allowed ? "Permission not confirmed in Auto Clip" : c.queued ? "Already in the queue" : c.job_title}
                  className={`relative block w-full border text-left transition ${on ? "border-[rgba(200,255,58,0.95)]" : "border-border"} ${off ? "opacity-45" : "hover:border-foreground/50"}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {c.thumb ? <img src={autoclip.file(c.jid, c.thumb)} alt="" className="aspect-[9/16] w-full object-cover" /> : <div className="aspect-[9/16] w-full bg-muted" />}
                  {on && <CheckCircle2 className="absolute right-1 top-1 h-5 w-5 text-primary" />}
                  <span className="block truncate px-1.5 py-1 text-[11px]">{c.title || `Clip ${c.n}`}</span>
                  {(!c.allowed || c.queued) && <span className="block px-1.5 pb-1 text-[10px] text-amber-300">{c.queued ? "In queue" : c.permission === "blocked" ? "Not allowed to reuse" : "Permission not confirmed"}</span>}
                </button>
              </li>
            );
          })}
          {tab.uploads.map((u) => {
            const k = `u:${u.id}`;
            const on = sel.has(k);
            return (
              <li key={k} className="relative">
                <button type="button" aria-pressed={on} onClick={() => toggle(sel, k, setSel)} className={`relative block w-full border text-left ${on ? "border-[rgba(200,255,58,0.95)]" : "border-border"}`}>
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  {u.thumb ? <img src={autoclip.uploadCover(u.id)} alt="" className="aspect-[9/16] w-full object-cover" /> : <div className="aspect-[9/16] w-full bg-muted" />}
                  {on && <CheckCircle2 className="absolute right-1 top-1 h-5 w-5 text-primary" />}
                  <span className="block truncate px-1.5 py-1 text-[11px]">{u.title}</span>
                  <span className="block px-1.5 pb-1 text-[10px] text-muted-foreground">Uploaded</span>
                </button>
                <button type="button" aria-label={`Remove ${u.title}`} onClick={() => delUp.mutate(u.id)} className="absolute bottom-1 right-1 bg-black/70 p-1"><Trash2 className="h-3 w-3" /></button>
              </li>
            );
          })}
        </ul>
        <div className="mt-3 space-y-2 border border-dashed border-border p-3">
          <div className="text-sm font-medium">…or upload your own video</div>
          <label className="flex items-start gap-2 text-sm"><input type="checkbox" className="mt-1" checked={ack} onChange={(e) => setAck(e.target.checked)} />I made this, or have permission to post it.</label>
          <input ref={file} type="file" accept="video/*" className={field + " py-1.5"} disabled={!ack || upload.isPending} onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); }} />
          {upload.isPending && <p className="inline-flex items-center gap-2 text-xs text-muted-foreground"><Upload className="h-3 w-3" />Uploading…</p>}
          {upload.isError && <Note tone="err">{(upload.error as Error).message}</Note>}
        </div>
      </div>

      <div>
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">2 · Channels ({chans.size} picked)</span>
        <div className="mt-2 flex flex-wrap gap-2">
          {tab.channels.map((c) => (
            <button key={c.id} type="button" aria-pressed={chans.has(c.id)} onClick={() => toggle(chans, c.id, setChans)}
              className={`border px-3 py-2 text-sm ${chans.has(c.id) ? "border-[rgba(200,255,58,0.85)] bg-[rgba(200,255,58,0.12)]" : "border-border text-muted-foreground"}`}>{c.title}{c.platform && c.platform !== "youtube" && <span className="ml-1.5 text-[10px] uppercase opacity-70">{c.platform}</span>}</button>
          ))}
        </div>
        {chans.size > 1 && <p className="mt-1 text-xs text-muted-foreground">Each video goes to every picked channel. Posting the same video to several channels of one platform can look like spam: use different channels for different audiences. Instagram posts are always public; TikTok posts stay private until TikTok audits your app.</p>}
      </div>

      <div className="space-y-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">3 · When</span>
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="When to post">
          {([["auto", "Pick the times for me", `${tab.plan.per_day}/day, ${tab.plan.hours[0]}:00–${tab.plan.hours[1]}:00 (set above)`], ["schedule", "At a time I choose", "then spaced by the minimum gap"], ["now", "As soon as possible", "one after another"]] as const).map(([m, l, h]) => (
            <button key={m} type="button" role="radio" aria-checked={mode === m} onClick={() => setMode(m)}
              className={`border px-3 py-2 text-left text-sm ${mode === m ? "border-[rgba(200,255,58,0.85)] bg-[rgba(200,255,58,0.12)]" : "border-border text-muted-foreground"}`}>{l}<span className="block text-[11px] opacity-70">{h}</span></button>
          ))}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          {mode === "schedule" && <Label text="First post at" hint={`Your computer's clock; the tab shows times in studio time (UTC${tz >= 0 ? "+" : "−"}${Math.floor(Math.abs(tz) / 60)}:${String(Math.abs(tz) % 60).padStart(2, "0")}).`}><input type="datetime-local" className={field} value={at} onChange={(e) => setAt(e.target.value)} /></Label>}
          <Label text="Visibility"><select className={field} value={privacy} onChange={(e) => setPrivacy(e.target.value)}><option value="">Default ({tab.plan.privacy})</option><option value="private">Private</option><option value="unlisted">Unlisted</option><option value="public">Public</option></select></Label>
        </div>
      </div>
      {add.isError && <Note tone="err">{(add.error as Error).message}</Note>}
      <button type="button" className={btnPrimary} disabled={!ready || add.isPending} onClick={() => add.mutate()}>
        {add.isPending ? "Adding…" : ready ? `Queue ${total} post${total === 1 ? "" : "s"}` : "Pick videos, channels and when"}
      </button>
      {!tab.rights_ack && <p className="text-xs text-muted-foreground">Library clips post only if their source was confirmed in Auto Clip (the permission tag).</p>}
    </Card>
  );
}
