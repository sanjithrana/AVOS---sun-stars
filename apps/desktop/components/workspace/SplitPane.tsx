"use client";

import { useEffect, useRef, type ReactNode } from "react";

const KEY = "avos-split";

/** Inputs on the left, output on the right. On wide screens the divider can be dragged (or moved with the arrow keys) and the width is remembered. */
export function SplitPane({ left, right, min = 300, max = 620, initial = 400 }: { left: ReactNode; right: ReactNode; min?: number; max?: number; initial?: number }) {
  const root = useRef<HTMLDivElement>(null);
  const width = useRef(initial);
  const drag = useRef(false);
  const apply = (v: number) => { width.current = Math.min(max, Math.max(min, v)); root.current?.style.setProperty("--split-w", `${Math.round(width.current)}px`); };
  const save = () => { try { window.localStorage.setItem(KEY, String(Math.round(width.current))); } catch { /* storage blocked */ } };
  useEffect(() => {
    let v = initial;
    try { const s = Number(window.localStorage.getItem(KEY)); if (s >= min && s <= max) v = s; } catch { /* storage blocked */ }
    apply(v);
    const move = (e: PointerEvent) => { if (drag.current && root.current) apply(e.clientX - root.current.getBoundingClientRect().left); };
    const up = () => { if (drag.current) { drag.current = false; document.body.style.userSelect = ""; save(); } };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initial, min, max]);
  return (
    <div ref={root} className="lg:flex lg:items-start" style={{ ["--split-w" as string]: `${initial}px` }} data-testid="split-pane">
      <aside className="mb-6 min-w-0 lg:sticky lg:top-0 lg:mb-0 lg:max-h-[calc(100dvh-9rem)] lg:w-[var(--split-w)] lg:shrink-0 lg:overflow-y-auto lg:pr-1">{left}</aside>
      <div role="separator" aria-orientation="vertical" aria-label="Resize panels" tabIndex={0}
        onPointerDown={(e) => { drag.current = true; document.body.style.userSelect = "none"; e.preventDefault(); }}
        onKeyDown={(e) => { if (e.key === "ArrowLeft") { apply(width.current - 24); save(); } if (e.key === "ArrowRight") { apply(width.current + 24); save(); } }}
        className="group mx-2 hidden w-3 shrink-0 cursor-col-resize self-stretch lg:block"><span className="mx-auto block h-full w-px bg-border transition-colors group-hover:bg-primary group-focus-visible:bg-primary" /></div>
      <section className="min-w-0 flex-1">{right}</section>
    </div>
  );
}
