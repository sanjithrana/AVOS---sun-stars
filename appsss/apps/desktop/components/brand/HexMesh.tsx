"use client";

import { useEffect, useRef } from "react";

/* A glowing honeycomb floor that rolls like a slow wave toward the viewer: cyan on the left, violet in the middle, magenta on the right.

   Built to stay light on integrated graphics:
   - no canvas shadowBlur (the expensive part); the glow is one wide faint stroke under one thin bright stroke
   - every hexagon of one colour and depth band goes into ONE path, so a frame is ~48 strokes instead of thousands
   - 24 frames a second at most, at most 1.25x pixel density
   - it pauses while you scroll, when it is off screen or the tab is hidden, and holds still for reduced motion */
const COLS = 40, ROWS = 26, R = 0.8, BANDS = 6, HUES = 8, FPS = 24;

export function HexMesh({ className = "" }: { className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const cv = ref.current;
    const ctx = cv?.getContext("2d", { alpha: true });
    if (!cv || !ctx) return;
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const dpr = Math.min(1.25, window.devicePixelRatio || 1);
    let w = 0, h = 0, raf = 0, last = 0, visible = true, scrolling = 0;
    const t0 = performance.now();
    const hx = Math.sqrt(3) * R, vy = 1.5 * R;
    const stops = [[70, 210, 255], [150, 95, 255], [235, 70, 245]];               // cyan, violet, magenta
    const colours = Array.from({ length: HUES }, (_, i) => {
      const k = (i / (HUES - 1)) * 2, j = Math.min(1, Math.floor(k)), f = k - j;
      return stops[j].map((c, n) => Math.round(c + (stops[j + 1][n] - c) * f));
    });
    const size = () => {
      const r = cv.getBoundingClientRect();
      w = r.width; h = r.height;
      cv.width = Math.max(1, Math.round(w * dpr)); cv.height = Math.max(1, Math.round(h * dpr));
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      paint(performance.now());
    };
    const project = (x: number, z: number, y: number, out: number[]) => {
      const near = 7, d = z + near, horizon = h * 0.02;
      const sx = Math.max(130, w * 0.085), K = (h * 1.05 - horizon) * near;
      out[0] = w / 2 + (x * sx * near) / d;
      out[1] = horizon + K / d - (y * K) / d / 3.2;
    };
    const height = (x: number, z: number, t: number) =>
      0.32 * Math.sin(x * 0.55 + t * 0.7) * Math.cos(z * 0.42 - t * 0.5) + 0.22 * Math.sin((x - z) * 0.3 + t * 0.35);

    const p = [0, 0];
    function paint(now: number) {
      if (!w || !h) return;
      const t = still ? 2 : (now - t0) / 1000;
      const paths: Path2D[][] = Array.from({ length: BANDS }, () => Array.from({ length: HUES }, () => new Path2D()));
      for (let row = ROWS; row >= 0; row--) {
        const band = Math.min(BANDS - 1, Math.floor((row / (ROWS + 1)) * BANDS));
        for (let col = -COLS / 2; col <= COLS / 2; col++) {
          const cx = col * hx + (row % 2 ? hx / 2 : 0), cz = row * vy;
          const hue = Math.max(0, Math.min(HUES - 1, Math.round(((cx / (COLS * hx * 0.32)) + 1) / 2 * (HUES - 1))));
          const path = paths[band][hue];
          let off = 0;
          for (let k = 0; k < 6; k++) {
            const ang = (Math.PI / 3) * k + Math.PI / 6;
            const x = cx + R * Math.cos(ang), z = cz + R * Math.sin(ang);
            project(x, z, height(x, z, t), p);
            if (p[0] < -40 || p[0] > w + 40) off++;
            if (k === 0) path.moveTo(p[0], p[1]); else path.lineTo(p[0], p[1]);
          }
          if (off < 6) path.closePath();
        }
      }
      ctx!.clearRect(0, 0, w, h);
      ctx!.lineJoin = "round";
      for (let b = BANDS - 1; b >= 0; b--) {
        const depth = 1 - b / BANDS;
        const a = Math.min(1, Math.pow(depth, 1.3) * 1.05);
        for (let i = 0; i < HUES; i++) {
          const [r, g, bl] = colours[i];
          if (b < 2) {                                   // the glow, only on the two nearest bands where it shows
            ctx!.strokeStyle = `rgba(${r},${g},${bl},${a * 0.2})`;
            ctx!.lineWidth = 3.5;
            ctx!.stroke(paths[b][i]);
          }
          ctx!.strokeStyle = `rgba(${Math.min(255, r + 40)},${Math.min(255, g + 40)},${bl},${a})`;
          ctx!.lineWidth = 1;                            // the line
          ctx!.stroke(paths[b][i]);
        }
      }
    }
    function loop(now: number) {
      raf = 0;
      if (!visible || document.hidden) return;
      if (now - last >= 1000 / FPS && now > scrolling) { last = now; paint(now); }
      raf = requestAnimationFrame(loop);
    }
    const start = () => { if (!still && !raf && visible && !document.hidden) raf = requestAnimationFrame(loop); };
    const onScroll = () => { scrolling = performance.now() + 180; };                     // let the page scroll first
    const ro = new ResizeObserver(size);
    ro.observe(cv);
    const io = new IntersectionObserver(([e]) => { visible = e.isIntersecting; start(); }, { threshold: 0 });
    io.observe(cv);
    document.addEventListener("visibilitychange", start);
    window.addEventListener("scroll", onScroll, { capture: true, passive: true });
    size();
    start();
    return () => {
      cancelAnimationFrame(raf); ro.disconnect(); io.disconnect();
      document.removeEventListener("visibilitychange", start);
      window.removeEventListener("scroll", onScroll, { capture: true } as EventListenerOptions);
    };
  }, []);
  return <canvas ref={ref} className={`pointer-events-none block h-full w-full ${className}`} aria-hidden />;
}
