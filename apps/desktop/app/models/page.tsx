"use client";

import { useState } from "react";
import { AlertTriangle, Boxes, CheckCircle2, CircleDashed, Download, ExternalLink, Loader2, RefreshCw, Server } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { DownloadPanel } from "@/components/models/DownloadPanel";
import { DownloadsList } from "@/components/models/DownloadsList";
import { useModels } from "@/hooks/queries";
import { settingsApi } from "@/lib/api/settings";
import type { CatalogModel, ModelTask, ModelsStatus } from "@/types";

const TASK_ORDER: ModelTask[] = ["image", "video", "avatar", "control", "reference", "speech", "sound"];

/** Where each model is used in AVOS, in words. */
const USED_IN: Record<string, string> = {
  "facts-image": "Explainer: shot pictures",
  "facts-video": "Explainer: shot clips",
  "facts-avatar": "Explainer: talking presenter",
  "facts-presenter": "Explainer: presenter portrait",
  "studio-backgrounds": "Animations: AI backdrops",
  "studio-finish-scene": "Animations: AI finish",
  "studio-finish-character": "Animations: AI finish",
  "series-characters": "Series: character sheets",
  "series-keyframes": "Series: keyframes",
  "series-voices": "Series: voices",
  "series-sound": "Series: sound",
};

const BACKEND_LABEL: Record<string, string> = { gpu: "Your GPU workers", comfyui: "Your GPU server", fal: "fal.ai", cloudflare: "Cloudflare (free)" };

function rankLabel(m: CatalogModel, task: ModelTask): string {
  if (task === "control") return m.role === "continuity" ? "Continuity" : "Reference";
  if (task === "speech") return m.role === "designer" ? "Voice design" : m.role === "indic" ? "Indian languages" : "Best";
  if (task === "sound") return m.role === "music" ? "Music" : "Sound effects";
  return m.rank === 1 ? "Best" : m.rank === 2 ? "Top 2" : m.rank === 3 ? "Fallback" : "GPU server";
}

function ModelCard({ m, task, onDownload }: { m: CatalogModel; task: ModelTask; onDownload: (m: CatalogModel) => void }) {
  const used = [...new Set(m.used_in.map((u) => USED_IN[u] ?? u))];
  return (
    <div
      className="flex flex-col gap-3 border border-border bg-card/40 p-5"
      data-testid={`model-${m.id}`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-base font-semibold text-foreground">{m.name}</h3>
            <span
              className={`px-2 py-0.5 text-[11px] font-medium ${
                m.rank === 1 ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "bg-muted text-muted-foreground"
              }`}
            >
              {rankLabel(m, task)}
            </span>
          </div>
          <p className="text-xs text-muted-foreground">
            {m.maker} · {m.size}
          </p>
        </div>
        {m.ready ? (
          <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="h-4 w-4" /> Ready · {BACKEND_LABEL[m.backend ?? ""] ?? m.backend}
          </span>
        ) : (
          <span className="flex shrink-0 items-center gap-1 text-xs font-medium text-muted-foreground">
            <CircleDashed className="h-4 w-4" /> Not set up
          </span>
        )}
      </div>

      {m.downloaded && (
        <div className={`border px-3 py-2 text-xs ${m.downloaded.variants.length ? "border-emerald-500/40 bg-emerald-500/5" : "border-amber-500/40 bg-amber-500/5"}`}
          data-testid={`downloaded-${m.id}`}>
          {m.downloaded.variants.length > 0 ? (
            <p className="font-medium text-emerald-700 dark:text-emerald-300">Downloaded on this PC: {m.downloaded.variants.join(", ")}</p>
          ) : null}
          {m.downloaded.partial && <p className="text-amber-700 dark:text-amber-300">A download isn&apos;t finished (.part file): press Download again with the same version to resume.</p>}
          {m.downloaded.variants.length > 0 && !(m.backend === "gpu" || m.backend === "comfyui") && (
            <p className="mt-1 text-muted-foreground">To run it from these files: start ComfyUI and the AVOS worker (apps\tools\start-gpu.bat, or start-cpu.bat
              without an NVIDIA card), add the worker on the <a href="/gpu" className="underline">GPU page</a>, and upload its workflow (Settings → Models).
              Then pick it per step in a film or series (Models panel).</p>
          )}
        </div>
      )}

      <p className="text-sm text-foreground/90">{m.best_for}</p>
      <p className="text-xs text-muted-foreground">{m.why}</p>

      <div className="space-y-1 text-xs">
        {Object.entries(m.backends).map(([b, missing]) => (
          <p key={b} className="flex gap-2">
            <span className="w-32 shrink-0 text-muted-foreground">{BACKEND_LABEL[b] ?? b}</span>
            {missing ? (
              <span className="min-w-0 break-words text-amber-600 dark:text-amber-400 [overflow-wrap:anywhere]">{missing}</span>
            ) : (
              <span className="text-emerald-600 dark:text-emerald-400">
                ready{b === "fal" && m.fal ? ` · ${m.fal.price}` : b === "comfyui" ? " · free per call" : b === "gpu" ? " · the router picks GPU and precision" : ""}
              </span>
            )}
          </p>
        ))}
        {Object.keys(m.backends).length === 0 && m.fabric?.adapters?.some((a) => a === "speech" || a === "foley") && (
          <p className="text-muted-foreground" data-testid={`worker-only-${m.id}`}>
            Runs on a GPU worker&apos;s {m.fabric.adapters.includes("speech") ? "speech" : "foley"} backend (add a worker on the GPU page; setup in apps/gpu_worker/README.md)
            {m.languages && m.languages.length > 0 && <> · speaks {m.languages.length} languages</>}.
          </p>
        )}
        {Object.keys(m.backends).length === 0 && !m.fabric?.adapters?.some((a) => a === "speech" || a === "foley") && (
          <p className="text-muted-foreground">
            No hosted API or ComfyUI nodes yet: research code for your own GPU server
            {m.selfhost && (
              <>
                {" "}(
                <a href={m.selfhost.repo} target="_blank" rel="noreferrer" className="underline">
                  repo
                </a>
                )
              </>
            )}
            .
          </p>
        )}
        {!m.backends.fal && m.fal === undefined && Object.keys(m.backends).length > 0 && (
          <p className="text-muted-foreground">No hosted API: runs only on your GPU server.</p>
        )}
      </div>

      {m.fabric && Object.keys(m.fabric.vram_gb ?? {}).length > 0 && (
        <p className="text-xs text-muted-foreground" data-testid={`vram-${m.id}`}>
          VRAM: {Object.entries(m.fabric.vram_gb).map(([p, gb]) => `${p} ${gb} GB`).join(" · ")}
        </p>
      )}

      <div className="mt-auto flex flex-wrap items-center gap-2 pt-1 text-[11px]">
        <a
          href={m.license_url}
          target="_blank"
          rel="noreferrer"
          title={m.license_note ?? ""}
          className={`inline-flex items-center gap-1 border px-2 py-0.5 ${
            m.commercial === "yes"
              ? "border-emerald-500/30 text-emerald-700 dark:text-emerald-300"
              : "border-amber-500/40 text-amber-700 dark:text-amber-300"
          }`}
          data-testid={`license-${m.id}`}
        >
          {m.commercial === "conditional" && <AlertTriangle className="h-3 w-3" />}
          {m.license}
          {m.commercial === "yes" ? " · commercial OK" : " · conditions"}
          <ExternalLink className="h-3 w-3" />
        </a>
        {used.map((u) => (
          <span key={u} className="bg-muted px-2 py-0.5 text-muted-foreground">
            {u}
          </span>
        ))}
      </div>
      {m.license_note && <p className="text-[11px] text-muted-foreground">{m.license_note}</p>}
      {m.download && (
        <button type="button" onClick={() => onDownload(m)} data-testid={`download-${m.id}`}
          className="mt-1 inline-flex items-center justify-center gap-1.5 border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm font-medium text-amber-700 transition-colors hover:bg-amber-500/20 dark:text-amber-300">
          <Download className="h-4 w-4" />Download
        </button>
      )}
    </div>
  );
}

function Settings({ data, onRetried }: { data: ModelsStatus; onRetried?: () => void }) {
  const s = data.settings;
  return (
    <div className="grid gap-3 border border-border bg-card/30 p-5 text-sm sm:grid-cols-2 lg:grid-cols-4" data-testid="models-settings">
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">fal.ai</p>
        <p className={s.providers?.fal ? "text-amber-600 dark:text-amber-400" : s.fal ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"} data-testid="models-fal">
          {s.providers?.fal ? "Key set, but skipped for now" : s.fal ? "Key set (FAL_KEY)" : "No key: add it in Settings → API keys"}
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Your GPU server (ComfyUI)</p>
        <p className="break-all text-foreground/90">{s.comfyui || "Not set (COMFYUI_URL)"}</p>
        <p className="break-all text-xs text-muted-foreground">Workflows: {s.workflowDir}</p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">GPU workers</p>
        <p className="text-foreground/90" data-testid="models-workers">
          {s.gpuWorkers ? `${s.gpuWorkersOnline ?? 0} of ${s.gpuWorkers} online` : "None yet"}{" "}
          <a href="/gpu" className="text-xs text-amber-600 underline dark:text-amber-400">GPU page</a>
        </p>
      </div>
      <div>
        <p className="text-xs uppercase tracking-wide text-muted-foreground">Backend</p>
        <p className="text-foreground/90">
          {s.modelBackend === "auto" ? "Auto: the router picks your GPU workers, GPU server, free tiers or fal.ai per shot" : `Forced: ${s.modelBackend}`}
        </p>
      </div>
      {Object.entries(s.providers ?? {}).map(([p, msg]) => (
        <p key={p} className="border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-800 dark:text-amber-200 sm:col-span-2 lg:col-span-4" data-testid={`provider-${p}`}>
          {msg} AVOS uses your GPU workers, free tiers or the next model meanwhile.{" "}
          <button className="font-medium underline" data-testid={`retry-${p}`} onClick={async () => { await settingsApi.retryProvider(p); onRetried?.(); }}>Try it again now</button>
        </p>
      ))}
      <p className="text-xs text-muted-foreground sm:col-span-2 lg:col-span-4">
        These models need a large GPU (24–80 GB). Rent one on RunPod, Vast.ai or Lambda and run ComfyUI there, or use
        fal.ai with a key. Setup steps: apps/comfyui_workflows/README.md.
      </p>
    </div>
  );
}

export default function ModelsPage() {
  const { data, isLoading, error, refetch, isFetching } = useModels();
  const [downloading, setDownloading] = useState<CatalogModel | null>(null);

  const header = (
    <div className="flex flex-1 items-center justify-between">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Boxes className="h-4 w-4" /> Model catalog
      </div>
      <button
        type="button"
        onClick={() => refetch()}
        className="flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
      >
        <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} /> Refresh
      </button>
    </div>
  );

  return (
    <AppShell header={header}>
      <div className="mx-auto max-w-7xl space-y-8 p-4 md:p-8">
        <div>
          <h1 className="mb-2 text-2xl font-bold text-foreground md:text-3xl">Models</h1>
          <p className="max-w-3xl text-sm text-muted-foreground">
            The open models AVOS uses for each job, which one is picked by default, where each can run, and its licence.
            Pick them in the Explainer shot list and in the Animations AI settings.
          </p>
        </div>

        {isLoading && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading…
          </p>
        )}
        {error && (
          <p role="alert" className="border border-red-500/30 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {(error as Error).message}
          </p>
        )}

        {data && (
          <>
            <Settings data={data} onRetried={() => void refetch()} />
            <DownloadsList />
            {TASK_ORDER.map((task) => {
              const list = data.models.filter((m) => m.task === task).sort((a, b) => a.rank - b.rank);
              if (!list.length) return null;
              return (
                <section key={task} className="space-y-3" data-testid={`task-${task}`}>
                  <div>
                    <h2 className="flex items-center gap-2 text-lg font-semibold text-foreground">
                      <Server className="h-4 w-4 text-amber-500" /> {data.tasks[task]?.label ?? task}
                    </h2>
                    <p className="text-sm text-muted-foreground">{data.tasks[task]?.auto}</p>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {list.map((m) => (
                      <ModelCard key={m.id} m={m} task={task} onDownload={setDownloading} />
                    ))}
                  </div>
                </section>
              );
            })}
          </>
        )}
      </div>
      {downloading && <DownloadPanel model={downloading} onClose={() => setDownloading(null)} onStarted={() => setDownloading(null)} />}
    </AppShell>
  );
}
