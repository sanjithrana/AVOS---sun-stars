"use client";
/* eslint-disable @next/next/no-img-element -- images are served by the API, not Next */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Clapperboard, CheckCircle2, Film, Loader2, Play } from "lucide-react";
import { queryKeys, useGpuJobs } from "@/hooks/queries";
import { BACKEND_LABEL, fmtS, fmtUsd } from "@/components/gpu/RunsTable";
import { assetsApi, shotsApi } from "@/lib/api";
import type { GpuJobRow, Shot, ShotSpecStatus } from "@/types";

// Week 3 Day 13: per-shot generation progress. Shots are the unit of
// generation (not Jobs - candidates are produced synchronously by the
// mocked Video agent, the same way the Blender stage is), so this reads
// straight from the live shots list (GET /projects/{id}/shots), which
// SSE's VIDEO_GENERATED/BLENDER_RENDERED events already keep fresh with
// no polling (see hooks/useLiveProject.ts).
const STAGE_PROGRESS: Record<string, number> = {
  DRAFT: 5,
  PLANNED: 25,
  BLENDER_READY: 50,
  GENERATING: 70,
  QA_PENDING: 100,
  PASSED: 100,
  APPROVED: 100,
  FAILED: 100,
  REPAIRING: 80,
};

const STAGE_LABEL: Record<string, string> = {
  DRAFT: "Awaiting continuity check",
  PLANNED: "Awaiting Blender stage",
  BLENDER_READY: "Physics ready — awaiting generation",
  GENERATING: "Generating candidates…",
  QA_PENDING: "3 candidates ready for QA",
  PASSED: "Passed QA",
  APPROVED: "Approved",
  FAILED: "Continuity issue",
  REPAIRING: "Repairing",
};

function barColor(status: string): string {
  if (status === "FAILED") return "bg-red-500";
  if (status === "QA_PENDING" || status === "PASSED" || status === "APPROVED") return "bg-green-500";
  if (status === "REPAIRING") return "bg-orange-500";
  if (status === "BLENDER_READY") return "bg-purple-500";
  return "bg-amber-500";
}

interface GenerationMonitorProps {
  projectId: string;
  shots: Shot[];
}

/**
 * GenerationMonitor: a progress row per shot (ShotSpec -> compiled
 * prompt -> physics proxy -> generated candidates), with a manual
 * "Generate" action for any shot that's BLENDER_READY but hasn't been
 * generated yet (plan_shots already runs this automatically; this covers
 * a shot added or edited afterward). Once QA_PENDING, the 3 candidates
 * (AVOS-08 s8.3) are listed by seed/hash - real thumbnails once a real
 * generator is wired in, deterministic MOCK placeholders otherwise.
 */
export function GenerationMonitor({ projectId, shots }: GenerationMonitorProps) {
  const queryClient = useQueryClient();
  const generate = useMutation({
    mutationFn: (shotId: string) => shotsApi.generate(shotId),
    onSuccess: (detail) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.shots(projectId) });
      queryClient.setQueryData(queryKeys.shot(detail.id), detail);
    },
  });

  // Where each shot's pictures and clip ran (Model Fabric runs, live over GPU_JOB_* events)
  const runs = useGpuJobs(projectId, 10_000);
  const runsByShot = new Map<string, GpuJobRow[]>();
  for (const j of runs.data ?? []) if (j.shot_id) runsByShot.set(j.shot_id, [...(runsByShot.get(j.shot_id) ?? []), j]);

  if (shots.length === 0) return null;

  return (
    <section className="border-t border-border p-4" data-testid="generation-monitor">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Generation</h2>
        <span className="text-xs text-muted-foreground">
          {shots.filter((s) => (STAGE_PROGRESS[s.status] ?? 0) >= 100).length}/{shots.length} ready
        </span>
      </div>

      <div className="flex flex-col gap-2">
        {shots.map((shot) => {
          const status = shot.status as ShotSpecStatus | string;
          const progress = STAGE_PROGRESS[status] ?? 0;
          const candidates = shot.spec.video_generation?.candidates ?? [];
          const canGenerate = status === "BLENDER_READY";
          const isGenerating = generate.isPending && generate.variables === shot.id;

          return (
            <div
              key={shot.id}
              data-testid="generation-row"
              data-shot-status={status}
              className="rounded-lg border border-border bg-card/40 p-3"
            >
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 text-xs text-foreground/90">
                  <Film className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="font-medium">Shot {String(shot.shot_index + 1).padStart(2, "0")}</span>
                  <span className="text-muted-foreground">{STAGE_LABEL[status] ?? status}</span>
                </div>
                {canGenerate && (
                  <button
                    onClick={() => generate.mutate(shot.id)}
                    disabled={isGenerating}
                    data-testid="generate-shot"
                    className="flex items-center gap-1.5 rounded-md bg-gradient-to-r from-purple-500 to-amber-500 px-2.5 py-1 text-[11px] font-medium text-white disabled:opacity-50"
                  >
                    {isGenerating ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <Clapperboard className="h-3 w-3" />
                    )}
                    {isGenerating ? "Generating…" : "Generate"}
                  </button>
                )}
                {progress >= 100 && candidates.length > 0 && (
                  <span className="flex items-center gap-1 text-[11px] text-green-400">
                    <CheckCircle2 className="h-3.5 w-3.5" /> {candidates.length} candidates
                  </span>
                )}
              </div>

              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={`h-full rounded-full transition-all ${barColor(status)}`}
                  style={{ width: `${progress}%` }}
                  data-testid="generation-progress"
                  data-progress={progress}
                />
              </div>

              {candidates.length > 0 && (
                <div className="mt-2 flex gap-2" data-testid="candidate-list">
                  {candidates.map((c) => (
                    <a
                      key={c.index}
                      data-testid="candidate"
                      title={c.render_asset_id ? `Play clip (seed ${c.seed})` : `Open image (seed ${c.seed})`}
                      href={assetsApi.contentUrl(c.render_asset_id ?? c.thumbnail_asset_id)}
                      target="_blank"
                      rel="noreferrer"
                      className="relative h-16 w-10 overflow-hidden rounded-md border border-border bg-muted/60"
                    >
                      <img
                        src={assetsApi.contentUrl(c.thumbnail_asset_id)}
                        alt={`Candidate ${c.index + 1}`}
                        className="h-full w-full object-cover"
                      />
                      {c.render_asset_id && (
                        <span className="absolute inset-0 flex items-center justify-center bg-black/30">
                          <Play className="h-3.5 w-3.5 fill-white text-white" />
                        </span>
                      )}
                    </a>
                  ))}
                </div>
              )}

              <ShotRuns runs={(runsByShot.get(shot.id) ?? []).filter((j) => j.version == null || j.version === shot.current_version)} />

              {generate.isError && generate.variables === shot.id && (
                <p className="mt-2 text-[11px] text-red-400">{(generate.error as Error).message}</p>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

/** "Wan 2.2 · RTX 4090 · fp8 · 42 s" for the shot's clip, plus its pictures; live progress while running. */
function ShotRuns({ runs }: { runs: GpuJobRow[] }) {
  if (!runs.length) return null;
  const clip = runs.find((j) => j.task !== "image" && j.status !== "error") ?? runs.find((j) => j.task !== "image");
  const pics = runs.filter((j) => j.task === "image");
  const where = (j: GpuJobRow) =>
    j.backend === "gpu" ? `${j.gpu ?? j.worker_name} · ${j.precision}` : BACKEND_LABEL[j.backend] ?? j.backend;
  const line = (j: GpuJobRow) =>
    j.status === "done" ? `${j.model} · ${where(j)} · ${fmtS(j.gpu_seconds)} · ${fmtUsd(j.cost_usd)}`
      : j.status === "error" ? `${j.model} on ${where(j)} failed`
        : `${j.model} · ${where(j)} · ${j.step ?? j.status} ${Math.round((j.progress || 0) * 100)}%`;
  return (
    <div className="mt-2 space-y-0.5 text-[11px] text-muted-foreground" data-testid="shot-runs">
      {clip && <p title={(clip.reasons ?? []).join(" · ")}>Clip: {line(clip)}</p>}
      {pics.length > 0 && <p>Pictures: {pics.length} × {line(pics[0])}</p>}
    </div>
  );
}
