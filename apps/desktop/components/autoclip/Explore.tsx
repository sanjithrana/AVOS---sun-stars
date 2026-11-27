"use client";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Scissors, TrendingUp, X } from "lucide-react";
import { autoclip, type ExploreList } from "@/lib/autoclip";
import { Note, btn, field } from "./ui";

const views = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}K` : String(n));
const len = (s: number) => (s >= 3600 ? `${Math.floor(s / 3600)}:${String(Math.floor((s % 3600) / 60)).padStart(2, "0")}h` : `${Math.round(s / 60)}m`);
function ago(iso: string) {
  if (!iso) return "";
  const m = (Date.now() - new Date(iso).getTime()) / 60000;
  return m < 60 ? `${Math.max(1, Math.round(m))} min ago` : m < 1440 ? `${Math.round(m / 60)} h ago` : `${Math.round(m / 1440)} d ago`;
}
const CAT_ORDER = ["all", "podcasts", "interviews", "business", "comedy", "true_crime", "news", "education", "sports", "gaming", "fitness", "tech",
  "entertainment", "music", "film", "people", "howto", "autos", "travel", "pets"];

/** What is trending right now, by category: pick one and it opens in "Make clips" with the link filled in. */
export function Explore({ onPick }: { onPick: (url: string) => void }) {
  const qc = useQueryClient();
  const [cat, setCat] = useState("all");
  const [region, setRegion] = useState("IN");
  const [busy, setBusy] = useState(false);
  const [length, setLength] = useState("long");
  const [shown, setShown] = useState(24);
  const q = useQuery<ExploreList>({ queryKey: ["autoclip", "explore", cat, region, length], queryFn: () => autoclip.explore(cat, region, false, length), staleTime: 10 * 60_000, retry: false });
  const [refreshErr, setRefreshErr] = useState("");
  const refresh = async () => {                      // a failed refresh keeps the list you have and says why, it never breaks the page
    setBusy(true); setRefreshErr("");
    try { qc.setQueryData(["autoclip", "explore", cat, region, length], await autoclip.explore(cat, region, true, length)); }
    catch (e) { setRefreshErr(`Refresh failed (${(e as Error).message}). Showing the last list; try again in a minute.`); }
    finally { setBusy(false); }
  };
  const d = q.data;
  const [handle, setHandle] = useState("");
  const [chErr, setChErr] = useState("");
  const add = async () => { setChErr(""); try { await autoclip.exploreAdd(handle); setHandle(""); qc.removeQueries({ queryKey: ["autoclip", "explore"] }); q.refetch(); } catch (e) { setChErr((e as Error).message); } };
  const del = async (h: string) => { await autoclip.exploreDel(h); qc.removeQueries({ queryKey: ["autoclip", "explore"] }); q.refetch(); };
  const cats = d?.cats ?? { all: "All" };
  return (
    <section className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div><h2 className="display text-3xl">Explore</h2><p className="text-sm text-muted-foreground">The newest long videos and live streams from the channels people clip most, ranked by views per hour. Updated hourly.</p></div>
        <div className="flex items-center gap-2">
          {d?.updated && <span className="text-xs text-muted-foreground">Updated {ago(d.updated)}</span>}
          <select className="h-10 border border-border bg-transparent px-2 text-sm" value={region} onChange={(e) => setRegion(e.target.value)} aria-label="Country">
            {Object.entries(d?.regions ?? { IN: "India", US: "United States", GB: "United Kingdom" }).map(([k, n]) => <option key={k} value={k}>{n}</option>)}
          </select>
          <select className="h-10 border border-border bg-transparent px-2 text-sm" value={length} onChange={(e) => { setLength(e.target.value); setShown(24); }} aria-label="Length">
            <option value="long">Long videos and streams (clippable)</option><option value="any">Every length</option>
          </select>
          <button type="button" className={btn} onClick={refresh} disabled={busy}><RefreshCw className={`h-4 w-4 ${busy ? "animate-spin" : ""}`} />Refresh</button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2" role="tablist" aria-label="Category">
        {CAT_ORDER.filter((k) => cats[k] || k === "all").map((k) => (
          <button key={k} type="button" role="tab" aria-selected={cat === k} onClick={() => { setCat(k); setShown(24); }}
            className={`rounded-full border px-4 py-2 text-sm transition ${cat === k ? "border-primary bg-primary text-primary-foreground" : "border-border hover:bg-muted"}`}>{cats[k] ?? "All"}</button>
        ))}
      </div>
      {q.isError && <Note tone="err">{(q.error as Error).message} Press Refresh to try again.</Note>}
      {refreshErr && <Note tone="warn">{refreshErr}</Note>}
      {d?.note && <Note tone="warn">{d.note}</Note>}
      {d?.source === "search" && !d.note && <p className="text-xs text-muted-foreground">Connect a YouTube channel (YouTube card on the clips page) for the real trending charts; this list is a plain search.</p>}
      {!d && !q.isError && <p className="text-sm text-muted-foreground">Loading what is trending…</p>}
      {d && d.items.length === 0 && <p className="text-sm text-muted-foreground">Nothing long enough to clip is trending here right now. Try another category or country.</p>}
      <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
        {d?.items.slice(0, shown).map((v) => (
          <article key={v.id} className="group space-y-2">
            <div className="relative overflow-hidden rounded-2xl bg-black">
              <img src={v.thumb} alt="" loading="lazy" className="aspect-video w-full object-cover transition" />
              <button type="button" onClick={() => onPick(v.url)} className="absolute bottom-3 left-3 inline-flex items-center gap-1.5 rounded-full bg-white px-4 py-2 text-sm font-medium text-black shadow hover:bg-white/90"><Scissors className="h-4 w-4" />Get clips</button>
              <span className={`absolute bottom-3 right-3 rounded-md px-2 py-0.5 text-xs font-semibold ${v.live ? "bg-red-600 text-white" : "bg-black/80 text-white"}`}>{v.live ? "● LIVE" : len(v.seconds)}</span>
            </div>
            <a href={v.url} target="_blank" rel="noreferrer" className="line-clamp-2 font-semibold leading-snug hover:underline">{v.title}</a>
            <p className="text-sm text-muted-foreground">{v.channel}</p>
            <p className="flex flex-wrap items-center gap-x-2 text-xs text-muted-foreground">{v.views ? `${views(v.views)} views` : ""}{v.published ? ` · ${ago(v.published)}` : ""}
              {!!v.per_hour && <span className="inline-flex items-center gap-1 font-semibold text-emerald-400"><TrendingUp className="h-3.5 w-3.5" />{views(v.per_hour)} views per hour</span>}</p>
          </article>
        ))}
      </div>
      {d && d.items.length > shown && <div className="flex justify-center"><button type="button" className={btn} onClick={() => setShown(shown + 24)}>Show more ({d.items.length - shown} left)</button></div>}
      {d && length === "long" && (d.total ?? 0) > d.items.length && <p className="text-center text-xs text-muted-foreground">{(d.total ?? 0) - d.items.length} shorter trending videos are hidden. Pick &ldquo;Every length&rdquo; to see them.</p>}
      <div className="space-y-2 border border-border p-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Channels you follow here</span>
        <div className="flex flex-wrap gap-2">
          {(d?.mine ?? []).map((h) => <span key={h} className="inline-flex items-center gap-1 border border-border px-2 py-1 text-sm">{h}<button type="button" aria-label={`Stop following ${h}`} onClick={() => del(h)}><X className="h-3.5 w-3.5" /></button></span>)}
          {!(d?.mine ?? []).length && <span className="text-xs text-muted-foreground">Add the channels you clip from; their newest videos and streams show up in every category.</span>}
        </div>
        <div className="flex gap-2"><input className={field} placeholder="@IShowSpeed or a channel link" value={handle} onChange={(e) => setHandle(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && handle.trim()) add(); }} />
          <button type="button" className={btn} disabled={!handle.trim()} onClick={add}><Plus className="h-4 w-4" />Follow</button></div>
        {chErr && <Note tone="err">{chErr}</Note>}
        {d?.watching && <p className="text-xs text-muted-foreground">Also following for {d.cats?.[d.cat] ?? "this list"}: {d.watching.filter((h) => !(d.mine ?? []).includes(h)).join(", ")}</p>}
      </div>
      <p className="text-xs text-muted-foreground">Trending does not mean free to clip: the permission check runs when you press Get clips. Many creators allow clipping (some pay per view); others don&apos;t.</p>
    </section>
  );
}
