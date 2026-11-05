"use client";

import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Clapperboard,
  Loader2,
  MapPin,
  Pencil,
  RefreshCw,
  Sparkles,
  Users,
  XCircle,
} from "lucide-react";
import { useShot } from "@/hooks/queries";
import { shotsApi } from "@/lib/api";
import type { ShotContent, ShotDetail, ShotEdit } from "@/types";

type TabKey = "narrative" | "camera" | "character" | "environment" | "prompt";

const TABS: { key: TabKey; label: string }[] = [
  { key: "narrative", label: "Narrative" },
  { key: "camera", label: "Camera" },
  { key: "character", label: "Character" },
  { key: "environment", label: "Environment" },
  { key: "prompt", label: "Prompt" },
];

const SHOT_TYPE_LABEL: Record<string, string> = {
  wide: "Wide",
  medium: "Medium",
  close_up: "Close-up",
  insert: "Insert",
};


/** Read-only prompt preview derived from the ShotSpec (the pixel stage
 * builds its real prompt from the same fields). */
export function buildPromptPreview(c: ShotContent): string {
  const parts: string[] = [];
  if (c.style) parts.push(c.style);
  parts.push(
    `${SHOT_TYPE_LABEL[c.camera.shot_type] ?? c.camera.shot_type} shot, ${c.camera.angle} angle, ` +
      `${c.camera.movement} camera, ${c.camera.lens_mm}mm lens`
  );
  if (c.description) parts.push(c.description);
  const chars = Object.entries(c.characters).map(([name, s]) =>
    [name, s.clothing && `wearing ${s.clothing}`, s.emotion, s.position].filter(Boolean).join(", ")
  );
  if (chars.length) parts.push(`Characters: ${chars.join("; ")}`);
  const env = c.environment;
  const setting = [env.location, env.time_of_day, env.weather].filter(Boolean).join(", ");
  if (setting) parts.push(`Setting: ${setting}`);
  parts.push(`Lighting: ${c.lighting.key}, ${c.lighting.mood}`);
  return parts.map((p) => p.trim().replace(/[.\s]+$/, "").replace(/_/g, " ")).join(". ") + ".";
}

function Field({ label, children, testId }: { label: string; children: React.ReactNode; testId?: string }) {
  return (
    <div>
      <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">{label}</p>
      <div className="text-sm leading-relaxed text-foreground" data-testid={testId}>
        {children}
      </div>
    </div>
  );
}

function Empty({ text }: { text: string }) {
  return <p className="text-xs text-muted-foreground">{text}</p>;
}

function NarrativeTab({ shot }: { shot: ShotDetail }) {
  const c = shot.spec.content;
  const continuity = shot.spec.continuity;
  return (
    <div className="space-y-4">
      <Field label="Beat">
        {c.beat_label} · {c.start_time.toFixed(2)}s → {c.end_time.toFixed(2)}s
        {c.scene_index !== null && <span className="text-muted-foreground"> · scene {c.scene_index + 1}</span>}
      </Field>
      <Field label="Narration" testId="shot-narration">
        {c.narration || <span className="text-muted-foreground">—</span>}
      </Field>
      <Field label="Visual description">
        <span className="text-muted-foreground">{c.description || "—"}</span>
      </Field>
      <Field label="Continuity">
        {continuity ? (
          <div className="space-y-2" data-testid="shot-continuity">
            <p className={`flex items-center gap-1.5 text-xs ${continuity.passed ? "text-green-300" : "text-red-300"}`}>
              {continuity.passed ? <CheckCircle2 className="h-3.5 w-3.5" /> : <XCircle className="h-3.5 w-3.5" />}
              {continuity.passed ? "Passed" : "Failed"} against WorldState v{continuity.world_state_version}
            </p>
            {continuity.violations.map((v, i) => (
              <p
                key={`${v.code}-${i}`}
                className={`flex gap-1.5 text-xs ${v.severity === "error" ? "text-red-300" : "text-amber-300"}`}
              >
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" />
                <span>
                  <span className="font-mono">{v.code}</span> — {v.message}
                </span>
              </p>
            ))}
          </div>
        ) : (
          <span className="text-xs text-muted-foreground">Not validated yet.</span>
        )}
      </Field>
    </div>
  );
}

function CameraTab({ content }: { content: ShotContent }) {
  const cam = content.camera;
  return (
    <div className="grid grid-cols-2 gap-4">
      <Field label="Shot type" testId="shot-type">
        {SHOT_TYPE_LABEL[cam.shot_type] ?? cam.shot_type}
      </Field>
      <Field label="Lens">{cam.lens_mm}mm</Field>
      <Field label="Angle">{cam.angle}</Field>
      <Field label="Movement">{cam.movement}</Field>
      <Field label="Needs physics">{content.requires_physics ? "Yes" : "No"}</Field>
    </div>
  );
}

function CharacterTab({ content }: { content: ShotContent }) {
  const characters = Object.entries(content.characters);
  const objects = Object.entries(content.objects);
  if (characters.length === 0 && objects.length === 0) {
    return <Empty text="No characters or tracked objects in this shot." />;
  }
  return (
    <div className="space-y-3">
      {characters.map(([name, s]) => (
        <div key={name} className="rounded-lg border border-border bg-card/60 p-3" data-testid="shot-character">
          <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-foreground">
            <Users className="h-3.5 w-3.5 text-amber-400" /> {name}
          </p>
          <dl className="grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
            <dt className="text-muted-foreground">Clothing</dt>
            <dd className="text-foreground/90">{s.clothing ?? "—"}</dd>
            <dt className="text-muted-foreground">Position</dt>
            <dd className="text-foreground/90">{s.position ?? "—"}</dd>
            <dt className="text-muted-foreground">Emotion</dt>
            <dd className="text-foreground/90">{s.emotion ?? "—"}</dd>
            <dt className="text-muted-foreground">Props</dt>
            <dd className="text-foreground/90">{s.props.length ? s.props.join(", ") : "—"}</dd>
          </dl>
        </div>
      ))}
      {objects.map(([name, o]) => (
        <div key={name} className="rounded-lg border border-border bg-card/60 p-3 text-xs">
          <p className="mb-1 font-semibold text-foreground">{name}</p>
          <p className="text-muted-foreground">
            {o.state ?? "—"}
            {o.position ? ` · ${o.position}` : ""}
          </p>
        </div>
      ))}
    </div>
  );
}

function EnvironmentTab({ content }: { content: ShotContent }) {
  const env = content.environment;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <Field label="Location" testId="shot-location">
          <span className="flex items-center gap-1">
            <MapPin className="h-3.5 w-3.5 text-muted-foreground" /> {env.location ?? "—"}
          </span>
        </Field>
        <Field label="Time of day">{env.time_of_day ?? "—"}</Field>
        <Field label="Weather">{env.weather ?? "—"}</Field>
        <Field label="Lighting">
          {content.lighting.key} · {content.lighting.mood}
        </Field>
      </div>
      <Field label="Style">{content.style ?? "—"}</Field>
      {content.scene_change && <p className="text-xs text-blue-300">Starts a new scene (location may change).</p>}
      {content.state_changes.length > 0 && (
        <Field label="Declared state changes">
          <ul className="list-disc space-y-1 pl-4 text-xs text-foreground/90">
            {content.state_changes.map((ch, i) => (
              <li key={i}>
                {ch.entity ? `${ch.entity}.` : ""}
                {ch.field} → {String(ch.value)}
                {ch.reason ? <span className="text-muted-foreground"> ({ch.reason})</span> : null}
              </li>
            ))}
          </ul>
        </Field>
      )}
    </div>
  );
}

function PromptTab({ content }: { content: ShotContent }) {
  return (
    <div className="space-y-2">
      <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
        {content.prompt ? "Prompt (written by you)" : "Prompt (built from this shot)"}
      </p>
      <pre
        className="whitespace-pre-wrap rounded-lg border border-border bg-background p-3 font-mono text-xs leading-relaxed text-foreground/90"
        data-testid="shot-prompt"
      >
        {content.prompt || buildPromptPreview(content)}
      </pre>
      <p className="text-[11px] text-muted-foreground">Change it below in “Edit &amp; regenerate”.</p>
    </div>
  );
}

const SHOT_TYPES = ["wide", "medium", "close_up", "insert"];
const ANGLES = ["eye_level", "low", "high", "overhead", "dutch"];
const MOVES = ["static", "pan", "tilt", "dolly_in", "dolly_out", "tracking", "orbit", "handheld", "zoom_in", "zoom_out"];
const STEP_LABEL: Record<string, string> = {
  saved: "Saved new version", physics: "Preparing the shot", visuals: "Making the picture and clip", final: "Re-rendering the final video", done: "Done",
};

const inputCls =
  "w-full rounded-lg border border-border bg-background px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted-foreground focus:border-amber-500/50 focus:outline-none";

function Pick({ label, value, onChange, options, id }: { label: string; value: string; onChange: (v: string) => void; options: string[]; id: string }) {
  return (
    <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
      {label}
      <input list={`${id}-list`} className={`${inputCls} mt-1 normal-case tracking-normal`} value={value} onChange={(e) => onChange(e.target.value)} data-testid={id} />
      <datalist id={`${id}-list`}>{options.map((o) => <option key={o} value={o} />)}</datalist>
    </label>
  );
}

/** Rewrite this shot (what we see, camera, place, the exact prompt) and regenerate it; the final video is
 * re-rendered with the new shot. Nothing changed = a new take with fresh seeds. */
function EditShot({ shot }: { shot: ShotDetail }) {
  const c = shot.spec.content;
  const preview = buildPromptPreview(c);
  const qc = useQueryClient();
  const [description, setDescription] = useState(c.description);
  const [shotType, setShotType] = useState<string>(c.camera.shot_type);
  const [angle, setAngle] = useState(c.camera.angle);
  const [movement, setMovement] = useState(c.camera.movement);
  const [lens, setLens] = useState(String(c.camera.lens_mm));
  const [location, setLocation] = useState(c.environment.location ?? "");
  const [timeOfDay, setTimeOfDay] = useState(c.environment.time_of_day ?? "");
  const [weather, setWeather] = useState(c.environment.weather ?? "");
  const [mood, setMood] = useState(c.lighting.mood);
  const [prompt, setPrompt] = useState(c.prompt || preview);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const status = useQuery({
    queryKey: ["regen", shot.id],
    queryFn: () => shotsApi.regenStatus(shot.id),
    refetchInterval: (q) => (q.state.data?.state === "running" ? 2000 : false),
  });
  const running = status.data?.state === "running";
  const wasRunning = useRef(false);
  useEffect(() => {
    if (running) wasRunning.current = true;
    if (!running && wasRunning.current) {
      wasRunning.current = false;
      qc.invalidateQueries();      // new version, candidates and final video
    }
  }, [running, qc]);

  const submit = async (newTake: boolean) => {
    setErr("");
    setBusy(true);
    try {
      const edit: ShotEdit = newTake
        ? { new_take: true }
        : {
            description,
            camera: { shot_type: shotType, angle, movement, lens_mm: Number(lens) || c.camera.lens_mm },
            environment: { location, time_of_day: timeOfDay, weather },
            lighting: { mood },
            prompt: prompt.trim() && prompt.trim() !== preview.trim() ? prompt.trim() : c.prompt && prompt.trim() === c.prompt ? c.prompt : null,
          };
      await shotsApi.edit(shot.id, edit);
      await status.refetch();
      qc.invalidateQueries({ queryKey: ["shot", shot.id] });
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 border-t border-border pt-4" data-testid="edit-shot">
      <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-amber-400">
        <Pencil className="h-3 w-3" /> Edit &amp; regenerate this shot
      </p>
      <label className="block text-[10px] uppercase tracking-wider text-muted-foreground">
        What we see
        <textarea rows={3} className={`${inputCls} mt-1 normal-case tracking-normal`} value={description} onChange={(e) => setDescription(e.target.value)} data-testid="edit-description" />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <Pick id="edit-shot-type" label="Shot type" value={shotType} onChange={setShotType} options={SHOT_TYPES} />
        <Pick id="edit-angle" label="Angle" value={angle} onChange={setAngle} options={ANGLES} />
        <Pick id="edit-movement" label="Camera move" value={movement} onChange={setMovement} options={MOVES} />
        <Pick id="edit-lens" label="Lens (mm)" value={lens} onChange={setLens} options={["18", "24", "35", "50", "85", "135"]} />
        <Pick id="edit-location" label="Location" value={location} onChange={setLocation} options={[]} />
        <Pick id="edit-time" label="Time of day" value={timeOfDay} onChange={setTimeOfDay} options={["dawn", "morning", "noon", "afternoon", "sunset", "night"]} />
        <Pick id="edit-weather" label="Weather" value={weather} onChange={setWeather} options={["clear", "cloudy", "rain", "snow", "fog", "storm"]} />
        <Pick id="edit-mood" label="Light mood" value={mood} onChange={setMood} options={["warm", "cool", "dramatic", "soft", "neon", "golden hour"]} />
      </div>
      <label className="block text-[10px] uppercase tracking-wider text-muted-foreground">
        Prompt for the picture and clip (edit freely)
        <textarea rows={6} className={`${inputCls} mt-1 font-mono normal-case tracking-normal`} value={prompt} onChange={(e) => setPrompt(e.target.value)} data-testid="edit-prompt" />
      </label>
      {prompt.trim() !== preview.trim() && (
        <button type="button" className="text-[11px] text-muted-foreground underline hover:text-foreground" onClick={() => setPrompt(preview)}>
          Use the prompt built from the fields above
        </button>
      )}
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={busy || running}
          onClick={() => submit(false)}
          className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50"
          data-testid="edit-save"
        >
          {busy || running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          Save &amp; regenerate shot
        </button>
        <button
          type="button"
          disabled={busy || running}
          onClick={() => submit(true)}
          className="rounded-lg border border-border px-3 py-2 text-xs text-foreground hover:bg-muted disabled:opacity-50"
          data-testid="edit-take"
          title="Same shot, new seeds"
        >
          New take
        </button>
      </div>
      {running && (
        <p className="flex items-center gap-1.5 text-xs text-amber-300" data-testid="regen-status">
          <Loader2 className="h-3 w-3 animate-spin" /> v{status.data?.version}: {STEP_LABEL[status.data?.step ?? "saved"]}…
        </p>
      )}
      {status.data?.state === "done" && (
        <p className="flex items-center gap-1.5 text-xs text-emerald-400" data-testid="regen-status">
          <CheckCircle2 className="h-3 w-3" /> v{status.data.version} is ready; the final video was re-rendered with it.
        </p>
      )}
      {status.data?.state === "error" && <p className="text-xs text-red-400" data-testid="regen-status">Regeneration failed: {status.data.error}</p>}
      {err && <p className="text-xs text-red-400" data-testid="edit-error">{err}</p>}
      <p className="text-[11px] text-muted-foreground">
        The narration stays the same. Only this shot is made again (with the project&apos;s picture and video models); then the final video is re-rendered.
      </p>
    </div>
  );
}

/** Right panel for a selected shot: the current version in five tabs, and an editor that saves a new version
 * and regenerates the shot. */
export function ShotEditor({ shotId }: { shotId: string }) {
  const { data: shot, isLoading, error } = useShot(shotId);
  const [tab, setTab] = useState<TabKey>("narrative");

  return (
    <div className="flex h-full flex-col" data-testid="shot-editor">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
        <Clapperboard className="h-4 w-4 text-amber-400" />
        <h2 className="text-sm font-semibold text-foreground">
          {shot ? `Shot ${String(shot.shot_index + 1).padStart(2, "0")}` : "Shot"}
        </h2>
        {shot && (
          <span className="ml-auto rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground">
            v{shot.current_version} · {shot.status}
          </span>
        )}
      </div>

      {isLoading && (
        <div className="flex flex-1 items-center justify-center text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      )}
      {error && !shot && <p className="p-4 text-xs text-red-400">Could not load this shot.</p>}

      {shot && (
        <>
          <div role="tablist" className="flex shrink-0 gap-0.5 overflow-x-auto border-b border-border px-2 py-2">
            {TABS.map((t) => (
              <button
                key={t.key}
                role="tab"
                aria-selected={tab === t.key}
                data-testid={`shot-tab-${t.key}`}
                onClick={() => setTab(t.key)}
                className={`whitespace-nowrap rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                  tab === t.key ? "bg-amber-500/15 text-amber-300" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="flex-1 space-y-5 overflow-y-auto p-4" role="tabpanel">
            {tab === "narrative" && <NarrativeTab shot={shot} />}
            {tab === "camera" && <CameraTab content={shot.spec.content} />}
            {tab === "character" && <CharacterTab content={shot.spec.content} />}
            {tab === "environment" && <EnvironmentTab content={shot.spec.content} />}
            {tab === "prompt" && <PromptTab content={shot.spec.content} />}

            <EditShot key={`${shot.id}-${shot.current_version}`} shot={shot} />

            {shot.versions.length > 1 && (
              <div className="border-t border-border pt-4">
                <p className="mb-2 flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-muted-foreground">
                  <Sparkles className="h-3 w-3" /> Versions
                </p>
                <ul className="space-y-1 text-xs text-muted-foreground">
                  {[...shot.versions].reverse().map((v) => (
                    <li key={v.shotspec_id} className="flex justify-between">
                      <span>
                        v{v.version}
                        {v.parent_version ? ` ← v${v.parent_version}` : ""}
                      </span>
                      <span className="text-muted-foreground">{v.status}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
