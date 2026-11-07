"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, Check, CheckCircle2, Copy, Download, Loader2, OctagonX, Play, RefreshCw, Trash2, TriangleAlert } from "lucide-react";
import { stickman, type Clip, type Project } from "@/lib/stickman";

const ORDER = ["topics", "brief", "story", "roster", "clips", "refs", "scenes", "animate", "voice", "finish"];

function Copy_({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); } catch { /* clipboard blocked */ } }}
      className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-1 text-xs hover:bg-accent">{done ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}{done ? "Copied" : label}</button>
  );
}

function Steps({ p }: { p: Project }) {
  const at = ORDER.indexOf(p.stage);
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5" aria-label="Progress">
      {p.stages.map((s, i) => {
        const done = p.status === "done" || i < at || (i === at && p.status === "waiting" && s.id !== "topics");
        const now = i === at && p.status === "working";
        return (
          <li key={s.id} className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs ${now ? "border-amber-500 bg-amber-500/10" : done ? "border-emerald-500/40" : "border-border text-muted-foreground"}`}>
            {done ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /> : now ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-amber-600" /> : <span className="h-4 w-4 shrink-0 rounded-full border border-border" />}
            {s.label}
          </li>
        );
      })}
    </ol>
  );
}

function Prompt({ title, text, words }: { title: string; text: string; words?: number }) {
  return (
    <details className="rounded-xl border border-border">
      <summary className="flex cursor-pointer flex-wrap items-center gap-2 px-3 py-2 text-sm font-medium">{title}{words ? <span className="text-xs font-normal text-muted-foreground">{words} words</span> : null}</summary>
      <div className="space-y-2 border-t border-border p-3"><Copy_ text={text} /><pre className="whitespace-pre-wrap text-xs text-muted-foreground">{text}</pre></div>
    </details>
  );
}

function ClipCard({ p, c, busy, onAgain }: { p: Project; c: Clip; busy: boolean; onAgain: (what: "scene" | "video", note: string) => void }) {
  const [note, setNote] = useState("");
  const story = p.story?.clips[c.n - 1];
  return (
    <article className="rounded-2xl border border-border bg-card/50 p-4 md:p-5" data-testid={`clip-${c.n}`}>
      <header className="flex flex-wrap items-center gap-2">
        <span className="rounded-lg bg-amber-500/15 px-2 py-1 text-xs font-bold text-amber-700 dark:text-amber-300">C{String(c.n).padStart(2, "0")}</span>
        <span className="text-sm font-semibold">{c.t0}-{c.t1} s</span>
        <span className="text-xs text-muted-foreground">{c.location}, {c.time_of_day}</span>
        {c.engine && <span className="ml-auto rounded-full border border-border px-2.5 py-1 text-xs">{c.engine === "ai_video" ? "AI video" : c.engine === "blender" ? "3D" : "Picture + camera move"}</span>}
      </header>
      <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,200px)]">
        <div className="space-y-3 text-sm">
          <p><span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Narration</span><br />{story?.narration}</p>
          {c.narration_warning && <p className="flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-300"><TriangleAlert className="h-3.5 w-3.5" />{c.narration_warning}</p>}
          {c.voice_warning && <p className="flex items-center gap-1.5 text-xs text-amber-700 dark:text-amber-300"><TriangleAlert className="h-3.5 w-3.5" />{c.voice_warning}</p>}
          <ol className="space-y-1 text-xs text-muted-foreground">
            {(["hook", "main", "reaction", "outcome"] as const).map((k, i) => <li key={k}><b>{["0-2 s", "2-5 s", "5-8 s", "8-10 s"][i]}</b> {c.beats[k]}</li>)}
          </ol>
          <p className="text-xs text-muted-foreground">Ends: {c.outgoing.summary} · next clip: {c.transition === "match" ? "matches this last frame" : `cut${c.transition_note ? ` (${c.transition_note})` : ""}`}</p>
          {c.video_note && <p className="text-xs text-amber-700 dark:text-amber-300">{c.video_note}</p>}
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-1">
          {c.scene ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={stickman.file(p.id, c.scene, c.version ?? 1)} alt={`Clip ${c.n} scene`} className="w-full rounded-xl bg-muted" /> : <div className="flex aspect-[9/16] items-center justify-center rounded-xl bg-muted text-xs text-muted-foreground">Made after you approve the sheets</div>}
          {c.video && <video src={stickman.file(p.id, c.video, c.version ?? 1)} controls muted playsInline className="w-full rounded-xl bg-black" />}
        </div>
      </div>
      <div className="mt-4 space-y-2">
        <Prompt title="Scene-image prompt" text={c.scene_prompt} words={c.words.scene} />
        <Prompt title="10-second animation prompt" text={c.animation_prompt} words={c.words.animation} />
      </div>
      {c.scene && (
        <footer className="mt-4 flex flex-wrap items-center gap-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="What should change in the picture? (optional)" className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm" />
          <button type="button" disabled={busy} onClick={() => { onAgain("scene", note); setNote(""); }} className="rounded-full border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50">New scene image</button>
          <button type="button" disabled={busy || !c.video} onClick={() => onAgain("video", "")} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50"><RefreshCw className="h-4 w-4" />Animate again</button>
        </footer>
      )}
    </article>
  );
}

export function ProjectView({ id }: { id: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["stickman", id], queryFn: () => stickman.get(id), refetchInterval: (s) => (s.state.data?.busy || s.state.data?.status === "working" ? 2000 : 6000), retry: false });
  const p = q.data;
  const set = (np: Project) => qc.setQueryData(["stickman", id], np);
  const [draft, setDraft] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  useEffect(() => { if (p?.status !== "waiting") setDraft({}); }, [p?.status]);

  const act = useMutation({ mutationFn: (f: () => Promise<Project | { ok: true }>) => f(), onSuccess: (r) => { if ("id" in r) set(r as Project); else qc.invalidateQueries({ queryKey: ["stickman", id] }); } });
  const approve = useMutation({ mutationFn: async () => { if (Object.keys(draft).length) await stickman.editNarration(id, draft); return stickman.approve(id); }, onSuccess: (np) => { set(np); setDraft({}); } });
  const saveNarr = useMutation({ mutationFn: () => stickman.editNarration(id, draft), onSuccess: (np) => { set(np); setDraft({}); } });
  const del = useMutation({ mutationFn: () => stickman.remove(id), onSuccess: () => router.push("/stickman") });

  if (q.isError) return <p className="m-8 rounded-2xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm">{(q.error as Error).message}</p>;
  if (!p) return <div className="flex justify-center p-16"><Loader2 className="h-6 w-6 animate-spin" /></div>;
  const running = p.status === "working";
  const atTopics = p.status === "waiting" && p.stage === "topics";
  const atRefs = p.status === "waiting" && p.stage === "refs";
  const err = act.error || approve.error || saveNarr.error;

  return (
    <div className="mx-auto max-w-4xl space-y-8 px-4 py-8 md:px-8">
      <div>
        <Link href="/stickman" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />All videos</Link>
        <div className="mt-2 flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold" data-testid="stickman-title">{p.title}</h1>
            <p className="text-sm text-muted-foreground">{p.project?.date_place || "Choosing an event"} · {p.clip_count} clips × 10 s · {p.aspect}</p>
          </div>
          {running && <button type="button" onClick={() => act.mutate(() => stickman.cancel(id))} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm hover:bg-accent"><OctagonX className="h-4 w-4" />Stop</button>}
          <button type="button" aria-label="Delete" onClick={() => { if (window.confirm("Delete this video and all its files?")) del.mutate(); }} className="rounded-full border border-border px-3 py-2 text-muted-foreground hover:bg-accent"><Trash2 className="h-4 w-4" /></button>
        </div>
      </div>

      <Steps p={p} />

      {(p.status === "error" || p.status === "stopped") && (
        <div className="rounded-2xl border border-red-500/40 bg-red-500/5 p-5" role="alert">
          <p className="flex items-center gap-2 font-semibold"><AlertCircle className="h-5 w-5 text-red-600" />{p.status === "stopped" ? "Stopped" : "This step did not finish"}</p>
          {p.error && <p className="mt-1 text-sm text-muted-foreground">{p.error}</p>}
          <p className="mt-1 text-sm text-muted-foreground">Everything already made is kept. Continue picks up where it stopped.</p>
          <button type="button" onClick={() => act.mutate(() => stickman.resume(id))} className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-4 py-2 text-sm font-semibold text-white"><Play className="h-4 w-4" />Continue</button>
        </div>
      )}

      {atTopics && p.topics && (
        <section data-testid="stickman-topics">
          <h2 className="text-lg font-semibold">Which topic would you like to make?</h2>
          <p className="mt-1 text-sm text-muted-foreground">Recommended: <b>{p.topics.topics[p.topics.recommended]?.title}</b>. {p.topics.why}</p>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {p.topics.topics.map((t, i) => (
              <article key={t.title} className={`flex flex-col rounded-2xl border p-4 ${i === p.topics!.recommended ? "border-amber-500 bg-amber-500/5" : "border-border bg-card/50"}`}>
                <p className="font-semibold">{t.title}{i === p.topics!.recommended && <span className="ml-2 rounded-full bg-amber-500 px-2 py-0.5 text-[10px] font-bold text-white">RECOMMENDED</span>}</p>
                <p className="text-xs text-muted-foreground">{t.date_place} · {t.clips} clips · {t.duration_s} s · {t.difficulty}</p>
                <p className="mt-2 text-sm">{t.premise}</p>
                <p className="mt-2 text-xs text-muted-foreground"><b>First 2 seconds:</b> {t.opening_visual}</p>
                <p className="mt-1 text-xs text-muted-foreground"><b>Conflict:</b> {t.conflict}</p>
                <p className="mt-1 text-xs text-muted-foreground"><b>Ending:</b> {t.ending}</p>
                <button type="button" onClick={() => act.mutate(() => stickman.pick(id, i))} className="mt-4 self-start rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2 text-sm font-semibold text-white" data-testid={`pick-${i}`}>Make this one</button>
              </article>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Want different ideas? e.g. more from Asia, nothing about war" className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm" />
            <button type="button" onClick={() => { act.mutate(() => stickman.moreTopics(id, note)); setNote(""); }} className="rounded-full border border-border px-3 py-2 text-sm hover:bg-accent">Eight new ideas</button>
          </div>
        </section>
      )}

      {atRefs && (
        <div className="rounded-2xl border border-sky-500/40 bg-sky-500/5 p-5">
          <p className="font-semibold">Check the character sheets before any scene is made</p>
          <p className="mt-1 text-sm text-muted-foreground">Compare each sheet with its identity paragraph below. If a design is off, fix the wording in the package or approve anyway; scenes and video are the paid steps. You can also edit the narration here.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" disabled={approve.isPending} onClick={() => approve.mutate()} className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-5 py-2.5 font-semibold text-white disabled:opacity-60" data-testid="stickman-approve">
              {approve.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}Approve and make the video</button>
            {Object.keys(draft).length > 0 && <button type="button" onClick={() => saveNarr.mutate()} className="rounded-full border border-border px-4 py-2.5 text-sm hover:bg-accent">Save narration changes</button>}
          </div>
        </div>
      )}
      {err && <p className="rounded-2xl border border-red-500/40 bg-red-500/5 p-3 text-sm" role="alert">{(err as Error).message}</p>}

      {p.final && (
        <section className="rounded-3xl border border-emerald-500/40 bg-emerald-500/5 p-5 md:p-6" data-testid="stickman-final">
          <h2 className="text-lg font-semibold">Your video is ready</h2>
          <div className="mt-4 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <video src={stickman.file(id, p.final, p.updatedAt)} controls playsInline className={`rounded-2xl bg-black ${p.aspect === "16:9" ? "w-full" : "max-h-[70vh]"}`} />
            <div className="space-y-2 text-sm">
              <p className="text-muted-foreground">{p.finalSeconds}s, with voice and word-by-word captions.</p>
              <a href={stickman.file(id, p.final)} download className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-4 py-2 font-semibold text-white"><Download className="h-4 w-4" />Download MP4</a>
            </div>
          </div>
        </section>
      )}

      {p.brief && (
        <section>
          <h2 className="text-lg font-semibold">Fact brief</h2>
          <p className="mt-2 flex items-start gap-2 rounded-2xl border border-amber-500/40 bg-amber-500/5 p-3 text-sm text-amber-800 dark:text-amber-200" data-testid="verification-banner">
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" />Verification pending. This studio did not check any source. Confirm each claim against the sources named below before you publish.</p>
          <div className="mt-3 space-y-3 rounded-2xl border border-border bg-card/50 p-4 text-sm">
            <p><b>{p.brief.event}</b> · {p.brief.date} · {p.brief.location}</p>
            <p><b>Cause:</b> {p.brief.cause}</p><p><b>Turning point:</b> {p.brief.turning_point}</p><p><b>Outcome:</b> {p.brief.outcome}</p>
            <ul className="list-disc space-y-1 pl-5">{p.brief.facts.map((f) => <li key={f.claim}>{f.claim} <span className={`text-xs ${f.confidence === "check" ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground"}`}>({f.confidence})</span></li>)}</ul>
            {p.brief.disputed.length > 0 && <p><b>Sources disagree on:</b> {p.brief.disputed.join("; ")}</p>}
            <p><b>Sources to check:</b> {p.brief.sources_to_check.join("; ") || "none suggested"}</p>
            {p.brief.dramatization_notes.length > 0 && <p><b>Staging, not record:</b> {p.brief.dramatization_notes.join("; ")}</p>}
          </div>
        </section>
      )}

      {p.story && (
        <section>
          <h2 className="text-lg font-semibold">Story and narration</h2>
          <div className="mt-3 space-y-3">
            {p.story.clips.map((c) => (
              <label key={c.n} className="block rounded-2xl border border-border bg-card/50 p-3 text-sm">
                <span className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">C{String(c.n).padStart(2, "0")} · {c.t0}-{c.t1} s · {c.purpose}</span>
                <textarea rows={2} disabled={!atRefs} value={draft[String(c.n)] ?? c.narration} onChange={(e) => setDraft((d) => ({ ...d, [String(c.n)]: e.target.value }))}
                  className="mt-1 w-full resize-none rounded-xl border border-border bg-background p-2.5 disabled:opacity-80" />
              </label>
            ))}
          </div>
        </section>
      )}

      {p.roster && (
        <section>
          <h2 className="text-lg font-semibold">Characters</h2>
          <div className="mt-3 grid grid-cols-1 gap-4">
            {p.roster.map((c) => (
              <figure key={c.id} className="overflow-hidden rounded-2xl border border-border bg-card/50">
                {p.assets[`sheet:${c.id}`] ? /* eslint-disable-next-line @next/next/no-img-element */ <img src={stickman.file(id, p.assets[`sheet:${c.id}`])} alt={`${c.name} reference sheet`} className="w-full bg-muted" />
                  : <div className="flex aspect-video items-center justify-center bg-muted text-xs text-muted-foreground">{p.stage === "refs" && running ? "Drawing the reference sheet…" : "Reference sheet comes next"}</div>}
                <figcaption className="space-y-1 p-4 text-sm">
                  <p><b>{c.id} · {c.name}</b> <span className="text-muted-foreground">{c.role}</span></p>
                  <p className="flex flex-wrap gap-1.5">{c.accents.map((a) => <span key={a.hex} className="inline-flex items-center gap-1 rounded-full border border-border px-2 py-0.5 text-xs"><span className="h-3 w-3 rounded-full border border-border" style={{ background: a.hex }} />{a.name} {a.hex}</span>)}</p>
                  <p className="text-xs text-muted-foreground">{c.head_shape}; {c.hair_or_headwear}; {c.clothing}; prop: {c.signature_prop}; {c.distinguishing_feature}</p>
                </figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {p.clips.length > 0 && (
        <section>
          <h2 className="text-lg font-semibold">Clips</h2>
          <div className="mt-3 space-y-4">
            {p.clips.map((c) => <ClipCard key={c.n} p={p} c={c} busy={running || p.busy} onAgain={(what, n) => act.mutate(() => stickman.clipAgain(id, c.n, what, n))} />)}
          </div>
        </section>
      )}

      {p.clips.length > 0 && (
        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Continuity and the written package</h2>
          <ul className="space-y-1 text-sm" data-testid="continuity">
            {(p.continuity?.issues ?? []).length === 0 ? <li className="text-emerald-700 dark:text-emerald-300">No continuity problems found by the automatic check.</li>
              : p.continuity!.issues.map((i, k) => <li key={k} className={i.level === "info" ? "text-muted-foreground" : "text-amber-700 dark:text-amber-300"}>{i.clip}: {i.text}</li>)}
          </ul>
          {p.consistency && <Prompt title="Character consistency agent instructions (paste into any image or video tool)" text={p.consistency} />}
          <a href={stickman.packageUrl(id)} download className="inline-flex items-center gap-1.5 rounded-full border border-border px-4 py-2 text-sm hover:bg-accent"><Download className="h-4 w-4" />Download the written package (Markdown)</a>
        </section>
      )}

      <details className="rounded-2xl border border-border p-4 text-sm" open={running}>
        <summary className="cursor-pointer font-medium">What the studio is doing</summary>
        <ul className="mt-3 space-y-1.5">{[...p.log].reverse().slice(0, 40).map((l, i) => <li key={i} className={l.kind === "error" ? "text-red-600" : l.kind === "warn" ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground"}>{l.text}</li>)}</ul>
      </details>
    </div>
  );
}
