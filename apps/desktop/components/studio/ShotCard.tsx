/* eslint-disable @next/next/no-img-element -- images/clips are served by the API, not Next */
import { AlertTriangle, Box, CheckCircle2, Clock, Film, XCircle } from "lucide-react";
import { assetsApi } from "@/lib/api";
import type { Shot } from "@/types";

const STATUS_STYLE: Record<string, { label: string; cls: string }> = {
  DRAFT: { label: "Draft", cls: "bg-slate-500/15 text-foreground/90 border-slate-500/30" },
  PLANNED: { label: "Planned", cls: "bg-blue-500/15 text-blue-300 border-blue-500/30" },
  BLENDER_READY: { label: "Physics ready", cls: "bg-purple-500/15 text-purple-300 border-purple-500/30" },
  GENERATING: { label: "Generating", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  QA_PENDING: { label: "QA", cls: "bg-amber-500/15 text-amber-300 border-amber-500/30" },
  PASSED: { label: "Passed", cls: "bg-green-500/15 text-green-300 border-green-500/30" },
  APPROVED: { label: "Approved", cls: "bg-green-500/15 text-green-300 border-green-500/30" },
  FAILED: { label: "Continuity issue", cls: "bg-red-500/15 text-red-300 border-red-500/30" },
  REPAIRING: { label: "Repairing", cls: "bg-orange-500/15 text-orange-300 border-orange-500/30" },
};

const SHOT_TYPE_LABEL: Record<string, string> = {
  wide: "Wide",
  medium: "Medium",
  close_up: "Close-up",
  insert: "Insert",
};

interface ShotCardProps {
  shot: Shot;
  selected: boolean;
  onSelect: (shotId: string) => void;
}

export function ShotCard({ shot, selected, onSelect }: ShotCardProps) {
  const content = shot.spec.content;
  const status = STATUS_STYLE[shot.status] ?? STATUS_STYLE.DRAFT;
  const continuity = shot.spec.continuity;
  const errors = continuity?.violations.filter((v) => v.severity === "error").length ?? 0;
  const warnings = continuity?.violations.filter((v) => v.severity === "warning").length ?? 0;
  const lead = shot.spec.video_generation?.candidates?.[0];

  return (
    <button
      onClick={() => onSelect(shot.id)}
      data-testid="shot-card"
      data-status={shot.status}
      className={`flex flex-col overflow-hidden rounded-xl border text-left transition-colors ${
        selected ? "border-amber-500/60 bg-amber-500/5" : "border-border bg-card/50 hover:border-border"
      }`}
    >
      <div className="relative flex aspect-video items-center justify-center overflow-hidden bg-gradient-to-br from-slate-800 to-slate-950">
        {lead?.render_asset_id ? (
          <video
            src={assetsApi.contentUrl(lead.render_asset_id)}
            muted
            loop
            autoPlay
            playsInline
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : lead ? (
          <img
            src={assetsApi.contentUrl(lead.thumbnail_asset_id)}
            alt=""
            className="absolute inset-0 h-full w-full object-cover [image-rendering:auto]"
          />
        ) : shot.spec.physics_proxy_asset_id ? (
          <Box className="h-7 w-7 text-purple-400/70" />
        ) : (
          <Film className="h-7 w-7 text-muted-foreground/60" />
        )}
        <span className="absolute left-2 top-2 rounded-md bg-muted/80 px-2 py-0.5 text-[10px] font-semibold text-foreground/90">
          {String(shot.shot_index + 1).padStart(2, "0")} · {SHOT_TYPE_LABEL[content.camera.shot_type] ?? content.camera.shot_type}
        </span>
        <span className={`absolute right-2 top-2 rounded-full border px-2 py-0.5 text-[10px] font-medium ${status.cls}`}>
          {status.label}
        </span>
        <span className="absolute bottom-2 right-2 flex items-center gap-1 rounded-md bg-muted/80 px-2 py-0.5 text-[10px] text-muted-foreground">
          <Clock className="h-3 w-3" /> {content.start_time.toFixed(1)}–{content.end_time.toFixed(1)}s
        </span>
        {shot.current_version > 1 && (
          <span className="absolute bottom-2 left-2 rounded-md bg-muted/80 px-2 py-0.5 text-[10px] text-muted-foreground">
            v{shot.current_version}
          </span>
        )}
      </div>
      <div className="flex flex-1 flex-col gap-2 p-3">
        <p className="line-clamp-2 text-xs leading-relaxed text-foreground/90">{content.narration || content.description}</p>
        <div className="mt-auto flex items-center gap-2 text-[10px]">
          {continuity === null ? (
            <span className="text-muted-foreground">Not checked</span>
          ) : errors > 0 ? (
            <span className="flex items-center gap-1 text-red-400">
              <XCircle className="h-3 w-3" /> {errors} continuity error{errors > 1 ? "s" : ""}
            </span>
          ) : (
            <span className="flex items-center gap-1 text-green-400">
              <CheckCircle2 className="h-3 w-3" /> Continuity OK
            </span>
          )}
          {warnings > 0 && (
            <span className="flex items-center gap-1 text-amber-400">
              <AlertTriangle className="h-3 w-3" /> {warnings}
            </span>
          )}
        </div>
      </div>
    </button>
  );
}
