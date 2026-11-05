"use client";

import { useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent, type ReactNode } from "react";
import { AlertCircle, Check, CheckCircle2, ChevronDown, CircleDashed, CircleSlash, Loader2, MinusCircle, OctagonX, Play, RotateCcw, Send } from "lucide-react";
import type { Agent, AgentState, Project } from "@/lib/explainer";

/* The left side of a video: the crew working, as a conversation. Every line the studio logs is shown under the agent who
   did it; the approvals arrive here as questions; your instructions go in at the bottom. The right side shows the output. */

const WHO: [RegExp, string][] = [
  [/fact|research|wikipedia/i, "Researcher"],
  [/script|shot list|plan ready|writer/i, "Scriptwriter"],
  [/cast memory|recognised|remembered/i, "Cast memory"],
  [/drawing (?:ref|char|host|portrait)|character|portrait|sheet/i, "Character designer"],
  [/drawing|prop|world|poster|set\b/i, "Set and prop designer"],
  [/last frame/i, "Key-pose artist"],
  [/did not match|continuity/i, "Continuity checker"],
  [/storyboard|frame/i, "Storyboard artist"],
  [/voice/i, "Voice actor"],
  [/lip-?sync/i, "Lip-sync"],
  [/shot s\d+ with|clip|animat|video model/i, "Animator"],
  [/music/i, "Composer"],
  [/caption|joining|final|ready/i, "Editor"],
];
const whoOf = (text: string) => WHO.find(([rx]) => rx.test(text))?.[1] ?? "Studio";

const ICON: Record<AgentState, { el: typeof CheckCircle2; tone: string }> = {
  done: { el: CheckCircle2, tone: "text-[#52c79a]" }, working: { el: Loader2, tone: "animate-spin text-[var(--signal)]" },
  waiting: { el: CircleDashed, tone: "text-muted-foreground" }, skipped: { el: MinusCircle, tone: "text-[#d9a64e]" },
  off: { el: CircleSlash, tone: "text-muted-foreground" }, error: { el: AlertCircle, tone: "text-[#e0657c]" },
};

interface Block { who: string; team: string; names: string[]; lines: { text: string; kind: string }[] }
// agents who take turns shot by shot share one card (the voice actor and the animator alternate S01, S01, S02, S02…)
const TEAM: Record<string, string> = { "Voice actor": "shoot", Animator: "shoot", "Lip-sync": "shoot", "Storyboard artist": "board", "Key-pose artist": "board", "Continuity checker": "board",
  "Character designer": "design", "Set and prop designer": "design" };

export interface Gate { title: string; help: string; action: string; onApprove: () => void; pending: boolean }

export function AgentPanel({ p, gate, error, onStop, onContinue, onDirect, onRewrite, busy, controls, onGrab, compact }: {
  p: Project; gate: Gate | null; error: string | null; busy: boolean;
  controls?: ReactNode; onGrab?: (e: RPointerEvent<HTMLElement>) => void; compact?: boolean;
  onStop: () => void; onContinue: () => void; onDirect: (note: string, scope: "look" | "story") => void; onRewrite: (note: string) => void;
}) {
  const [note, setNote] = useState("");
  const [tasks, setTasks] = useState(false);
  const feed = useRef<HTMLDivElement>(null);
  const running = p.status === "working";
  const blocks = useMemo(() => {
    const out: Block[] = [];
    for (const l of p.log.slice(-80)) {
      const who = l.kind === "error" ? "Studio" : whoOf(l.text);
      const team = TEAM[who] ?? who;
      const last = out[out.length - 1];
      if (last && last.team === team) {
        last.lines.push({ text: l.text, kind: l.kind });
        if (!last.names.includes(who)) last.names.push(who);
      } else out.push({ who, team, names: [who], lines: [{ text: l.text, kind: l.kind }] });
    }
    return out;
  }, [p.log]);
  useEffect(() => { const el = feed.current; if (el) el.scrollTop = el.scrollHeight; }, [blocks.length, p.log.length, gate?.title]);
  const agents = p.agents ?? [];
  const done = agents.filter((a) => a.state === "done").length;
  const working = agents.filter((a) => a.state === "working");
  const canDirect = !!p.plan && !running && !p.busy;
  const send = (scope: "look" | "story" | "rewrite") => {
    const n = note.trim();
    if (n.length < 3) return;
    if (scope === "rewrite") onRewrite(n); else onDirect(n, scope);
    setNote("");
  };

  return (
    <section className="agent-panel flex h-full min-h-0 flex-col rounded-3xl border border-border" aria-label="Agent" data-testid="agent-panel">
      <header onPointerDown={onGrab} className={`flex items-center gap-3 border-b border-border px-4 py-3 ${onGrab ? "cursor-grab touch-none select-none active:cursor-grabbing" : ""} ${compact ? "border-b-0" : ""}`}>
        <span className={`h-2 w-2 shrink-0 rounded-full ${running ? "animate-pulse bg-[var(--signal)] shadow-[0_0_12px_rgba(150,120,255,0.9)]" : p.status === "error" ? "bg-[#e0657c]" : p.status === "waiting" ? "bg-[#d9a64e]" : "bg-[#52c79a]"}`} aria-hidden />
        <p className="min-w-0 flex-1 truncate text-sm font-medium">
          {running ? (working[0]?.name ? `${working[0].name} is working` : "Working") : p.status === "waiting" ? "Waiting for you" : p.status === "error" ? "Needs attention" : p.status === "stopped" ? "Stopped" : "Done"}
        </p>
        {running && <button type="button" onPointerDown={(e) => e.stopPropagation()} onClick={onStop} className="inline-flex items-center gap-1 rounded-full border border-border px-3 py-1 text-xs hover:bg-accent"><OctagonX className="h-3.5 w-3.5" />Stop</button>}
        {controls}
      </header>
      {!compact && <>

      <div className="border-b border-border px-4 py-2">
        <button type="button" onClick={() => setTasks(!tasks)} aria-expanded={tasks} className="flex w-full items-center justify-between gap-2 text-left text-xs text-muted-foreground" data-testid="agent-tasks-toggle">
          <span>Tasks · {done} of {agents.length || 15} done</span>
          <ChevronDown className={`h-4 w-4 transition-transform ${tasks ? "rotate-180" : ""}`} />
        </button>
        <div className="mt-2 h-1 overflow-hidden rounded-full bg-muted" aria-hidden><div className="h-full rounded-full bg-primary transition-[width] duration-700" style={{ width: `${agents.length ? Math.round((done / agents.length) * 100) : 0}%` }} /></div>
        {tasks && (
          <ul className="mt-3 max-h-64 space-y-1.5 overflow-y-auto pr-1" data-testid="agent-tasks">
            {agents.map((a: Agent) => {
              const I = ICON[a.state] ?? ICON.waiting;
              return (
                <li key={a.id} className="flex items-start gap-2 text-[12px]">
                  <I.el className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${I.tone}`} />
                  <span className="min-w-0"><span className="text-foreground">{a.name}</span>{a.output && <span className="block truncate text-muted-foreground">{a.output}</span>}</span>
                </li>
              );
            })}
          </ul>
        )}
      </div>

      <div ref={feed} className="min-h-0 flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite" data-testid="agent-feed">
        <div className="rounded-2xl bg-[rgba(124,92,255,0.12)] px-3.5 py-2.5 text-sm">
          <p className="text-[11px] text-muted-foreground">You</p>
          <p className="mt-0.5 line-clamp-4 whitespace-pre-line">{p.brief}</p>
        </div>
        {blocks.map((b, i) => {
          const last = i === blocks.length - 1;
          const shown = b.lines.slice(-4);
          return (
            <div key={i} className="agent-step rounded-2xl border border-border px-3.5 py-2.5">
              <p className="flex items-center gap-2 text-[11px] text-[var(--signal)]">
                {last && running ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}{b.names.join(" · ")}
                {b.lines.length > 4 && <span className="text-muted-foreground">· {b.lines.length} steps</span>}
              </p>
              <ul className="mt-1 space-y-0.5">
                {shown.map((l, k) => <li key={k} className={`text-[13px] leading-snug ${l.kind === "error" ? "text-[#ff8aa0]" : l.kind === "warn" ? "text-[#e7c27d]" : "text-muted-foreground"}`}>{l.text}</li>)}
              </ul>
            </div>
          );
        })}
        {error && (
          <div className="rounded-2xl border border-[#e0657c]/45 px-3.5 py-3" role="alert">
            <p className="flex items-center gap-2 text-sm font-medium"><AlertCircle className="h-4 w-4 text-[#e0657c]" />{p.status === "stopped" ? "Stopped" : "This step did not finish"}</p>
            <p className="mt-1 text-[13px] text-muted-foreground">{error}</p>
            <button type="button" onClick={onContinue} className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-sm font-semibold"><Play className="h-3.5 w-3.5" />Continue</button>
          </div>
        )}
        {gate && (
          <div className="rounded-2xl border border-[rgba(185,172,255,0.5)] bg-[rgba(124,92,255,0.08)] px-3.5 py-3" data-testid="agent-gate">
            <p className="text-sm font-medium">{gate.title}</p>
            <p className="mt-1 text-[13px] leading-snug text-muted-foreground">{gate.help}</p>
            <button type="button" disabled={gate.pending} onClick={gate.onApprove} className="mt-3 inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-2 text-sm font-semibold disabled:opacity-60" data-testid="explainer-approve">
              {gate.pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}{gate.action}
            </button>
          </div>
        )}
      </div>

      <form className="border-t border-border p-3" onSubmit={(e) => { e.preventDefault(); send(p.status === "waiting" && p.stage === "plan" ? "rewrite" : "story"); }}>
        <label htmlFor="agent-note" className="sr-only">Tell the agent what to change</label>
        <textarea id="agent-note" value={note} onChange={(e) => setNote(e.target.value)} rows={2} data-testid="direct-note"
          disabled={!(canDirect || (p.status === "waiting" && p.stage === "plan")) || busy}
          placeholder={p.status === "waiting" && p.stage === "plan" ? "Tell the writer what to change, e.g. make it funnier, a shorter hook" : running ? "The crew is working…" : "Tell the agent what to change, e.g. a vivid magenta and sky-blue look"}
          className="w-full resize-none rounded-2xl border border-border p-3 text-sm outline-none disabled:opacity-60" />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {p.status === "waiting" && p.stage === "plan" ? (
            <button type="submit" disabled={note.trim().length < 3 || busy} className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-border px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"><RotateCcw className="h-3.5 w-3.5" />Write again</button>
          ) : (
            <>
              <button type="button" disabled={!canDirect || busy || note.trim().length < 3} onClick={() => send("look")} className="rounded-full border border-border px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50" data-testid="direct-look">Change the look</button>
              <button type="submit" disabled={!canDirect || busy || note.trim().length < 3} className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-primary px-4 py-1.5 text-xs font-semibold disabled:opacity-40" data-testid="direct-story"><Send className="h-3.5 w-3.5" />Change the story</button>
            </>
          )}
        </div>
      </form>
      </>}
    </section>
  );
}
