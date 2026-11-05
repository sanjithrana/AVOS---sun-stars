import { Clapperboard, Clock, Film, Loader2 } from "lucide-react";
import type { ScriptScene, Shot } from "@/types";
import { ShotCard } from "./ShotCard";

interface StoryboardProps {
  shots: Shot[];
  scenes: ScriptScene[];
  selectedShotId: string | null;
  selectedSceneIndex: number | null;
  onSelectShot: (shotId: string) => void;
  onSelectScene: (index: number) => void;
  canPlan: boolean;
  planning: boolean;
  planError: string | null;
  onPlan: () => void;
  emptyText: string;
}

/**
 * Shot list once shots exist (Week 3). Before that: the approved
 * script's scenes, and - once narration exists - a "Plan shots" action
 * that turns the semantic beats into ShotSpecs.
 */
export function Storyboard(props: StoryboardProps) {
  const { shots, scenes } = props;

  if (shots.length > 0) {
    const total = shots[shots.length - 1].end_time;
    return (
      <section className="p-4">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Storyboard</h2>
          <span className="text-xs text-muted-foreground">
            {shots.length} shots · {total.toFixed(1)}s
          </span>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="shot-list">
          {shots.map((shot) => (
            <ShotCard
              key={shot.id}
              shot={shot}
              selected={props.selectedShotId === shot.id}
              onSelect={props.onSelectShot}
            />
          ))}
        </div>
      </section>
    );
  }

  return (
    <section className="p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Storyboard</h2>
        {props.canPlan && (
          <button
            onClick={props.onPlan}
            disabled={props.planning}
            data-testid="plan-shots"
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
          >
            {props.planning ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Clapperboard className="h-3.5 w-3.5" />}
            {props.planning ? "Planning shots…" : "Plan shots from beats"}
          </button>
        )}
      </div>
      {props.planError && <p className="mb-3 text-xs text-red-400">{props.planError}</p>}

      {scenes.length === 0 ? (
        <div
          data-testid="storyboard-empty"
          className="flex h-40 flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-border text-sm text-muted-foreground"
        >
          <Film className="h-6 w-6" />
          {props.emptyText}
        </div>
      ) : (
        <>
          <p className="mb-3 text-xs text-muted-foreground" data-testid="storyboard-no-shots">
            No shots yet — showing the script&apos;s scenes.
            {props.canPlan ? " Plan shots to split them into timed shots." : " Shots are planned once narration is generated."}
          </p>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3" data-testid="storyboard">
            {scenes.map((scene) => (
              <button
                key={scene.index}
                onClick={() => props.onSelectScene(scene.index)}
                className={`flex flex-col overflow-hidden rounded-xl border text-left transition-colors ${
                  props.selectedSceneIndex === scene.index
                    ? "border-amber-500/60 bg-amber-500/5"
                    : "border-border bg-card/50 hover:border-border"
                }`}
              >
                <div className="relative flex aspect-video items-center justify-center bg-gradient-to-br from-slate-800 to-slate-950">
                  <Film className="h-7 w-7 text-muted-foreground/60" />
                  <span className="absolute left-2 top-2 rounded-md bg-muted/80 px-2 py-0.5 text-[10px] font-semibold text-foreground/90">
                    Scene {String(scene.index + 1).padStart(2, "0")}
                  </span>
                  <span className="absolute bottom-2 right-2 flex items-center gap-1 rounded-md bg-muted/80 px-2 py-0.5 text-[10px] text-muted-foreground">
                    <Clock className="h-3 w-3" /> {scene.estimated_seconds.toFixed(1)}s
                  </span>
                </div>
                <p className="line-clamp-3 p-3 text-xs leading-relaxed text-foreground/90">{scene.narration}</p>
              </button>
            ))}
          </div>
        </>
      )}
    </section>
  );
}
