"use client";

// GPU compute: your GPU workers (VRAM, loaded models, queue), the Model Router's choices, generation limits and
// every run. AVOS decides WHAT runs (model, precision, where); the workers decide HOW (ComfyUI / Wan2GP / Diffusers).
import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity, AlertTriangle, CheckCircle2, CircleDashed, Cpu, Gauge, Loader2, Plus, Power, RefreshCw, Route, Server,
  SlidersHorizontal, Thermometer, Trash2, X, Zap,
} from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { BACKEND_LABEL, RunsTable, fmtS, fmtUsd } from "@/components/gpu/RunsTable";
import { queryKeys, useGpu, useGpuJobs } from "@/hooks/queries";
import { useLiveProject } from "@/hooks/useLiveProject";
import { gpuApi } from "@/lib/api";
import {
  PREFERENCE_LABEL, type GenerationLimits, type GpuWorker, type Preference, type RoutePlan,
} from "@/types";

const input =
  "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/30";
const btn = "inline-flex items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted disabled:opacity-50";
const primary =
  "inline-flex items-center gap-1.5 rounded-xl bg-primary hover:bg-[#8873be] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50";

function Card({ icon, title, sub, children, id, right }: { icon: ReactNode; title: string; sub?: string; children: ReactNode; id: string; right?: ReactNode }) {
  return (
    <section id={id} className="rounded-xl border border-border bg-card/50 p-5" data-testid={`gpu-${id}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">{icon}{title}</h2>
          {sub && <p className="mt-1 text-sm text-muted-foreground">{sub}</p>}
        </div>
        {right}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}


function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card/40 p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
      {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
    </div>
  );
}

// ---------------- workers ----------------
function VramBar({ w }: { w: GpuWorker }) {
  const total = w.gpu?.vram_gb ?? 0;
  if (!total) return null;
  const free = w.gpu?.free_vram_gb ?? total;
  const models = w.loaded_models ?? [];
  const modelGb = models.reduce((a, m) => a + (m.vram_gb || 0), 0);
  // nvidia-smi's number when the worker has one; never less than what the loaded models need
  const used = Math.max(0, total - free, modelGb);
  const other = Math.max(0, used - modelGb);
  const pct = (gb: number) => `${Math.min(100, (gb / total) * 100)}%`;
  const colors = ["bg-amber-500", "bg-orange-500", "bg-rose-500", "bg-violet-500"];
  return (
    <div>
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{w.gpu?.device === "cpu" ? `Memory: ${w.gpu.ram_gb ?? 0} GB RAM + ${w.gpu.swap_gb ?? 0} GB page file (CPU, ≤${w.gpu.max_side ?? 512}px, ≤${w.gpu.max_seconds ?? 5}s clips)` : "VRAM"}</span>
        <span data-testid="vram-text">{used.toFixed(1)} / {total.toFixed(0)} GB</span>
      </div>
      <div className="mt-1 flex h-2.5 overflow-hidden rounded-full bg-muted" role="img" aria-label={`VRAM ${used.toFixed(1)} of ${total} GB used`}>
        {models.map((m, i) => (
          <div key={`${m.model}-${m.adapter}`} className={colors[i % colors.length]} style={{ width: pct(m.vram_gb || 0) }} title={`${m.model} (${m.precision}) ${m.vram_gb} GB`} />
        ))}
        {other > 0.05 && <div className="bg-slate-400/60" style={{ width: pct(other) }} title={`Other programs ${other.toFixed(1)} GB`} />}
      </div>
    </div>
  );
}

function WorkerCard({ w, onChanged }: { w: GpuWorker; onChanged: () => void }) {
  const [busy, setBusy] = useState(""), [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const act = async (tag: string, fn: () => Promise<unknown>, ok?: (r: unknown) => string) => {
    setBusy(tag); setMsg(null);
    try {
      const r = await fn();
      if (ok) setMsg({ ok: true, text: ok(r) });
      onChanged();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy("");
    }
  };
  const adapters = Object.entries(w.adapters ?? {});
  const running = w.running;
  const state = !w.enabled ? "off" : !w.online ? "offline" : w.status ?? "ready";
  const pill =
    state === "generating" || state === "loading" ? "bg-amber-500/15 text-amber-700 dark:text-amber-300"
      : state.startsWith("ready") ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300"
        : "bg-red-500/10 text-red-600 dark:text-red-400";
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card/40 p-5" data-testid={`worker-${w.id}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-base font-semibold text-foreground">{w.name}</h3>
          <p className="truncate text-xs text-muted-foreground">{w.url}</p>
        </div>
        <span className={`shrink-0 rounded-md px-2 py-0.5 text-[11px] font-medium ${pill}`} data-testid="worker-state">{state}</span>
      </div>

      {w.online ? (
        <>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
            <span className="flex items-center gap-1.5 font-medium text-foreground"><Cpu className="h-4 w-4 text-amber-500" />{w.gpu?.name ?? "No GPU found"}{w.gpu?.fake ? " (pretend)" : ""}</span>
            {w.gpu?.temperature_c != null && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Thermometer className="h-3.5 w-3.5" />{w.gpu.temperature_c} °C</span>}
            {w.gpu?.utilization != null && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Activity className="h-3.5 w-3.5" />{w.gpu.utilization}%</span>}
            <span className="text-xs text-muted-foreground">{w.cost_per_hour ? `$${w.cost_per_hour}/h` : "free (your GPU)"}</span>
          </div>
          <VramBar w={w} />
          <div className="flex flex-wrap gap-1.5 text-[11px]">
            {Object.entries(w.supports ?? {}).filter(([k, v]) => v && ["bf16", "fp8", "fp4", "int8", "triton", "sageattention", "flash_attn", "nunchaku"].includes(k)).map(([k]) => (
              <span key={k} className="rounded-lg bg-muted px-2 py-0.5 text-muted-foreground">{k}</span>
            ))}
          </div>

          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Backends</p>
            {adapters.length === 0 && <p className="text-xs text-muted-foreground">None configured on the worker (WORKER_ADAPTERS).</p>}
            {adapters.map(([name, a]) => (
              <div key={name} className="flex gap-2 text-xs">
                {a.ready ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" /> : <CircleDashed className="h-4 w-4 shrink-0 text-muted-foreground" />}
                <div className="min-w-0">
                  <span className="font-medium text-foreground">{name}</span>
                  {a.ready ? (
                    <span className="text-muted-foreground"> · {a.attention} attention · {a.precisions.join(", ")} · {a.models.length ? a.models.join(", ") : "no models installed yet"}</span>
                  ) : (
                    <span className="text-amber-600 dark:text-amber-400 [overflow-wrap:anywhere]"> · {a.why}</span>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Loaded models</p>
            {(w.loaded_models ?? []).length === 0 && <p className="text-xs text-muted-foreground">None: the first shot loads its model.</p>}
            {(w.loaded_models ?? []).map((m) => (
              <div key={`${m.model}-${m.adapter}`} className="flex items-center justify-between gap-2 text-xs" data-testid={`loaded-${m.model}`}>
                <span className="text-foreground">{m.model} <span className="text-muted-foreground">· {m.adapter} · {m.precision} · {m.vram_gb} GB · used {m.uses}×{m.pinned ? " · pinned" : ""}</span></span>
                {!m.pinned && (
                  <button className="text-muted-foreground hover:text-red-400" disabled={!!busy} title="Free its VRAM"
                    onClick={() => act(`u-${m.model}`, () => gpuApi.unloadModel(w.id, { model: m.model, adapter: m.adapter }))}>
                    <X className="h-3.5 w-3.5" />
                  </button>
                )}
              </div>
            ))}
          </div>

          <div className="text-xs text-muted-foreground" data-testid="worker-queue">
            {running ? (
              <div className="space-y-1">
                <p className="text-foreground">{running.status === "loading" ? "Loading" : "Running"} {running.model} ({running.precision}) · {running.step}{running.tag ? <span className="text-muted-foreground"> · {running.tag}</span> : null}</p>
                <div className="h-1.5 overflow-hidden rounded-full bg-muted"><div className="h-full bg-amber-500 transition-all" style={{ width: `${Math.round((running.progress || 0) * 100)}%` }} /></div>
              </div>
            ) : "Idle."}
            {(w.queue ?? []).length > 0 && (
              <ol className="mt-1 space-y-0.5" data-testid="worker-queue-list">
                {(w.queue ?? []).slice(0, 6).map((j, i) => (
                  <li key={j.id} className="flex items-center gap-1.5">
                    <span className="w-4 text-right">{i + 1}.</span>
                    <span className="text-foreground">{j.task === "load" ? `warm up ${j.model}` : `${j.model} ${j.task}`}</span>
                    {j.priority === 0 && <span className="rounded bg-amber-500/20 px-1 text-[10px] text-amber-700 dark:text-amber-300">urgent</span>}
                    {j.tag && <span className="truncate">· {j.tag}</span>}
                  </li>
                ))}
                {(w.queue ?? []).length > 6 && <li>… {(w.queue ?? []).length - 6} more</li>}
              </ol>
            )}
            {(w.queue ?? []).length === 0 && (w.queue_depth ?? 0) > 0 && <p>{w.queue_depth} job(s) waiting.</p>}
            {w.avg_job_seconds != null && <p>Average job: {fmtS(w.avg_job_seconds)}</p>}
          </div>
        </>
      ) : (
        <p className="text-sm text-amber-600 dark:text-amber-400 [overflow-wrap:anywhere]" data-testid="worker-error">{w.error}</p>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-1">
        <button className={btn} disabled={!!busy} onClick={() => act("t", () => gpuApi.testWorker(w.id), (r) => (r as GpuWorker).summary ?? (r as GpuWorker).error ?? "Checked")} data-testid="worker-test">
          {busy === "t" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Server className="h-4 w-4" />}Test
        </button>
        {"comfyui" in (w.adapters ?? {}) && (
          <button className={btn} disabled={!!busy} title="Send the ComfyUI workflows uploaded in Settings → Models to this worker"
            onClick={() => act("wf", () => gpuApi.pushWorkflows(w.id), (r) => {
              const x = r as { sent: string[]; failed: string[] };
              return x.sent.length ? `Sent ${x.sent.join(", ")}${x.failed.length ? ` · failed: ${x.failed.join("; ")}` : ""}` : "No workflows uploaded yet (Settings → Models).";
            })}>
            Send workflows
          </button>
        )}
        <button className={btn} disabled={!!busy} onClick={() => act("e", () => gpuApi.saveWorker({ id: w.id, name: w.name, url: w.url, cost_per_hour: w.cost_per_hour_setting ?? null, enabled: !w.enabled }))}>
          <Power className="h-4 w-4" />{w.enabled ? "Turn off" : "Turn on"}
        </button>
        <button className={`${btn} ml-auto hover:text-red-400`} disabled={!!busy} onClick={() => { if (confirm(`Remove ${w.name}?`)) act("d", () => gpuApi.deleteWorker(w.id)); }} aria-label={`Remove ${w.name}`}>
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
      {msg && <p className={`text-xs ${msg.ok ? "text-emerald-500" : "text-red-400"} [overflow-wrap:anywhere]`} data-testid="worker-msg">{msg.text}</p>}
    </div>
  );
}

function AddWorker({ onChanged }: { onChanged: () => void }) {
  const [name, setName] = useState(""), [url, setUrl] = useState(""), [cost, setCost] = useState("");
  const [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const add = async () => {
    setBusy(true); setErr("");
    try {
      await gpuApi.saveWorker({ name: name.trim() || url.trim(), url: url.trim(), cost_per_hour: cost.trim() === "" ? null : cost.trim() });
      setName(""); setUrl(""); setCost("");
      onChanged();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="rounded-xl border border-dashed border-border p-5" data-testid="add-worker">
      <h3 className="flex items-center gap-2 text-base font-semibold text-foreground"><Plus className="h-4 w-4 text-amber-500" />Add a GPU worker</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Run <span className="font-mono">apps/gpu_worker</span> on the GPU machine (your PC with an RTX card, a RunPod / Vast.ai pod, a cloud VM), then paste its address.
      </p>
      <div className="mt-3 grid gap-2 sm:grid-cols-[1fr_1.4fr_120px_auto]">
        <input className={input} placeholder="Name, e.g. RTX 4090 at home" value={name} onChange={(e) => setName(e.target.value)} aria-label="Worker name" />
        <input className={input} placeholder="http://192.168.1.20:8700 or https://<pod>-8700.proxy.runpod.net" value={url} onChange={(e) => setUrl(e.target.value)} aria-label="Worker address" data-testid="worker-url" />
        <input className={input} placeholder="$ / hour" value={cost} onChange={(e) => setCost(e.target.value)} aria-label="Cost per hour" inputMode="decimal" />
        <button className={primary} disabled={busy || !url.trim()} onClick={add} data-testid="worker-add">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}Add</button>
      </div>
      {err && <p className="mt-2 text-xs text-red-400">{err}</p>}
      <p className="mt-2 text-xs text-muted-foreground">
        Protect workers with a shared token: set <span className="font-mono">GPU_WORKER_TOKEN</span> in <Link href="/settings#keys" className="underline">Settings → API keys</Link> and the same value on each worker. Setup guide: apps/gpu_worker/README.md.
      </p>
    </div>
  );
}

// ---------------- limits ----------------
function Limits({ limits, preferences, onSaved }: { limits: GenerationLimits; preferences: Preference[]; onSaved: () => void }) {
  const [draft, setDraft] = useState<Record<string, string | boolean>>({});
  const [busy, setBusy] = useState(false), [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const val = (k: keyof GenerationLimits) => (k in draft ? draft[k] : limits[k] ?? "") as string | boolean;
  const set = (k: string, v: string | boolean) => setDraft((d) => ({ ...d, [k]: v }));
  const save = async () => {
    setBusy(true); setMsg(null);
    try {
      const body: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(draft)) body[k] = v === "" ? null : v;
      await gpuApi.setLimits(body as Partial<GenerationLimits>);
      setDraft({});
      setMsg({ ok: true, text: "Saved" });
      onSaved();
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card id="limits" icon={<SlidersHorizontal className="h-5 w-5 text-amber-400" />} title="Generation limits"
      sub="How the router trades quality, speed and cost for every shot, and when it stops trying. A project can override these (Priority in New video).">
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Preference">
          {preferences.map((p) => (
            <button key={p} role="radio" aria-checked={val("preference") === p} onClick={() => set("preference", p)} data-testid={`pref-${p}`}
              className={`rounded-xl border px-3 py-1.5 text-sm ${val("preference") === p ? "border-amber-500/60 bg-amber-500/10 text-foreground" : "border-border text-muted-foreground hover:text-foreground"}`}>
              {PREFERENCE_LABEL[p]}
            </button>
          ))}
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs text-muted-foreground">Max cost per shot (USD)
            <input className={`${input} mt-1`} inputMode="decimal" placeholder="no limit" value={String(val("max_cost_per_shot") ?? "")} onChange={(e) => set("max_cost_per_shot", e.target.value)} data-testid="limit-cost" />
          </label>
          <label className="text-xs text-muted-foreground">Max time per shot (seconds)
            <input className={`${input} mt-1`} inputMode="numeric" placeholder="no limit" value={String(val("max_seconds_per_shot") ?? "")} onChange={(e) => set("max_seconds_per_shot", e.target.value)} />
          </label>
          <label className="text-xs text-muted-foreground">Max generations per shot
            <input className={`${input} mt-1`} inputMode="numeric" value={String(val("max_attempts") ?? "")} onChange={(e) => set("max_attempts", e.target.value)} data-testid="limit-attempts" />
          </label>
          <label className="flex items-center gap-2 self-end pb-2 text-sm text-foreground">
            <input type="checkbox" className="h-4 w-4 accent-amber-500" checked={Boolean(val("allow_hosted"))} onChange={(e) => set("allow_hosted", e.target.checked)} />
            Allow paid hosted APIs (fal.ai, Replicate)
          </label>
        </div>
        <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm text-foreground">
          <label className="flex items-center gap-2">
            <input type="checkbox" className="h-4 w-4 accent-amber-500" checked={Boolean(val("auto_qa"))} onChange={(e) => set("auto_qa", e.target.checked)} data-testid="limit-auto-qa" />
            QA every shot and repair failures automatically
          </label>
          <label className="flex items-center gap-2">
            <input type="checkbox" className="h-4 w-4 accent-amber-500" checked={Boolean(val("review_shots"))} onChange={(e) => set("review_shots", e.target.checked)} data-testid="limit-review" />
            Let me review the shots before the final video
          </label>
        </div>
        <div className="flex items-center gap-3">
          <button className={primary} disabled={busy || Object.keys(draft).length === 0} onClick={save} data-testid="limits-save">{busy && <Loader2 className="h-4 w-4 animate-spin" />}Save limits</button>
          {msg && <span className={`text-xs ${msg.ok ? "text-emerald-500" : "text-red-400"}`}>{msg.text}</span>}
          <span className="text-xs text-muted-foreground">After the last generation a person decides (the repair ladder stops).</span>
        </div>
      </div>
    </Card>
  );
}

// ---------------- router preview ----------------
function RoutePreview() {
  const [task, setTask] = useState<"image" | "video" | "avatar">("video");
  const [seconds, setSeconds] = useState("5"), [prompt, setPrompt] = useState("");
  const [audio, setAudio] = useState(false), [continuity, setContinuity] = useState(false);
  const [plan, setPlan] = useState<RoutePlan | null>(null), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const run = async () => {
    setBusy(true); setErr("");
    try {
      setPlan(await gpuApi.route({ task, seconds: Number(seconds) || 5, prompt, has_audio: audio, continuity }));
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <Card id="route" icon={<Route className="h-5 w-5 text-amber-400" />} title="Ask the router"
      sub="What AVOS would pick for a shot like this right now: model, where, precision, and the estimate. Nothing is generated.">
      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-muted-foreground">Job
          <select className={`${input} mt-1 w-auto`} value={task} onChange={(e) => setTask(e.target.value as typeof task)} aria-label="Job" data-testid="route-task">
            <option value="video">Video clip</option><option value="image">Picture</option><option value="avatar">Talking presenter</option>
          </select>
        </label>
        {task !== "image" && (
          <label className="text-xs text-muted-foreground">Seconds
            <input className={`${input} mt-1 w-20`} inputMode="decimal" value={seconds} onChange={(e) => setSeconds(e.target.value)} />
          </label>
        )}
        {task === "image" && (
          <label className="min-w-[240px] flex-1 text-xs text-muted-foreground">Prompt (text in the picture changes the choice)
            <input className={`${input} mt-1`} value={prompt} onChange={(e) => setPrompt(e.target.value)} placeholder="A poster titled 'Volcanoes'" />
          </label>
        )}
        {task === "video" && (
          <>
            <label className="flex items-center gap-2 pb-2 text-sm text-foreground"><input type="checkbox" className="accent-amber-500" checked={audio} onChange={(e) => setAudio(e.target.checked)} />Follows narration</label>
            <label className="flex items-center gap-2 pb-2 text-sm text-foreground"><input type="checkbox" className="accent-amber-500" checked={continuity} onChange={(e) => setContinuity(e.target.checked)} />Keep look (repair)</label>
          </>
        )}
        <button className={primary} onClick={run} disabled={busy} data-testid="route-run">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Zap className="h-4 w-4" />}Route</button>
      </div>
      {err && <p className="mt-2 text-sm text-red-400">{err}</p>}
      {plan && (
        <div className="mt-4 space-y-3" data-testid="route-result">
          {plan.placements.length === 0 && <p className="text-sm text-amber-600 dark:text-amber-400">Nothing can run this now: see why below.</p>}
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-sm">
              <thead className="text-xs uppercase text-muted-foreground">
                <tr><th className="py-1 pr-3">#</th><th className="pr-3">Model</th><th className="pr-3">Where</th><th className="pr-3">Quality</th><th className="pr-3">Time</th><th className="pr-3">Cost</th><th>Why</th></tr>
              </thead>
              <tbody>
                {plan.placements.slice(0, 8).map((p, i) => (
                  <tr key={`${p.model}-${p.backend}-${p.worker_id}-${p.adapter}`} className={`border-t border-border align-top ${i === 0 ? "bg-amber-500/5" : ""}`}>
                    <td className="py-2 pr-3 text-muted-foreground">{i === 0 ? <span className="font-semibold text-amber-600 dark:text-amber-400">pick</span> : i + 1}</td>
                    <td className="pr-3 font-medium text-foreground">{p.model_name}</td>
                    <td className="pr-3 text-foreground">
                      {p.backend === "gpu" ? <>{p.worker_name}<span className="block text-xs text-muted-foreground">{p.gpu} · {p.adapter} · {p.precision}{p.offload ? " · offload" : ""}</span></> : BACKEND_LABEL[p.backend] ?? p.backend}
                    </td>
                    <td className="pr-3">{p.quality.toFixed(2)}</td>
                    <td className="pr-3">{fmtS(p.est_seconds)}</td>
                    <td className="pr-3">{fmtUsd(p.est_cost)}</td>
                    <td className="text-xs text-muted-foreground">{p.reasons.join(" · ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {plan.rejected.length > 0 && (
            <details className="text-xs text-muted-foreground">
              <summary className="cursor-pointer">{plan.rejected.length} option(s) ruled out</summary>
              <ul className="mt-1 space-y-0.5">
                {plan.rejected.map((r, i) => <li key={i}><span className="text-foreground">{r.model}</span> on {r.worker ?? BACKEND_LABEL[r.backend] ?? r.backend}{r.adapter ? ` (${r.adapter})` : ""}: {r.why}</li>)}
              </ul>
            </details>
          )}
        </div>
      )}
    </Card>
  );
}

function Learned() {
  const q = useQuery({ queryKey: ["gpu-learned"], queryFn: gpuApi.learned, refetchInterval: 30_000, retry: false });
  const rows = q.data?.rows ?? [];
  return (
    <Card id="learned" icon={<Gauge className="h-5 w-5 text-amber-400" />} title="What routing has learned"
      sub={`Measured speed, success and QA per model and GPU. After ${q.data?.min_runs ?? 3} runs the router uses these instead of the catalog's estimates.`}>
      {rows.length === 0 ? <p className="text-sm text-muted-foreground">Nothing measured yet.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[560px] text-left text-sm">
            <thead className="text-xs uppercase text-muted-foreground"><tr><th className="py-1 pr-3">Model</th><th className="pr-3">Where</th><th className="pr-3">Runs</th><th className="pr-3">Succeeded</th><th className="pr-3">Time per unit</th><th className="pr-3">Avg QA</th><th>In use</th></tr></thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.model}|${r.where}`} className="border-t border-border">
                  <td className="py-2 pr-3 font-medium text-foreground">{r.model}</td>
                  <td className="pr-3 text-foreground">{BACKEND_LABEL[r.where.toLowerCase()] ?? r.where}</td>
                  <td className="pr-3">{r.runs}</td>
                  <td className="pr-3">{r.runs ? `${Math.round((r.ok / r.runs) * 100)}%` : "—"}</td>
                  <td className="pr-3">{fmtS(r.unit_seconds)}</td>
                  <td className="pr-3">{r.avg_qa != null ? r.avg_qa.toFixed(2) : "—"}</td>
                  <td>{r.used_for_routing ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <span className="text-xs text-muted-foreground">not yet</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export default function GpuPage() {
  const qc = useQueryClient();
  const gpu = useGpu();
  const runs = useGpuJobs(undefined, 5_000);
  useLiveProject();
  const refresh = () => {
    qc.invalidateQueries({ queryKey: queryKeys.gpu });
    qc.invalidateQueries({ queryKey: queryKeys.models });
  };
  const d = gpu.data;
  const online = d?.workers.filter((w) => w.online).length ?? 0;

  const header = (
    <div className="flex flex-1 items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-muted-foreground"><Cpu className="h-4 w-4" /> GPU compute</div>
      <button type="button" onClick={refresh} className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground">
        <RefreshCw className={`h-4 w-4 ${gpu.isFetching ? "animate-spin" : ""}`} /> Refresh
      </button>
    </div>
  );

  return (
    <AppShell header={header}>
      <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
        <div>
          <h1 className="mb-2 text-2xl font-bold text-foreground md:text-3xl">GPU</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            Your GPU workers and what they are doing. For every picture and clip the Model Router picks the model, the GPU
            (or a hosted API) and the precision that fits its VRAM, by quality, speed and cost, and keeps models loaded between shots.
          </p>
        </div>

        {gpu.isLoading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading…</p>}
        {gpu.error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">{(gpu.error as Error).message}</p>}

        {d && (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="gpu-stats">
              <Stat label="Workers online" value={`${online} / ${d.workers.length}`} sub={d.modelBackend === "gpu" ? "Only GPU workers (Settings)" : d.modelBackend === "auto" ? "Auto: workers, then free tiers, then fal.ai" : `Forced: ${d.modelBackend}`} />
              <Stat label="Runs" value={d.totals.runs} sub={`${d.totals.done} done · ${d.totals.failed} failed`} />
              <Stat label="GPU time" value={fmtS(d.totals.gpu_seconds)} />
              <Stat label="Spent" value={fmtUsd(d.totals.cost_usd)} sub="GPU hours + hosted APIs" />
            </div>

            <Card id="workers" icon={<Server className="h-5 w-5 text-amber-400" />} title="GPU workers"
              sub="One worker per GPU. AVOS doesn't care where the GPU is: your PC, a rented pod or a cloud VM.">
              {!d.tokenSet && d.workers.length > 0 && (
                <p className="mb-3 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">
                  <AlertTriangle className="h-4 w-4 shrink-0" />No GPU_WORKER_TOKEN set: anyone who can reach a worker&apos;s address can use its GPU.
                </p>
              )}
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {d.workers.map((w) => <WorkerCard key={w.id} w={w} onChanged={refresh} />)}
              </div>
              <div className="mt-4"><AddWorker onChanged={refresh} /></div>
            </Card>

            <Limits limits={d.limits} preferences={d.preferences} onSaved={refresh} />
            <RoutePreview />

            <Card id="runs" icon={<Activity className="h-5 w-5 text-amber-400" />} title="Runs"
              sub="Every picture and clip, where it ran, how long it took and what it cost. Live while a project is generating.">
              <RunsTable jobs={runs.data ?? d.jobs} />
            </Card>

            <Learned />
          </>
        )}
      </div>
    </AppShell>
  );
}
