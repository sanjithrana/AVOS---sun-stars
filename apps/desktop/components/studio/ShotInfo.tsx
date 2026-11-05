import { Info } from "lucide-react";
import type { AudioResult, ScriptScene } from "@/types";

/**
 * Time span of one scene inside the narration. Scenes can contain
 * several sentences, so this walks the word timestamps (TTS reads the
 * scenes' narration back-to-back) instead of pairing scene N with
 * sentence N.
 */
function sceneSpan(
  scenes: ScriptScene[],
  sceneIndex: number,
  audio: AudioResult
): { start: number; end: number } | undefined {
  const wordCount = (text: string) => text.trim().split(/\s+/).filter(Boolean).length;
  let first = 0;
  for (const s of scenes) {
    if (s.index === sceneIndex) break;
    first += wordCount(s.narration);
  }
  const scene = scenes.find((s) => s.index === sceneIndex);
  if (!scene) return undefined;
  const last = first + wordCount(scene.narration) - 1;
  const startWord = audio.words[first];
  const endWord = audio.words[Math.min(last, audio.words.length - 1)];
  return startWord && endWord ? { start: startWord.start, end: endWord.end } : undefined;
}

/** Right panel: details for the selected scene (Week 3 adds shots). */
export function ShotInfo({
  scene,
  scenes,
  audio,
  researchNotes,
}: {
  scene: ScriptScene | undefined;
  scenes: ScriptScene[];
  audio: AudioResult | undefined;
  researchNotes: string[] | undefined;
}) {
  const span = scene && audio ? sceneSpan(scenes, scene.index, audio) : undefined;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
        <Info className="h-4 w-4 text-amber-400" />
        <h2 className="text-sm font-semibold text-foreground">Scene Info</h2>
      </div>
      <div className="flex-1 space-y-5 overflow-y-auto p-4 text-sm">
        {scene ? (
          <>
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Scene</p>
              <p className="font-semibold text-foreground">
                {String(scene.index + 1).padStart(2, "0")} · ~{scene.estimated_seconds.toFixed(1)}s
              </p>
            </div>
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Narration</p>
              <p className="leading-relaxed text-foreground">{scene.narration}</p>
            </div>
            <div>
              <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Planned visual</p>
              <p className="leading-relaxed text-muted-foreground">{scene.visual_description}</p>
            </div>
            {span && (
              <div>
                <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">Narration timing</p>
                <p className="font-mono text-xs text-blue-300" data-testid="scene-timing">
                  {span.start.toFixed(2)}s → {span.end.toFixed(2)}s
                </p>
              </div>
            )}
          </>
        ) : (
          <p className="text-xs text-muted-foreground">Select a scene in the storyboard to see its details.</p>
        )}

        {researchNotes && researchNotes.length > 0 && (
          <div className="border-t border-border pt-4">
            <p className="mb-2 text-[10px] uppercase tracking-wider text-muted-foreground">Research notes</p>
            <ul className="list-disc space-y-1 pl-4 text-xs text-muted-foreground">
              {researchNotes.map((n) => (
                <li key={n}>{n}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
