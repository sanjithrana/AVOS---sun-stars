"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// Films home: your films and "New film" — one prompt (plain text with time codes, or JSON) → a film made in seven
// approved stages. Characters can come from your library.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BookUser, Braces, Clapperboard, Film, ImagePlus, Loader2, Music2, Plus, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useAgentsInfo, useCrew } from "@/components/reelmimic/Shell";
import { modelLabel, seriesApi } from "@/components/series/api";
import { LibraryPicker } from "@/components/series/Library";
import type { SeriesSummary } from "@/components/series/types";

const field = "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-amber-500/40";
const label = "mb-1 block text-xs font-medium text-muted-foreground";

export const EXAMPLE = `Create a 15-second cinematic 3D animated comedy, Pixar style, vibrant colours, smooth 24fps.

SETTING
A lush forest road after rain: wet asphalt, big reflective puddles, tall green trees, soft mist, golden sunlight.

CHARACTERS
Wolf: a cheerful grey wolf in a yellow tropical shirt, driving a small red convertible with cream seats.
Rabbit: a tiny white rabbit in blue overalls and sunglasses, driving a huge orange off-road truck with oversized black tyres and a raised seat.

0–3 SECONDS
Wide tracking shot from the side: the wolf sings and bobs his head while driving; his front tyre hits a puddle and splashes the rabbit standing on the roadside grass. Wolf sings "La la la, what a lovely day!"

3–5 SECONDS
Close-up, eye-level, static: the soaked rabbit wipes water from his face; his annoyed look turns into a mischievous smile as he notices his truck. Rabbit says "Oh, it's on."

5–8 SECONDS
Medium shot, slow push-in: the wolf keeps singing until an enormous shadow covers his little car; he looks up, eyes wide, the song stops.

8–11 SECONDS
Low angle, wide lens, tracking: the rabbit's giant truck rolls up beside the convertible. Emphasise the enormous difference in scale.

11–15 SECONDS
Wide, slow pull-back: the truck rolls through a huge puddle; a curved sheet of muddy water arcs over and drenches the wolf. The truck drives on; one last drop falls from the wolf's ear. Final plop.

AUDIO
forest ambience with birds, playful orchestral comedy music that stops for the quiet beat, small-car engine, deep truck engine rumble, two big splashes, dripping, a final plop.

RULES
Same faces, fur colours and clothes in every shot. No text on screen.`;

export function FilmHome() {
  const list = useQuery({ queryKey: ["series", "list"], queryFn: seriesApi.list, refetchInterval: 5000, retry: false });
  const films: SeriesSummary[] = (list.data ?? []).filter((x) => x.kind === "film");
  return (
    <main className="mx-auto max-w-7xl space-y-8 p-4 md:p-8" data-testid="films-home">
      <div>
        <Link href="/animations" className="text-xs text-muted-foreground hover:underline">← Animations</Link>
        <h1 className="mb-2 mt-1 text-2xl font-bold text-foreground md:text-3xl">Films: prompt → animation</h1>
        <p className="max-w-4xl text-muted-foreground">
          Lock the look, storyboard, animate every frame separately, design the sound, assemble. Your prompt is read into timed shots, characters and a world;
          you approve the breakdown, each character, the storyboard and the cut. Every stage leaves real files you can download.
        </p>
        <ol className="mt-3 flex flex-wrap gap-2 text-xs text-muted-foreground">
          {["Breakdown", "Characters & world", "Storyboard", "Motion", "Prompts", "Render", "Edit bay"].map((x, i) => (
            <li key={x} className="rounded-full border border-border px-2 py-0.5"><b className="text-amber-600">{i + 1}</b> {x}</li>
          ))}
        </ol>
      </div>
      <NewFilm />
      <section>
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-foreground"><Clapperboard className="h-5 w-5 text-amber-500" />Your films</h2>
        {list.isError ? <p className="rounded-2xl border border-amber-500/40 bg-amber-500/5 p-4 text-sm" data-testid="films-offline">{(list.error as Error).message}</p> :
          list.isLoading ? <div className="h-24 animate-pulse rounded-2xl bg-muted/40" /> : films.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-border p-6 text-sm text-muted-foreground">No films yet. Paste a prompt above.</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3" data-testid="films-list">
              {films.map((f) => (
                <Link key={f.id} href={`/animations/films/${f.id}`} className="overflow-hidden rounded-2xl border border-border bg-card/40 transition hover:border-amber-500/60" data-testid={`film-${f.id}`}>
                  <div className="aspect-video bg-muted/40">{f.thumb ? <img src={seriesApi.file(f.id, f.thumb)} alt="" className="h-full w-full object-cover" /> :
                    <div className="flex h-full items-center justify-center text-muted-foreground"><Film className="h-8 w-8" /></div>}</div>
                  <div className="space-y-1 p-4">
                    <div className="flex items-center gap-2"><b className="truncate text-foreground">{f.title}</b>{f.working && <Loader2 className="h-4 w-4 animate-spin text-amber-500" />}</div>
                    <p className="text-xs text-muted-foreground">{f.status === "done" ? "Finished" : f.episodes ? "In production" : f.stage === "review" ? "Breakdown waiting for you" : f.stage === "approved" ? "Characters" : "Reading the prompt"}
                      {" · "}{f.approved}/{f.characters} characters</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
      </section>
    </main>
  );
}

function NewFilm() {
  const router = useRouter();
  const langs = useQuery({ queryKey: ["series", "languages"], queryFn: seriesApi.languages, staleTime: 60_000, retry: false });
  const info = useAgentsInfo();
  const [crew] = useCrew(info.data);
  const [crewPick, setCrewPick] = useState("");
  const [prompt, setPrompt] = useState("");
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("en");
  const [aspect, setAspect] = useState("16:9");
  const [style, setStyle] = useState("");
  const [refs, setRefs] = useState<File[]>([]);
  const [theme, setTheme] = useState<File | null>(null);
  const [cast, setCast] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previews = useMemo(() => refs.map((f) => URL.createObjectURL(f)), [refs]);
  const readyCrews = (info.data?.agents ?? []).filter((a) => a.ready);
  const chosenCrew = crewPick || (readyCrews.some((a) => a.id === crew) ? crew : readyCrews[0]?.id) || "builtin";
  const isJson = /^\s*(```json|[{[])/.test(prompt);
  const lang = langs.data?.find((l) => l.code === language);
  const sections = (prompt.match(/(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)?\s*[–—-]\s*(\d+(?:\.\d+)?)\s*(?:s|sec|seconds)\b/gi) ?? []).length;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const f = new FormData();
    Object.entries({ prompt, title, language, aspect, style, crew: chosenCrew, library: cast.join(",") }).forEach(([k, v]) => f.append(k, v));
    refs.forEach((r) => f.append("refs", r));
    if (theme) f.append("theme", theme);
    try {
      const { id } = await seriesApi.createFilm(f);
      router.push(`/animations/films/${id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-card/40 p-5 md:p-6" data-testid="new-film">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground"><Sparkles className="h-5 w-5 text-amber-500" />New film</h2>
        <span className="grow" />
        <Button type="button" size="sm" variant="ghost" onClick={() => setPrompt(EXAMPLE)} data-testid="film-example">Load an example prompt</Button>
      </div>
      <div>
        <label className={label} htmlFor="f-prompt">Your prompt: story, setting, characters, then what happens when (“0–3 SECONDS: …”, “SHOT 4 (3.00–4.00s) – close-up: …”), audio, rules. Or paste JSON.</label>
        <textarea id="f-prompt" className={`${field} min-h-72 font-mono text-xs leading-relaxed`} value={prompt} onChange={(e) => setPrompt(e.target.value)} required data-testid="film-prompt"
          placeholder={"Create a 15-second cinematic 3D animated comedy…\n\nSETTING\n…\n\nCHARACTERS\n…\n\n0–3 SECONDS\n…"} />
        <p className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
          {isJson ? <><Braces className="h-3.5 w-3.5" />JSON prompt: its shots are used as they are</> : sections ? `${sections} timed sections found: they become shots with exactly those times` : "No time codes: the AI splits the story into 1.5–3 s shots"}
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <div className="md:col-span-2">
          <label className={label} htmlFor="f-title">Title (optional: the AI names it)</label>
          <input id="f-title" className={field} value={title} onChange={(e) => setTitle(e.target.value)} data-testid="film-title" />
        </div>
        <div>
          <label className={label} htmlFor="f-lang">Dialogue language</label>
          <select id="f-lang" className={field} value={language} onChange={(e) => setLanguage(e.target.value)}>
            {(langs.data ?? [{ code: "en", name: "English (US)" }, { code: "hi", name: "Hindi" }]).map((l) => <option key={l.code} value={l.code}>{l.name}</option>)}
          </select>
          {lang && <p className="mt-1 text-[11px] text-muted-foreground">{lang.lines.length ? `Voices: ${lang.lines.map(modelLabel).join(", ")}` : "Edge voices"}</p>}
        </div>
        <div>
          <label className={label} htmlFor="f-aspect">Frame</label>
          <select id="f-aspect" className={field} value={aspect} onChange={(e) => setAspect(e.target.value)}>
            <option value="16:9">16:9</option><option value="9:16">9:16 (Shorts / Reels)</option><option value="1:1">1:1</option><option value="4:3">4:3</option>
          </select>
        </div>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <div>
          <label className={label} htmlFor="f-style">Art style (optional: read from the prompt)</label>
          <input id="f-style" className={field} value={style} onChange={(e) => setStyle(e.target.value)} placeholder="3D Pixar-style, cinematic lighting" />
          <div className="mt-2 flex flex-wrap items-center gap-2">
            {previews.map((src, i) => <img key={src} src={src} alt={`style ${i + 1}`} className="h-12 w-20 rounded-lg border border-border object-cover" />)}
            <label className="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:border-amber-500">
              <ImagePlus className="h-4 w-4" />Style pictures<input type="file" accept="image/png,image/jpeg,image/webp" multiple className="hidden" onChange={(e) => setRefs([...refs, ...Array.from(e.target.files ?? [])].slice(0, 3))} />
            </label>
          </div>
        </div>
        <div>
          <label className={label} htmlFor="f-crew">AI crew (reads the prompt, plans the shots, checks every frame)</label>
          <select id="f-crew" className={field} value={chosenCrew} onChange={(e) => setCrewPick(e.target.value)} data-testid="film-crew">
            {readyCrews.map((a) => <option key={a.id} value={a.id}>{a.label}</option>)}
            {!readyCrews.some((a) => a.id === "builtin") && <option value="builtin">Built-in rules (no AI)</option>}
          </select>
        </div>
        <div>
          <span className={label}>Music (optional: else the prompt&apos;s music cue)</span>
          <label className="flex cursor-pointer items-center gap-1 truncate rounded-xl border border-dashed border-border px-3 py-2 text-xs text-muted-foreground hover:border-amber-500">
            <Music2 className="h-4 w-4 shrink-0" /><span className="truncate">{theme ? theme.name : "Upload a track"}</span>
            <input type="file" accept="audio/*" className="hidden" onChange={(e) => setTheme(e.target.files?.[0] ?? null)} />
          </label>
        </div>
      </div>
      <div>
        <span className={label}><BookUser className="mr-1 inline h-3.5 w-3.5" />Cast from your library (optional: matched to the prompt&apos;s characters by name)</span>
        <LibraryPicker value={cast} onChange={setCast} />
      </div>
      {error && <p className="text-sm text-red-600 dark:text-red-400" data-testid="film-error">{error}</p>}
      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={busy || prompt.trim().length < 10} data-testid="film-create">{busy ? <Loader2 className="animate-spin" /> : <Plus />}Analyze &amp; build</Button>
        <span className="text-xs text-muted-foreground">Next: the breakdown (shots, characters, world, camera, sound) for you to check. Nothing is drawn until you approve it.</span>
      </div>
    </form>
  );
}
