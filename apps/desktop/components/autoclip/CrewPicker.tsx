"use client";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download } from "lucide-react";
import { autoclip } from "@/lib/autoclip";
import { Label, Note, btn, field } from "./ui";

const TIER: Record<string, string> = { local: "free, on this PC", free: "free tier", paid: "paid", custom: "your own" };
const VISION_IDEAS = ["qwen2.5vl:7b", "minicpm-v", "llava:7b", "gemma3:12b"];

/** Which AI chooses the best moments, writes titles/descriptions and (if it can see) labels unclear scenes.
 *  "No AI" still works: loudness, the transcript and face rules. Free = Ollama on this PC; paid = a key in AVOS Settings. */
export function CrewPicker({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["crews"], queryFn: autoclip.crews, staleTime: 20_000, retry: false });
  const cur = q.data?.agents.find((a) => a.id === value);
  const [vm, setVm] = useState("");
  useEffect(() => setVm(cur?.visionModel ?? ""), [cur?.visionModel]);
  const save = useMutation({ mutationFn: (b: { agent: string; model?: string; visionModel?: string }) => autoclip.setCrew(b), onSuccess: (d) => qc.setQueryData(["crews"], d) });
  const pull = useMutation({ mutationFn: (m: string) => autoclip.pull(m), onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["crews"] }), 4000) });
  const agents = q.data?.agents ?? [];
  return (
    <div className="space-y-3 border border-border p-3">
      <div className="text-sm font-medium">AI helper <span className="text-xs font-normal text-muted-foreground">(optional)</span></div>
      <p className="text-xs text-muted-foreground">It reads the transcript to pick and rank the best moments and write titles and descriptions, and can look at unclear scenes to choose a layout. Without one, loudness, the transcript and the face rules do the work.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Label text="Use">
          <select className={field} value={value} onChange={(e) => onChange(e.target.value)} aria-label="AI helper">
            <option value="builtin">No AI (built-in rules)</option>
            {agents.filter((a) => a.id !== "builtin").map((a) => <option key={a.id} value={a.id}>{a.label} · {TIER[a.tier] ?? a.tier}{a.ready ? "" : " · not set up"}</option>)}
          </select>
        </Label>
        {cur?.id === "ollama" && cur.models && (
          <Label text="Text model (Ollama)">
            <select className={field} value={cur.model} onChange={(e) => save.mutate({ agent: "ollama", model: e.target.value })}>{[...new Set([cur.model ?? "", ...cur.models])].filter(Boolean).map((m) => <option key={m} value={m}>{m}</option>)}</select>
          </Label>
        )}
      </div>
      {value !== "builtin" && cur && (
        <p className={`text-xs ${cur.ready ? "text-muted-foreground" : "text-amber-300"}`}>
          {cur.ready ? cur.detail : `${cur.detail}. ${cur.fix ?? ""}`} {cur.ready && (cur.vision ? "· can look at pictures" : "· text only: can't look at scenes")}
        </p>
      )}
      {cur?.id === "ollama" && (
        <div className="space-y-2">
          <Label text="Vision model for unclear scenes (Ollama, optional)" hint="One small picture per unclear scene is sent to it, on your PC. A 7B vision model takes 10-30 s per picture on a CPU.">
            <div className="flex flex-wrap gap-2">
              <input className={field + " max-w-xs"} list="vision-ideas" value={vm} placeholder="e.g. qwen2.5vl:7b" onChange={(e) => setVm(e.target.value)} />
              <datalist id="vision-ideas">{VISION_IDEAS.map((m) => <option key={m} value={m} />)}</datalist>
              <button type="button" className={btn} disabled={save.isPending || vm === (cur.visionModel ?? "")} onClick={() => save.mutate({ agent: "ollama", visionModel: vm.trim() })}>Save</button>
              {vm && <button type="button" className={btn} disabled={pull.isPending} onClick={() => pull.mutate(vm.trim())}><Download className="h-4 w-4" />{pull.isPending ? "Starting…" : "Download it"}</button>}
            </div>
          </Label>
          {pull.isSuccess && <Note>Downloading in the background through Ollama. This can take several minutes; the status above updates when it is there.</Note>}
        </div>
      )}
      {!cur?.needsKey || cur.hasKey ? null : <Note tone="warn">{cur?.fix}</Note>}
      {q.isError && <Note tone="warn">Couldn&apos;t read the AI list ({(q.error as Error).message}). The built-in rules still work.</Note>}
      {save.isError && <Note tone="err">{(save.error as Error).message}</Note>}
    </div>
  );
}
