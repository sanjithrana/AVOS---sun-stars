"use client";
// Which model makes each step of this film / series, and where it runs: Auto (your GPUs first, then free tiers, then
// paid APIs) or your pick — a model you downloaded and run on your GPU / ComfyUI, or one on fal.ai / Cloudflare with
// your API key. A provider with no credit or a refused key is skipped (and said here).
import Link from "next/link";
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, ChevronDown, Cpu, KeyRound, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { seriesApi } from "./api";
import type { Act } from "./shared";
import type { StepChoice } from "./types";

const sel = "w-full rounded-lg border border-border bg-background px-2 py-1.5 text-sm text-foreground";

export function ModelChoices({ sid, act, open: startOpen = false }: { sid: string; act: Act; open?: boolean }) {
  const qc = useQueryClient();
  const [open, setOpen] = useState(startOpen);
  const q = useQuery({ queryKey: ["series", sid, "models"], queryFn: () => seriesApi.modelChoices(sid), staleTime: 15_000, retry: false });
  const [edits, setDraft] = useState<Record<string, { model: string; backend: string }>>({});
  const steps = q.data?.steps ?? [];
  const draft: Record<string, { model: string; backend: string }> = { ...Object.fromEntries(steps.map((s) => [s.step, { model: s.model, backend: s.backend }])), ...edits };
  const dirty = steps.some((s) => draft[s.step] && (draft[s.step].model !== s.model || draft[s.step].backend !== s.backend));
  const readyCount = steps.filter((s) => current(s, draft[s.step]?.model)?.ready || ["off", "edge"].includes(draft[s.step]?.model ?? "")).length;
  const save = () => act("models", async () => {
    const r = await seriesApi.setModelChoices(sid, draft);
    await qc.invalidateQueries({ queryKey: ["series", sid, "models"] });
    setDraft({});
    return r;
  });

  return (
    <div className="rounded-xl border border-border bg-card/30" data-testid="model-choices">
      <button className="flex w-full items-center gap-2 p-4 text-left" onClick={() => setOpen(!open)}>
        <Cpu className="h-4 w-4 text-amber-500" />
        <b className="text-sm text-foreground">Models</b>
        <span className="text-sm text-muted-foreground">{q.isLoading ? "checking…" : `${readyCount} of ${steps.length} steps ready · pick the model and where each step runs`}</span>
        <span className="grow" /><ChevronDown className={`h-4 w-4 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="space-y-3 border-t border-border p-4">
          {Object.entries(q.data?.providers ?? {}).map(([p, msg]) => (
            <p key={p} className="flex items-start gap-2 rounded-xl border border-amber-500/40 bg-amber-500/5 p-2 text-xs text-amber-800 dark:text-amber-200" data-testid={`provider-${p}`}>
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />{msg}
            </p>
          ))}
          {q.isError && <p className="text-sm text-red-600">{(q.error as Error).message}</p>}
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
            {steps.map((s) => {
              const d = draft[s.step] ?? { model: s.model, backend: s.backend };
              const opt = current(s, d.model);
              const where = opt ? Object.entries(opt.backends) : [];
              return (
                <div key={s.step} className="space-y-1.5 rounded-xl border border-border p-3" data-testid={`choice-${s.step}`}>
                  <b className="text-sm text-foreground">{s.label}</b>
                  <div className="grid grid-cols-2 gap-2">
                    <select className={sel} value={d.model} data-testid={`choice-${s.step}-model`}
                      onChange={(e) => setDraft({ ...draft, [s.step]: { model: e.target.value, backend: "auto" } })}>
                      <option value="auto">Auto (best that&apos;s ready)</option>
                      {s.options.map((o) => <option key={o.id} value={o.id}>{o.ready ? "✓ " : "✗ "}{o.name}</option>)}
                    </select>
                    <select className={sel} value={d.backend} disabled={!where.length} data-testid={`choice-${s.step}-where`}
                      onChange={(e) => setDraft({ ...draft, [s.step]: { ...d, backend: e.target.value } })}>
                      <option value="auto">Where: auto</option>
                      {where.map(([b, info]) => <option key={b} value={b}>{info.why ? "✗ " : "✓ "}{info.label}</option>)}
                    </select>
                  </div>
                  <Status s={s} model={d.model} backend={d.backend} />
                </div>
              );
            })}
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-3">
            <Button size="sm" disabled={!dirty} onClick={() => void save()} data-testid="choices-save"><Save />Save my choices</Button>
            <span className="text-xs text-muted-foreground">
              Used from the next thing it makes (redo shots to apply to rendered ones). Keys for fal.ai, Cloudflare and others:{" "}
              <Link href="/settings" className="inline-flex items-center gap-1 text-amber-600 underline"><KeyRound className="h-3 w-3" />Settings → API keys</Link>
              {" "}· downloaded models: <Link href="/models" className="text-amber-600 underline">Models page</Link>
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function current(s: StepChoice, model?: string) {
  if (!model || model === "auto") return s.options.find((o) => o.ready && !["off", "edge"].includes(o.id));
  return s.options.find((o) => o.id === model);
}

function Status({ s, model, backend }: { s: StepChoice; model: string; backend: string }) {
  if (model === "off") return <p className="text-xs text-muted-foreground">Off: nothing is made for this step.</p>;
  if (model === "edge") return <p className="text-xs text-muted-foreground">Free Microsoft Edge voices (needs internet), one per character.</p>;
  const o = current(s, model);
  if (!o) return <p className="flex items-center gap-1 text-xs text-amber-700 dark:text-amber-300"><AlertTriangle className="h-3.5 w-3.5" />Nothing is ready for this step yet: AVOS uses its free fallback.</p>;
  const b = backend !== "auto" ? o.backends[backend] : null;
  if (b && b.why) return <p className="text-xs text-amber-700 dark:text-amber-300">{b.label}: {b.why} (until then: {o.ready ? `${o.name} on ${o.backend}` : "the next ready option"})</p>;
  if (!o.ready) return <p className="text-xs text-amber-700 dark:text-amber-300">{o.name}: {o.why}</p>;
  return (
    <p className="flex items-center gap-1 text-xs text-emerald-700 dark:text-emerald-300">
      <CheckCircle2 className="h-3.5 w-3.5" />{model === "auto" ? "Auto → " : ""}{o.name} on {backend !== "auto" && b ? b.label : o.backend}{o.price && (backend === "fal" || o.backend === "fal") ? ` · ${o.price}` : ""}
    </p>
  );
}
