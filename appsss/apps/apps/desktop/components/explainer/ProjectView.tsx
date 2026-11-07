"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, ArrowLeft, Check, CheckCircle2, Download, Loader2, OctagonX, Play, RotateCcw, Trash2 } from "lucide-react";
import Link from "next/link";
import { explainer, type Project, type Shot } from "@/lib/explainer";
import { ShotCard } from "./ShotCard";
import { Scenes, Timeline } from "./Views";
import { FadeImg } from "./FadeImg";

const ORDER = ["plan", "design", "board", "shoot", "finish"] as const;
const NEXT_HELP: Record<string, string> = {
  plan: "Read the script and shot list below. Change any line or pick how a shot is made, then approve.",
  design: "These are the characters, set and props every picture is drawn from. Redraw any you don't like, then approve to draw the storyboard.",
  board: "These are the pictures every shot starts from. Redo any you don't like, then approve to make the video.",
};

function Steps({ p }: { p: Project }) {
  const at = ORDER.indexOf(p.stage);
  const total = p.stages.length || 5;
  const pct = p.status === "done" ? 100 : Math.round(((at + (p.status === "working" ? 0.5 : p.status === "waiting" ? 1 : 0)) / total) * 100);
  const live = p.status === "working" ? [...p.log].reverse().find((l) => l.kind !== "error")?.text : null;
  return (
    <div className="space-y-3">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
        <div className="h-full rounded-full bg-gradient-to-r from-amber-500 to-orange-500 transition-[width] duration-700 ease-out" style={{ width: `${Math.max(4, pct)}%` }} />
      </div>
      {live && <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-live="polite" data-testid="explainer-live"><span className="relative flex h-2 w-2"><span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-500/60" /><span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" /></span><span key={live} className="animate-in fade-in duration-300">{live}</span></p>}
      <Stepper p={p} at={at} />
    </div>
  );
}

function Stepper({ p, at }: { p: Project; at: number }) {
  return (
    <ol className="grid grid-cols-2 gap-2 sm:grid-cols-5" aria-label="Progress">
      {p.stages.map((s, i) => {
        const done = p.status === "done" || i < at || (i === at && p.status === "waiting");
        const now = i === at && p.status === "working";
        return (
          <li key={s.id} className={`flex items-center gap-2 rounded-xl border px-3 py-2 text-xs transition-colors duration-500 ${now ? "border-amber-500 bg-amber-500/10" : done ? "border-emerald-500/40" : "border-border text-muted-foreground"}`}>
            {done ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" /> : now ? <Loader2 className="h-4 w-4 shrink-0 animate-spin text-amber-600" /> : <span className="h-4 w-4 shrink-0 rounded-full border border-border" />}
            {s.label}
          </li>
        );
      })}
    </ol>
  );
}

function Brief({ text, meta }: { text: string; meta: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 160;
  return (
    <div className="text-sm text-muted-foreground">
      <p className={!open && long ? "line-clamp-2 whitespace-pre-line" : "whitespace-pre-line"}>{text}</p>
      <p className="mt-1 text-xs">{meta}{long && <button type="button" onClick={() => setOpen(!open)} className="ml-2 underline" data-testid="brief-toggle">{open ? "Show less" : "See more"}</button>}</p>
    </div>
  );
}

function DirectPanel({ onGo, busy }: { onGo: (note: string, scope: "story" | "look") => void; busy: boolean }) {
  const [note, setNote] = useState("");
  const go = (scope: "story" | "look") => { onGo(note.trim(), scope); setNote(""); };
  return (
    <section className="rounded-2xl border border-border p-4" data-testid="direct-panel">
      <h2 className="font-semibold">Direct this</h2>
      <p className="mt-1 text-sm text-muted-foreground">Tell the studio what to change. The voice and music you already have are kept.</p>
      <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} data-testid="direct-note"
        placeholder="e.g. make the whole film a vivid magenta and sky-blue palette · or · open with a stronger question"
        className="mt-3 w-full resize-none rounded-xl border border-border bg-background p-3 text-sm outline-none focus:border-amber-500" />
      <div className="mt-2 flex flex-wrap gap-2">
        <button type="button" disabled={busy || note.trim().length < 3} onClick={() => go("look")} className="rounded-full bg-amber-500 px-4 py-2 text-sm font-semibold text-white transition active:scale-[0.98] disabled:opacity-50">Change the look (redraw everything)</button>
        <button type="button" disabled={busy || note.trim().length < 3} onClick={() => go("story")} className="rounded-full border border-border px-4 py-2 text-sm transition hover:bg-accent disabled:opacity-50">Change the story or script</button>
      </div>
    </section>
  );
}

export function ProjectView({ id }: { id: string }) {
  const router = useRouter();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["explainer", id], queryFn: () => explainer.get(id), refetchInterval: (s) => (s.state.data?.busy || s.state.data?.status === "working" ? 2000 : 6000), retry: false });
  const p = q.data;
  const set = (np: Project) => qc.setQueryData(["explainer", id], np);
  const [draft, setDraft] = useState<Record<string, Partial<Shot>>>({});
  const [note, setNote] = useState("");
  const [view, setView] = useState<"shots" | "scenes" | "timeline">("shots");
  const dirty = Object.keys(draft).length > 0;
  useEffect(() => { if (p?.status !== "waiting") setDraft({}); }, [p?.status]);

  const save = useMutation({ mutationFn: (shots: Shot[]) => explainer.patch(id, { plan: { shots } }), onSuccess: (np) => { set(np); setDraft({}); } });
  const approve = useMutation({ mutationFn: async () => {
    if (dirty && p?.plan) await explainer.patch(id, { plan: { shots: p.plan.shots.map((s) => ({ ...s, ...draft[s.id] })) } });
    return explainer.approve(id);
  }, onSuccess: (np) => { set(np); setDraft({}); } });
  const act = useMutation({ mutationFn: (f: () => Promise<Project | { ok: true }>) => f(), onSuccess: (r) => { if ("id" in r) set(r as Project); else qc.invalidateQueries({ queryKey: ["explainer", id] }); } });
  const del = useMutation({ mutationFn: () => explainer.remove(id), onSuccess: () => router.push("/explainer") });

  const shots = useMemo(() => (p?.plan?.shots ?? []).map((s) => ({ ...s, ...draft[s.id] })), [p, draft]);
  if (q.isError) return <p className="m-8 rounded-2xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm">{(q.error as Error).message}</p>;
  if (!p) return (
    <div className="mx-auto max-w-4xl space-y-6 px-4 py-8 md:px-8" aria-busy="true">
      <div className="h-8 w-2/3 animate-pulse rounded-lg bg-muted" />
      <div className="h-1.5 animate-pulse rounded-full bg-muted" />
      <div className="grid grid-cols-5 gap-2">{Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-9 animate-pulse rounded-xl bg-muted" />)}</div>
      <div className="h-64 animate-pulse rounded-2xl bg-muted" />
    </div>
  );

  const gate = p.status === "waiting" ? (p.stage === "plan" ? "plan" : p.stage === "design" ? "design" : "board") : null;
  const running = p.status === "working";
  const err = act.error || approve.error || save.error;

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-4 py-8 animate-in fade-in duration-500 md:px-8">
      <div>
        <Link href="/explainer" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"><ArrowLeft className="h-4 w-4" />All videos</Link>
        <div className="mt-2 flex flex-wrap items-start gap-3">
          <div className="min-w-0 flex-1">
            <h1 className="text-2xl font-bold" data-testid="explainer-title">{p.title || p.brief}</h1>
            <Brief text={p.brief} meta={`${p.totalSeconds || p.seconds}s · ${p.aspect}`} />
            {p.source && <a href={p.source.url} target="_blank" rel="noreferrer" className="text-xs text-amber-700 underline dark:text-amber-300">Source: {p.source.title}</a>}
          </div>
          {running && <button type="button" onClick={() => act.mutate(() => explainer.cancel(id))} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm hover:bg-accent"><OctagonX className="h-4 w-4" />Stop</button>}
          <button type="button" onClick={() => { if (window.confirm("Delete this video and all its files?")) del.mutate(); }} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm text-muted-foreground hover:bg-accent" aria-label="Delete"><Trash2 className="h-4 w-4" /></button>
        </div>
      </div>

      <Steps p={p} />

      {(p.status === "error" || p.status === "stopped") && (
        <div className="rounded-2xl border border-red-500/40 bg-red-500/5 p-5" role="alert">
          <p className="flex items-center gap-2 font-semibold"><AlertCircle className="h-5 w-5 text-red-600" />{p.status === "stopped" ? "Stopped" : "This step did not finish"}</p>
          {p.error && <p className="mt-1 text-sm text-muted-foreground">{p.error}</p>}
          <p className="mt-1 text-sm text-muted-foreground">Everything already made is kept. Continue picks up where it stopped.</p>
          <button type="button" onClick={() => act.mutate(() => explainer.resume(id))} className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-4 py-2 text-sm font-semibold text-white"><Play className="h-4 w-4" />Continue</button>
        </div>
      )}

      {gate && (
        <div className="sticky top-2 z-20 animate-in fade-in slide-in-from-top-2 rounded-2xl border border-sky-500/40 bg-background/90 p-5 shadow-lg backdrop-blur duration-300">
          <p className="font-semibold">{gate === "plan" ? "Step 1 of 3: approve the script" : gate === "design" ? "Step 2 of 3: approve the characters and backgrounds" : "Step 3 of 3: approve the scene storyboard"}</p>
          <p className="mt-1 text-sm text-muted-foreground">{NEXT_HELP[gate]}</p>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <button type="button" disabled={approve.isPending} onClick={() => approve.mutate()} className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-amber-500 to-orange-500 px-5 py-2.5 font-semibold text-white disabled:opacity-60" data-testid="explainer-approve">
              {approve.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}{gate === "plan" ? "Approve and draw the characters" : gate === "design" ? "Approve and draw the storyboard" : "Approve and make the video"}
            </button>
            {gate === "plan" && dirty && <button type="button" onClick={() => save.mutate(shots)} className="rounded-full border border-border px-4 py-2.5 text-sm hover:bg-accent">Save changes</button>}
          </div>
          {gate === "plan" && (
            <div className="mt-3 flex flex-wrap gap-2">
              <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Or tell the writer what to change, e.g. make it funnier, shorter hook" className="min-w-0 flex-1 rounded-xl border border-border bg-background px-3 py-2 text-sm" />
              <button type="button" disabled={!note.trim()} onClick={() => { act.mutate(() => explainer.redoPlan(id, note)); setNote(""); }} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-2 text-sm hover:bg-accent disabled:opacity-50"><RotateCcw className="h-4 w-4" />Write again</button>
            </div>
          )}
        </div>
      )}
      {err && <p className="rounded-2xl border border-red-500/40 bg-red-500/5 p-3 text-sm" role="alert">{(err as Error).message}</p>}

      {p.final && (
        <section className="animate-in fade-in zoom-in-95 rounded-3xl border border-emerald-500/40 bg-emerald-500/5 p-5 duration-500 md:p-6" data-testid="explainer-final">
          <h2 className="text-lg font-semibold">Your video is ready</h2>
          <div className="mt-4 flex flex-col items-center gap-4 sm:flex-row sm:items-start">
            <video src={explainer.file(id, p.final, p.updatedAt)} controls playsInline className={`rounded-2xl bg-black ${p.aspect === "16:9" ? "w-full" : "max-h-[70vh]"}`} />
            <div className="space-y-2 text-sm">
              <p className="text-muted-foreground">{p.finalSeconds}s, with voice and word-by-word captions.</p>
              <a href={explainer.file(id, p.final)} download className="inline-flex items-center gap-1.5 rounded-full bg-amber-500 px-4 py-2 font-semibold text-white"><Download className="h-4 w-4" />Download MP4</a>
            </div>
          </div>
        </section>
      )}

      <div className="xl:grid xl:grid-cols-[minmax(0,1fr)_320px] xl:gap-6">
        <div className="space-y-6">
          {shots.length > 0 && (
            <div className="flex flex-wrap items-center gap-1 rounded-xl border border-border p-1 text-sm" role="tablist" aria-label="View" data-testid="view-tabs">
              {([["shots", "Shots"], ["scenes", "Scenes"], ["timeline", "Timeline"]] as const).map(([v, l]) => (
                <button key={v} type="button" role="tab" aria-selected={view === v} onClick={() => setView(v)}
                  className={`rounded-full px-4 py-1.5 transition-colors ${view === v ? "bg-amber-500 text-white" : "text-muted-foreground hover:bg-accent"}`}>{l}</button>
              ))}
            </div>
          )}

          {p.research && view === "shots" && (
            <details className="rounded-2xl border border-border bg-card/50 p-4 text-sm" open={p.research.status === "ok" && !shots.length} data-testid="research-panel">
              <summary className="cursor-pointer text-base font-semibold">
                Research{p.research.status === "ok" ? ` · ${p.research.facts.length} facts from ${p.research.sources.length} sources` : " · skipped"}
              </summary>
              {p.research.status !== "ok" ? (
                <p className="mt-3 text-muted-foreground">The script was written without checked facts: {p.research.reason || "no reason given"}.</p>
              ) : (
                <div className="mt-3 space-y-3">
                  <ul className="space-y-2">
                    {p.research.facts.map((f, i) => (
                      <li key={i} className="flex gap-2"><span className="text-amber-600">✓</span>
                        <span>{f.fact} <a href={f.source.url} target="_blank" rel="noreferrer" className="whitespace-nowrap text-xs text-muted-foreground underline">{f.source.title}</a></span></li>
                    ))}
                  </ul>
                  {p.research.misconceptions.length > 0 && <p><b>Common mistakes:</b> {p.research.misconceptions.join(" · ")}</p>}
                  {p.research.unknowns.length > 0 && <p><b>Still uncertain:</b> {p.research.unknowns.join(" · ")}</p>}
                </div>
              )}
            </details>
          )}

          {(p.board || p.contact) && view === "shots" && (
            <section>
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold">{p.board ? "Production storyboard" : "Storyboard"}</h2>
                {p.board && <a href={explainer.file(id, p.board, p.updatedAt)} target="_blank" rel="noreferrer" download={`${p.title || "storyboard"}.png`} className="inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-sm transition hover:bg-accent"><Download className="h-4 w-4" />Open full size</a>}
              </div>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={explainer.file(id, (p.board || p.contact) as string, p.updatedAt)} alt="Storyboard: key visual, every shot with action, camera, lighting and mood, characters, set and palette" className="mt-3 w-full animate-in fade-in rounded-2xl border border-border duration-500" data-testid="storyboard-overview" />
            </section>
          )}

          {view === "scenes" && <Scenes p={p} shots={shots} />}
          {view === "timeline" && <Timeline p={p} shots={shots} />}

          {shots.length > 0 && (
            <section className={view === "shots" ? "" : "hidden"}>
              <h2 className="text-lg font-semibold">Shots</h2>
              <div className="mt-3 space-y-4">
                {shots.map((s) => (
                  <ShotCard key={s.id} p={p} shot={s} editable={gate === "plan"} busy={running || p.busy}
                    onEdit={(patch) => setDraft((d) => ({ ...d, [s.id]: { ...d[s.id], ...patch } }))}
                    onAgain={(what, n, extra) => act.mutate(() => explainer.shotAgain(id, s.id, what, n, undefined, extra))}
                    onRate={(up, n) => act.mutate(() => explainer.rate(id, s.id, up, n))} />
                ))}
              </div>
            </section>
          )}
        </div>

        <aside className="mt-6 space-y-6 xl:mt-0 xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:self-start xl:overflow-y-auto">
          {p.plan && (
            <section data-testid="assets-panel">
              <h2 className="text-lg font-semibold">Characters &amp; world</h2>
              {p.plan.palette && p.plan.palette.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-2" data-testid="palette">
                  {p.plan.palette.map((c) => (
                    <span key={c.hex} title={`${c.name} ${c.hex}`} className="inline-flex items-center gap-1.5 rounded-full border border-border px-2 py-1 text-[11px]">
                      <span className="h-3.5 w-3.5 rounded-full border border-black/10" style={{ background: c.hex }} />{c.name}</span>
                  ))}
                </div>
              )}
              <div className="mt-3 grid grid-cols-2 gap-3 xl:grid-cols-1">
                {[...(p.assets.poster ? [{ key: "poster", name: p.plan.title, look: p.plan.logline || "", kind: "Key visual" }] : []), ...p.plan.characters.map((c) => ({ key: `char:${c.id}`, name: c.name, look: c.look, kind: "Character" })),
                  ...p.plan.props.map((x) => ({ key: `prop:${x.id}`, name: x.name, look: x.look, kind: "Prop" })),
                  { key: "world", name: p.plan.world.name, look: p.plan.world.look, kind: "Set" }].map((a) => (
                  <figure key={a.key} className="overflow-hidden rounded-2xl border border-border bg-card/50 transition-shadow duration-300 hover:shadow-md">
                    {p.assets[a.key] ? <FadeImg src={explainer.file(id, p.assets[a.key])} alt={a.name} className="w-full bg-muted" />
                      : <div className={`flex aspect-video items-center justify-center bg-muted text-xs text-muted-foreground ${p.stage === "design" && running ? "animate-pulse" : ""}`}>{p.stage === "design" && running ? "Drawing…" : "Drawn after you approve the script"}</div>}
                    <figcaption className="p-3 text-sm"><span className="text-xs uppercase tracking-wider text-muted-foreground">{a.kind}</span><br /><b>{a.name}</b><span className="block text-xs text-muted-foreground">{a.look}</span>
                      {gate === "design" && p.assets[a.key] && (
                        <button type="button" disabled={act.isPending} onClick={() => { const n = window.prompt("What should change? (optional)", "") ?? null; if (n !== null) act.mutate(() => explainer.redoAsset(id, a.key, n)); }}
                          className="mt-2 inline-flex items-center gap-1.5 rounded-full border border-border px-2.5 py-1 text-xs hover:bg-accent" data-testid={`redo-${a.key}`}><RotateCcw className="h-3.5 w-3.5" />Redraw</button>
                      )}</figcaption>
                  </figure>
                ))}
              </div>
            </section>
          )}
          {p.plan && !running && !p.busy && p.status !== "waiting" && (
            <DirectPanel busy={act.isPending} onGo={(note, scope) => act.mutate(() => explainer.direct(id, note, scope))} />
          )}
        </aside>
      </div>

      <details className="rounded-2xl border border-border p-4 text-sm" open={running}>
        <summary className="cursor-pointer font-medium">What the studio is doing</summary>
        <ul className="mt-3 space-y-1.5">
          {[...p.log].reverse().slice(0, 40).map((l, i) => <li key={i} className={l.kind === "error" ? "text-red-600" : l.kind === "warn" ? "text-amber-700 dark:text-amber-300" : "text-muted-foreground"}>{l.text}</li>)}
        </ul>
      </details>
    </div>
  );
}
