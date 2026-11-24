"use client";
import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, Link2, Scissors } from "lucide-react";
import { autoclip, type Overview } from "@/lib/autoclip";
import { CrewPicker } from "./CrewPicker";
import { RightsCheck, type PermState } from "./RightsCheck";
import { LayoutPicker } from "./Pickers";
import { CaptionStudio, type CaptionValue } from "./CaptionStudio";
import { BrandKit, SavedLooks } from "./BrandKit";
import type { BrandOpts, RightsCheck as RC, SavedLook } from "@/lib/autoclip";
import { EditingPicker, type EditOpts } from "./EditingPicker";
import { Readiness } from "./Readiness";
import { FramePicker, type FrameValue } from "./FramePicker";
import { Card, Label, Note, Switch, btnPrimary, field } from "./ui";

/** Link or upload -> N captioned vertical clips. */
export function MakeClips({ ov, onMade, initialUrl = "" }: { ov: Overview; onMade: (id: string) => void; initialUrl?: string }) {
  const qc = useQueryClient();
  const d = ov.settings.defaults;
  const [url, setUrl] = useState(initialUrl);
  const [file, setFile] = useState<File | null>(null);
  const [srt, setSrt] = useState<File | null>(null);
  const [perm, setPerm] = useState<PermState>({ verdict: "", ack: false, ok: false, live: false, minutes: 20 });
  const [o, setO] = useState({ count: d.count, min_seconds: d.min_seconds, max_seconds: d.max_seconds, layout: d.layout, caption: d.caption, quality: d.quality, start_min: "", end_min: "", preset: "", crew: "builtin", multi: "speaker" });
  const [ed, setEd] = useState<EditOpts>({ edit: d.edit ?? "classic", zoom: d.zoom ?? true, stickers: d.stickers ?? true, look: d.look ?? "clean", fx: d.fx ?? true, sfx: d.sfx ?? true, progress: d.progress ?? false, loudness: d.loudness ?? true, music: d.music ?? "auto", music_volume: d.music_volume ?? 0.14, coach: d.coach ?? false });
  const [hy, setHy] = useState({ hype_only: d.hype_only ?? true, hype_level: d.hype_level ?? "balanced", smart: "auto", smart_min: "45", tighten: true, whole: true, accurate: true, research: true, content: "auto", game_view: "auto", finder: true, riser: false });
  const [fr, setFr] = useState<FrameValue>({ template: "none", canvas: {}, card: {} });
  const [mode, setMode] = useState<"clips" | "captions">("clips");
  const [cv, setCv] = useState<CaptionValue>({ caption: d.caption, cap: d.cap ?? {}, cap_lang: d.cap_lang ?? "auto", whisper_model: d.whisper_model ?? ov.capabilities.whisper_pick ?? "small" });
  const [brand, setBrand] = useState<BrandOpts>(d.brand ?? {});
  const setCap = (p: Partial<CaptionValue>) => setCv((x) => ({ ...x, ...p }));
  const applyLook = (l: SavedLook) => {
    setCv((x) => ({ ...x, caption: l.caption ?? x.caption, cap: l.cap ?? {}, cap_lang: l.cap_lang ?? x.cap_lang }));
    setBrand(l.brand ?? {});
    if (l.layout) set("layout", l.layout);
    setEd((x) => ({ ...x, ...(l.music ? { music: l.music } : {}), ...(l.edit ? { edit: l.edit } : {}), ...(l.look ? { look: l.look } : {}) }));
  };
  const setE = <K extends keyof EditOpts>(k: K, v: EditOpts[K]) => setEd((x) => ({ ...x, [k]: v }));
  const set = (k: string, v: string | number) => setO((x) => ({ ...x, [k]: v }));
  const cap = ov.capabilities;
  const [autoSet, setAutoSet] = useState(false);
  if (!autoSet && cap.reframe?.ready) { setAutoSet(true); if (o.layout === "blur") set("layout", "auto"); }
  const presets = ov.presets ?? [];
  const active = presets.find((x) => x.id === o.preset);
  const choose = (id: string) => {
    const pr = presets.find((x) => x.id === id);
    setO((x) => ({ ...x, preset: id, ...(pr ? pr.defaults : { count: d.count, min_seconds: d.min_seconds, max_seconds: d.max_seconds, caption: d.caption, layout: d.layout }) }));
    setCap({ caption: pr ? pr.defaults.caption : d.caption });
  };
  const extra = { caption: cv.caption, cap: cv.cap, cap_lang: cv.cap_lang, whisper_model: cv.whisper_model, brand, mode };
  const clean = url.trim();
  const rq = useQuery<RC>({ queryKey: ["autoclip", "rights", clean], queryFn: () => autoclip.check(clean), enabled: false });
  const [fileMin, setFileMin] = useState(0);
  useEffect(() => {
    if (!file) { setFileMin(0); return; }
    const u = URL.createObjectURL(file), vid = document.createElement("video");
    vid.preload = "metadata"; vid.onloadedmetadata = () => { setFileMin((vid.duration || 0) / 60); URL.revokeObjectURL(u); }; vid.src = u;
    return () => URL.revokeObjectURL(u);
  }, [file]);
  const minutes = file ? fileMin : (rq.data?.duration ? rq.data.duration / 60 : perm.live ? perm.minutes : 0);
  const estOpts = { ...o, ...ed, ...hy, ...extra, ...fr };
  const est = useQuery({ queryKey: ["autoclip", "estimate", minutes, JSON.stringify(estOpts)], queryFn: () => autoclip.estimate(minutes, estOpts), enabled: minutes > 0, retry: false, staleTime: 60_000 });
  const go = useMutation({
    mutationFn: () => {
      if (file) {
        const f = new FormData();
        f.append("file", file);
        if (srt) f.append("srt", srt);
        Object.entries({ ...o, ...ed, ...hy, ...extra, ...fr }).forEach(([k, v]) => { if (v !== "") f.append(k, typeof v === "object" ? JSON.stringify(v) : String(v)); });
        f.append("verdict", "own"); f.append("ack", String(perm.ack));
        return autoclip.make(f);
      }
      return autoclip.makeFromLink({ url, verdict: perm.verdict || "ask", ack: perm.ack, live_minutes: perm.live ? perm.minutes : undefined, ...Object.fromEntries(Object.entries({ ...o, ...ed, ...hy, ...extra, ...fr }).filter(([, v]) => v !== "")) });
    },
    onSuccess: (j) => { qc.invalidateQueries({ queryKey: ["autoclip"] }); setUrl(""); setFile(null); setSrt(null); onMade(j.id); },
  });
  const ready = (!!file || url.trim().length > 8) && perm.ok;
  const fileIn = useRef<HTMLInputElement>(null);
  const kind = o.preset ? "game" : hy.content === "talk" ? "talk" : hy.content === "game" ? "game" : "any";
  /** One recipe per kind of video, so every setting agrees with every other (no half-gaming, half-podcast mixes). */
  const RECIPES = {
    talk: { hy: { content: "talk", hype_only: false, finder: true, whole: false, tighten: true, accurate: true }, layout: "auto", multi: "speaker",
            caption: cap.caption_styles?.podcast_sub ? "podcast_sub" : d.caption, edit: "clean", music: "none",
            says: "Complete answers picked from the transcript · close shot of whoever talks · clean subtitles · no music · gentle zooms" },
    game: { hy: { content: "game", hype_only: true, hype_level: "balanced", finder: true, whole: true, tighten: true, accurate: true }, layout: "auto", multi: "speaker",
            caption: cap.caption_styles?.gaming ? "gaming" : d.caption, edit: "punchy", music: "none",
            says: "Hype peaks (audio, action, chat, comments) · streamer cam on top, game below · gaming captions · punchy effects · game sound kept, no music" },
    any: { hy: { content: "auto", hype_only: true, hype_level: "balanced", finder: true, whole: true, tighten: true, accurate: true }, layout: "auto", multi: "speaker",
           caption: d.caption, edit: "classic", music: "auto",
           says: "Decides talk or game from the video · best moments by every signal · bold captions · classic effects · soft music" },
  } as const;
  const pickKind = (k: "talk" | "game" | "any") => {
    const r = RECIPES[k];
    if (k !== "game") choose("");
    setHy((x) => ({ ...x, ...r.hy }));
    setO((x) => ({ ...x, layout: cap.reframe?.ready ? r.layout : "blur", multi: r.multi }));
    setCap({ caption: r.caption });
    applyEdit(r.edit);
    setE("music", r.music);
  };
  const EDITS: Record<string, [string, Partial<EditOpts>]> = {
    off: ["None", { edit: "off", zoom: false, stickers: false, fx: false, sfx: false, progress: false, look: "none" }],
    clean: ["Clean", { edit: "clean", zoom: true, stickers: false, fx: false, sfx: false, progress: false, look: "clean" }],
    classic: ["Classic", { edit: "classic", zoom: true, stickers: true, fx: false, sfx: true, progress: false, look: "clean" }],
    punchy: ["Punchy", { edit: "punchy", zoom: true, stickers: true, fx: true, sfx: true, progress: true, look: "vivid" }],
  };
  const applyEdit = (k: string) => setEd((x) => ({ ...x, ...(EDITS[k]?.[1] ?? {}) }));
  const LENGTHS: [string, number, number][] = [["Quick", 15, 30], ["Standard", 30, 45], ["Long", 45, 90]];
  const lenOn = LENGTHS.find(([, a, b]) => a === o.min_seconds && b === o.max_seconds)?.[0];
  const capName = cap.caption_styles?.[cv.caption]?.label ?? cap.captions?.[cv.caption] ?? cv.caption;
  const tplName = cap.template_info?.[fr.template]?.label ?? "No template";
  const chip = (on: boolean) => `border px-3 py-2 text-sm transition ${on ? "border-[rgba(200,255,58,0.85)] bg-[rgba(200,255,58,0.12)] text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`;
  return (
    <Card title="Make clips" hint="Paste a link, press Get clips. Everything else is already set for you.">
      {/* 1. what kind of video: sets layout, captions and how moments are picked */}
      <div className="grid gap-2 sm:grid-cols-3" role="radiogroup" aria-label="What kind of video">
        {([["talk", "People talking", "Podcast, interview, talk: complete answers, close shot of the speaker"],
           ["game", "Gaming / stream", "Hype moments, streamer cam on top, the game below"],
           ["any", "Anything else", "Decides from the video itself"]] as const).map(([id, name, sub]) => (
          <button key={id} type="button" role="radio" aria-checked={kind === id} onClick={() => pickKind(id)} className={`${chip(kind === id)} text-left`}>
            <span className="block font-medium text-foreground">{name}</span>
            <span className="block text-xs text-muted-foreground">{sub}</span>
          </button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground"><span className="text-foreground">This sets:</span> {RECIPES[kind].says}. Change any of it below only if you need to.</p>
      {kind === "game" && presets.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>Game kit:</span>
          <button type="button" className={chip(!o.preset)} onClick={() => choose("")}>None</button>
          {presets.map((x) => <button key={x.id} type="button" className={chip(o.preset === x.id)} onClick={() => { choose(x.id); setHy((h) => ({ ...h, content: "game" })); }}>{x.name}</button>)}
        </div>
      )}

      {/* 2. the video */}
      <div className="pill-cta" role="group" aria-label="Video link">
        <Link2 className="h-4 w-4 shrink-0 text-[#6b6b75]" aria-hidden />
        <input value={url} disabled={!!file} onChange={(e) => setUrl(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter" && ready && !go.isPending) go.mutate(); }}
          placeholder={file ? file.name : "Paste a YouTube, Twitch, Kick or TikTok link"} aria-label="Video link" />
        <button type="button" className={btnPrimary} disabled={!ready || go.isPending} onClick={() => go.mutate()}><Scissors className="h-4 w-4" />{go.isPending ? "Starting…" : perm.live && !file ? "Record live and make clips" : mode === "captions" ? "Add captions" : "Get clips"}</button>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <button type="button" className="underline underline-offset-2 hover:text-foreground" onClick={() => fileIn.current?.click()}>{file ? `Change file (${file.name})` : "or upload a video file"}</button>
        {file && <button type="button" className="underline underline-offset-2 hover:text-foreground" onClick={() => setFile(null)}>remove</button>}
        <input ref={fileIn} type="file" accept="video/*" className="hidden" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        <label className="flex cursor-pointer items-center gap-1.5"><input type="checkbox" checked={mode === "captions"} onChange={(e) => setMode(e.target.checked ? "captions" : "clips")} />Already cut, just add captions</label>
      </div>
      {est.data && <p className="text-xs text-muted-foreground">About <span className="font-semibold text-foreground">{est.data.low}–{est.data.high} min</span> for {est.data.clips} clip{est.data.clips > 1 ? "s" : ""} on this computer.</p>}
      <RightsCheck url={url} isFile={!!file} onChange={setPerm} />

      {/* 3. length and count */}
      {mode === "clips" && (
        <div className="flex flex-wrap items-end gap-4">
          <div className="space-y-1">
            <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Clip length</span>
            <div className="flex flex-wrap gap-2">
              {LENGTHS.map(([n, a, b]) => <button key={n} type="button" className={chip(lenOn === n)} onClick={() => setO((x) => ({ ...x, min_seconds: a, max_seconds: b }))}>{n} <span className="text-xs opacity-70">{a}–{b}s</span></button>)}
            </div>
          </div>
          <Label text="How many">
            <select className={field} value={o.count} onChange={(e) => set("count", +e.target.value)}>
              <option value={0}>Auto (from the length)</option>
              {[1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20].map((n) => <option key={n} value={n}>{n}</option>)}
            </select>
          </Label>
        </div>
      )}

      {/* 4. the one thing that most improves the picks */}
      <div className="border border-[rgba(200,255,58,0.35)] p-3">
        <p className="mb-2 text-xs text-muted-foreground"><span className="font-medium text-foreground">AI helper</span> — picks complete, interesting moments and writes titles. Without one, only loudness is used.</p>
        <CrewPicker value={o.crew} onChange={(v) => set("crew", v)} />
      </div>

      {/* 5. everything else, folded away */}
      <Section title="Captions" value={capName}>
        <CaptionStudio ov={ov} v={cv} set={setCap} />
      </Section>
      <Section title="Template & layout" value={`${tplName} · ${cap.layouts?.[o.layout]?.split(" (")[0] ?? o.layout}`}>
        <FramePicker ov={ov} v={fr} set={(p) => setFr((x) => ({ ...x, ...p }))} />
        <div className="space-y-2"><span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Layout</span><LayoutPicker value={o.layout} onChange={(v) => set("layout", v)} options={cap.layouts} /></div>
        {cap.reframe && !cap.reframe.ready && o.layout === "auto" && <Note tone="warn">Face tracking isn&apos;t installed, so this falls back to the blurred layout. {cap.reframe.fix}</Note>}
        <div className="grid gap-4 sm:grid-cols-2">
          {kind !== "talk" && (
            <Label text="How much of the game to show">
              <select className={field} value={hy.game_view} onChange={(e) => setHy((x) => ({ ...x, game_view: e.target.value }))}>
                <option value="auto">Auto</option><option value="whole">All of it</option><option value="most">Most of it</option><option value="close">Close up</option>
              </select>
            </Label>
          )}
          {o.layout === "auto" && (
            <Label text="Two people on screen">
              <select className={field} value={o.multi} onChange={(e) => set("multi", e.target.value)}><option value="speaker">Close shot of whoever talks</option><option value="split">Split screen</option></select>
            </Label>
          )}
        </div>
      </Section>
      <Section title="Branding & saved looks" value={brand.wm ? "Watermark on" : "Off"}>
        <SavedLooks current={{ caption: cv.caption, cap: cv.cap, brand, layout: o.layout, music: ed.music, edit: ed.edit, look: ed.look, cap_lang: cv.cap_lang }} apply={applyLook} />
        <BrandKit v={brand} set={setBrand} />
      </Section>
      <Section title="Editing & music" value={`${EDITS[ed.edit]?.[0] ?? ed.edit} · ${ed.music === "none" ? "no music" : "music"}`}>
        <div className="space-y-1">
          <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Edit style</span>
          <div className="flex flex-wrap gap-2">
            {Object.entries(EDITS).map(([k, [name]]) => <button key={k} type="button" className={chip(ed.edit === k)} onClick={() => applyEdit(k)}>{name}</button>)}
          </div>
          <p className="text-xs text-muted-foreground">Clean: slow zooms only (talk). Classic: zooms, keyword badges, pops. Punchy: everything plus flashes on the peaks and a progress bar (gaming).</p>
        </div>
        <Label text="Music">
          <select className={field} value={ed.music === "none" ? "none" : "auto"} onChange={(e) => setE("music", e.target.value)}>
            <option value="none">No music (keeps the original sound clean)</option><option value="auto">Soft music that fits each clip, dips under voices</option>
          </select>
        </Label>
        {ed.music !== "none" && <Switch on={hy.riser} onChange={(v) => setHy((x) => ({ ...x, riser: v }))} label="Music rises to the payoff" hint="Low under the talking, climbing to a peak in the last seconds." />}
        <Section title="Fine-tune effects, colour and your own music" value="optional">
          <EditingPicker o={ed} set={setE} ov={ov} />
        </Section>
      </Section>
      <Section title="Advanced" value="Usually leave these">
        <div className="grid gap-4 sm:grid-cols-3">
          <Label text="Quality"><select className={field} value={o.quality} onChange={(e) => set("quality", e.target.value)}><option value="720p">720p</option><option value="1080p">1080p</option></select></Label>
          <Label text="From minute"><input type="number" min={0} className={field} value={o.start_min} onChange={(e) => set("start_min", e.target.value)} /></Label>
          <Label text="To minute"><input type="number" min={0} className={field} value={o.end_min} onChange={(e) => set("end_min", e.target.value)} /></Label>
          {mode === "clips" && <>
            <Label text="Shortest (s)"><input type="number" min={5} max={170} className={field} value={o.min_seconds} onChange={(e) => set("min_seconds", +e.target.value)} /></Label>
            <Label text="Longest (s)"><input type="number" min={10} max={180} className={field} value={o.max_seconds} onChange={(e) => set("max_seconds", +e.target.value)} /></Label>
          </>}
        </div>
        {file && (
          <Label text="Subtitles for your file (optional .srt)"><input type="file" accept=".srt" className={field + " py-1.5"} onChange={(e) => setSrt(e.target.files?.[0] ?? null)} /></Label>
        )}
        {mode === "clips" && <div className="space-y-3">
          {kind !== "talk" && (
            <Label text="How many moments to accept" hint="Balanced suits almost every video. Only the biggest: fewer, stronger clips. More: a lower bar when a video is calm.">
              <select className={field} value={hy.hype_level} onChange={(e) => setHy((x) => ({ ...x, hype_level: e.target.value }))}><option value="strict">Only the biggest</option><option value="balanced">Balanced (recommended)</option><option value="more">More moments</option></select>
            </Label>
          )}
          <Switch on={hy.accurate} onChange={(v) => setHy((x) => ({ ...x, accurate: v }))} label="Accurate captions" hint="Listens to each clip again instead of trusting YouTube's auto-captions. Slower, far fewer wrong words. Keep on." />
          <Switch on={hy.research} onChange={(v) => setHy((x) => ({ ...x, research: v }))} label="Titles and hashtags from the top Shorts on the topic" hint="Keep on unless you write your own titles." />
        </div>}
        <Readiness />
      </Section>

      {go.isError && <Note tone="err">{(go.error as Error).message}</Note>}
      {(!cap.yt_dlp || !cap.whisper) && (
        <Note tone="warn">Missing: {[!cap.yt_dlp && "yt-dlp (links)", !cap.whisper && "faster-whisper (captions)"].filter(Boolean).join(", ")}. Install with <code className="font-mono">docker compose exec animation-studio pip install yt-dlp faster-whisper</code>.</Note>
      )}
      <p className="text-xs text-muted-foreground">Clip only video you own or have permission to use.</p>
    </Card>
  );
}

/** A folded group: the title and what is chosen now; open it to change. */
function Section({ title, value, children }: { title: string; value: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-border">
      <button type="button" aria-expanded={open} onClick={() => setOpen((x) => !x)} className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-muted/40">
        <span className="text-sm font-medium">{title}</span>
        <span className="flex min-w-0 items-center gap-2 text-xs text-muted-foreground"><span className="truncate">{value}</span>{open ? <ChevronUp className="h-4 w-4 shrink-0" /> : <ChevronDown className="h-4 w-4 shrink-0" />}</span>
      </button>
      {open && <div className="space-y-4 border-t border-border p-3">{children}</div>}
    </div>
  );
}
