"use client";

// Settings shared by Explainer and Animations: API keys, the GPU server (ComfyUI), models you add, ComfyUI workflows.
import { useMemo, useRef, useState, type ReactNode } from "react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2, CircleDashed, Cpu, ExternalLink, KeyRound, Loader2, Plus, Server, Settings2, Trash2, Upload, Wand2, X,
} from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { queryKeys, useModels } from "@/hooks/queries";
import { settingsApi } from "@/lib/api";
import type { AppSettings, CatalogModel, CustomModelDef, SettingKey } from "@/types";

const SETTINGS_KEY = ["settings"] as const;
const input =
  "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-amber-500/50 focus:outline-none focus:ring-2 focus:ring-amber-500/30";
const btn = "inline-flex items-center gap-1.5 rounded-xl border border-border px-3 py-2 text-sm text-foreground transition-colors hover:bg-muted disabled:opacity-50";
const primary =
  "inline-flex items-center gap-1.5 rounded-xl bg-primary hover:bg-[#8873be] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50";

function Card({ icon, title, sub, children, id }: { icon: ReactNode; title: string; sub: string; children: ReactNode; id: string }) {
  return (
    <section id={id} className="rounded-xl border border-border bg-card/50 p-5" data-testid={`settings-${id}`}>
      <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">{icon}{title}</h2>
      <p className="mb-4 mt-1 text-sm text-muted-foreground">{sub}</p>
      {children}
    </section>
  );
}

function useSave() {
  const qc = useQueryClient();
  const [busy, setBusy] = useState(""), [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const run = async (tag: string, fn: () => Promise<AppSettings | unknown>, ok = "Saved") => {
    setBusy(tag); setMsg(null);
    try {
      const r = await fn();
      if (r && typeof r === "object" && "keys" in (r as object)) qc.setQueryData(SETTINGS_KEY, r);
      await qc.invalidateQueries({ queryKey: queryKeys.models });
      setMsg({ ok: true, text: ok });
      return r;
    } catch (e) {
      setMsg({ ok: false, text: (e as Error).message });
    } finally {
      setBusy("");
    }
  };
  return { busy, msg, run, setMsg };
}

// ---------------- API keys ----------------
function KeyRow({ k }: { k: SettingKey }) {
  const [value, setValue] = useState("");
  const { busy, msg, run } = useSave();
  return (
    <div className="grid grid-cols-1 gap-2 border-t border-border py-3 first:border-t-0 md:grid-cols-[260px_1fr_auto]" data-key={k.name}>
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-medium text-foreground">
          {k.set ? <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-500" /> : <CircleDashed className="h-4 w-4 shrink-0 text-muted-foreground" />}
          <span className="truncate">{k.label}</span>
          {k.url && <a href={k.url} target="_blank" rel="noreferrer" className="text-muted-foreground hover:text-amber-500" title="Get a key"><ExternalLink className="h-3.5 w-3.5" /></a>}
        </div>
        <div className="truncate font-mono text-[11px] text-muted-foreground">{k.name} · {k.uses}</div>
      </div>
      <div className="flex min-w-0 items-center gap-2">
        <input className={input} type={k.secret ? "password" : "text"} value={value} onChange={(e) => setValue(e.target.value)} autoComplete="off" spellCheck={false}
          placeholder={k.set ? `${k.value}  (from ${k.source === "settings" ? "Settings" : ".env"}) — type to replace` : k.secret ? "Paste the key" : "Value"} aria-label={k.name} />
      </div>
      <div className="flex items-center gap-2">
        <button className={primary} disabled={!value.trim() || !!busy} onClick={() => run("save", async () => { const r = await settingsApi.setKeys({ [k.name]: value.trim() }); setValue(""); return r; })}>
          {busy === "save" ? <Loader2 className="h-4 w-4 animate-spin" /> : null}Save
        </button>
        {k.source === "settings" && <button className={btn} disabled={!!busy} onClick={() => run("clear", () => settingsApi.setKeys({ [k.name]: null }), "Removed")}>Clear</button>}
        {msg && <span className={`text-xs ${msg.ok ? "text-emerald-500" : "text-red-400"}`}>{msg.text}</span>}
      </div>
    </div>
  );
}

function Keys({ s }: { s: AppSettings }) {
  const groups = useMemo(() => {
    const g = new Map<string, SettingKey[]>();
    for (const k of s.keys) g.set(k.group, [...(g.get(k.group) ?? []), k]);
    return [...g.entries()];
  }, [s.keys]);
  const [name, setName] = useState(""), [value, setValue] = useState("");
  const { busy, msg, run } = useSave();
  return (
    <Card id="keys" icon={<KeyRound className="h-5 w-5 text-amber-400" />} title="API keys"
      sub="Used by Explainer and Animations. A key saved here wins over the same name in apps/.env; Clear goes back to .env. Keys stay on this computer.">
      {groups.map(([group, keys]) => (
        <div key={group} className="mb-4">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{group}</h3>
          <div className="rounded-xl border border-border px-3">{keys.map((k) => <KeyRow key={k.name} k={k} />)}</div>
        </div>
      ))}
      <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">Add any other key</h3>
      <div className="flex flex-wrap items-center gap-2">
        <input className={`${input} max-w-xs font-mono`} placeholder="NAME_LIKE_THIS" value={name} onChange={(e) => setName(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"))} aria-label="New key name" />
        <input className={`${input} max-w-md`} type="password" placeholder="Value" value={value} onChange={(e) => setValue(e.target.value)} aria-label="New key value" />
        <button className={primary} disabled={!name || !value || !!busy} onClick={() => run("add", async () => { const r = await settingsApi.setKeys({ [name]: value }); setName(""); setValue(""); return r; }, "Added")}>
          <Plus className="h-4 w-4" />Add key
        </button>
        {msg && <span className={`text-xs ${msg.ok ? "text-emerald-500" : "text-red-400"}`}>{msg.text}</span>}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">For example DEEPSEEK_API_KEY or TOGETHER_API_KEY, then use that name for a model below.</p>
    </Card>
  );
}

// ---------------- GPU server ----------------
function Gpu({ s }: { s: AppSettings }) {
  const [url, setUrl] = useState<string | null>(null);
  const shown = url ?? s.gpu.comfyui_url;
  const { busy, msg, run, setMsg } = useSave();
  const test = async () => {
    setMsg(null);
    const r = await settingsApi.testGpu().catch((e: Error) => ({ ok: false, detail: e.message }));
    setMsg({ ok: r.ok, text: r.detail });
  };
  return (
    <Card id="gpu" icon={<Cpu className="h-5 w-5 text-amber-400" />} title="GPU server"
      sub="Your own GPU running ComfyUI (for example an A100 rented on RunPod or Vast.ai). Models whose workflow you upload below run there, free per call, before any paid API.">
      <div className="flex flex-wrap items-center gap-2">
        <input className={`${input} max-w-md`} value={shown} onChange={(e) => setUrl(e.target.value)} placeholder="http://<pod address>:8188" aria-label="ComfyUI address" data-testid="gpu-url" />
        <button className={primary} disabled={!!busy || shown === s.gpu.comfyui_url} onClick={() => run("gpu", async () => { const r = await settingsApi.setGpu({ comfyui_url: shown }); setUrl(null); return r; })}>Save</button>
        <button className={btn} onClick={test} disabled={!s.gpu.comfyui_url} data-testid="gpu-test"><Server className="h-4 w-4" />Test connection</button>
        <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          Run models on
          <select className={`${input} w-auto`} value={s.gpu.model_backend} onChange={(e) => run("mb", () => settingsApi.setGpu({ model_backend: e.target.value }))} aria-label="Backend">
            <option value="auto">Auto (GPU workers, GPU server, free tiers, then fal.ai)</option>
            <option value="gpu">Only my GPU workers</option>
            <option value="comfyui">Only my GPU server</option>
            <option value="fal">Only fal.ai</option>
          </select>
        </label>
      </div>
      {msg && <p className={`mt-2 text-sm ${msg.ok ? "text-emerald-500" : "text-red-400"}`} data-testid="gpu-msg">{msg.text}</p>}
      <p className="mt-3 text-sm text-muted-foreground">
        Several GPUs, or want AVOS to pick the GPU, precision and model per shot? Add <Link href="/gpu" className="text-amber-600 underline dark:text-amber-400">GPU workers</Link> (apps/gpu_worker): they run ComfyUI, Wan2GP or Diffusers and keep models loaded between shots.
      </p>
      <p className="mt-3 text-xs text-muted-foreground">Workflows are saved in <span className="font-mono">{s.workflowDir}</span>. How to export them: apps/comfyui_workflows/README.md.</p>
    </Card>
  );
}

// ---------------- models ----------------
function WorkflowButton({ m, has }: { m: CatalogModel; has: boolean }) {
  const file = useRef<HTMLInputElement>(null);
  const { busy, msg, run } = useSave();
  return (
    <span className="flex flex-wrap items-center gap-2">
      <input ref={file} type="file" accept=".json,application/json" hidden data-testid={`wf-file-${m.id}`}
        onChange={async (e) => {
          const f = e.target.files?.[0];
          e.target.value = "";
          if (!f) return;
          const text = await f.text();
          await run("up", () => settingsApi.uploadWorkflow(m.id, text), "Workflow uploaded");
        }} />
      <button className={btn} disabled={!!busy} onClick={() => file.current?.click()}>
        {busy === "up" ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}{has ? "Replace workflow" : "Upload workflow"}
      </button>
      {has && <button className={btn} disabled={!!busy} onClick={() => run("rm", () => settingsApi.deleteWorkflow(m.id), "Workflow removed")} title="Remove workflow"><X className="h-4 w-4" /></button>}
      {msg && <span className={`text-xs ${msg.ok ? "text-emerald-500" : "text-red-400"}`} data-testid={`wf-msg-${m.id}`}>{msg.text}</span>}
    </span>
  );
}

function ModelRow({ m, s }: { m: CatalogModel; s: AppSettings }) {
  const { busy, msg, run, setMsg } = useSave();
  const has = !!m.comfyui && s.workflows.includes(m.comfyui.workflow);
  return (
    <div className="flex flex-col gap-2 border-t border-border py-3 first:border-t-0 lg:flex-row lg:items-center" data-model={m.id}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2 text-sm font-medium text-foreground">
          {m.ready ? <CheckCircle2 className="h-4 w-4 text-emerald-500" /> : <CircleDashed className="h-4 w-4 text-muted-foreground" />}
          {m.name}
          {m.custom && <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-[11px] text-amber-600 dark:text-amber-300">yours · {m.kind}</span>}
          <span className="rounded-md bg-muted px-2 py-0.5 text-[11px] text-muted-foreground">{m.task}</span>
        </div>
        <div className="text-xs text-muted-foreground">{m.ready ? `Ready on ${({ gpu: "your GPU workers", comfyui: "your GPU server", fal: "fal.ai", cloudflare: "Cloudflare" } as Record<string, string>)[m.backend ?? ""] ?? m.backend}` : m.missing}{m.custom ? ` · ${m.why}` : ""}</div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {m.comfyui && <WorkflowButton m={m} has={has} />}
        {m.custom && (
          <>
            <button className={btn} disabled={!!busy} onClick={async () => { setMsg(null); const r = await settingsApi.testModel(m.id).catch((e: Error) => ({ ok: false, detail: e.message })); setMsg({ ok: r.ok, text: r.detail }); }}>Test</button>
            <button className={btn} disabled={!!busy} onClick={() => run("del", () => settingsApi.deleteModel(m.id), "Deleted")} aria-label={`Delete ${m.name}`}><Trash2 className="h-4 w-4" /></button>
          </>
        )}
        {msg && <span className={`text-xs ${msg.ok ? "text-emerald-500" : "text-red-400"}`}>{msg.text}</span>}
      </div>
    </div>
  );
}

const KIND_FOR: Record<string, { value: CustomModelDef["kind"]; label: string }[]> = {
  image: [{ value: "fal", label: "fal.ai model" }, { value: "replicate", label: "Replicate model" }, { value: "comfyui", label: "ComfyUI workflow (your GPU)" }],
  video: [{ value: "fal", label: "fal.ai model" }, { value: "replicate", label: "Replicate model" }, { value: "comfyui", label: "ComfyUI workflow (your GPU)" }],
  avatar: [{ value: "fal", label: "fal.ai model" }, { value: "replicate", label: "Replicate model" }, { value: "comfyui", label: "ComfyUI workflow (your GPU)" }],
  llm: [{ value: "openai", label: "OpenAI-compatible API (DeepSeek, Together, LM Studio, vLLM…)" }],
};
const TASK_LABEL: Record<string, string> = { image: "Pictures", video: "Video clips", avatar: "Talking presenter", llm: "Text (scripts, AI crew)" };

function AddModel({ s }: { s: AppSettings }) {
  const [task, setTask] = useState<CustomModelDef["task"]>("image");
  const [kind, setKind] = useState<CustomModelDef["kind"]>("fal");
  const [name, setName] = useState(""), [id, setId] = useState(""), [endpoint, setEndpoint] = useState("");
  const [baseUrl, setBaseUrl] = useState(""), [model, setModel] = useState(""), [keyEnv, setKeyEnv] = useState("");
  const [inputs, setInputs] = useState<string | null>(null), [output, setOutput] = useState(""), [license, setLicense] = useState(""), [notes, setNotes] = useState("");
  const { busy, msg, run } = useSave();
  const autoId = (id || name).toLowerCase().replace(/[^a-z0-9._-]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 39);
  const defaultInputs = s.defaultInputs[`${kind}:${task}`];
  const inputsText = inputs ?? (defaultInputs ? JSON.stringify(defaultInputs, null, 2) : "");
  const pickTask = (t: CustomModelDef["task"]) => { setTask(t); setKind(KIND_FOR[t][0].value); setInputs(null); };
  const save = () => run("add", async () => {
    const r = await settingsApi.saveModel({
      id: autoId, name: name || autoId, task, kind, endpoint, base_url: baseUrl, model, key_env: keyEnv, output, license, notes,
      ...(kind === "fal" || kind === "replicate" ? { inputs: inputsText } : {}),
    });
    setName(""); setId(""); setEndpoint(""); setBaseUrl(""); setModel(""); setInputs(null); setOutput(""); setNotes(""); setLicense("");
    return r;
  }, kind === "comfyui" ? "Added — now upload its workflow in the list above" : "Added — it's now in the Explainer and Animations pickers");
  return (
    <div className="mt-5 rounded-xl border border-dashed border-amber-500/40 p-4" data-testid="add-model">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-foreground"><Plus className="h-4 w-4 text-amber-500" />Add a model</h3>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
        <label className="text-xs text-muted-foreground">What it makes
          <select className={`${input} mt-1`} value={task} onChange={(e) => pickTask(e.target.value as CustomModelDef["task"])} data-testid="add-task">
            {Object.entries(TASK_LABEL).map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select></label>
        <label className="text-xs text-muted-foreground">Where it runs
          <select className={`${input} mt-1`} value={kind} onChange={(e) => { setKind(e.target.value as CustomModelDef["kind"]); setInputs(null); }} data-testid="add-kind">
            {KIND_FOR[task].map((k) => <option key={k.value} value={k.value}>{k.label}</option>)}
          </select></label>
        <label className="text-xs text-muted-foreground">Name
          <input className={`${input} mt-1`} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. FLUX 1.1 Pro" data-testid="add-name" /></label>
        <label className="text-xs text-muted-foreground">Id (used in projects)
          <input className={`${input} mt-1 font-mono`} value={id || autoId} onChange={(e) => setId(e.target.value)} placeholder="flux-pro" data-testid="add-id" /></label>
        {(kind === "fal" || kind === "replicate") && (
          <label className="text-xs text-muted-foreground md:col-span-2">{kind === "fal" ? "fal.ai endpoint (from the model's API page)" : "Replicate model (owner/name or owner/name:version)"}
            <input className={`${input} mt-1 font-mono`} value={endpoint} onChange={(e) => setEndpoint(e.target.value)} placeholder={kind === "fal" ? "fal-ai/flux-pro/v1.1" : "black-forest-labs/flux-1.1-pro"} data-testid="add-endpoint" /></label>
        )}
        {kind === "openai" && (
          <>
            <label className="text-xs text-muted-foreground">Base URL
              <input className={`${input} mt-1 font-mono`} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.deepseek.com/v1 or http://localhost:1234/v1" data-testid="add-base" /></label>
            <label className="text-xs text-muted-foreground">Model name
              <input className={`${input} mt-1 font-mono`} value={model} onChange={(e) => setModel(e.target.value)} placeholder="deepseek-chat" data-testid="add-model-name" /></label>
          </>
        )}
        {kind !== "comfyui" && (
          <label className="text-xs text-muted-foreground">API key name {kind === "openai" ? "(empty for a local server)" : `(default ${kind === "fal" ? "FAL_KEY" : "REPLICATE_API_TOKEN"})`}
            <input className={`${input} mt-1 font-mono`} value={keyEnv} onChange={(e) => setKeyEnv(e.target.value.toUpperCase().replace(/[^A-Z0-9_]/g, "_"))} placeholder={kind === "openai" ? "DEEPSEEK_API_KEY" : ""} data-testid="add-key" /></label>
        )}
        <label className="text-xs text-muted-foreground">Licence (optional)
          <input className={`${input} mt-1`} value={license} onChange={(e) => setLicense(e.target.value)} placeholder="e.g. Apache-2.0" /></label>
        {(kind === "fal" || kind === "replicate") && (
          <>
            <label className="text-xs text-muted-foreground md:col-span-2">Inputs it sends (JSON, with placeholders)
              <textarea className={`${input} mt-1 h-32 font-mono text-xs`} value={inputsText} onChange={(e) => setInputs(e.target.value)} spellCheck={false} data-testid="add-inputs" />
            </label>
            <p className="text-[11px] text-muted-foreground md:col-span-2">
              Placeholders: {Object.entries(s.placeholders).map(([k, v]) => <span key={k} className="mr-2 whitespace-nowrap"><code className="text-amber-600 dark:text-amber-300">{`{{${k}}}`}</code> {v}</span>)}
            </p>
            <label className="text-xs text-muted-foreground">Where the result URL is (optional)
              <input className={`${input} mt-1 font-mono`} value={output} onChange={(e) => setOutput(e.target.value)} placeholder="auto (video / images / output)" /></label>
          </>
        )}
        {kind === "comfyui" && (
          <p className="text-xs text-muted-foreground md:col-span-2">After adding, upload its workflow (Workflow → Export (API) in ComfyUI, with {"{{PROMPT}}"} and, for video, {"{{IMAGE}}"} / {"{{AUDIO}}"} / {"{{VIDEO}}"} typed into the fields) in the list above. It runs on your GPU server.</p>
        )}
        <label className="text-xs text-muted-foreground">Notes (optional)
          <input className={`${input} mt-1`} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="what it's good at" /></label>
      </div>
      <div className="mt-3 flex items-center gap-3">
        <button className={primary} onClick={save} disabled={!!busy || !autoId} data-testid="add-save">{busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}Add model</button>
        {msg && <span className={`text-sm ${msg.ok ? "text-emerald-500" : "text-red-400"}`} data-testid="add-msg">{msg.text}</span>}
      </div>
    </div>
  );
}

function Models({ s }: { s: AppSettings }) {
  const { data } = useModels();
  const list = data?.models ?? [];
  const groups: [string, CatalogModel[]][] = [
    ["Your models", list.filter((m) => m.custom)],
    ["Open models (catalog)", list.filter((m) => !m.custom)],
  ];
  return (
    <Card id="models" icon={<Wand2 className="h-5 w-5 text-amber-400" />} title="Models"
      sub="Every model Explainer and Animations can use. Upload a ComfyUI workflow to run a model on your GPU server, or add any fal.ai, Replicate, ComfyUI or OpenAI-compatible model of your own.">
      {groups.map(([title, ms]) => ms.length > 0 && (
        <div key={title} className="mb-4">
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
          <div className="rounded-xl border border-border px-3">{ms.map((m) => <ModelRow key={m.id} m={m} s={s} />)}</div>
        </div>
      ))}
      <p className="text-xs text-muted-foreground">Licences, prices and what each model is best at: <Link href="/models" className="underline">Models page</Link>.</p>
      <AddModel s={s} />
    </Card>
  );
}

export default function SettingsPage() {
  const q = useQuery({ queryKey: SETTINGS_KEY, queryFn: settingsApi.get, retry: false });
  const header = (
    <div className="flex items-center gap-2 text-sm text-muted-foreground"><Settings2 className="h-4 w-4" /> Settings · shared by Explainer and Animations</div>
  );
  return (
    <AppShell header={header}>
      <div className="mx-auto max-w-7xl space-y-6 p-4 md:p-8">
        <div>
          <h1 className="mb-2 text-2xl font-bold text-foreground md:text-3xl">Settings</h1>
          <p className="text-muted-foreground">API keys, your GPU server and your own models, for both Explainer and Animations.</p>
          <nav className="mt-3 flex flex-wrap gap-2 text-sm">
            {[["keys", "API keys"], ["gpu", "GPU server"], ["models", "Models"]].map(([a, l]) => (
              <a key={a} href={`#${a}`} className="rounded-xl border border-border px-3 py-1.5 text-muted-foreground hover:border-amber-500/40 hover:text-foreground">{l}</a>
            ))}
            <Link href="/gpu" className="rounded-xl border border-border px-3 py-1.5 text-muted-foreground hover:border-amber-500/40 hover:text-foreground">GPU workers →</Link>
          </nav>
        </div>
        {q.isLoading && <p className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Loading…</p>}
        {q.error && <p role="alert" className="rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">{(q.error as Error).message}</p>}
        {q.data && (
          <>
            <Keys s={q.data} />
            <Gpu s={q.data} />
            <Models s={q.data} />
            <p className="text-xs text-muted-foreground">Saved in <span className="font-mono">{q.data.file}</span> (on the shared Docker volume). Animations reads the same file.</p>
          </>
        )}
      </div>
    </AppShell>
  );
}
