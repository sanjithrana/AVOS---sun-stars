"use client";

import { useCallback, useEffect, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import { Bot, Minus, PanelTopOpen, X } from "lucide-react";
import type { Project } from "@/lib/explainer";
import { AgentPanel, type Gate } from "./AgentPanel";

/* The agent as a floating window over the output: drag it by its title bar anywhere, resize it from the corner, fold it
   to its title bar, or close it to a round button that brings it back. Where you left it is remembered on this computer. */

type Mode = "open" | "min" | "closed";
interface Box { x: number; y: number; w: number; h: number }
const KEY = "avos.agent.window";
const MIN_W = 300, MIN_H = 260, BAR = 56;

function load(): { mode: Mode; box: Box | null } {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || "null");
    if (v && typeof v === "object") return { mode: (["open", "min", "closed"] as Mode[]).includes(v.mode) ? v.mode : "open", box: v.box ?? null };
  } catch { /* private window or blocked storage: defaults */ }
  return { mode: "open", box: null };
}
function save(mode: Mode, box: Box | null) { try { localStorage.setItem(KEY, JSON.stringify({ mode, box })); } catch { /* ignore */ } }

function clamp(b: Box): Box {
  const vw = window.innerWidth, vh = window.innerHeight;
  const w = Math.min(Math.max(MIN_W, b.w), vw - 16), h = Math.min(Math.max(MIN_H, b.h), vh - 16);
  return { w, h, x: Math.min(Math.max(8, b.x), vw - w - 8), y: Math.min(Math.max(8, b.y), vh - Math.min(h, BAR) - 8) };
}
const start = (): Box => {
  const vw = window.innerWidth, vh = window.innerHeight;
  const w = Math.min(420, vw - 32), h = Math.min(640, vh - 120);
  return clamp({ x: vw - w - 24, y: vh - h - 24, w, h });
};

type AgentProps = Omit<Parameters<typeof AgentPanel>[0], "controls" | "onGrab" | "compact">;

export function FloatingAgent(props: AgentProps) {
  const [mode, setMode] = useState<Mode>("open");
  const [box, setBox] = useState<Box | null>(null);
  const drag = useRef<{ kind: "move" | "size"; sx: number; sy: number; b: Box } | null>(null);
  useEffect(() => {
    const s = load();
    setMode(s.mode);
    setBox(clamp(s.box ?? start()));
    const onResize = () => setBox((b) => (b ? clamp(b) : b));
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);
  useEffect(() => { if (box) save(mode, box); }, [mode, box]);

  const begin = useCallback((kind: "move" | "size") => (e: RPointerEvent<HTMLElement>) => {
    if (!box || e.button !== 0) return;
    if ((e.target as HTMLElement).closest("button") && kind === "move") return;
    e.preventDefault();
    (e.currentTarget as HTMLElement).setPointerCapture(e.pointerId);
    drag.current = { kind, sx: e.clientX, sy: e.clientY, b: box };
  }, [box]);
  const moveTo = (e: RPointerEvent<HTMLElement>) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.sx, dy = e.clientY - d.sy;
    setBox(clamp(d.kind === "move" ? { ...d.b, x: d.b.x + dx, y: d.b.y + dy } : { ...d.b, w: d.b.w + dx, h: d.b.h + dy }));
  };
  const end = () => { drag.current = null; };

  const waiting = props.p.status === "waiting";
  const working = props.p.status === "working";
  if (!box) return null;

  if (mode === "closed") {
    return (
      <button type="button" onClick={() => setMode("open")} data-testid="agent-launcher" aria-label={waiting ? "Open the agent: it is waiting for you" : "Open the agent"}
        className="agent-launcher fixed bottom-6 right-6 z-50 inline-flex h-14 items-center gap-2 rounded-full bg-primary pl-4 pr-5 text-sm font-semibold">
        <Bot className="h-5 w-5" />Agent
        {(waiting || working) && <span className={`ml-1 h-2.5 w-2.5 rounded-full ${waiting ? "bg-[#ffd27a]" : "animate-pulse bg-white"}`} aria-hidden />}
      </button>
    );
  }

  const controls = (
    <span className="ml-1 flex items-center gap-1" onPointerDown={(e) => e.stopPropagation()}>
      <button type="button" onClick={() => setMode(mode === "min" ? "open" : "min")} className="rounded-full p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        aria-label={mode === "min" ? "Unfold the agent" : "Fold the agent"} data-testid="agent-min">{mode === "min" ? <PanelTopOpen className="h-4 w-4" /> : <Minus className="h-4 w-4" />}</button>
      <button type="button" onClick={() => setMode("closed")} className="rounded-full p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground" aria-label="Close the agent" data-testid="agent-close"><X className="h-4 w-4" /></button>
    </span>
  );

  return (
    <div role="dialog" aria-label="Agent" data-testid="agent-window" onPointerMove={moveTo} onPointerUp={end} onPointerCancel={end}
      className="agent-window fixed z-50" style={{ left: box.x, top: box.y, width: box.w, height: mode === "min" ? "auto" : box.h }}>
      <AgentPanel {...props} controls={controls} onGrab={begin("move")} compact={mode === "min"} />
      {mode === "open" && (
        <span onPointerDown={begin("size")} data-testid="agent-resize" aria-hidden
          className="absolute bottom-1 right-1 h-5 w-5 cursor-nwse-resize touch-none rounded-br-[1.25rem] border-b-2 border-r-2 border-[rgba(185,172,255,0.6)]" />
      )}
    </div>
  );
}
