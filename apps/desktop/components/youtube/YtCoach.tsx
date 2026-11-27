"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, Loader2, RefreshCw } from "lucide-react";
import { autoclip, type CoachChange, type CoachRow, type CoachView, type RetentionSummary } from "@/lib/autoclip";
import { Card, Note, Switch, btn, btnPrimary } from "@/components/autoclip/ui";

const MODES: [string, string, string][] = [
  ["off", "Off", "Nothing changes by itself."],
  ["suggest", "Suggest", "It studies your posts and tells you what works. You decide."],
  ["auto", "Auto", "It also picks each new clip's recipe (when “Let the coach choose” is on in Make clips)."],
];
const nice = (v: string | boolean) => (v === true ? "on" : v === false ? "off" : String(v));

function Table({ title, rows }: { title: string; rows: CoachRow[] }) {
  const best = Math.max(...rows.filter((r) => r.mean != null).map((r) => r.mean as number), -99);
  return (
    <div className="border border-border p-3">
      <div className="mb-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">{title}</div>
      <table className="w-full text-xs">
        <thead><tr className="text-left text-muted-foreground"><th className="py-1 font-normal">Choice</th><th className="font-normal">Clips</th><th className="font-normal">Avg views</th><th className="text-right font-normal">Score</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={nice(r.option)} className={r.mean != null && r.mean === best && r.n >= 2 ? "text-primary" : ""}>
            <td className="py-1">{nice(r.option)}</td><td>{r.n}</td><td>{r.avg_views ?? "–"}</td><td className="text-right tabular-nums">{r.mean == null ? "–" : r.mean.toFixed(2)}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}

function Curve({ r }: { r: RetentionSummary }) {
  const pts = r.curve.map((v, i) => `${(i / 19) * 100},${40 - Math.min(1, v) * 38}`).join(" ");
  return (
    <div className="border border-border p-3">
      <div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Where viewers stay ({r.n} clips)</div>
      <svg viewBox="0 0 100 42" className="h-24 w-full" role="img" aria-label="Share of viewers still watching through a clip" preserveAspectRatio="none"><polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.6" vectorEffect="non-scaling-stroke" className="text-primary" /></svg>
      <div className="flex justify-between text-[11px] text-muted-foreground"><span>start</span><span>end of clip</span></div>
      <p className="mt-1 text-xs">On average {r.avg_view_pct.toFixed(0)}% of each clip is watched. {(r.early_hold * 100).toFixed(0)}% are still there 15% in; {(r.end_hold * 100).toFixed(0)}% at 90%.</p>
    </div>
  );
}

const nice2 = (v: string | boolean | null) => (v === true ? "on" : v === false ? "off" : v == null ? "–" : String(v));

function Changes({ rows, onUndo, busy }: { rows: CoachChange[]; onUndo: (id: string) => void; busy: boolean }) {
  if (!rows.length) return null;
  return (
    <details className="border border-border p-3">
      <summary className="cursor-pointer text-sm">What the coach changed ({rows.length})</summary>
      <ul className="mt-3 space-y-2 text-sm">
        {rows.map((r) => (
          <li key={r.id} className="flex flex-wrap items-start justify-between gap-2">
            <span>
              <span className="text-xs text-muted-foreground">{new Date(r.at).toLocaleString()} · {r.kind === "defaults" ? "Your defaults" : `Clip ${r.n}`}</span>
              <span className="block">{Object.entries(r.diff).map(([k, d]) => `${k}: ${nice2(d.from)} → ${nice2(d.to)}`).join(" · ")}</span>
            </span>
            {r.undone ? <span className="text-xs text-muted-foreground">Undone</span> : <button type="button" className={btn} disabled={busy} onClick={() => onUndo(r.id)}>Undo{r.kind === "clip" ? " (re-renders the clip)" : ""}</button>}
          </li>))}
      </ul>
    </details>
  );
}

export function YtCoach() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["coach"], queryFn: () => autoclip.coach(), retry: false });
  const set = useMutation({ mutationFn: (b: Parameters<typeof autoclip.coachSet>[0]) => autoclip.coachSet(b), onSuccess: (d) => qc.setQueryData(["coach"], d) });
  const run = useMutation({ mutationFn: () => autoclip.coachAnalyse(), onSuccess: (d) => qc.setQueryData(["coach"], d) });
  const undo = useMutation({ mutationFn: (id: string) => autoclip.coachUndo(id), onSuccess: (d) => { qc.setQueryData(["coach"], d); qc.invalidateQueries({ queryKey: ["autoclip"] }); } });
  const apply = useMutation({ mutationFn: () => autoclip.coachApply(), onSuccess: () => qc.invalidateQueries({ queryKey: ["autoclip"] }) });
  const c: CoachView | undefined = q.data;
  const ins = c?.insights;
  const tabs = ins?.tables ?? {};
  const names: Record<string, string> = { ...(c?.labels ?? {}), length: "Clip length", title: "Title style", hour: "Posting time (UTC)" };
  return (
    <Card title="Coach" hint="Studies every clip you posted and learns which edits get more views." right={
      <button type="button" className={btn} disabled={run.isPending || !c || c.mode === "off"} onClick={() => run.mutate()}>{run.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}Analyse now</button>}>
      {q.isError && <Note tone="err">{(q.error as Error).message}</Note>}
      {c && (
        <>
          <div role="radiogroup" aria-label="Coach mode" className="grid gap-2 sm:grid-cols-3">
            {MODES.map(([k, l, d]) => (
              <button key={k} type="button" role="radio" aria-checked={c.mode === k} onClick={() => set.mutate({ mode: k })} className={`border p-3 text-left transition ${c.mode === k ? "border-signal/85 bg-signal/12" : "border-border text-muted-foreground hover:text-foreground"}`}>
                <div className="flex items-center gap-2 text-sm font-medium"><Brain className="h-4 w-4" />{l}</div><div className="mt-1 text-xs">{d}</div>
              </button>))}
          </div>
          {c.mode !== "off" && (
            <>
              <div className="grid gap-3 sm:grid-cols-2">
                {Object.entries(c.labels).map(([k, l]) => <Switch key={k} on={!!c.dims[k]} onChange={(v) => set.mutate({ dims: { [k]: v } })} label={l} hint={k === "music" ? "Off by default: it only picks among moods, never your licence choices." : undefined} />)}
              </div>
              <p className="text-xs text-muted-foreground">
                How it learns: each clip is a recipe (caption, edit style, colour look, zoom, callouts, music). After about a day and a half, its views per day and likes become a score, compared with your other clips on the same channel.
                The coach mostly picks the choices that scored best, and tries others about {Math.round(c.explore * 100)}% of the time so it can find something better. This is a bandit, the kind of reinforcement learning that works with a few clips a day.
                It sees views, likes and comments only: YouTube&apos;s basic API doesn&apos;t give watch time.
              </p>
            </>
          )}
          {c.mode !== "off" && !ins && <Note>No analysis yet. Post some clips made here, wait a day or two, then press Analyse now (it also runs once a day by itself).</Note>}
          {ins && (
            <div className="space-y-4">
              <p className="text-sm">{ins.summary} <span className="text-xs text-muted-foreground">({ins.by === "ai" ? "explained by AI" : "rule-based"} · {new Date(ins.at).toLocaleString()})</span></p>
              <div className="grid gap-3 md:grid-cols-2">
                {ins.do_more.length > 0 && <div className="border border-border p-3 text-sm"><div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Do more</div><ul className="list-disc space-y-1 pl-4">{ins.do_more.map((x) => <li key={x}>{x}</li>)}</ul></div>}
                {ins.avoid.length > 0 && <div className="border border-border p-3 text-sm"><div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Do less</div><ul className="list-disc space-y-1 pl-4">{ins.avoid.map((x) => <li key={x}>{x}</li>)}</ul></div>}
                {[...ins.title_tips, ...ins.hashtag_tips].length > 0 && <div className="border border-border p-3 text-sm"><div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Titles and hashtags</div><ul className="list-disc space-y-1 pl-4">{[...ins.title_tips, ...ins.hashtag_tips].map((x) => <li key={x}>{x}</li>)}</ul></div>}
                {ins.experiments.length > 0 && <div className="border border-border p-3 text-sm"><div className="mb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">Try next</div><ul className="list-disc space-y-1 pl-4">{ins.experiments.map((x) => <li key={x}>{x}</li>)}</ul></div>}
              </div>
              {ins.retention ? <Curve r={ins.retention} /> : <p className="text-xs text-muted-foreground">Watch time: none yet. YouTube shares it 2-3 days after posting. A channel connected before this update must be disconnected and connected again to allow it.</p>}
              {ins.tags.length > 0 && <p className="text-xs text-muted-foreground">Hashtags added to new posts from your best clips: {ins.tags.map((t) => `#${t}`).join(" ")}</p>}
              {Object.keys(ins.best).length > 0 && (
                <div className="flex flex-wrap items-center gap-3">
                  <span className="text-sm">Clearly ahead: {Object.entries(ins.best).map(([k, v]) => `${c.labels[k] ?? k}: ${nice(v)}`).join(" · ")}</span>
                  <button type="button" className={btnPrimary} disabled={apply.isPending} onClick={() => apply.mutate()}>Apply best to my defaults</button>
                  {apply.isSuccess && <span className="text-xs text-primary">Saved: new clips start with these.</span>}
                </div>
              )}
              <details><summary className="cursor-pointer text-sm">The numbers behind it</summary>
                <div className="mt-3 grid gap-3 md:grid-cols-2 xl:grid-cols-3">{Object.entries(tabs).filter(([, r]) => r.length > 0).map(([k, rows]) => <Table key={k} title={names[k] ?? k} rows={rows} />)}</div>
                <p className="mt-2 text-xs text-muted-foreground">Score = how far above (+) or below (−) your channel&apos;s average these clips were, in standard steps. With only a few clips per row, small differences are noise.</p>
              </details>
            </div>
          )}
          {run.data?.retention_fetch?.needs_reconnect?.length ? <Note tone="warn">Watch time could not be read for a channel connected before this update. Disconnect it and connect it again.</Note> : null}
          <Changes rows={c.changes ?? []} onUndo={(id) => undo.mutate(id)} busy={undo.isPending} />
          {(set.isError || run.isError || apply.isError || undo.isError) && <Note tone="err">{((set.error || run.error || apply.error || undo.error) as Error).message}</Note>}
        </>
      )}
    </Card>
  );
}
