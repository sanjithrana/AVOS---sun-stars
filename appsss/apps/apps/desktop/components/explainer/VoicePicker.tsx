"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Check, Loader2, Play, Square, Star } from "lucide-react";
import { explainer, type Voice } from "@/lib/explainer";

const FAV_KEY = "avos-voice-favorites";
const readFavs = (): string[] => { try { return JSON.parse(localStorage.getItem(FAV_KEY) || "[]"); } catch { return []; } };
const saveFavs = (v: string[]) => { try { localStorage.setItem(FAV_KEY, JSON.stringify(v)); } catch { /* private window */ } };

/** Pick the narrator: language, dialect, gender, preview, favourites. Nothing chosen = the studio's default voice. */
export function VoicePicker({ value, onChange }: { value: Voice | null; onChange: (v: Voice | null) => void }) {
  const [open, setOpen] = useState(false);
  const [lang, setLang] = useState("English");
  const [dialect, setDialect] = useState("");
  const [gender, setGender] = useState("");
  const [q, setQ] = useState("");
  const [favOnly, setFavOnly] = useState(false);
  const [favs, setFavs] = useState<string[]>([]);
  const [playing, setPlaying] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const audio = useRef<HTMLAudioElement | null>(null);
  useEffect(() => { setFavs(readFavs()); return () => audio.current?.pause(); }, []);
  const all = useQuery({ queryKey: ["explainer-voices"], queryFn: () => explainer.voices(), enabled: open, retry: false, staleTime: 3600000 });

  const languages = useMemo(() => [...new Set((all.data ?? []).map((v) => v.language))].sort(), [all.data]);
  const dialects = useMemo(() => [...new Set((all.data ?? []).filter((v) => v.language === lang).map((v) => v.dialect))].sort(), [all.data, lang]);
  const shown = useMemo(() => (all.data ?? []).filter((v) => (favOnly ? favs.includes(v.id) : v.language === lang) && (!dialect || v.dialect === dialect)
    && (!gender || v.gender === gender) && (!q || `${v.name} ${v.tags.join(" ")}`.toLowerCase().includes(q.toLowerCase()))), [all.data, lang, dialect, gender, q, favOnly, favs]);

  const play = (v: Voice) => {
    if (playing === v.id) { audio.current?.pause(); setPlaying(null); return; }
    audio.current?.pause();
    setErr(null); setLoading(v.id);
    const a = new Audio(explainer.voicePreview(v.id));
    audio.current = a;
    a.oncanplay = () => { setLoading(null); setPlaying(v.id); void a.play(); };
    a.onended = () => setPlaying(null);
    a.onerror = () => { setLoading(null); setPlaying(null); setErr("Couldn't play a sample. Voices need an internet connection."); };
  };
  const star = (id: string) => { const n = favs.includes(id) ? favs.filter((x) => x !== id) : [...favs, id]; setFavs(n); saveFavs(n); };
  const sel = "rounded-xl border border-border bg-background px-3 py-2 text-sm";

  return (
    <div className="mt-6 text-sm">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Narrator voice</p>
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} data-testid="voice-toggle"
        className="inline-flex items-center gap-2 rounded-full border border-border px-3 py-2 transition hover:bg-accent">
        {value ? <><Check className="h-4 w-4 text-emerald-600" />{value.name} · {value.language} ({value.dialect}) · {value.gender}</> : "Automatic (default voice) — choose one…"}
      </button>
      {value && <button type="button" onClick={() => onChange(null)} className="ml-2 text-xs text-muted-foreground underline">Use default</button>}
      {open && (
        <div className="mt-3 animate-in fade-in slide-in-from-top-1 rounded-2xl border border-border p-4 duration-300">
          {all.isLoading && <p className="flex items-center gap-2 text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading voices…</p>}
          {all.isError && <p className="text-red-600" role="alert">{(all.error as Error).message}</p>}
          {all.data && (
            <>
              <div className="grid gap-2 sm:grid-cols-4">
                <select className={sel} value={lang} onChange={(e) => { setLang(e.target.value); setDialect(""); setFavOnly(false); }} aria-label="Language" data-testid="voice-language">
                  {languages.map((l) => <option key={l}>{l}</option>)}
                </select>
                <select className={sel} value={dialect} onChange={(e) => setDialect(e.target.value)} aria-label="Dialect">
                  <option value="">All dialects</option>{dialects.map((d) => <option key={d}>{d}</option>)}
                </select>
                <select className={sel} value={gender} onChange={(e) => setGender(e.target.value)} aria-label="Gender">
                  <option value="">All genders</option><option>Female</option><option>Male</option>
                </select>
                <input className={sel} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search a voice" aria-label="Search" />
              </div>
              <button type="button" onClick={() => setFavOnly(!favOnly)} aria-pressed={favOnly}
                className={`mt-2 rounded-full border px-3 py-1 text-xs ${favOnly ? "border-amber-500 bg-amber-500/15" : "border-border hover:bg-accent"}`}>Favourites ({favs.length})</button>
              {err && <p className="mt-2 text-xs text-red-600" role="alert">{err}</p>}
              <ul className="mt-3 grid max-h-72 gap-2 overflow-y-auto pr-1 sm:grid-cols-2 lg:grid-cols-3" data-testid="voice-list">
                {shown.map((v) => {
                  const on = value?.id === v.id;
                  return (
                    <li key={v.id} className={`flex items-center gap-2 rounded-xl border p-2 transition-colors ${on ? "border-amber-500 bg-amber-500/10" : "border-border hover:bg-accent/50"}`}>
                      <button type="button" onClick={() => play(v)} aria-label={`Preview ${v.name}`} className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-muted transition hover:bg-amber-500/20">
                        {loading === v.id ? <Loader2 className="h-4 w-4 animate-spin" /> : playing === v.id ? <Square className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
                      </button>
                      <button type="button" onClick={() => { onChange(v); setOpen(false); }} className="min-w-0 flex-1 text-left" data-testid={`voice-${v.id}`}>
                        <span className="block truncate font-medium">{v.name} <span className="text-xs text-muted-foreground">{v.gender === "Female" ? "♀" : v.gender === "Male" ? "♂" : ""}</span></span>
                        <span className="block truncate text-xs text-muted-foreground">{v.dialect}{v.tags.length ? ` · ${v.tags.join(", ")}` : ""}</span>
                      </button>
                      <button type="button" onClick={() => star(v.id)} aria-label="Favourite" aria-pressed={favs.includes(v.id)}><Star className={`h-4 w-4 ${favs.includes(v.id) ? "fill-amber-500 text-amber-500" : "text-muted-foreground"}`} /></button>
                    </li>
                  );
                })}
                {!shown.length && <li className="text-muted-foreground">No voices match.</li>}
              </ul>
            </>
          )}
        </div>
      )}
    </div>
  );
}
