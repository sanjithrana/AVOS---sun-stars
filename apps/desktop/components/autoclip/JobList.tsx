"use client";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, ExternalLink, Loader2, Send, Square, Trash2, RotateCw } from "lucide-react";
import { Progress } from "@/components/shared/Progress";
import { autoclip, type Clip, type Job, type Overview } from "@/lib/autoclip";
import { SceneEditor } from "./SceneEditor";
import { PolishEditor } from "./PolishEditor";
import { Note, btn, btnPrimary, field, mmss } from "./ui";

function toLocal(iso?: string | null) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(+d)) return "";
  return new Date(+d - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function QueueTo({ jobId, n }: { jobId: string; n: number }) {
  const qc = useQueryClient();
  const yt = useQuery({ queryKey: ["yt"], queryFn: () => autoclip.yt(), retry: false });
  const [sel, setSel] = useState<Set<string>>(new Set());
  const add = useMutation({
    mutationFn: () => autoclip.ytAdd({ items: [{ jid: jobId, n }], channels: [...sel], mode: "auto" }),
    onSuccess: (t) => { qc.setQueryData(["yt"], t); setSel(new Set()); },
  });
  const chans = yt.data?.channels ?? [];
  if (!chans.length) return null;
  const waiting = (yt.data?.posts ?? []).filter((p) => p.status === "queued" && p.src.jid === jobId && p.src.n === n);
  return (
    <div className="space-y-2 border border-border p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Add this clip to a channel queue</div>
      <div className="flex flex-wrap gap-2">
        {chans.map((c) => (
          <button key={c.id} type="button" aria-pressed={sel.has(c.id)} onClick={() => { const x = new Set(sel); x.has(c.id) ? x.delete(c.id) : x.add(c.id); setSel(x); }}
            className={`border px-3 py-1.5 text-sm ${sel.has(c.id) ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground"}`}>
            {c.title}<span className="ml-1.5 text-[10px] uppercase opacity-70">{c.platform || "youtube"}</span>
          </button>
        ))}
        <button type="button" className={btnPrimary + " !h-9"} disabled={sel.size === 0 || add.isPending} onClick={() => add.mutate()}>{add.isPending ? "Adding…" : `Add to ${sel.size || ""} queue${sel.size === 1 ? "" : "s"}`}</button>
      </div>
      {waiting.length > 0 && <p className="text-xs text-primary">In the queue of: {waiting.map((p) => p.channel_title).join(", ")}. Times are set on the YouTube tab.</p>}
      {add.isError && <Note tone="err">{(add.error as Error).message}</Note>}
    </div>
  );
}

function QueueAll({ jobId, count }: { jobId: string; count: number }) {
  const qc = useQueryClient();
  const yt = useQuery({ queryKey: ["yt"], queryFn: () => autoclip.yt(), retry: false });
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [vis, setVis] = useState("public");
  const [gap, setGap] = useState("2");
  const [custom, setCustom] = useState("3");
  const gh = gap === "custom" ? Number(custom) : Number(gap);
  const all = useMutation({
    mutationFn: () => autoclip.ytAdd(gh <= 0.1
      ? { items: [{ jid: jobId, all: true }], channels: [...sel], mode: "drip", privacy: vis }
      : { items: [{ jid: jobId, all: true }], channels: [...sel], mode: "every", gap_hours: gh, privacy: vis }),
    onSuccess: (t) => { qc.setQueryData(["yt"], t); },
  });
  const chans = yt.data?.channels ?? [];
  if (!chans.length) return null;
  const sel_ = "h-9 border border-border bg-transparent px-2 text-sm text-foreground";
  return (
    <div className="space-y-2 border border-signal/50 p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Queue all {count} clips at once</div>
      <div className="flex flex-wrap gap-2">
        {chans.map((c) => (
          <button key={c.id} type="button" aria-pressed={sel.has(c.id)} onClick={() => { const x = new Set(sel); x.has(c.id) ? x.delete(c.id) : x.add(c.id); setSel(x); }}
            className={`border px-3 py-1.5 text-sm ${sel.has(c.id) ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground"}`}>
            {c.title}<span className="ml-1.5 text-[10px] uppercase opacity-70">{c.platform || "youtube"}</span>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-muted-foreground">Visibility
          <select value={vis} onChange={(e) => setVis(e.target.value)} className={"ml-1.5 " + sel_}>
            <option value="public">Public</option><option value="private">Private</option><option value="unlisted">Unlisted</option>
          </select>
        </label>
        <label className="text-xs text-muted-foreground">Gap between posts
          <select value={gap} onChange={(e) => setGap(e.target.value)} className={"ml-1.5 " + sel_}>
            <option value="0.05">3–5 min</option><option value="1">1 hour</option><option value="2">2 hours</option><option value="4">4 hours</option><option value="6">6 hours</option><option value="12">12 hours</option><option value="custom">Custom…</option>
          </select>
        </label>
        {gap === "custom" && <input type="number" min={0.1} max={72} step={0.5} value={custom} onChange={(e) => setCustom(e.target.value)} className="h-9 w-20 border border-border bg-transparent px-2 text-sm" aria-label="Hours between posts" />}
        <button type="button" className={btnPrimary + " !h-9"} disabled={sel.size === 0 || all.isPending || !(gh > 0)} onClick={() => all.mutate()}>{all.isPending ? "Adding…" : `Queue all ${count} clips`}</button>
      </div>
      {all.isSuccess && <p className="text-xs text-primary">{(all.data as { made: number }).made} posts queued as {vis}. The first goes out now, then one every {gh <= 0.1 ? "3–5 min" : `${gh} h`}. See them on the YouTube tab.</p>}
      {all.isError && <Note tone="err">{(all.error as Error).message}</Note>}
    </div>
  );
}

const views = (n: number) => n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}K` : String(n);

/** What the packaging team chose for this clip, and why: the top Shorts on the same topic and what they use. */
function Packaging({ job, clip }: { job: Job; clip: Clip }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const again = useMutation({ mutationFn: () => autoclip.repack(job.id, clip.n), onSuccess: (j) => qc.setQueryData(["autoclip", "job", job.id], j) });
  const pk = clip.seo;
  const r = (job.research ?? []).find((x) => x.query === pk?.query);
  return (
    <div className="space-y-2 border border-border p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Packaging{pk && <> · {pk.by === "ai" ? "written by your AI from the research" : "from the research"}{pk.query && <> · searched &ldquo;{pk.query}&rdquo;</>}</>}</span>
        <button type="button" className={btn + " !h-8 !px-3 text-xs"} disabled={again.isPending} onClick={() => again.mutate()}>{again.isPending ? "Researching…" : pk ? "Research again" : "Research now"}</button>
      </div>
      {pk ? (<>
        {pk.description && <p className="whitespace-pre-line text-xs text-muted-foreground">{pk.description}</p>}
        <div className="flex flex-wrap gap-1.5">{pk.hashtags.map((t) => <span key={t} className="border border-signal/60 px-2 py-0.5 text-xs">#{t}</span>)}{pk.mentions.map((m) => <span key={m} className="border border-sky-400/60 px-2 py-0.5 text-xs text-sky-300">{m}</span>)}</div>
        {pk.sound && (
          <p className="text-xs">
            Top sound on this topic: <span className="font-medium">♪ {pk.sound.title}{pk.sound.artist && ` · ${pk.sound.artist}`}</span> (in {pk.sound.uses} of the top Shorts).{" "}
            {pk.music_id ? <span className="text-primary">It is on your music shelf, so this clip uses it.</span> : <span className="text-muted-foreground">Apps can&apos;t attach YouTube sounds: add the track to your music shelf (if you have the rights) and it is used automatically, or pick the sound in the YouTube app after posting.</span>}
          </p>
        )}
        {r && r.analysis.examples.length > 0 && (
          <div>
            <button type="button" className="text-xs underline" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} the top Shorts it learned from ({r.analysis.examples.length})</button>
            {open && <ol className="mt-1 space-y-0.5 text-xs text-muted-foreground">{r.analysis.examples.map((e) => <li key={e.id}><a className="underline" href={`https://youtube.com/shorts/${e.id}`} target="_blank" rel="noreferrer">{e.title}</a> · {views(e.views)} views · {e.channel}</li>)}</ol>}
          </div>
        )}
      </>) : <p className="text-xs text-muted-foreground">Not researched yet. The team looks up the most-viewed Shorts on this clip&apos;s topic and picks the hashtags, mentions and sound they use.</p>}
      {again.isError && <Note tone="err">{(again.error as Error).message}</Note>}
    </div>
  );
}

/** "Today 11:49 AM", "Yesterday 6:02 PM", "Mon 24 Nov, 11:49 AM" */
export function when(iso?: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const t = d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
  const day = new Date(); day.setHours(0, 0, 0, 0);
  const diff = Math.round((day.getTime() - new Date(d).setHours(0, 0, 0, 0)) / 86400000);
  if (diff === 0) return `today ${t}`;
  if (diff === 1) return `yesterday ${t}`;
  return `${d.toLocaleDateString([], { weekday: "short", day: "numeric", month: "short", year: d.getFullYear() !== new Date().getFullYear() ? "numeric" : undefined })}, ${t}`;
}

const WHY: Record<string, string> = { visual: "Visual action", audio: "Audio", reaction: "Streamer reaction", chat: "Live chat", replay: "Replay graph", comments: "Comment timestamps", words: "Excited words" };

function ClipRow({ job, clip, ov }: { job: Job; clip: Clip; ov: Overview }) {
  const qc = useQueryClient();
  const [title, setTitle] = useState(clip.title);
  const refresh = (j: Job) => qc.setQueryData(["autoclip", "job", job.id], j);
  const edit = useMutation({ mutationFn: (b: Parameters<typeof autoclip.edit>[2]) => autoclip.edit(job.id, clip.n, b), onSuccess: refresh });
  const grant = useMutation({ mutationFn: () => autoclip.confirmPermission(job.id), onSuccess: () => { qc.invalidateQueries({ queryKey: ["autoclip"] }); qc.invalidateQueries({ queryKey: ["yt"] }); } });
  const posted = !!clip.youtube_id;
  const ready = clip.status === "ready" && !!clip.file;
  return (
    <li className="grid gap-3 border border-border p-3 md:grid-cols-[140px_1fr]">
      <div>
        {ready ? <video key={clip.rev ?? 0} src={autoclip.file(job.id, clip.file!, String(clip.rev ?? ""))} poster={clip.cover || clip.thumb ? autoclip.file(job.id, (clip.cover || clip.thumb)!, String(clip.rev ?? "")) : undefined} controls preload="none" className="aspect-[9/16] w-full bg-black object-cover" />
          : <div className="flex aspect-[9/16] w-full items-center justify-center bg-muted text-xs text-muted-foreground">Cutting…</div>}
      </div>
      <div className="min-w-0 space-y-2">
        {job.source.kind === "live" && <div><span className="inline-block border border-red-400/70 px-2 py-0.5 text-[11px] text-red-300">Live recording · {job.source.minutes ?? 20} min</span></div>}
        <div className="flex flex-wrap items-center gap-2">{job.permission && <span className={`inline-block border px-2 py-0.5 text-[11px] ${job.permission === "unconfirmed" || job.permission === "blocked" ? "border-amber-400/80 text-amber-300" : "border-signal/60"}`}>{({ own: "Yours", cc: "Creative Commons: credit the channel", granted: "Permission confirmed", unconfirmed: "Permission not confirmed: won't post", blocked: "Not clippable" } as Record<string, string>)[job.permission]}</span>}
          {!posted && (job.permission === "unconfirmed" || (!job.permission && !ov.settings.rights_ack)) && (
            <button type="button" className={btn + " !h-7 !px-3 text-xs"} disabled={grant.isPending} onClick={() => grant.mutate()}>I have permission to use this video</button>)}</div>
        <div className="text-xs text-muted-foreground">Clip {clip.n} · {mmss(clip.start)}–{mmss(clip.end)} ({Math.round(clip.end - clip.start)}s){clip.captions === false && " · no captions"}{clip.ai_score != null && ` · AI score ${clip.ai_score}/10`}</div>
        {clip.why && Object.keys(clip.why).length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs" title="How strongly each signal fired in this clip (0-100). Signals that were not available for this video are not shown.">
            <span className="text-muted-foreground">Picked for:</span>
            {Object.entries(clip.why).filter(([, v]) => v >= 0.15).slice(0, 5).map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-1 border border-border px-1.5 py-0.5"><span className="inline-block h-1.5 rounded-full bg-primary" style={{ width: `${Math.max(4, v * 28)}px` }} />{WHY[k] ?? k} {Math.round(v * 100)}</span>
            ))}
          </div>
        )}
        {(clip.moment || clip.hook) && <div className="flex flex-wrap items-center gap-2 text-xs">{clip.moment && <span className="border border-signal/60 px-2 py-0.5">{clip.moment}</span>}{clip.hook && <span className="text-muted-foreground">Hook on screen: “{clip.hook}”</span>}</div>}
        <input className={field} value={title} maxLength={95} disabled={posted} onChange={(e) => setTitle(e.target.value)} onBlur={() => title !== clip.title && edit.mutate({ title })} aria-label={`Title of clip ${clip.n}`} />
        {clip.reframe && clip.reframe.length > 0 && !posted && <SceneEditor jobId={job.id} n={clip.n} scenes={clip.reframe} onDone={refresh} />}
        {ready && !posted && !job.busy && <Packaging job={job} clip={clip} />}
        {ready && !posted && !job.busy && <PolishEditor key={clip.rev ?? 0} jobId={job.id} clip={clip} onDone={refresh} styles={ov.capabilities.edit_styles ?? { classic: "Classic", punchy: "Punchy", clean: "Clean" }} looks={ov.capabilities.looks ?? { clean: "Clean", cinematic: "Cinematic", vivid: "Vivid", warm: "Warm", cool: "Cool", mono: "Mono", film: "Film", none: "None" }} />}
        {posted ? (
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <span className="inline-flex items-center gap-1 text-primary"><CheckCircle2 className="h-4 w-4" />Posted</span>
            <a className="inline-flex items-center gap-1 underline" href={`https://youtube.com/shorts/${clip.youtube_id}`} target="_blank" rel="noreferrer">Open on YouTube <ExternalLink className="h-3 w-3" /></a>
            {clip.stats?.views != null && <span className="text-muted-foreground">{clip.stats.views} views</span>}
            {clip.retention && <span className="text-muted-foreground">{clip.retention.avg_view_pct.toFixed(0)}% watched on average</span>}
            {clip.exp && <span className="text-xs text-muted-foreground">{clip.exp.phase === "done" ? `Title test: kept ${clip.exp.result?.kept ?? "A"}` : `Title test running: title ${clip.exp.phase} now`}</span>}
          </div>
        ) : (<>
          {ready && <QueueTo jobId={job.id} n={clip.n} />}
          <div className="flex flex-wrap items-end gap-3">
            <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!clip.approved} disabled={!ready} onChange={(e) => edit.mutate({ approved: e.target.checked })} />Approved for autopilot</label>
          </div></>
        )}
        {clip.error && <Note tone="err">{clip.error}</Note>}
        {(edit.isError || grant.isError) && <Note tone="err">{((edit.error || grant.error) as Error).message}</Note>}
      </div>
    </li>
  );
}

/** Each stage with how long it took (or how long it has been running). */
function StageTimes({ j }: { j: Job }) {
  const now = Date.now() / 1000;
  const any = j.stages.some((s) => j.steps?.[s.id]?.started);
  if (!any) return null;
  return (
    <ol className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-muted-foreground">
      {j.stages.map((s) => {
        const st = j.steps?.[s.id];
        if (!st) return <li key={s.id} className="opacity-50">{s.label}</li>;
        const secs = st.secs ?? (st.status === "working" && st.started ? now - st.started : null);
        return (
          <li key={s.id} className={st.status === "working" ? "text-foreground" : ""}>
            {st.status === "done" ? "✓ " : st.status === "working" ? "● " : st.status === "error" ? "✕ " : ""}{s.label}
            {secs != null && <span className="ml-1 font-mono">{mmss(secs)}</span>}
          </li>
        );
      })}
    </ol>
  );
}

export function JobView({ id, ov, onGone }: { id: string; ov: Overview; onGone: () => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["autoclip", "job", id], queryFn: () => autoclip.job(id), refetchInterval: (s) => (s.state.data?.busy ? 2000 : false), retry: false });
  const act = useMutation({
    mutationFn: (a: "run" | "stop" | "remove"): Promise<unknown> => (a === "run" ? autoclip.run(id) : a === "stop" ? autoclip.stop(id) : autoclip.remove(id)),
    onSuccess: (_r, a) => { qc.invalidateQueries({ queryKey: ["autoclip"] }); if (a === "remove") onGone(); },
  });
  const j = q.data;
  if (q.isError) return <Note tone="err">{(q.error as Error).message}</Note>;
  if (!j) return <p className="text-sm text-muted-foreground">Loading…</p>;
  const last = j.log[j.log.length - 1];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0"><div className="truncate font-medium">{j.title}</div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground">{j.busy && <Loader2 className="h-3 w-3 animate-spin" />}{j.status === "working" ? (j.stages.find((s) => s.id === j.stage)?.label ?? "Working") : j.status === "done" ? "Ready" : j.status === "stopped" ? "Stopped" : "Stopped with an error"}{j.auto && " · made by autopilot"}{j.createdAt && <span title={new Date(j.createdAt).toLocaleString()}> · started {when(j.createdAt)}</span>}</div></div>
        <div className="flex gap-2">
          {j.busy && <button className={btn} onClick={() => act.mutate("stop")}><Square className="h-4 w-4" />Stop</button>}
          {!j.busy && j.status !== "done" && <button className={btn} onClick={() => act.mutate("run")}><RotateCw className="h-4 w-4" />Carry on</button>}
          {!j.busy && j.clips.length > 0 && j.status === "error" && <button className={btn} title="Throw away the chosen moments and start choosing again" onClick={() => autoclip.run(id, true).then(() => qc.invalidateQueries({ queryKey: ["autoclip"] }))}>Start over</button>}
          {!j.busy && <button className={btn} onClick={() => confirm("Delete this video and its clips?") && act.mutate("remove")} aria-label="Delete"><Trash2 className="h-4 w-4" /></button>}
        </div>
      </div>
      {j.error && <Note tone="err">{j.error}</Note>}
      <StageTimes j={j} />
      {j.busy && (j.progress ? <Progress pct={j.progress.pct} text={j.progress.text} since={j.createdAt} /> : <Progress text={last?.text} since={j.createdAt} />)}
      {j.clips.filter((c) => c.status === "ready" && c.file && !c.youtube_id).length > 1 && !j.busy && <QueueAll jobId={j.id} count={j.clips.filter((c) => c.status === "ready" && c.file && !c.youtube_id).length} />}
      {j.clips.length > 0 && <ul className="space-y-3">{j.clips.map((c) => <ClipRow key={c.n} job={j} clip={c} ov={ov} />)}</ul>}
    </div>
  );
}
