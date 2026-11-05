"use client";

import { AlertTriangle, Download, Film } from "lucide-react";

import { formatDuration } from "@/components/projects/status";
import { assetsApi } from "@/lib/api";
import { VIDEO_PROVIDERS, type FinalVideoResult } from "@/types";

const SOURCE_LABEL: Record<string, { label: string; cls: string }> = {
  clip: { label: "AI clip", cls: "border-green-500/30 bg-green-500/10 text-green-300" },
  image: { label: "Animated image", cls: "border-sky-500/30 bg-sky-500/10 text-sky-300" },
  card: { label: "No visual", cls: "border-red-500/30 bg-red-500/10 text-red-300" },
};

function providerLabel(value: string): string {
  if (value === "none") return "Animated images";
  const found = VIDEO_PROVIDERS.find((p) => p.value === value);
  return found ? found.label.split(" (")[0] : value;
}

function fileName(projectName: string): string {
  const slug = projectName.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return `${slug || "avos-video"}.mp4`;
}

export function FinalVideoCard({
  video,
  projectName,
  warnings = [],
}: {
  video: FinalVideoResult;
  projectName: string;
  warnings?: string[];
}) {
  const src = assetsApi.contentUrl(video.asset_id);
  const portrait = video.height > video.width;

  return (
    <div className="rounded-2xl border border-amber-500/30 bg-card/50 p-6" data-testid="final-video">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Film className="h-5 w-5 text-amber-500" /> Your video
        </h3>
        <a
          href={assetsApi.downloadUrl(video.asset_id, fileName(projectName))}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2 text-sm font-medium text-white shadow-lg shadow-amber-500/25 hover:from-amber-600 hover:to-orange-600"
          data-testid="download-video"
        >
          <Download className="h-4 w-4" /> Download MP4
        </a>
      </div>

      <div className="flex justify-center rounded-xl bg-black">
        <video
          key={video.asset_id}
          src={src}
          controls
          playsInline
          preload="metadata"
          className={portrait ? "max-h-[70vh] w-auto" : "w-full"}
        />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted-foreground">
        <span>{formatDuration(video.duration_seconds)}</span>
        <span>
          {video.width}×{video.height}
        </span>
        <span>{(video.size_bytes / 1_000_000).toFixed(1)} MB</span>
        <span>Shots: {providerLabel(video.video_provider)}</span>
      </div>

      {video.shot_sources.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {video.shot_sources.map((source, i) => {
            const style = SOURCE_LABEL[source] ?? SOURCE_LABEL.card;
            return (
              <span key={i} className={`rounded-full border px-2.5 py-0.5 text-xs ${style.cls}`}>
                {i + 1} · {style.label}
              </span>
            );
          })}
        </div>
      )}

      {warnings.length > 0 && (
        <ul className="mt-4 space-y-1 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-xs text-amber-200">
          {warnings.map((w, i) => (
            <li key={i} className="flex gap-2">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" /> {w}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
