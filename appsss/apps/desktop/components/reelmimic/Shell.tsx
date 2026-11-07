"use client";
// Frame of the Animations tab inside AVOS: the scoped ".rm" roots (translated by i18n.ts), the header that sits in
// AppShell's header slot (brand, crew capsule, language menu), the engine-offline card and the shared crew state.
import Link from "next/link";
import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, agentLabel, engineStatus, findAgent } from "./api";
import { attachI18n, getLang, LANGS, setLang } from "./i18n";
import { BrandMark, I, store, useOutside } from "./ui";
import type { AgentKind, AgentsInfo } from "./types";

const noop = () => () => {};
const useMounted = () => useSyncExternalStore(noop, () => true, () => false);

// ---------- agents info (shared by header, composer, settings) ----------
const pullRunning = (d?: AgentsInfo) => !!d && Object.values(d.pulls || {}).some((p) => !p.done);
export const AGENTS_KEY = ["studio", "agents-info"] as const;
export function useAgentsInfo() {
  return useQuery({
    queryKey: AGENTS_KEY,
    queryFn: api.agentsInfo,
    retry: false,
    staleTime: 5_000,
    // while a model download runs, follow its progress every 2 s
    refetchInterval: (q) => (pullRunning(q.state.data) ? 2_000 : 15_000),
  });
}

// ---------- the crew picked in the composer (remembered per browser) ----------
const CREW_KEY = "rm:crew";
const crewSubs = new Set<() => void>();
export const crewStore = {
  get: () => store.get(CREW_KEY) as AgentKind | null,
  set: (v: AgentKind) => { store.set(CREW_KEY, v); crewSubs.forEach((f) => f()); },
  subscribe: (f: () => void) => { crewSubs.add(f); return () => { crewSubs.delete(f); }; },
};
/** The crew new projects use: the remembered pick if it is ready, otherwise the service's default. */
export function useCrew(info: AgentsInfo | undefined): [AgentKind | null, (v: AgentKind) => void] {
  const picked = useSyncExternalStore(crewStore.subscribe, crewStore.get, () => null);
  const a = findAgent(info, picked);
  const crew = a?.ready ? a.id : info?.default ?? null;
  return [crew, crewStore.set];
}

// ---------- scoped root: translated, client-rendered, swaps to the offline card while the service is down ----------
export function RmRoot({ children, className = "" }: { children: ReactNode; className?: string }) {
  const mounted = useMounted();
  const off = useSyncExternalStore(engineStatus.subscribe, engineStatus.get, engineStatus.server);
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { if (mounted && ref.current) return attachI18n(ref.current); }, [mounted]);
  return (
    <div ref={ref} className={`rm rm-main ${className}`}>
      {!mounted ? null : off ? <main className="home"><EngineOffline /></main> : children}
    </div>
  );
}

/** Shown while the Animation Studio service can't be reached: how to start it. Polls and recovers by itself. */
export function EngineOffline() {
  useEffect(() => {
    const t = setInterval(() => { api.agentsInfo().catch(() => {}); }, 3000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="banner warn fade-in offline-card" data-testid="studio-offline">
      <div className="b-ico"><I n="power" s={2.2} /></div>
      <div className="grow">
        <h3>動畫服務沒有在執行</h3>
        <div className="small muted">動畫是由本機的動畫服務（Animation Studio）製作的。啟動它之後，這個頁面會自己連上。</div>
        <ol className="offline-steps">
          <li><span>在 apps 資料夾執行：</span><code>docker compose up -d animation-studio</code></li>
          <li><span>或雙擊</span><code>apps\start-animations.bat</code></li>
          <li><span>使用本機（免費）AI 團隊時，Ollama 也要在執行，並先下載模型：</span><code>ollama serve</code><code>ollama pull qwen2.5:7b</code></li>
        </ol>
        <div className="row small faint" style={{ marginTop: 12 }}><span className="spin-ring" style={{ width: 12, height: 12 }} />正在重新連線…</div>
      </div>
    </div>
  );
}

// ---------- header (AppShell's header slot) ----------
export function RmHeader() {
  const mounted = useMounted();
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => { if (mounted && ref.current) return attachI18n(ref.current); }, [mounted]);
  return (
    <div ref={ref} className="rm rm-nav">
      <Link className="brand" href="/animations"><BrandMark /><span>動畫</span></Link>
      <Link className="btn sm plain" href="/animations/films" data-testid="nav-films">短片</Link>
      <Link className="btn sm plain" href="/animations/series" data-testid="nav-series">系列</Link>
      <span className="sp" />
      {mounted && <CrewCapsule />}
      {mounted && <LangMenu />}
    </div>
  );
}

function CrewCapsule() {
  const info = useAgentsInfo();
  const [crew] = useCrew(info.data);
  const a = findAgent(info.data, crew);
  const state = info.isLoading ? "" : a?.ready ? "on" : "bad";
  return (
    <div className="agents-cap" title="已連線的 AI 導演" data-testid="crew-capsule">
      <span><i className={`dot ${state}`} /><span className="lbl">{info.data ? agentLabel(crew ?? undefined, info.data) : "AI 團隊"}</span></span>
    </div>
  );
}

// ---------- language menu ----------
export function LangMenu() {
  const [cur, setCur] = useState(getLang), [open, setOpen] = useState(false), ref = useRef<HTMLDivElement>(null);
  const close = useCallback(() => setOpen(false), []);
  useOutside(ref, open, close);
  const L = LANGS.find((l) => l.id === cur)!;
  return (
    <div className="lang" ref={ref} data-no-i18n>
      <button type="button" className="lang-btn" onClick={() => setOpen(!open)} aria-haspopup="listbox" aria-expanded={open} title="Language / 介面語言" data-testid="lang-menu"><I n="globe" /><span>{L.short}</span></button>
      {open && <div className="lang-menu" role="listbox">{LANGS.map((l) => (
        <button type="button" key={l.id} role="option" aria-selected={l.id === cur} className={l.id === cur ? "on" : ""} onClick={() => { setLang(l.id); setCur(l.id); setOpen(false); }}>
          <span>{l.label}</span>{l.id === cur && <I n="check" s={2.4} />}</button>))}</div>}
    </div>
  );
}
