"use client";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { autoclip, type Job, type Scene } from "@/lib/autoclip";
import { Note, btn, mmss } from "./ui";

const NAME: Record<string, string> = { follow: "Follow the speaker", split: "Split screen", facecam: "Content + face cam", salient: "Follow the action", blur: "Whole frame", fill: "Fill the screen" };

/** The scenes AI Reframe found in this clip and the layout it chose for each. Change any, then re-cut (the video is not searched again, so it is quick). */
export function SceneEditor({ jobId, n, scenes, onDone }: { jobId: string; n: number; scenes: Scene[]; onDone: (j: Job) => void }) {
  const [pick, setPick] = useState<Record<string, string>>({});
  const go = useMutation({ mutationFn: () => autoclip.reframe(jobId, n, pick), onSuccess: (j) => { setPick({}); onDone(j); } });
  const changed = Object.keys(pick).length > 0;
  return (
    <details className="border border-border text-sm">
      <summary className="cursor-pointer px-3 py-2 font-medium">AI Reframe: {scenes.length} scene{scenes.length === 1 ? "" : "s"}</summary>
      <div className="space-y-2 p-3">
        <ul className="space-y-1.5">
          {scenes.map((s) => (
            <li key={s.i} className="grid grid-cols-[64px_1fr] items-center gap-2 sm:grid-cols-[92px_1fr_auto]">
              <span className="text-xs text-muted-foreground">{mmss(s.t0)}–{mmss(s.t1)}</span>
              <span className="min-w-0 truncate text-xs" title={s.why}>{s.faces} face{s.faces === 1 ? "" : "s"} · {s.why}{s.label ? ` (${s.label})` : ""}{s.pinned ? " · yours" : ""}</span>
              <select className="h-8 border border-border bg-transparent px-2 text-xs" aria-label={`Layout of scene ${s.i + 1}`} value={pick[String(s.i)] ?? (s.pinned ? s.layout : "auto")}
                onChange={(e) => setPick({ ...pick, [String(s.i)]: e.target.value })}>
                <option value="auto">Automatic: {NAME[s.auto] ?? s.auto}</option>
                {s.can.map((k) => <option key={k} value={k}>{NAME[k] ?? k}</option>)}
              </select>
            </li>
          ))}
        </ul>
        {go.isError && <Note tone="err">{(go.error as Error).message}</Note>}
        <button type="button" className={btn} disabled={!changed || go.isPending} onClick={() => go.mutate()}>{go.isPending ? "Cutting again…" : "Re-cut with these layouts"}</button>
      </div>
    </details>
  );
}
