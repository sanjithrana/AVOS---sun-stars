"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// Series home: your series and "New series" (title, language, premise, cast, style pictures, theme, part plan, crew).
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Clapperboard, ImagePlus, Loader2, Music2, Plus, Sparkles, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAgentsInfo, useCrew } from "@/components/reelmimic/Shell";
import { modelLabel, seriesApi } from "./api";
import type { SeriesSummary } from "./types";

const field = "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-amber-500/40";
const label = "mb-1 block text-xs font-medium text-muted-foreground";

export function SeriesHome() {
  const list = useQuery({ queryKey: ["series", "list"], queryFn: seriesApi.list, refetchInterval: 5000, retry: false });
  const items: SeriesSummary[] = (list.data ?? []).filter((x) => x.kind !== "film");
  return (
    <main className="mx-auto max-w-7xl space-y-8 p-4 md:p-8" data-testid="series-home">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Link href="/animations" className="text-xs text-muted-foreground hover:underline">← Animations</Link>
          <h1 className="mb-2 mt-1 text-2xl font-bold text-foreground md:text-3xl">Series</h1>
          <p className="max-w-3xl text-muted-foreground">
            An animated series made with you at every step: the AI drafts each character (look and voice) and you approve them one by one;
            episodes are written and rendered in parts (1 min, then 3 min, …) and nothing moves on until you approve the part you just watched.
          </p>
        </div>
      </div>

      <NewSeries />

      <section>
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground"><Clapperboard className="h-5 w-5 text-amber-500" />Your series</h2>
        {list.isError ? <p className="rounded-xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm text-amber-800 dark:text-amber-200" data-testid="series-offline">{(list.error as Error).message}</p> :
          list.isLoading ? <div className="h-24 animate-pulse rounded-xl bg-muted/40" /> : items.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-6 text-sm text-muted-foreground">No series yet. Create one above.</p>
        ) : (
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="series-list">
            {items.map((s) => (
              <Link key={s.id} href={`/animations/series/${s.id}`} className="group overflow-hidden rounded-xl border border-border bg-card/40 transition hover:border-amber-500/60" data-testid={`series-${s.id}`}>
                <div className="aspect-video bg-muted/40">
                  {s.thumb ? <img src={seriesApi.file(s.id, s.thumb)} alt="" className="h-full w-full object-cover" /> : <div className="flex h-full items-center justify-center text-muted-foreground"><Users className="h-8 w-8" /></div>}
                </div>
                <div className="space-y-1 p-4">
                  <div className="flex items-center gap-2">
                    <b className="truncate text-foreground">{s.title}</b>
                    {s.working && <Loader2 className="h-4 w-4 animate-spin text-amber-500" />}
                  </div>
                  <p className="text-xs text-muted-foreground">{s.languageName} · {s.approved}/{s.characters} characters approved · {s.episodes} episode{s.episodes === 1 ? "" : "s"}</p>
                </div>
              </Link>
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function NewSeries() {
  const router = useRouter();
  const langs = useQuery({ queryKey: ["series", "languages"], queryFn: seriesApi.languages, staleTime: 60_000, retry: false });
  const info = useAgentsInfo();
  const [crew] = useCrew(info.data);
  const [crewPick, setCrewPick] = useState<string>("");
  const [title, setTitle] = useState("");
  const [premise, setPremise] = useState("");
  const [language, setLanguage] = useState("hi");
  const [aspect, setAspect] = useState("16:9");
  const [tone, setTone] = useState("family comedy");
  const [cast, setCast] = useState("");
  const [suggest, setSuggest] = useState(true);
  const [style, setStyle] = useState("");
  const [refs, setRefs] = useState<File[]>([]);
  const [theme, setTheme] = useState<File | null>(null);
  const [plan, setPlan] = useState("1,3");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previews = useMemo(() => refs.map((f) => URL.createObjectURL(f)), [refs]);
  const lang = langs.data?.find((l) => l.code === language);
  const readyCrews = (info.data?.agents ?? []).filter((a) => a.ready);
  // the crew new series use: your pick, else the Animations crew if it's ready, else the first ready one
  const chosenCrew = crewPick || (readyCrews.some((a) => a.id === crew) ? crew : readyCrews[0]?.id) || "builtin";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const f = new FormData();
    Object.entries({ title, premise, language, aspect, tone, cast, style, partPlan: plan, suggestCast: suggest ? "1" : "0", crew: chosenCrew })
      .forEach(([k, v]) => f.append(k, v));
    refs.forEach((r) => f.append("refs", r));
    if (theme) f.append("theme", theme);
    try {
      const { id } = await seriesApi.create(f);
      router.push(`/animations/series/${id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-5 rounded-xl border border-border bg-card/40 p-5 md:p-6" data-testid="new-series">
      <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground"><Sparkles className="h-5 w-5 text-amber-500" />New series</h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <label className={label} htmlFor="s-title">Title</label>
          <input id="s-title" className={field} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Sharma Ji Ka Ghar" required data-testid="series-title" />
        </div>
        <div>
          <label className={label} htmlFor="s-lang">Language the characters speak</label>
          <select id="s-lang" className={field} value={language} onChange={(e) => setLanguage(e.target.value)} data-testid="series-language">
            {(langs.data ?? [{ code: "hi", name: "Hindi" }, { code: "en", name: "English (US)" }]).map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
          </select>
          {lang && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              {lang.lines.length ? `Voices: ${lang.lines.map(modelLabel).join(", ")}` : "No open voice model speaks it yet: Edge voices are used"}{lang.note ? ` · ${lang.note}` : ""}
            </p>
          )}
        </div>
      </div>
      <div>
        <label className={label} htmlFor="s-premise">Premise: what the series is about</label>
        <textarea id="s-premise" className={`${field} min-h-20`} value={premise} onChange={(e) => setPremise(e.target.value)} data-testid="series-premise"
          placeholder="A middle-class family in a small flat: a mischievous 12-year-old, his strict but loving mother, a father who avoids every argument…" />
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div>
          <label className={label} htmlFor="s-cast">Your characters (one per line: Name - who they are, how they look)</label>
          <textarea id="s-cast" className={`${field} min-h-24`} value={cast} onChange={(e) => setCast(e.target.value)} data-testid="series-cast"
            placeholder={"Bunty - 12, skinny, messy hair, green t-shirt, always scheming\nMummy - 40, purple saree, glasses, catches every lie"} />
          <label className="mt-2 flex items-center gap-2 text-xs text-muted-foreground"><input type="checkbox" checked={suggest} onChange={(e) => setSuggest(e.target.checked)} /> Let the AI add the other characters the premise needs</label>
        </div>
        <div>
          <label className={label} htmlFor="s-style">Art style (and pictures that show it)</label>
          <textarea id="s-style" className={`${field} min-h-16`} value={style} onChange={(e) => setStyle(e.target.value)} data-testid="series-style"
            placeholder="Flat 2D, thick dark outlines, warm saturated colours, big expressive eyes" />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {previews.map((src, i) => <img key={src} src={src} alt={`style ${i + 1}`} className="h-14 w-24 rounded-lg border border-border object-cover" />)}
            <label className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:border-amber-500">
              <ImagePlus className="h-4 w-4" /> Style pictures
              <input type="file" accept="image/png,image/jpeg,image/webp" multiple className="hidden" data-testid="series-refs"
                onChange={(e) => setRefs([...refs, ...Array.from(e.target.files ?? [])].slice(0, 3))} />
            </label>
          </div>
          <p className="mt-1 text-[11px] text-muted-foreground">Pictures guide the drawing style only. Your characters are drawn from your descriptions, not copied from the pictures.</p>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
        <div>
          <label className={label} htmlFor="s-aspect">Frame</label>
          <select id="s-aspect" className={field} value={aspect} onChange={(e) => setAspect(e.target.value)}>
            <option value="16:9">16:9 (YouTube)</option><option value="9:16">9:16 (Shorts / Reels)</option><option value="1:1">1:1</option><option value="4:3">4:3</option>
          </select>
        </div>
        <div>
          <label className={label} htmlFor="s-tone">Tone</label>
          <input id="s-tone" className={field} value={tone} onChange={(e) => setTone(e.target.value)} />
        </div>
        <div>
          <label className={label} htmlFor="s-plan">Part lengths (minutes)</label>
          <input id="s-plan" className={field} value={plan} onChange={(e) => setPlan(e.target.value)} title="First part, then the rest: 1,3 makes 1, 3, 3, 3…" data-testid="series-plan" />
        </div>
        <div>
          <label className={label} htmlFor="s-crew">AI writers</label>
          <select id="s-crew" className={field} value={chosenCrew} onChange={(e) => setCrewPick(e.target.value)} data-testid="series-crew">
            {readyCrews.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            {!readyCrews.some((a) => a.id === "builtin") && <option value="builtin">Built-in rules (no AI)</option>}
          </select>
        </div>
        <div>
          <span className={label}>Theme music (optional)</span>
          <label className="flex cursor-pointer items-center gap-1 truncate rounded-xl border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:border-amber-500">
            <Music2 className="h-4 w-4 shrink-0" /> <span className="truncate">{theme ? theme.name : "Upload a track"}</span>
            <input type="file" accept="audio/*" className="hidden" onChange={(e) => setTheme(e.target.files?.[0] ?? null)} />
          </label>
        </div>
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400" data-testid="series-error">{error}</p>}
      <div className="flex items-center gap-3">
        <Button type="submit" disabled={busy || !title.trim()} data-testid="series-create">
          {busy ? <Loader2 className="animate-spin" /> : <Plus />} Create the series
        </Button>
        <span className="text-xs text-muted-foreground">Next: the AI drafts each character&apos;s look and voice for you to approve.</span>
      </div>
    </form>
  );
}
