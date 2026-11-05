"use client";
// Open AI models in the Animations tab (shared AVOS catalog, see the Models page):
//   - AI settings: which model draws the AI backdrops, the fal.ai key and your GPU server's ComfyUI address
//   - Project result: "AI finish" runs the finished film through Wan VACE / Wan 2.2 Animate / SCAIL-2 / LTX-2.3
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "./api";
import { say } from "./i18n";
import { useAgentsInfo } from "./Shell";
import { I } from "./ui";
import type { AgentSettingsBody, AgentsInfo, FinishModel, FinishStatus, ImageModel, OpenModel, SnapshotView } from "./types";

const BACKEND: Record<string, [string, string]> = {
  gpu: ["你的 GPU 工作機", "your GPU workers"],
  comfyui: ["你的 GPU 伺服器", "your GPU server"],
  fal: ["fal.ai（付費）", "fal.ai (paid)"],
  cloudflare: ["Cloudflare 免費額度", "Cloudflare free tier"],
};
const where = (b?: string | null) => (b && BACKEND[b] ? say(...BACKEND[b]) : b || "");

function Ready({ m }: { m: OpenModel }) {
  return m.ready
    ? <span className="cap ok"><I n="check" s={2.4} />{where(m.backend)}</span>
    : <span className="cap" title={m.why || ""}>{say("未設定", "not set up")}</span>;
}

const IMAGE_LABEL: Record<string, [string, string]> = {
  free: ["免費串接（Cloudflare → Pollinations）", "Free chain (Cloudflare → Pollinations)"],
  best: ["自動挑最佳（Z-Image；要字就用 Qwen-Image）", "Best per picture (Z-Image; Qwen-Image for text)"],
  "z-image": ["Z-Image Turbo", "Z-Image Turbo"],
  "qwen-image": ["Qwen-Image（畫面裡有文字）", "Qwen-Image (text in the picture)"],
  "flux-schnell": ["FLUX.1 schnell（快速草稿）", "FLUX.1 schnell (fast drafts)"],
};

/** AI settings → open models: backdrop image model, fal.ai key, GPU server, what's ready. */
export function OpenModelsSettings({ info, save }: { info: AgentsInfo; save: (b: AgentSettingsBody) => Promise<void> }) {
  const M = info.models;
  const [key, setKey] = useState(""), [typed, setUrl] = useState<string | null>(null);
  const [busy, setBusy] = useState(false), [msg, setMsg] = useState("");
  if (!M) return null;
  const url = typed ?? M.comfyui ?? "";
  const run = async (body: AgentSettingsBody) => {
    setBusy(true); setMsg("");
    try { await save(body); setMsg(say("已儲存", "Saved")); setKey(""); setUrl(null); } catch (e) { setMsg((e as Error).message); }
    setBusy(false);
  };
  const choice = info.render.imageModel || "free";
  return (
    <div data-testid="open-models">
      <div className="sub-h row" style={{ gap: 6 }}><I n="layers" /><span>{say("開源 AI 模型", "Open AI models")}</span><span className="grow" />
        <Link href="/models" className="small" style={{ textDecoration: "underline" }}>{say("模型總覽", "All models")}</Link>
        <Link href="/settings" className="small" style={{ textDecoration: "underline" }} data-testid="open-settings">{say("設定頁", "Settings")}</Link></div>
      <div className="list">
        <div className="li"><div className="li-ico accent"><I n="image" /></div>
          <div className="grow"><div className="t">{say("AI 背景用的模型", "Model for AI backdrops")}</div>
            <div className="d">{say("畫面來源選「AI 生成圖片」時使用；失敗會改用免費串接。", "Used when Pictures is set to AI images; falls back to the free chain if it fails.")}</div>
          <select className="om-pick" value={choice} disabled={busy} data-testid="image-model" aria-label={say("AI 背景用的模型", "Model for AI backdrops")}
            onChange={(e) => run({ render: { imageModel: e.target.value as ImageModel } })}>
            {(Object.keys(IMAGE_LABEL) as ImageModel[]).map((k) => {
              const m = M.images.find((x) => x.id === k);
              return <option key={k} value={k}>{say(...IMAGE_LABEL[k])}{m && !m.ready ? say("（未設定）", " (not set up)") : ""}</option>;
            })}
            {M.images.filter((m) => m.custom).map((m) => (
              <option key={m.id} value={m.id}>{m.name}{say("（你加的）", " (yours)")}{!m.ready ? say("（未設定）", " (not set up)") : ""}</option>))}
          </select></div></div>
        {M.images.map((m) => <div key={m.id} className="li" data-model={m.id}><span className="grow"><b className="small">{m.name}</b>
          <span className="tiny faint" style={{ display: "block" }}>{m.ready ? m.bestFor : m.why}</span></span><Ready m={m} /></div>)}
      </div>
      <div className="list om-fields" style={{ marginTop: 10 }}>
        <label className="fld"><span>{say("fal.ai 金鑰（付費，用量計費）", "fal.ai key (paid, per use)")}</span>
          <div className="fld-pair">
            <input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder={say("貼上 fal.ai 金鑰", "Paste your fal.ai key")} autoComplete="off" spellCheck={false} data-testid="fal-key" />
            {M.fal && <span className="cap ok"><I n="check" s={2.4} />{say("已儲存", "saved")}</span>}
            <button type="button" className="btn sm primary" disabled={busy || !key.trim()} onClick={() => run({ models: { falKey: key.trim() } })}>{say("儲存", "Save")}</button>
            {M.fal && <button type="button" className="btn sm plain" disabled={busy} onClick={() => run({ models: { falKey: "" } })}>{say("清除", "Clear")}</button>}
          </div></label>
        <label className="fld"><span>{say("你的 GPU 伺服器（ComfyUI 位址）", "Your GPU server (ComfyUI address)")}</span>
          <div className="fld-pair">
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://203.0.113.5:8188" spellCheck={false} data-testid="comfyui-url" />
            <button type="button" className="btn sm primary" disabled={busy || url === (M.comfyui || "")} onClick={() => run({ models: { comfyuiUrl: url.trim() } })}>{say("儲存", "Save")}</button>
          </div>
          <span className="tiny faint">{say("在 RunPod / Vast.ai 租 GPU 跑 ComfyUI，再把每個模型的工作流程匯出到 apps/comfyui_workflows/<模型>.json。免費、優先使用。",
            "Rent a GPU on RunPod / Vast.ai, run ComfyUI there, and export each model's workflow to apps/comfyui_workflows/<model id>.json. Free per call, used first.")}</span>
          <span className="tiny faint">{say("也可以加入 GPU 工作機（GPU 頁面）：會自動選擇 GPU 和精度，並在鏡頭之間保持模型載入。", "Or add GPU workers on the GPU page: AVOS picks the GPU and precision and keeps models loaded between shots.")}{" "}
            <a href="/gpu" className="link">{say("GPU 頁面", "GPU page")}</a></span></label>
        {msg && <div className="small muted" style={{ marginTop: 6 }}>{msg}</div>}
      </div>
    </div>
  );
}

const FINISH_HINT: Record<string, [string, string]> = {
  "wan-vace": ["保留動作和構圖，用 AI 重新上色、補細節（深度控制）。", "Keeps the motion and framing; the AI re-renders the look (depth control)."],
  "wan-2.2-animate": ["每一鏡的第一格照著引擎的動作演一次。", "Each shot's first frame performs the engine's motion."],
  "scail-2": ["同上，用 SCAIL-2（只在你的 GPU 伺服器上）。", "The same with SCAIL-2 (your GPU server only)."],
  "ltx-2.3": ["從每一鏡的第一格重新生成動作。", "Re-animates each shot from its first frame."],
};

/** Result card: run the finished film through an open video model, then compare. */
export function AIFinish({ s, file }: { s: SnapshotView; file: (p: string) => string }) {
  const { data: info } = useAgentsInfo();
  const list = info?.models?.finish || [];
  const [picked, setModel] = useState<FinishModel | "">("");
  const model: FinishModel | "" = picked || ((list.find((m) => m.ready) || list[0])?.id as FinishModel | undefined) || "";
  const [busy, setBusy] = useState(false), [err, setErr] = useState("");
  // progress fetched here wins until the page's own snapshot brings a newer status
  const [local, setLocal] = useState<{ base: FinishStatus | null | undefined; st: FinishStatus | null } | null>(null);
  const st = local && local.base === s.finish ? local.st : s.finish ?? null;
  const setSt = (next: FinishStatus | null) => setLocal({ base: s.finish, st: next });
  const running = st?.state === "running";
  const id = s.job.id;
  const base = s.finish;
  useEffect(() => {   // the film's job is done, so no live events: follow the finish's progress here
    if (!running) return;
    const t = setInterval(() => { api.project(id).then((d) => setLocal({ base, st: d.finish ?? null })).catch(() => {}); }, 2000);
    return () => clearInterval(t);
  }, [running, id, base]);
  if (!s.video) return null;
  const chosen = list.find((m) => m.id === model);
  const start = async () => {
    if (!model) return;
    setBusy(true); setErr("");
    try { setSt((await api.finish(id, model)).finish); }
    catch (e) { setErr((e as Error).message); }
    setBusy(false);
  };
  const failed = st ? Object.entries(st.shots).filter(([, v]) => !v.ok) : [];
  return (
    <div className="critique" data-testid="ai-finish">
      <div className="row"><div className="avatar-ai finish"><I n="spark" /></div><b>{say("AI 精修", "AI finish")}</b>
        <span className="small faint" style={{ marginLeft: 8 }}>{say("用開源影片模型把整部片再跑一次，時間和聲音不變。", "Runs the whole film through an open video model; timing and sound stay the same.")}</span></div>
      <div className="row" style={{ marginTop: 10, gap: 8, flexWrap: "wrap" }}>
        <select value={model} onChange={(e) => setModel(e.target.value as FinishModel)} disabled={running || busy} data-testid="finish-model" aria-label={say("模型", "Model")}>
          {list.map((m) => <option key={m.id} value={m.id}>{m.name}{m.ready ? ` · ${where(m.backend)}` : say("（未設定）", " (not set up)")}</option>)}
        </select>
        <button type="button" className="btn sm primary" disabled={running || busy || !chosen?.ready} onClick={start} data-testid="finish-start">
          {busy || running ? <span className="spin-ring" /> : <I n="wand" />}{running ? say(`精修中 ${st!.done}/${st!.total}`, `Finishing ${st!.done}/${st!.total}`) : say("開始 AI 精修", "Start AI finish")}</button>
        {chosen?.license && <span className={`cap mini ${chosen.commercial === "yes" ? "" : "bad"}`} title={chosen.commercial === "yes" ? "" : say("商用有條件", "Conditions for commercial use")}>{chosen.license}</span>}
        {chosen?.price && chosen.backend === "fal" && <span className="tiny faint">{chosen.price}</span>}
      </div>
      {model && <div className="tiny faint" style={{ marginTop: 6 }}>{FINISH_HINT[model] ? say(...FINISH_HINT[model]) : say("你在設定頁加入的影片模型：每一鏡送出第一格和原本的片段。", "Your video model from Settings: each shot is sent with its first frame and the engine's clip.")}</div>}
      {chosen && !chosen.ready && <div className="small crew-fix" style={{ marginTop: 6 }}>{chosen.why}</div>}
      {err && <div className="small" style={{ color: "var(--red)", marginTop: 6 }}>{err}</div>}
      {st?.state === "error" && <div className="small" style={{ color: "var(--red)", marginTop: 6 }} data-testid="finish-error">{st.error}</div>}
      {failed.length > 0 && st?.state !== "running" && <div className="tiny faint" style={{ marginTop: 6 }}>
        {say(`${failed.length} 鏡沒有成功，保留引擎版本：`, `${failed.length} shot(s) kept the engine version: `)}{failed.map(([sid, v]) => `${sid} (${v.error})`).join("; ")}</div>}
      {st?.state === "done" && st.video && <div style={{ marginTop: 12 }}>
        <div className="row"><div className="sub-h" style={{ margin: 0 }}>{say(`AI 精修版 · ${st.name}`, `AI finish · ${st.name}`)}</div><span className="grow" />
          <a className="btn sm" href={file(st.video)} download><I n="download" />{say("下載 MP4", "Download MP4")}</a></div>
        <div className="player" style={{ marginTop: 8 }}><video data-testid="finish-video" src={`${file(st.video)}${file(st.video).includes("?") ? "&" : "?"}f=${st.done}-${st.model}`} preload="metadata" controls playsInline /></div>
      </div>}
    </div>
  );
}
