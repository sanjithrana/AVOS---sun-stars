// The shot's scene graph + motion blueprint on the client: the same rules as agentic_core/creative/scene.py
// (camera rigs per framing, camera moves), so what the Director previews is what the prompt compiler describes.
import type { Blueprint, CameraState, StageGraph } from "./types";

export const FRAMINGS = ["wide", "medium", "two-shot", "close-up", "over-the-shoulder", "insert"] as const;
export const MOVES = ["static", "push_in", "pull_out", "pan_left", "pan_right", "truck_left", "truck_right", "tilt_up", "tilt_down",
  "crane_up", "crane_down", "orbit_left", "orbit_right", "zoom_in", "handheld"] as const;
export const EASES = ["none", "power1.inOut", "power2.inOut", "power2.out", "power3.out", "sine.inOut", "expo.inOut"] as const;

// framing → [lens mm, distance, camera height, look-at height]
const RIG: Record<string, [number, number, number, number]> = {
  wide: [24, 6.5, 1.6, 1.1], medium: [35, 3.2, 1.5, 1.25], "two-shot": [35, 3.8, 1.5, 1.2],
  "close-up": [85, 2.4, 1.45, 1.45], "over-the-shoulder": [50, 2.6, 1.55, 1.4], insert: [85, 1.3, 1.1, 0.9],
};
const r3 = (n: number) => Math.round(n * 1000) / 1000;

export function cameraFor(framing: string, subject: [number, number] | null): CameraState {
  const [mm, dist, height, look] = RIG[framing] ?? RIG.medium;
  const [sx, sz] = subject ?? [0, 0];
  return { position: [r3(sx * 0.5), height, r3(sz + dist)], target: [r3(sx), look, r3(sz)], lens: mm };
}

export function moveCamera(cam: CameraState, move: string, amount = 1): CameraState {
  let p = [...cam.position] as [number, number, number];
  const t = [...cam.target] as [number, number, number];
  let lens = cam.lens;
  const d = [t[0] - p[0], t[1] - p[1], t[2] - p[2]];
  const k = amount;
  if (move === "push_in") p = p.map((v, i) => v + d[i] * 0.3 * k) as typeof p;
  else if (move === "pull_out") p = p.map((v, i) => v - d[i] * 0.35 * k) as typeof p;
  else if (move === "pan_left" || move === "pan_right") t[0] += (move === "pan_left" ? -0.9 : 0.9) * k;
  else if (move === "truck_left" || move === "truck_right") { const s = (move === "truck_left" ? -0.8 : 0.8) * k; p[0] += s; t[0] += s; }
  else if (move === "tilt_up" || move === "tilt_down") t[1] += (move === "tilt_up" ? 0.6 : -0.5) * k;
  else if (move === "crane_up" || move === "crane_down") p[1] = Math.max(0.3, p[1] + (move === "crane_up" ? 0.9 : -0.6) * k);
  else if (move === "orbit_left" || move === "orbit_right") {
    const a = ((move === "orbit_left" ? -20 : 20) * k * Math.PI) / 180;
    const dx = p[0] - t[0], dz = p[2] - t[2];
    p[0] = t[0] + dx * Math.cos(a) - dz * Math.sin(a);
    p[2] = t[2] + dx * Math.sin(a) + dz * Math.cos(a);
  } else if (move === "zoom_in") lens = Math.min(200, Math.round(lens * 1.4));
  return { position: p.map(r3) as [number, number, number], target: t.map(r3) as [number, number, number], lens };
}

/** Vertical field of view (degrees) of a full-frame lens. */
export const fovOf = (lens: number) => (2 * Math.atan(24 / (2 * Math.max(8, lens))) * 180) / Math.PI;

/** Re-frame the stage's camera for a framing, on the speaker (or the group). */
export function reframe(stage: StageGraph, framing: string): StageGraph {
  const focus = stage.actors.find((a) => a.speaking) ?? stage.actors[0];
  let subj: [number, number] | null = focus ? [focus.x, focus.z] : null;
  if ((framing === "two-shot" || framing === "wide") && stage.actors.length > 1)
    subj = [stage.actors.reduce((s, a) => s + a.x, 0) / stage.actors.length, stage.actors.reduce((s, a) => s + a.z, 0) / stage.actors.length];
  return { ...stage, framing, camera: cameraFor(framing, subj) };
}

/** A new camera move from the stage camera (the end is derived, like the server does). */
export function withMove(bp: Blueprint, stage: StageGraph, move: string, ease?: string): Blueprint {
  return { ...bp, camera: { ...bp.camera, move, ease: ease ?? bp.camera.ease, from: stage.camera, to: moveCamera(stage.camera, move), shake: move === "handheld" ? 0.15 : 0 } };
}
