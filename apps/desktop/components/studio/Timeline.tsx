import { AudioLines } from "lucide-react";
import { assetsApi } from "@/lib/api";
import type { AudioResult } from "@/types";
import { formatDuration } from "@/components/projects/status";

/** Generated narration with its sentence spans and semantic beats. */
export function Timeline({ audio }: { audio: AudioResult | undefined }) {
  if (!audio) {
    return (
      <section className="border-t border-border p-4">
        <h2 className="mb-3 text-xs font-semibold uppercase tracking-wider text-muted-foreground">Timeline</h2>
        <p className="flex items-center gap-2 text-xs text-muted-foreground">
          <AudioLines className="h-4 w-4" /> Narration appears here after the script is approved.
        </p>
      </section>
    );
  }

  const total = audio.duration_seconds || 1;
  const pct = (t: number) => `${Math.min(100, (t / total) * 100)}%`;

  return (
    <section className="space-y-3 border-t border-border p-4" data-testid="timeline">
      <div className="flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Timeline</h2>
        <span className="text-xs text-muted-foreground">
          {formatDuration(audio.duration_seconds)} · {audio.word_count} words · {audio.beats.length} beats
          {audio.cache_hit ? " · cached" : ""}
        </span>
      </div>

      <audio controls src={assetsApi.contentUrl(audio.asset_id)} className="w-full" />

      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="w-16 text-right text-[10px] text-muted-foreground">Sentences</span>
          <div className="relative h-6 flex-1 rounded bg-muted">
            {audio.sentences.map((s, i) => (
              <div
                key={i}
                title={s.text}
                className="absolute h-full overflow-hidden rounded border border-blue-500/50 bg-blue-500/20 px-1 text-[10px] leading-6 text-blue-200"
                style={{ left: pct(s.start), width: `calc(${pct(s.end - s.start)} - 2px)` }}
              >
                {s.text}
              </div>
            ))}
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-16 text-right text-[10px] text-muted-foreground">Beats</span>
          <div className="relative h-4 flex-1 rounded bg-muted">
            {audio.beats.map((b) => (
              <div
                key={b.label}
                title={`${b.label} @ ${b.time.toFixed(2)}s`}
                className="absolute top-0 h-full w-0.5 bg-amber-400"
                style={{ left: pct(b.time) }}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
