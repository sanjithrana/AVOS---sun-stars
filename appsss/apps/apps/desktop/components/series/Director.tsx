"use client";
// Director mode for one shot: a Three.js stage (the place, the characters from their approved sheets, the camera)
// and a GSAP timeline that plays the motion blueprint (the camera move with its ease, each character's timed
// actions). Edit the blocking, the camera and the timeline, then Save: only this shot is drawn / animated again.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import gsap from "gsap";
import { Camera, Clapperboard, Pause, Play, Plus, Save, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { seriesApi } from "./api";
import { field, type Act } from "./shared";
import { EASES, FRAMINGS, MOVES, cameraFor, fovOf, reframe, withMove } from "./stage";
import type { Blueprint, CameraState, Episode, Part, SeriesSnapshot, Shot, StageGraph, Vec3 } from "./types";

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v)) as T;
const TIMES = ["morning", "day", "afternoon", "evening", "night"];
const LIGHT: Record<string, [number, number]> = { morning: [0xfff1d6, 1.1], day: [0xffffff, 1.3], afternoon: [0xfff4e0, 1.2], evening: [0xffc98a, 0.9], night: [0x9fb4ff, 0.55] };

function fallbackStage(shot: Shot): StageGraph {
  const ids = shot.subjects ?? [];
  const xs = ids.length === 2 ? [-0.55, 0.55] : ids.length === 3 ? [-0.9, 0, 0.9] : [0];
  const actors = ids.map((id, i) => ({ id, x: xs[i] ?? 0, z: 0, facing: "camera", pose: "standing", expression: shot.emotion ?? "neutral", speaking: id === shot.speaker }));
  return { location: shot.location, time: "day", framing: shot.framing, lighting: { preset: "day", key: "bright daylight", mood: "cheerful" }, actors, props: [],
    camera: cameraFor(shot.framing, actors[0] ? [actors[0].x, actors[0].z] : null) };
}

function webglWorks(): boolean {
  if (typeof document === "undefined") return false;
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch { return false; }
}

interface Live { cam: { px: number; py: number; pz: number; tx: number; ty: number; tz: number; lens: number }; actors: Record<string, { x: number; z: number }> }

export function Director({ sid, snap, ep, part, shot, act, onClose }: {
  sid: string; snap: SeriesSnapshot; ep: Episode; part: Part; shot: Shot; act: Act; onClose: () => void;
}) {
  const [stage, setStage] = useState<StageGraph>(() => clone(shot.stage ?? fallbackStage(shot)));
  const [bp, setBp] = useState<Blueprint>(() => {
    const st = shot.stage ?? fallbackStage(shot);
    return clone(shot.blueprint ?? withMove({ duration: shot.seconds, camera: { move: "static", ease: "power1.inOut", from: st.camera, to: st.camera, shake: 0 },
      tracks: [], environment: [], lipsync: shot.speaker ?? null }, st, "static"));
  });
  const [view, setView] = useState<"camera" | "top">("camera");
  const [t, setT] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [sel, setSel] = useState<string | null>(stage.actors[0]?.id ?? null);
  const [dirty, setDirty] = useState(false);
  const [gl] = useState(webglWorks);
  const mount = useRef<HTMLDivElement>(null);
  const three = useRef<{
    renderer: THREE.WebGLRenderer; scene: THREE.Scene; shotCam: THREE.PerspectiveCamera; topCam: THREE.PerspectiveCamera;
    actors: Map<string, THREE.Object3D>; helper: THREE.CameraHelper; path: THREE.Line; sun: THREE.DirectionalLight; floor: THREE.Mesh;
  } | null>(null);
  const live = useRef<Live>({ cam: { px: 0, py: 1.5, pz: 3, tx: 0, ty: 1.2, tz: 0, lens: 35 }, actors: {} });
  const viewRef = useRef(view);
  const tl = useRef<gsap.core.Timeline | null>(null);
  const names = useMemo(() => Object.fromEntries(snap.series.characters.map((c) => [c.id, c.name])), [snap.series.characters]);
  const sheets = useMemo(() => Object.fromEntries(snap.series.characters.map((c) => [c.id, c.sheet ? seriesApi.file(sid, c.sheet) : ""])), [snap.series.characters, sid]);
  const plate = snap.series.locations.find((l) => l.id === shot.location)?.plate;
  const aspect = snap.series.format.width / snap.series.format.height;

  // ---------- render one frame from the live (GSAP-driven) state ----------
  const draw = useCallback(() => {
    const T = three.current;
    if (!T) return;
    const c = live.current.cam;
    T.shotCam.position.set(c.px, c.py, c.pz);
    T.shotCam.fov = fovOf(c.lens);
    T.shotCam.updateProjectionMatrix();
    T.shotCam.lookAt(c.tx, c.ty, c.tz);
    T.helper.update();
    T.helper.visible = viewRef.current === "top";
    T.path.visible = viewRef.current === "top";
    for (const [id, obj] of T.actors) {
      const a = live.current.actors[id];
      if (a) obj.position.set(a.x, 0, a.z);
      const pic = obj.getObjectByName("pic");
      if (pic) pic.lookAt(c.px, pic.getWorldPosition(new THREE.Vector3()).y, c.pz);     // billboards face the shot camera
    }
    T.renderer.render(T.scene, viewRef.current === "camera" ? T.shotCam : T.topCam);
  }, []);

  // ---------- the Three.js stage (once) ----------
  useEffect(() => {
    const el = mount.current;
    if (!el || !gl) return;
    const w = el.clientWidth || 800, h = Math.round(w / aspect);
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setSize(w, h);
    el.appendChild(renderer.domElement);
    renderer.domElement.dataset.testid = "director-canvas";
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1d1f26);
    scene.add(new THREE.AmbientLight(0xffffff, 0.75));
    const sun = new THREE.DirectionalLight(0xffffff, 1.2);
    sun.position.set(3, 6, 5);
    scene.add(sun);
    const floor = new THREE.Mesh(new THREE.PlaneGeometry(16, 12), new THREE.MeshStandardMaterial({ color: 0x8f8a80 }));
    floor.rotation.x = -Math.PI / 2;
    floor.position.z = 2;
    floor.name = "floor";
    scene.add(floor);
    const grid = new THREE.GridHelper(16, 16, 0x555555, 0x6d6a64);
    grid.position.set(0, 0.002, 2);
    scene.add(grid);
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(12, 6.75), new THREE.MeshBasicMaterial({ color: 0x5a6070 }));
    wall.position.set(0, 3.375, -4);
    scene.add(wall);
    if (plate) new THREE.TextureLoader().load(seriesApi.file(sid, plate), (tex) => {
      tex.colorSpace = THREE.SRGBColorSpace;
      (wall.material as THREE.MeshBasicMaterial).map = tex;
      (wall.material as THREE.MeshBasicMaterial).color.set(0xffffff);
      (wall.material as THREE.MeshBasicMaterial).needsUpdate = true;
      draw();
    });
    const shotCam = new THREE.PerspectiveCamera(40, aspect, 0.05, 100);
    const topCam = new THREE.PerspectiveCamera(50, aspect, 0.1, 200);
    topCam.position.set(0, 13, 6);
    topCam.lookAt(0, 0, 0.5);
    const helper = new THREE.CameraHelper(shotCam);
    scene.add(helper);
    const path = new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: 0x8b5cf6 }));
    scene.add(path);
    three.current = { renderer, scene, shotCam, topCam, actors: new Map(), helper, path, sun, floor };
    draw();
    return () => {
      three.current = null;
      renderer.dispose();
      el.removeChild(renderer.domElement);
    };
  }, [aspect, plate, sid, draw, gl]);

  // ---------- characters as billboards cut from their approved sheets (the front view), props as boxes ----------
  const actorKey = stage.actors.map((a) => a.id).join("|") + "#" + stage.props.map((p) => p.name).join("|");
  useEffect(() => {
    const T = three.current;
    if (!T) return;
    for (const obj of T.actors.values()) T.scene.remove(obj);
    T.actors.clear();
    const loader = new THREE.TextureLoader();
    stage.actors.forEach((a, i) => {
      const g = new THREE.Group();
      const hue = (i * 0.27) % 1;
      const ring = new THREE.Mesh(new THREE.RingGeometry(0.28, 0.34, 32), new THREE.MeshBasicMaterial({ color: new THREE.Color().setHSL(hue, 0.8, 0.55), side: THREE.DoubleSide }));
      ring.rotation.x = -Math.PI / 2;
      ring.position.y = 0.01;
      ring.name = "ring";
      g.add(ring);
      const pic = new THREE.Mesh(new THREE.PlaneGeometry(0.84, 1.6), new THREE.MeshBasicMaterial({ color: new THREE.Color().setHSL(hue, 0.5, 0.6), transparent: true, side: THREE.DoubleSide }));
      pic.position.y = 0.8;
      pic.name = "pic";
      g.add(pic);
      g.userData.id = a.id;
      if (sheets[a.id]) loader.load(sheets[a.id], (tex) => {
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.repeat.set(0.3, 1);          // the sheet's first view (front, full body)
        tex.offset.set(0.0, 0);
        const m = pic.material as THREE.MeshBasicMaterial;
        m.map = tex;
        m.color.set(0xffffff);
        m.needsUpdate = true;
        draw();
      });
      T.scene.add(g);
      T.actors.set(a.id, g);
    });
    stage.props.forEach((p) => {
      const box = new THREE.Mesh(new THREE.BoxGeometry(0.25, 0.25, 0.25), new THREE.MeshStandardMaterial({ color: 0x8b5cf6 }));
      box.position.set(p.x, 0.125, p.z);
      box.name = `prop:${p.name}`;
      const g = new THREE.Group();
      g.add(box);
      T.scene.add(g);
      T.actors.set(`prop:${p.name}`, g);
    });
    draw();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- rebuilt only when who/what is on stage changes
  }, [actorKey, sheets, draw]);

  // ---------- the GSAP timeline: the blueprint, scrubbable ----------
  useEffect(() => {
    const T = three.current;
    tl.current?.kill();
    const f = bp.camera.from, to = bp.camera.to;
    live.current.cam = { px: f.position[0], py: f.position[1], pz: f.position[2], tx: f.target[0], ty: f.target[1], tz: f.target[2], lens: f.lens };
    live.current.actors = Object.fromEntries(stage.actors.map((a) => [a.id, { x: a.x, z: a.z }]));
    const timeline = gsap.timeline({ paused: true, onUpdate: () => { setT(Math.round(timeline.time() * 100) / 100); draw(); },
      onComplete: () => setPlaying(false) });
    timeline.to(live.current.cam, { px: to.position[0], py: to.position[1], pz: to.position[2], tx: to.target[0], ty: to.target[1], tz: to.target[2],
      lens: to.lens, duration: bp.duration, ease: bp.camera.ease === "none" ? "none" : bp.camera.ease }, 0);
    for (const tr of bp.tracks) {
      const a = live.current.actors[tr.target];
      if (!a) continue;
      let prevT = 0;
      for (const k of tr.keys) {
        if (k.x !== undefined || k.z !== undefined) {
          timeline.to(a, { ...(k.x !== undefined ? { x: k.x } : {}), ...(k.z !== undefined ? { z: k.z } : {}), duration: Math.max(0.2, k.t - prevT), ease: "power1.inOut" }, prevT);
        }
        prevT = k.t;
      }
    }
    if (timeline.duration() < bp.duration) timeline.set({}, {}, bp.duration);
    tl.current = timeline;
    timeline.seek(0);
    if (T) {
      (T.path.geometry as THREE.BufferGeometry).setFromPoints([new THREE.Vector3(...f.position), new THREE.Vector3(...to.position)]);
      const [color, intensity] = LIGHT[stage.time] ?? LIGHT.day;
      T.sun.color.set(color);
      T.sun.intensity = intensity;
    }
    draw();
    return () => { timeline.kill(); };
  }, [bp, stage, draw]);

  // ---------- drag characters on the floor (top view) ----------
  const drag = useRef<string | null>(null);
  const onPointer = (e: React.PointerEvent, kind: "down" | "move" | "up") => {
    const T = three.current;
    if (!T || view !== "top") return;
    if (kind === "up") { drag.current = null; return; }
    const r = T.renderer.domElement.getBoundingClientRect();
    const ndc = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    const ray = new THREE.Raycaster();
    ray.setFromCamera(ndc, T.topCam);
    if (kind === "down") {
      const hits = ray.intersectObjects([...T.actors.values()], true);
      const hit = hits.find((h) => { let o: THREE.Object3D | null = h.object; while (o && !o.userData.id) o = o.parent; return !!o; });
      if (hit) { let o: THREE.Object3D | null = hit.object; while (o && !o.userData.id) o = o.parent; drag.current = o?.userData.id ?? null; setSel(drag.current); }
      return;
    }
    if (!drag.current) return;
    const p = new THREE.Vector3();
    if (!ray.ray.intersectPlane(new THREE.Plane(new THREE.Vector3(0, 1, 0), 0), p)) return;
    const id = drag.current;
    const x = Math.round(Math.max(-6, Math.min(6, p.x)) * 100) / 100, z = Math.round(Math.max(-4, Math.min(4, p.z)) * 100) / 100;
    live.current.actors[id] = { x, z };
    draw();
    setStage((s) => ({ ...s, actors: s.actors.map((a) => (a.id === id ? { ...a, x, z } : a)) }));
    setDirty(true);
  };

  // ---------- edits ----------
  const editStage = (next: StageGraph, keepMove = true) => {
    setStage(next);
    setBp((b) => withMove(b, next, keepMove ? b.camera.move : "static"));
    setDirty(true);
  };
  const setCam = (k: "position" | "target", i: number, v: number) => {
    const cam: CameraState = clone(stage.camera);
    (cam[k] as Vec3)[i] = v;
    editStage({ ...stage, camera: cam });
  };
  const setLens = (v: number) => editStage({ ...stage, camera: { ...stage.camera, lens: v } });
  const editBp = (next: Blueprint) => { setBp(next); setDirty(true); };
  const selActor = stage.actors.find((a) => a.id === sel);
  const track = bp.tracks.find((x) => x.target === sel);
  const setKeys = (keys: { t: number; action: string; x?: number }[]) => {
    const others = bp.tracks.filter((x) => x.target !== sel);
    editBp({ ...bp, tracks: sel ? [...others, { target: sel, keys: [...keys].sort((a, b) => a.t - b.t) }] : others });
  };
  const play = () => {
    const timeline = tl.current;
    if (!timeline) return;
    if (playing) { timeline.pause(); setPlaying(false); return; }
    if (timeline.progress() >= 1) timeline.seek(0);
    timeline.play();
    setPlaying(true);
  };
  const switchView = (v: "camera" | "top") => { viewRef.current = v; setView(v); requestAnimationFrame(draw); };

  const save = () => act(`director-${shot.id}`, async () => {
    const r = await seriesApi.saveStage(sid, ep.id, part.index, shot.id, stage, bp);
    onClose();
    return r;
  });

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-background p-3 md:p-6" data-testid="director">
      <div className="mx-auto max-w-7xl space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <Clapperboard className="h-5 w-5 text-amber-500" />
          <b className="text-lg text-foreground">Director · Part {part.index} · {shot.id}</b>
          <span className="text-sm text-muted-foreground">{shot.kind === "dialogue" ? `${names[shot.speaker ?? ""] ?? ""}: “${shot.text}”` : shot.motion}</span>
          <span className="grow" />
          <div className="inline-flex rounded-xl border border-border p-0.5 text-sm">
            <button className={`rounded-full px-3 py-1 ${view === "camera" ? "bg-amber-500 text-white" : "text-muted-foreground"}`} onClick={() => switchView("camera")} data-testid="view-camera"><Camera className="mr-1 inline h-3.5 w-3.5" />Camera</button>
            <button className={`rounded-full px-3 py-1 ${view === "top" ? "bg-amber-500 text-white" : "text-muted-foreground"}`} onClick={() => switchView("top")} data-testid="view-top">Overhead (drag people)</button>
          </div>
          <Button size="sm" onClick={save} disabled={!dirty} data-testid="director-save"><Save />Save and redo this shot</Button>
          <Button size="sm" variant="ghost" onClick={onClose} data-testid="director-close"><X />Close</Button>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_340px]">
          <div className="space-y-2">
            <div ref={mount} className="w-full overflow-hidden rounded-xl border border-border bg-black" style={{ aspectRatio: String(aspect) }}
              onPointerDown={(e) => onPointer(e, "down")} onPointerMove={(e) => onPointer(e, "move")} onPointerUp={(e) => onPointer(e, "up")} onPointerLeave={(e) => onPointer(e, "up")}>
              {!gl && <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted-foreground" data-testid="director-no-webgl">
                The 3D preview needs WebGL (turn on hardware acceleration in the browser). You can still edit the camera, the people and the timeline and save.</div>}
            </div>
            {/* the timeline */}
            <div className="space-y-2 rounded-xl border border-border bg-card/40 p-3" data-testid="director-timeline">
              <div className="flex items-center gap-3">
                <Button size="sm" variant="outline" onClick={play} data-testid="director-play">{playing ? <Pause /> : <Play />}{playing ? "Pause" : "Play"}</Button>
                <input type="range" min={0} max={bp.duration} step={0.01} value={t} className="flex-1 accent-amber-500" data-testid="director-scrub"
                  onChange={(e) => { const v = Number(e.target.value); tl.current?.pause(); setPlaying(false); tl.current?.seek(v); setT(v); }} />
                <span className="w-24 text-right font-mono text-xs text-muted-foreground">{t.toFixed(2)} / {bp.duration.toFixed(2)}s</span>
              </div>
              <Lane label={`Camera · ${bp.camera.move.replace(/_/g, " ")}`} duration={bp.duration} t={t} keys={[{ t: 0, label: "start" }, { t: bp.duration, label: "end" }]} bar />
              {stage.actors.map((a) => {
                const tr = bp.tracks.find((x) => x.target === a.id);
                return <Lane key={a.id} label={names[a.id] ?? a.id} duration={bp.duration} t={t} active={sel === a.id} onClick={() => setSel(a.id)}
                  keys={(tr?.keys ?? []).map((k) => ({ t: k.t, label: k.action }))} />;
              })}
              {bp.environment.length > 0 && <Lane label="Background" duration={bp.duration} t={t} keys={bp.environment.map((e) => ({ t: e.t, label: e.text }))} />}
            </div>
          </div>

          <div className="space-y-3 text-sm">
            <Panel title="Shot">
              <Row label="Framing"><select className={field} value={stage.framing} data-testid="director-framing"
                onChange={(e) => editStage(reframe(stage, e.target.value))}>{FRAMINGS.map((f) => <option key={f}>{f}</option>)}</select></Row>
              <Row label="Time"><select className={field} value={stage.time} onChange={(e) => editStage({ ...stage, time: e.target.value, lighting: { ...stage.lighting, preset: e.target.value, key: "" } })}>
                {TIMES.map((x) => <option key={x}>{x}</option>)}</select></Row>
            </Panel>
            <Panel title="Camera">
              <Row label="Move"><select className={field} value={bp.camera.move} data-testid="director-move" onChange={(e) => editBp(withMove(bp, stage, e.target.value))}>
                {MOVES.map((m) => <option key={m} value={m}>{m.replace(/_/g, " ")}</option>)}</select></Row>
              <Row label="Ease"><select className={field} value={bp.camera.ease} onChange={(e) => editBp(withMove(bp, stage, bp.camera.move, e.target.value))}>
                {EASES.map((m) => <option key={m}>{m}</option>)}</select></Row>
              <Slider label="Lens" min={14} max={135} step={1} value={stage.camera.lens} unit="mm" onChange={setLens} testid="director-lens" />
              <Slider label="Left / right" min={-6} max={6} step={0.05} value={stage.camera.position[0]} onChange={(v) => setCam("position", 0, v)} />
              <Slider label="Height" min={0.2} max={6} step={0.05} value={stage.camera.position[1]} onChange={(v) => setCam("position", 1, v)} />
              <Slider label="Distance" min={-3} max={12} step={0.05} value={stage.camera.position[2]} onChange={(v) => setCam("position", 2, v)} testid="director-distance" />
              <Slider label="Look at (x)" min={-6} max={6} step={0.05} value={stage.camera.target[0]} onChange={(v) => setCam("target", 0, v)} />
              <Slider label="Look at (height)" min={0} max={4} step={0.05} value={stage.camera.target[1]} onChange={(v) => setCam("target", 1, v)} />
            </Panel>
            <Panel title="People">
              <div className="flex flex-wrap gap-1">{stage.actors.map((a) => (
                <button key={a.id} onClick={() => setSel(a.id)} className={`rounded-full px-2 py-0.5 text-xs ${sel === a.id ? "bg-amber-500 text-white" : "bg-muted text-muted-foreground"}`}>{names[a.id] ?? a.id}{a.speaking ? " 🗣" : ""}</button>))}</div>
              {selActor && (
                <div className="space-y-2" data-testid="director-actor">
                  <Slider label="Left / right" min={-6} max={6} step={0.05} value={selActor.x} testid="director-actor-x"
                    onChange={(v) => editStage({ ...stage, actors: stage.actors.map((a) => (a.id === selActor.id ? { ...a, x: v } : a)) })} />
                  <Slider label="Depth" min={-4} max={4} step={0.05} value={selActor.z}
                    onChange={(v) => editStage({ ...stage, actors: stage.actors.map((a) => (a.id === selActor.id ? { ...a, z: v } : a)) })} />
                  <Row label="Pose"><input className={field} value={selActor.pose} onChange={(e) => editStage({ ...stage, actors: stage.actors.map((a) => (a.id === selActor.id ? { ...a, pose: e.target.value } : a)) })} /></Row>
                  <Row label="Expression"><input className={field} value={selActor.expression} onChange={(e) => editStage({ ...stage, actors: stage.actors.map((a) => (a.id === selActor.id ? { ...a, expression: e.target.value } : a)) })} /></Row>
                  <Row label="Facing"><select className={field} value={selActor.facing} onChange={(e) => editStage({ ...stage, actors: stage.actors.map((a) => (a.id === selActor.id ? { ...a, facing: e.target.value } : a)) })}>
                    <option value="camera">camera</option>{stage.actors.filter((a) => a.id !== selActor.id).map((a) => <option key={a.id} value={a.id}>{names[a.id] ?? a.id}</option>)}</select></Row>
                  <div className="space-y-1" data-testid="director-keys">
                    <div className="text-xs font-semibold text-muted-foreground">Timed actions</div>
                    {(track?.keys ?? []).map((k, i) => (
                      <div key={i} className="flex items-center gap-1">
                        <input type="number" min={0} max={bp.duration} step={0.1} className="w-16 rounded-lg border border-border bg-background px-1 py-1 text-xs" value={k.t}
                          onChange={(e) => setKeys((track?.keys ?? []).map((x, j) => (j === i ? { ...x, t: Math.max(0, Math.min(bp.duration, Number(e.target.value))) } : x)))} />
                        <input className="min-w-0 flex-1 rounded-lg border border-border bg-background px-2 py-1 text-xs" value={k.action}
                          onChange={(e) => setKeys((track?.keys ?? []).map((x, j) => (j === i ? { ...x, action: e.target.value } : x)))} data-testid="director-key-action" />
                        <button className="text-muted-foreground hover:text-red-500" title="Remove" onClick={() => setKeys((track?.keys ?? []).filter((_, j) => j !== i))}><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    ))}
                    <button className="inline-flex items-center gap-1 text-xs text-amber-600" data-testid="director-add-key"
                      onClick={() => setKeys([...(track?.keys ?? []), { t: Math.round(t * 10) / 10, action: "" }])}><Plus className="h-3 w-3" />Action at {t.toFixed(1)}s</button>
                  </div>
                </div>
              )}
            </Panel>
            <p className="text-xs text-muted-foreground">The stage is a blocking preview (people are cut-outs from their sheets). Save sends this layout, camera and timeline to the prompt compiler and redraws only this shot: a new layout redraws the picture; a new camera move or timing only re-animates it.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return <div className="space-y-2 rounded-xl border border-border bg-card/40 p-3"><b className="text-foreground">{title}</b>{children}</div>;
}
function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="block text-xs text-muted-foreground">{label}<div className="mt-0.5">{children}</div></label>;
}
function Slider({ label, min, max, step, value, onChange, unit = "", testid }: { label: string; min: number; max: number; step: number; value: number; onChange: (v: number) => void; unit?: string; testid?: string }) {
  return (
    <label className="block text-xs text-muted-foreground">
      <span className="flex justify-between"><span>{label}</span><span className="font-mono">{value.toFixed(step < 1 ? 2 : 0)}{unit}</span></span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-amber-500" data-testid={testid} />
    </label>
  );
}
function Lane({ label, duration, t, keys, bar, active, onClick }: { label: string; duration: number; t: number; keys: { t: number; label: string }[]; bar?: boolean; active?: boolean; onClick?: () => void }) {
  return (
    <div className={`flex items-center gap-2 ${onClick ? "cursor-pointer" : ""}`} onClick={onClick}>
      <span className={`w-28 shrink-0 truncate text-xs ${active ? "font-semibold text-amber-600" : "text-muted-foreground"}`} title={label}>{label}</span>
      <div className="relative h-6 flex-1 rounded bg-muted/60">
        {bar && <div className="absolute inset-y-2 left-0 right-0 rounded bg-amber-500/40" />}
        {keys.map((k, i) => <span key={i} title={`${k.t.toFixed(1)}s · ${k.label}`} className="absolute top-1 h-4 w-1.5 -translate-x-1/2 rounded bg-amber-500" style={{ left: `${(100 * k.t) / Math.max(0.01, duration)}%` }} />)}
        <span className="absolute inset-y-0 w-px bg-foreground/70" style={{ left: `${(100 * t) / Math.max(0.01, duration)}%` }} />
      </div>
    </div>
  );
}
