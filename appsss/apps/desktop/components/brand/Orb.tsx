"use client";

import { useEffect, useRef, useState } from "react";

/* AVOS mark: a glass sphere wrapped in curved film-frame tiles that slowly turns.
   Tiles are projected from a real sphere, so they bend at the edges like glass.
   Hover or focus lights it up and speeds the turn. */

const LAT = 4, LON = 7, GAP = 0.10, STEPS = 6, TILT = -0.42;
const SKIP = new Set([2, 9, 17, 24]);
const HUES = ["#8f7bff", "#ff8fd2", "#7fe3ff", "#b9acff", "#5b3df5", "#ffd1f0"];

type Tile = { d: string; z: number; key: number; hue: string; front: boolean };

function project(lat: number, lon: number, yaw: number, r: number): [number, number, number] {
  let x = Math.cos(lat) * Math.sin(lon), y = Math.sin(lat), z = Math.cos(lat) * Math.cos(lon);
  const cy = Math.cos(yaw), sy = Math.sin(yaw);
  [x, z] = [x * cy + z * sy, -x * sy + z * cy];
  const ct = Math.cos(TILT), st = Math.sin(TILT);
  [y, z] = [y * ct - z * st, y * st + z * ct];
  return [x * r, -y * r, z];
}

function tiles(yaw: number, r: number): Tile[] {
  const out: Tile[] = [];
  for (let i = 0; i < LAT; i++) for (let j = 0; j < LON; j++) {
    const k = i * LON + j;
    if (SKIP.has(k)) continue;
    const a0 = -Math.PI / 2 + ((i + GAP) / LAT) * Math.PI, a1 = -Math.PI / 2 + ((i + 1 - GAP) / LAT) * Math.PI;
    const b0 = ((j + GAP) / LON) * Math.PI * 2, b1 = ((j + 1 - GAP) / LON) * Math.PI * 2;
    const pts: [number, number, number][] = [];
    for (let s = 0; s <= STEPS; s++) pts.push(project(a0, b0 + (b1 - b0) * (s / STEPS), yaw, r));
    for (let s = 0; s <= STEPS; s++) pts.push(project(a0 + (a1 - a0) * (s / STEPS), b1, yaw, r));
    for (let s = 0; s <= STEPS; s++) pts.push(project(a1, b1 - (b1 - b0) * (s / STEPS), yaw, r));
    for (let s = 0; s <= STEPS; s++) pts.push(project(a1 - (a1 - a0) * (s / STEPS), b0, yaw, r));
    const z = pts.reduce((t, p) => t + p[2], 0) / pts.length;
    out.push({ d: "M" + pts.map((p) => `${p[0].toFixed(1)} ${p[1].toFixed(1)}`).join("L") + "Z", z, key: k, hue: HUES[k % HUES.length], front: z > 0 });
  }
  return out.sort((a, b) => a.z - b.z);
}

export function Orb({ size = 220, className = "" }: { size?: number; className?: string }) {
  const [yaw, setYaw] = useState(0.6);
  const hot = useRef(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0, last = performance.now(), acc = 0, seen = false, scrolling = 0;
    const tick = (t: number) => {
      raf = 0;
      if (!seen || document.hidden) return;                 // only turns while you can see it
      const dt = Math.min(0.1, (t - last) / 1000); last = t; acc += dt;
      if (acc > 1 / 24 && t > scrolling) { setYaw((y) => y + acc * (hot.current ? 0.9 : 0.18)); acc = 0; }
      raf = requestAnimationFrame(tick);
    };
    const go = () => { if (!raf && seen && !document.hidden) { last = performance.now(); raf = requestAnimationFrame(tick); } };
    const io = new IntersectionObserver(([e]) => { seen = e.isIntersecting; go(); });
    if (box.current) io.observe(box.current);
    const onScroll = () => { scrolling = performance.now() + 180; };
    window.addEventListener("scroll", onScroll, { capture: true, passive: true });
    document.addEventListener("visibilitychange", go);
    return () => { cancelAnimationFrame(raf); io.disconnect(); window.removeEventListener("scroll", onScroll, { capture: true } as EventListenerOptions); document.removeEventListener("visibilitychange", go); };
  }, []);
  const R = 96;
  const list = tiles(yaw, R);
  const on = () => { hot.current = true; }, off = () => { hot.current = false; };
  return (
    <div ref={box} className={`orb relative mx-auto ${className}`} style={{ width: size, height: size }} tabIndex={0} role="img" aria-label="AVOS"
      onMouseEnter={on} onMouseLeave={off} onFocus={on} onBlur={off}>
      <div className="orb-halo pointer-events-none absolute -inset-16 rounded-full" />
      <svg viewBox="-110 -110 220 220" width={size} height={size} className="orb-svg relative overflow-visible">
        <defs>
          {HUES.map((h, i) => (
            <linearGradient key={h} id={`orb-g${i}`} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0" stopColor="#ffffff" stopOpacity="0.95" />
              <stop offset="0.45" stopColor={h} />
              <stop offset="1" stopColor="#2a1f8a" />
            </linearGradient>
          ))}
          <radialGradient id="orb-core" cx="0.42" cy="0.38" r="0.7">
            <stop offset="0" stopColor="#3a2bb0" stopOpacity="0.55" />
            <stop offset="1" stopColor="#05030f" stopOpacity="0.9" />
          </radialGradient>
          <radialGradient id="orb-spec" cx="0.32" cy="0.26" r="0.45">
            <stop offset="0" stopColor="#fff" stopOpacity="0.55" />
            <stop offset="1" stopColor="#fff" stopOpacity="0" />
          </radialGradient>
        </defs>
        <circle r={R * 0.93} fill="url(#orb-core)" />
        {list.map((t) => (
          <path key={t.key} d={t.d}
            fill={t.front ? `url(#orb-g${HUES.indexOf(t.hue)})` : t.hue}
            fillOpacity={t.front ? 0.35 + t.z * 0.6 : 0.10}
            stroke={t.front ? "rgba(255,255,255,0.85)" : "rgba(200,190,255,0.25)"}
            strokeWidth={t.front ? 0.6 + t.z * 0.9 : 0.4}
            strokeLinejoin="round" />
        ))}
        <path d="M-12 -20 L22 0 L-12 20 Z" fill="#fff" opacity="0.92" />
        <circle r={R} fill="url(#orb-spec)" pointerEvents="none" />
      </svg>
    </div>
  );
}
