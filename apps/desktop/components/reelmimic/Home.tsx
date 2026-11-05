"use client";
/* eslint-disable @next/next/no-img-element -- previews come from the user's file / YouTube, not Next's image pipeline */
// Animations home: hero, composer, "how it works", project list (ported from ReelMimic's App.tsx Home/Composer),
// with the Claude Code / Codex switch replaced by a crew picker + AI settings for the multi-provider service.
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, agentLabel, findAgent } from "./api";
import { getLang, onLang, say, translate } from "./i18n";
import { I, Seg, AutoText, ago, RoundsEditor, useNow, useOutside } from "./ui";
import type { IconName, RoundValues } from "./ui";
import { Status } from "./Project";
import { AGENTS_KEY, useAgentsInfo, useCrew } from "./Shell";
import { OpenModelsSettings } from "./OpenModels";
import type { AgentInfo, AgentKind, AgentSettingsBody, AgentsInfo, AgentTier, ProjectSummary, Rounds } from "./types";

const SUGGEST = ["做一支類似風格的 30 秒影片，主軸是愛情，要有好笑的反轉", "同樣的剪法，改成介紹我們的新 App", "保留節奏和轉場，主題換成親情，直式 9:16", "把我的小故事畫成 Q 版漫畫，第一人稱旁白"];
const HOW: [IconName, string, string][] = [["scan", "拆解風格", "剪法、節奏、轉場、畫面語言逐鏡量測"], ["wand", "選製作技能", "判斷畫風，交給對應的製作 skill"], ["film", "前製企劃", "分鏡、運鏡、素材、定調畫面，和你來回對焦"], ["check", "關卡審查", "角色、每一段都即時檢查，過關才往下做"]];

export function Home() {
  const info = useAgentsInfo();
  const list = useQuery({
    queryKey: ["studio", "projects"],
    queryFn: () => api.projects().then((l) => [...l].sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""))),
    retry: false,
    refetchInterval: 5_000,
  });
  const now = useNow(true, 30_000);
  const [, rerender] = useState(0);
  useEffect(() => onLang(() => rerender((x) => x + 1)), []);
  const items: ProjectSummary[] = list.data ?? [];
  const done = items.filter((p) => p.stage === "done").length;
  const working = items.filter((p) => !["done", "error", "plan_review", "needs_input"].includes(p.stage)).length;
  const waiting = items.filter((p) => ["plan_review", "needs_input"].includes(p.stage)).length;
  const stats: [IconName, string, number, string][] = [
    ["film", say("全部專案", "Total projects"), items.length, "from-amber-500 to-orange-500"],
    ["spark", say("製作中", "In progress"), working, "from-blue-500 to-cyan-500"],
    ["bubble", say("等你回覆", "Waiting for you"), waiting, "from-purple-500 to-pink-500"],
    ["check", say("已完成", "Completed"), done, "from-emerald-500 to-green-600"],
  ];
  return (
    <main className="mx-auto max-w-7xl space-y-8 p-4 md:p-8" data-testid="animations-home">
      <div>
        <h1 className="mb-2 text-2xl font-bold text-foreground md:text-3xl">{say("動畫", "Animations")}</h1>
        <p className="text-muted-foreground">{say("丟一支喜歡的影片，做出同樣風格的新動畫：拆解風格、企劃、你核准後才製作，每一段都檢查過才交件。",
          "Give it a video you love and get a new animation in the same style: it studies the style, plans with you, renders only after you approve, and checks every part before delivering.")}</p>
      </div>

      <Link href="/animations/films" className="flex flex-wrap items-center gap-4 rounded-xl border border-amber-500/50 bg-accent p-4 transition hover:border-amber-500 md:p-5" data-testid="films-link">
        <span className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-primary hover:bg-[#8873be] text-white"><I n="film" s={2} /></span>
        <span className="min-w-0 flex-1">
          <b className="block text-foreground">{say("短片：提示詞 → 動畫（推薦）", "Films: prompt → animation (recommended)")}</b>
          <span className="text-sm text-muted-foreground">{say("貼上提示詞（可含時間碼或 JSON）：拆解、鎖定角色與世界、分鏡你核准後才逐格動畫，再配音效與音樂，最後輸出所有專案檔。",
            "Paste a prompt (with time codes, or JSON): breakdown → characters and world locked → a storyboard you approve → each frame animated → sound and music → the film and every project file.")}</span>
        </span>
        <span className="text-sm font-medium text-amber-600">{say("開啟", "Open")} →</span>
      </Link>

      <Link href="/animations/series" className="flex flex-wrap items-center gap-4 rounded-xl border border-amber-500/40 bg-accent p-4 transition hover:border-amber-500 md:p-5" data-testid="series-link">
        <span className="flex h-10 w-10 flex-none items-center justify-center rounded-xl bg-primary hover:bg-[#8873be] text-white"><I n="layers" s={2} /></span>
        <span className="min-w-0 flex-1">
          <b className="block text-foreground">{say("系列動畫", "Series")}</b>
          <span className="text-sm text-muted-foreground">{say("你核准每個角色（外型和聲音），劇集分段製作：先 1 分鐘，再每段 3 分鐘，每段你看過核准才繼續。",
            "Characters you approve one by one (look and voice), episodes written and rendered in parts (1 min, then 3 min…), each part approved before the next.")}</span>
        </span>
        <span className="text-sm font-medium text-amber-600">{say("開啟", "Open")} →</span>
      </Link>

      <section className="grid grid-cols-2 gap-4 md:gap-6 lg:grid-cols-4">
        {stats.map(([ico, label, value, color]) => (
          <div key={ico} className="rounded-xl border border-border bg-card/50 p-4 md:p-6">
            <div className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-accent text-[var(--signal)] md:h-12 md:w-12`}><I n={ico} s={2} style={{ fontSize: 20 }} /></div>
            <p className="mb-1 text-2xl font-bold text-foreground md:text-3xl">{list.isLoading ? "–" : value}</p>
            <p className="text-xs text-muted-foreground md:text-sm">{label}</p>
          </div>
        ))}
      </section>

      <section>
        <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold text-foreground md:text-xl">
          <I n="wand" className="text-amber-400" />{say("新動畫", "New animation")}
        </h2>
        <Composer info={info.data} />
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {HOW.map(([ico, t, d], i) => (
            <div key={t} className="flex gap-3 rounded-xl border border-border bg-card/30 p-3">
              <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-amber-500/10 text-amber-500"><I n={ico} /></span>
              <span className="min-w-0"><b className="block text-sm font-semibold text-foreground">{i + 1}. {t}</b><span className="text-xs text-muted-foreground">{d}</span></span>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold text-foreground md:text-xl">
          <I n="layers" className="text-amber-400" />{say("你的專案", "Your Projects")}
          {items.length > 0 && <span className="text-sm font-normal text-muted-foreground">{items.length}</span>}
        </h2>
        {items.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed border-border p-12 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-500/10 text-amber-500"><I n="film" style={{ fontSize: 30 }} /></div>
            <h3 className="text-xl font-bold text-foreground">{say("還沒有專案", "No animations yet")}</h3>
            <p className="text-muted-foreground">{say("在上面放一支參考影片並寫下你想做什麼。", "Add a reference video above and describe what you want.")}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">{items.map((p) => (
            <Link key={p.id} data-testid="animation-card" data-stage={p.stage} href={`/animations/${p.id}`}
              className="group flex flex-col overflow-hidden rounded-xl border border-border bg-card/50 transition-all duration-300 hover:border-amber-500/30 hover:shadow-xl hover:shadow-amber-500/10"
              onMouseEnter={(e) => { const v = e.currentTarget.querySelector("video"); if (v) { v.currentTime = 3; v.play().catch(() => {}); } }}
              onMouseLeave={(e) => e.currentTarget.querySelector("video")?.pause()}>
              <div className="relative aspect-video bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950 bg-cover bg-center" style={{ backgroundImage: p.thumb ? `url("${api.file(p.id, p.thumb)}")` : undefined }}>
                {!p.thumb && <span className="absolute inset-0 flex items-center justify-center text-slate-500"><I n="film" style={{ fontSize: 32 }} /></span>}
                {p.stage === "done" && <video className="absolute inset-0 h-full w-full object-cover" muted loop playsInline preload="none" src={api.file(p.id, "out/video.mp4")} onError={(e) => e.currentTarget.remove()} />}
                <span className="absolute right-3 top-3"><Status stage={p.stage} /></span>
              </div>
              <div className="flex flex-1 flex-col gap-1 p-4">
                <b className="truncate text-base font-semibold text-foreground transition-colors group-hover:text-amber-500">{p.title}</b>
                <span className="text-xs text-muted-foreground">{agentLabel(p.agent, info.data)} · {ago(p.updatedAt, now)}{p.needs ? ` · ${say(`${p.needs} 項待你提供`, `${p.needs} input(s) needed`)}` : ""}</span>
              </div>
            </Link>))}</div>
        )}
      </section>
    </main>
  );
}

const ytId = (u: string) => (u.match(/(?:v=|youtu\.be\/|shorts\/|embed\/)([\w-]{11})/) || [])[1];
function Composer({ info }: { info?: AgentsInfo }) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null), [url, setUrl] = useState(""), [linkMode, setLinkMode] = useState(false);
  const [brief, setBrief] = useState(""), [inputs, setInputs] = useState<File[]>([]);
  const [agent, setAgent] = useCrew(info);
  const [drag, setDrag] = useState(false), [busy, setBusy] = useState(false), [err, setErr] = useState("");
  const [rounds, setRounds] = useState<RoundValues>({}), [roundsOpen, setRoundsOpen] = useState(false);
  const [settings, setSettings] = useState(false), [needRef, setNeedRef] = useState(false);
  const config = useQuery({ queryKey: ["studio", "config"], queryFn: api.config, retry: false, staleTime: Infinity });
  const defaults: Rounds | null = config.data ? { castRounds: config.data.castRounds, chunkRounds: config.data.chunkRounds, finalRounds: config.data.finalRounds } : null;
  const customRounds = Object.entries(rounds).filter(([, v]) => v != null);
  const pick = useRef<HTMLInputElement>(null), assets = useRef<HTMLInputElement>(null);
  const preview = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  const validUrl = /^https?:\/\//.test(url.trim());
  const ok = (file || validUrl) && brief.trim() && !busy;
  const setVideo = (f: File | null | undefined) => { if (f && f.type.startsWith("video/")) { setFile(f); setUrl(""); setLinkMode(false); setErr(""); setNeedRef(false); } else if (f) setErr("請選擇影片檔（mp4 / mov / webm）"); };
  const submit = async () => {
    if (!ok) return; setBusy(true); setErr("");
    const f = new FormData();
    if (file) f.append("reference", file); else f.append("url", url.trim());
    f.append("brief", brief); if (agent) f.append("agent", agent); f.append("lang", getLang());
    inputs.forEach((x) => f.append("inputs", x));
    customRounds.forEach(([k, v]) => f.append(k, String(v)));
    try { const { id } = await api.create(f); router.push(`/animations/${id}`); } catch (e) { setErr((e as Error).message); setBusy(false); }
  };
  const yt = ytId(url);
  return (
    <>
      <div className={`composer fade-in ${drag ? "drag" : ""}`} style={{ animationDelay: "80ms" }} data-testid="composer"
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDrag(false); }}
        onDrop={(e) => { e.preventDefault(); setDrag(false); setVideo(e.dataTransfer.files[0]); }}>
        {file ? (
          <div className="ref-slot">
            <div className="ref-thumb"><video src={`${preview}#t=0.5`} muted preload="metadata" /></div>
            <div className="ref-meta"><span className="eyebrow">參考影片</span><b data-no-i18n>{file.name}</b><span className="small faint">{(file.size / 1e6).toFixed(1)} MB</span></div>
          </div>
        ) : linkMode ? (
          <>
            <div className="link-in"><I n="link" /><input autoFocus placeholder="貼上 YouTube 或影片連結" value={url} onChange={(e) => setUrl(e.target.value)} /><button type="button" className="icon-btn" style={{ width: 28, height: 28, fontSize: 14 }} onClick={() => { setLinkMode(false); setUrl(""); }} aria-label="取消"><I n="x" /></button></div>
            {validUrl && <div className="ref-slot fade-in"><div className="ref-thumb">{yt ? <img src={`https://i.ytimg.com/vi/${yt}/hqdefault.jpg`} alt="" /> : <I n="globe" />}</div><div className="ref-meta"><span className="eyebrow">參考影片連結</span><b data-no-i18n>{yt ? `YouTube · ${yt}` : url}</b><span className="small faint">建立專案時自動下載</span></div></div>}
          </>
        ) : (
          <div className="ref-empty" onClick={() => pick.current!.click()}>
            <div className="big-ico"><I n="film" /></div>
            <div className="grow"><b>拖入參考影片，或點擊選擇</b><span className="small">mp4 / mov / webm，手機螢幕錄影也可以（會自動裁掉介面）</span></div>
            <button type="button" className="btn sm" onClick={(e) => { e.stopPropagation(); setLinkMode(true); }}><I n="link" />貼連結</button>
          </div>
        )}
        <input ref={pick} type="file" accept="video/*" hidden data-testid="reference-file" onChange={(e) => setVideo(e.target.files![0])} />
        <AutoText minRows={3} placeholder="你想做什麼樣的影片？主題、長度、角色、想保留參考片的哪些地方…" value={brief} onChange={(e) => setBrief(e.target.value)} data-testid="brief"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(); }} />
        <div className="comp-bar">
          {file && <button type="button" className="tool-chip" onClick={() => pick.current!.click()}><I n="retry" />換影片</button>}
          {file && <button type="button" className="tool-chip" onClick={() => setFile(null)}><I n="x" />移除</button>}
          <button type="button" className={`tool-chip ${inputs.length ? "on" : ""}`} onClick={() => assets.current!.click()} title="配樂、歌詞、圖片、Logo、自家角色設計圖">
            <I n="clip" /><span className="chip-l">素材</span>{inputs.length > 0 && <span className="n">{inputs.length}</span>}</button>
          <input ref={assets} type="file" multiple hidden onChange={(e) => setInputs([...e.target.files!])} />
          {defaults && <button type="button" className={`tool-chip ${customRounds.length ? "on" : ""}`} onClick={() => setRoundsOpen(!roundsOpen)} aria-expanded={roundsOpen} title="每一關最多審查、修改幾輪">
            <I n="sliders" /><span className="chip-l">審查輪數</span>{customRounds.length > 0 && <span className="n">{customRounds.length}</span>}</button>}
          <span className="grow" />
          <CrewPicker info={info} value={agent} onChange={setAgent} onSettings={() => setSettings(true)} />
          <button type="button" className="icon-btn" onClick={() => setSettings(true)} aria-label="AI 設定" title="AI 設定" data-testid="ai-settings-btn"><I n="gear" /></button>
          <button type="button" className="send" disabled={busy || !brief.trim()} onClick={() => (file || validUrl ? submit() : (setErr(""), setNeedRef(true), pick.current!.click()))} aria-label="開始" data-testid="create-animation">{busy ? <span className="spin-ring" /> : <I n="spark" s={2.2} />}<span>開始製作</span></button>
        </div>
        {inputs.length > 0 && <div className="small faint" style={{ padding: "8px 10px 2px" }}><span>素材</span>：<span data-no-i18n>{inputs.map((f) => f.name).join("、")}</span></div>}
        {roundsOpen && defaults && <div className="comp-rounds fade-in"><RoundsEditor value={rounds} defaults={defaults} onChange={setRounds} /></div>}
      </div>
      {err ? <div className="small" style={{ color: "var(--red)", textAlign: "center", marginTop: 12 }}>{err}</div>
        : !(file || validUrl) && brief.trim() && needRef ? <div className="small" style={{ color: "var(--orange)", textAlign: "center", marginTop: 12 }} data-testid="need-reference">請選一支參考影片（或按「貼連結」），選好後再按「開始製作」。</div>
        : <div className="small faint" style={{ textAlign: "center", marginTop: 12 }}>先拆解與企劃，你核准前不會開始生成 · Ctrl+Enter 送出</div>}
      <div className="suggest">{SUGGEST.map((x) => <button type="button" key={x} onClick={() => setBrief(translate(x))}>{x}</button>)}</div>
      {settings && info && <AISettings info={info} onClose={() => setSettings(false)} />}
    </>
  );
}

// ---------- crew picker ----------
const TIERS: [AgentTier, string, IconName][] = [["local", "本機（免費，在你的電腦上執行）", "cpu"], ["free", "免費雲端", "cloud"], ["paid", "付費", "key"], ["custom", "你在設定頁加入的模型", "layers"]];
function CrewPicker({ info, value, onChange, onSettings }: { info?: AgentsInfo; value: AgentKind | null; onChange: (v: AgentKind) => void; onSettings: () => void }) {
  const [open, setOpen] = useState(false), ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useOutside(ref, open, close);
  const a = findAgent(info, value);
  const anyReady = !!info?.agents.some((x) => x.ready);
  return (
    <div className="crew" ref={ref}>
      <button type="button" className="tool-chip crew-btn" onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open} title="選擇 AI 團隊" data-testid="crew-picker">
        <i className={`dot ${!info ? "" : a?.ready ? "on" : "bad"}`} /><span className="crew-name">{a ? a.label : info ? agentLabel(value ?? undefined, info) : "AI 團隊"}</span><I n="down" s={2.2} />
      </button>
      {open && info && <div className="crew-pop" role="listbox" data-testid="crew-menu">
        {!anyReady && <div className="crew-empty small"><I n="alert" s={2.2} />還沒有可用的 AI 團隊</div>}
        {TIERS.map(([tier, title, ico]) => {
          const list = info.agents.filter((x) => x.tier === tier);
          if (!list.length) return null;
          return (
            <div key={tier} className="crew-group">
              <div className="crew-gh"><I n={ico} /><span>{title}</span></div>
              {list.map((x) => (
                <button type="button" key={x.id} role="option" aria-selected={x.id === value} disabled={!x.ready} data-agent={x.id}
                  className={`crew-opt ${x.id === value ? "on" : ""}`} title={x.ready ? x.detail : "請先在 AI 設定裡讓這個團隊就緒"}
                  onClick={() => { onChange(x.id); setOpen(false); }}>
                  <i className={`dot ${x.ready ? "on" : "bad"}`} />
                  <span className="grow">
                    <span className="crew-l"><b>{x.label}</b>{x.id === info.default && <span className="cap mini">預設</span>}</span>
                    <span className="tiny faint crew-d">{x.detail}</span>
                    {!x.ready && x.fix && <span className="tiny crew-fix">{x.fix}</span>}
                  </span>
                  {x.id === value && <I n="check" s={2.4} />}
                </button>))}
            </div>
          );
        })}
        <button type="button" className="crew-foot" onClick={() => { setOpen(false); onSettings(); }}><I n="gear" />AI 設定</button>
      </div>}
    </div>
  );
}

// ---------- AI settings ----------
export function AISettings({ info, onClose }: { info: AgentsInfo; onClose: () => void }) {
  const qc = useQueryClient();
  const [err, setErr] = useState("");
  const save = useCallback(async (body: AgentSettingsBody) => {
    setErr("");
    try { const r = await api.agentSettings(body); qc.setQueryData(AGENTS_KEY, r); }
    catch (e) { setErr((e as Error).message); throw e; }
  }, [qc]);
  useEffect(() => { const k = (e: KeyboardEvent) => e.key === "Escape" && onClose(); addEventListener("keydown", k); return () => removeEventListener("keydown", k); }, [onClose]);
  const R = info.render;
  return (
    <div className="sheet-bg" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="sheet" role="dialog" aria-modal="true" aria-label="AI 設定" data-testid="ai-settings">
        <div className="sheet-h"><div className="grow"><h2>AI 設定</h2><div className="small muted">設定會套用到之後的新專案。</div></div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="關閉"><I n="x" /></button></div>
        <div className="sheet-body">
          <div className="sub-h">成片設定</div>
          <div className="list">
            <div className="li"><div className="li-ico accent"><I n="film" /></div><div className="grow t">畫質</div>
              <Seg value={R.quality} onChange={(q) => save({ render: { quality: q } }).catch(() => {})} options={[{ value: "720p", label: "720p" }, { value: "1080p", label: "1080p" }]} /></div>
            <div className="li pics"><div className="li-ico accent"><I n="image" /></div>
              <div className="grow"><div className="t">畫面來源</div>
                <div className="pick">
                  <button type="button" className={R.images === "drawn" ? "on" : ""} aria-pressed={R.images === "drawn"} onClick={() => save({ render: { images: "drawn" } }).catch(() => {})}><I n="pencil" />引擎繪製（離線）</button>
                  <button type="button" className={R.images === "ai" ? "on" : ""} aria-pressed={R.images === "ai"} disabled={!R.imagesReady && R.images !== "ai"} onClick={() => save({ render: { images: "ai" } }).catch(() => {})}><I n="spark" />AI 生成圖片</button>
                </div>
                {R.imagesDetail && <div className="d">{R.imagesDetail}</div>}
              </div></div>
          </div>
          <OpenModelsSettings info={info} save={save} />
          {TIERS.map(([tier, title, ico]) => {
            const list = info.agents.filter((x) => x.tier === tier);
            if (!list.length) return null;
            return (
              <div key={tier}>
                <div className="sub-h row" style={{ gap: 6 }}><I n={ico} /><span>{title}</span></div>
                <div className="list">{list.map((a) => <ProviderRow key={a.id} a={a} info={info} save={save} />)}</div>
              </div>
            );
          })}
          {err && <div className="small" style={{ color: "var(--red)", marginTop: 10 }}>{err}</div>}
          <div className="tiny faint" style={{ margin: "14px 4px 0" }}><Link href="/settings" style={{ textDecoration: "underline" }}>金鑰、GPU 和你的模型都在設定頁</Link></div>
        </div>
      </div>
    </div>
  );
}

function ProviderRow({ a, info, save }: { a: AgentInfo; info: AgentsInfo; save: (b: AgentSettingsBody) => Promise<void> }) {
  const qc = useQueryClient();
  const isDefault = info.default === a.id, ollama = a.id === "ollama";
  const [open, setOpen] = useState(isDefault);
  const [model, setModel] = useState(a.model || ""), [key, setKey] = useState(""), [url, setUrl] = useState(a.url || "");
  const [vis, setVis] = useState(a.visionModel || "");
  const [busy, setBusy] = useState(""), [msg, setMsg] = useState("");
  const run = (k: string, fn: () => Promise<unknown>) => async () => {
    setBusy(k); setMsg("");
    try { await fn(); if (k === "save") setMsg("已儲存"); } catch (e) { setMsg((e as Error).message); }
    setBusy("");
  };
  const models = a.models || [];
  const pulls = ollama ? Object.entries(info.pulls || {}) : [];
  const dirty = model !== (a.model || "") || !!key || (ollama && (url !== (a.url || "") || vis !== (a.visionModel || "")));
  const listId = `rm-models-${a.id}`;
  return (
    <div className={`prov ${open ? "open" : ""}`} data-provider={a.id}>
      <button type="button" className="li click prov-h" onClick={() => setOpen(!open)} aria-expanded={open}>
        <i className={`dot ${a.ready ? "on" : "bad"}`} />
        <span className="grow" style={{ textAlign: "left" }}>
          <span className="crew-l"><b>{a.label}</b>{isDefault && <span className="cap mini">預設</span>}{a.vision && <span className="cap mini" title="看得懂圖片"><I n="eye" /></span>}</span>
          <span className="d prov-d">{a.detail}</span>
        </span>
        <I n="chev" className={`chev ${open ? "open" : ""}`} />
      </button>
      {open && <div className="prov-body">
        {!a.ready && a.fix && <div className="small crew-fix" style={{ marginBottom: 10 }}><b>怎麼修好</b>：{a.fix}</div>}
        <label className="fld"><span>模型</span>
          {ollama && models.length > 0 ? (
            <div className="fld-pair">
              <select value={models.includes(model) ? model : ""} onChange={(e) => setModel(e.target.value)} aria-label="已下載的模型">
                {models.map((m) => <option key={m} value={m}>{m}</option>)}
                <option value="">自訂模型名稱</option>
              </select>
              <input value={model} onChange={(e) => setModel(e.target.value)} placeholder={ollama ? "輸入要下載的模型名稱" : "自訂模型名稱"} spellCheck={false} />
            </div>
          ) : (
            <>
              <input value={model} onChange={(e) => setModel(e.target.value)} list={models.length ? listId : undefined} placeholder={ollama ? "輸入要下載的模型名稱" : "自訂模型名稱"} spellCheck={false} />
              {models.length > 0 && <datalist id={listId}>{models.map((m) => <option key={m} value={m} />)}</datalist>}
            </>
          )}
        </label>
        {a.needsKey && <label className="fld"><span>API 金鑰</span>
          <div className="fld-pair">
            <input type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="貼上 API 金鑰" autoComplete="off" spellCheck={false} />
            {a.hasKey && <span className="cap ok"><I n="check" s={2.4} />已儲存</span>}
            {a.hasKey && <button type="button" className="btn sm plain" disabled={!!busy} onClick={run("clear", () => save({ agent: a.id, key: "" }))}>清除</button>}
          </div></label>}
        {ollama && <label className="fld"><span>看圖模型（審查影格用）</span>
          <input value={vis} onChange={(e) => setVis(e.target.value)} list={models.length ? `${listId}-vis` : undefined} placeholder="例如 qwen2.5vl:7b（可留空）" spellCheck={false} data-testid="vision-model" />
          {models.length > 0 && <datalist id={`${listId}-vis`}>{models.map((m) => <option key={m} value={m} />)}</datalist>}
          <span className="tiny faint">審查員用它看角色設定圖和鏡頭影格。留空就只用量測檢查。</span></label>}
        {ollama && <label className="fld"><span>Ollama 位址</span><input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="http://127.0.0.1:11434" spellCheck={false} /></label>}
        <div className="row" style={{ marginTop: 12 }}>
          <button type="button" className="btn sm primary" disabled={!!busy || !dirty} onClick={run("save", async () => {
            await save({ agent: a.id, ...(model !== (a.model || "") && { model }), ...(key && { key }), ...(ollama && url !== (a.url || "") && { url }), ...(ollama && vis !== (a.visionModel || "") && { visionModel: vis }) });
            setKey("");
          })}>{busy === "save" ? <span className="spin-ring" /> : <I n="check" s={2.4} />}儲存</button>
          <button type="button" className="btn sm" disabled={!!busy || isDefault} onClick={run("def", () => save({ default: a.id }))}>{isDefault ? "已是預設" : "設為預設"}</button>
          {ollama && <button type="button" className="btn sm" disabled={!!busy || !model.trim() || !!(info.pulls?.[model] && !info.pulls[model].done)} data-testid="pull-model"
            onClick={run("pull", async () => { await api.pull(model.trim()); await qc.invalidateQueries({ queryKey: AGENTS_KEY }); })}><I n="download" />下載模型</button>}
          {msg && <span className="small muted">{msg}</span>}
        </div>
        {pulls.length > 0 && <div className="pulls">{pulls.map(([m, p]) => (
          <div key={m} className="pull" data-testid="pull-progress">
            <div className="row" style={{ gap: 8 }}><b className="small" data-no-i18n>{m}</b><span className="grow" />
              <span className={`small ${p.error ? "" : "faint"}`} style={p.error ? { color: "var(--red)" } : undefined}>{p.error ? "下載失敗" : p.done ? "下載完成" : p.pct != null ? `下載中 ${Math.round(p.pct)}%` : "下載中"}</span></div>
            <div className="pull-bar"><i style={{ width: `${p.done ? 100 : Math.max(2, Math.round(p.pct || 0))}%` }} className={p.error ? "bad" : p.done ? "ok" : ""} /></div>
            <div className="tiny faint" data-no-i18n>{p.error || p.status}</div>
          </div>))}</div>}
      </div>}
    </div>
  );
}
