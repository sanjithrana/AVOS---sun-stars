"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity as ActivityIcon, Bell, CheckCircle2, Clock, Cpu, Loader2, Search, TriangleAlert, X } from "lucide-react";
import { EMPTY_ACTIVITY, ago, fetchActivity, fetchCaps, type ActivityItem } from "@/lib/activity";

const PAGES: { href: string; label: string; hint: string }[] = [
  { href: "/", label: "Home", hint: "Production assistant" }, { href: "/explainer", label: "Explainer", hint: "Idea to finished video" },
  { href: "/stickman", label: "Stickman", hint: "Stickman videos" }, { href: "/animations", label: "Animations", hint: "Films, series, video style" },
  { href: "/skills", label: "Skills", hint: "Company Story, Mechanical Toy" }, { href: "/models", label: "Models", hint: "Open AI models in use" },
  { href: "/gpu", label: "GPU", hint: "Workers, router, runs" }, { href: "/settings", label: "Settings", hint: "Keys, GPU, your models" },
];

/** A small popover: closes on an outside click or Escape. */
function Pop({ label, icon, badge, tone, children, wide }: { label: string; icon: ReactNode; badge?: number; tone?: "run" | "wait" | "err"; children: ReactNode; wide?: boolean }) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const down = (e: MouseEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const key = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("mousedown", down);
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("mousedown", down); document.removeEventListener("keydown", key); };
  }, [open]);
  const dot = tone === "err" ? "bg-red-500" : tone === "wait" ? "bg-amber-400" : "bg-primary";
  return (
    <div ref={box} className="relative">
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} aria-haspopup="dialog" aria-label={label} title={label}
        className={`relative inline-flex h-10 items-center gap-2 rounded-full border px-3 text-sm transition-colors ${open ? "border-[rgba(185,172,255,0.7)] bg-[rgba(124,92,255,0.18)]" : "border-border text-muted-foreground hover:text-foreground"}`}>
        {icon}<span className="hidden xl:inline">{label}</span>
        {!!badge && <span className={`absolute -right-1 -top-1 flex h-[18px] min-w-[18px] items-center justify-center rounded-full px-1 text-[10px] font-semibold text-white ${dot}`}>{badge > 99 ? "99+" : badge}</span>}
      </button>
      {open && (
        <div role="dialog" aria-label={label} className={`absolute right-0 top-12 z-50 max-h-[70vh] overflow-y-auto rounded-2xl border border-border bg-popover text-popover-foreground shadow-2xl ${wide ? "w-[min(92vw,26rem)]" : "w-[min(92vw,22rem)]"}`}>
          {children}
        </div>
      )}
    </div>
  );
}

const STATE: Record<string, { text: string; cls: string }> = {
  running: { text: "Running", cls: "text-primary" }, waiting: { text: "Needs you", cls: "text-amber-400" }, error: { text: "Failed", cls: "text-red-400" },
  done: { text: "Done", cls: "text-muted-foreground" }, stopped: { text: "Stopped", cls: "text-muted-foreground" },
};

function Row({ it, onGo }: { it: ActivityItem; onGo: () => void }) {
  const st = STATE[it.state] ?? STATE.done;
  return (
    <li>
      <Link href={it.href} onClick={onGo} className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-[rgba(124,92,255,0.10)]">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border bg-muted">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          {it.thumb ? <img src={it.thumb} alt="" className="h-full w-full object-cover" loading="lazy" />
            : it.state === "running" ? <Loader2 className="h-5 w-5 animate-spin text-primary" /> : it.state === "error" ? <TriangleAlert className="h-5 w-5 text-red-400" /> : it.state === "waiting" ? <Bell className="h-5 w-5 text-amber-400" /> : <CheckCircle2 className="h-5 w-5 text-muted-foreground" />}
        </span>
        <span className="min-w-0 flex-1 text-left">
          <span className="block truncate text-sm font-medium">{it.title}</span>
          <span className="block truncate text-[11px] text-muted-foreground">{it.studio} · {it.stage || it.kind}{it.updatedAt ? ` · ${ago(it.updatedAt)}` : ""}</span>
          {it.state === "error" && it.error && <span className="block truncate text-[11px] text-red-400">{it.error}</span>}
        </span>
        <span className={`shrink-0 text-[11px] font-medium ${st.cls}`}>{st.text}</span>
      </Link>
    </li>
  );
}

function Empty({ title, text }: { title: string; text: string }) {
  return <div className="px-6 py-10 text-center"><p className="text-sm font-medium">{title}</p><p className="mt-1 text-xs leading-relaxed text-muted-foreground">{text}</p></div>;
}

/** ⌘K / Ctrl+K: jump to a page or to any run. */
function Palette({ items, onClose }: { items: ActivityItem[]; onClose: () => void }) {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [i, setI] = useState(0);
  const rows = useMemo(() => {
    const all = [...PAGES.map((p) => ({ href: p.href, title: p.label, sub: p.hint, kind: "Page" })), ...items.map((x) => ({ href: x.href, title: x.title, sub: `${x.studio} · ${x.stage || x.kind}`, kind: "Run" }))];
    const t = q.trim().toLowerCase();
    return (t ? all.filter((r) => `${r.title} ${r.sub}`.toLowerCase().includes(t)) : all).slice(0, 12);
  }, [q, items]);
  const go = (href: string) => { onClose(); router.push(href); };
  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-black/55 px-4 pt-[14vh]" onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }} role="dialog" aria-label="Search">
      <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-border bg-popover text-popover-foreground shadow-2xl">
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="h-4 w-4 text-muted-foreground" />
          <input autoFocus value={q} onChange={(e) => { setQ(e.target.value); setI(0); }} placeholder="Jump to a page or a run…" aria-label="Search pages and runs"
            onKeyDown={(e) => {
              if (e.key === "Escape") onClose();
              else if (e.key === "ArrowDown") { e.preventDefault(); setI((x) => Math.min(rows.length - 1, x + 1)); }
              else if (e.key === "ArrowUp") { e.preventDefault(); setI((x) => Math.max(0, x - 1)); }
              else if (e.key === "Enter" && rows[i]) go(rows[i].href);
            }}
            className="h-12 w-full bg-transparent text-sm outline-none placeholder:text-muted-foreground" />
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted-foreground hover:text-foreground"><X className="h-4 w-4" /></button>
        </div>
        <ul className="max-h-[50vh] overflow-y-auto py-1">
          {rows.length === 0 && <li className="px-4 py-6 text-center text-sm text-muted-foreground">Nothing matches.</li>}
          {rows.map((r, n) => (
            <li key={`${r.href}-${n}`}>
              <button type="button" onMouseEnter={() => setI(n)} onClick={() => go(r.href)} className={`flex w-full items-center gap-3 px-4 py-2.5 text-left ${n === i ? "bg-[rgba(124,92,255,0.16)]" : ""}`}>
                <span className="w-10 shrink-0 text-[10px] uppercase tracking-wider text-muted-foreground">{r.kind}</span>
                <span className="min-w-0 flex-1"><span className="block truncate text-sm">{r.title}</span><span className="block truncate text-[11px] text-muted-foreground">{r.sub}</span></span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** The bar on every page: running jobs, what waits for you, history, model status, search, and the Sun-Star mark on Home. */
export function TopBar() {
  const pathname = usePathname();
  const [palette, setPalette] = useState(false);
  const q = useQuery({
    queryKey: ["activity"], queryFn: fetchActivity, retry: false, staleTime: 2000,
    refetchInterval: (s) => (typeof document !== "undefined" && document.hidden ? false : (s.state.data?.counts.running ?? 0) > 0 ? 3000 : 12000),
  });
  const caps = useQuery({ queryKey: ["caps-bar"], queryFn: fetchCaps, retry: false, staleTime: 30000 });
  const a = q.data ?? EMPTY_ACTIVITY;
  const running = a.jobs.filter((j) => j.state === "running");
  const waiting = a.jobs.filter((j) => j.state === "waiting");
  const failed = a.recent.filter((j) => j.state === "error").slice(0, 5);
  const bell = waiting.length + failed.length;
  const close = () => { /* links close the popover through navigation */ };
  useEffect(() => {
    const k = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") { e.preventDefault(); setPalette((p) => !p); } };
    window.addEventListener("keydown", k);
    return () => window.removeEventListener("keydown", k);
  }, []);
  const c = caps.data;
  const dot = (ok: boolean | undefined) => <span className={`h-2 w-2 rounded-full ${ok === undefined ? "bg-muted-foreground/40" : ok ? "bg-emerald-400" : "bg-amber-400"}`} />;

  return (
    <div className="flex items-center gap-2" data-testid="top-bar">
      {pathname === "/" && (
        <div className="mr-1 hidden items-center gap-2 rounded-full border border-primary/30 bg-primary/10 px-3.5 py-1.5 lg:flex" aria-label="Sun-Star by Sanjuuuuuu">
          <span aria-hidden className="text-base leading-none">☀️</span>
          <span className="text-sm font-semibold tracking-wide">Sun-Star</span>
          <span className="text-xs text-muted-foreground">by Sanjuuuuuu</span>
        </div>
      )}
      <button type="button" onClick={() => setPalette(true)} aria-label="Search (Ctrl K)" title="Search (Ctrl K)"
        className="inline-flex h-10 items-center gap-2 rounded-full border border-border px-3 text-sm text-muted-foreground transition-colors hover:text-foreground">
        <Search className="h-4 w-4" /><span className="hidden 2xl:inline">Search</span><kbd className="hidden rounded border border-border px-1.5 text-[10px] 2xl:inline">Ctrl K</kbd>
      </button>
      <Pop label="Jobs" icon={running.length ? <Loader2 className="h-4 w-4 animate-spin" /> : <ActivityIcon className="h-4 w-4" />} badge={running.length} tone="run" wide>
        <div className="border-b border-border px-4 py-3"><p className="text-sm font-semibold">Background jobs</p><p className="text-[11px] text-muted-foreground">Generations and renders keep running even if you close the page.</p></div>
        {a.jobs.length === 0 ? <Empty title="No background jobs right now" text="Videos you make show up here while they are being made." />
          : <ul className="divide-y divide-border">{a.jobs.map((j) => <Row key={`${j.studio}-${j.id}`} it={j} onGo={close} />)}</ul>}
      </Pop>
      <Pop label="History" icon={<Clock className="h-4 w-4" />} wide>
        <div className="border-b border-border px-4 py-3"><p className="text-sm font-semibold">Recent</p><p className="text-[11px] text-muted-foreground">The last runs from every studio.</p></div>
        {a.recent.length === 0 ? <Empty title="Nothing yet" text="Finished and stopped runs appear here." /> : <ul className="divide-y divide-border">{a.recent.map((j) => <Row key={`${j.studio}-${j.id}`} it={j} onGo={close} />)}</ul>}
      </Pop>
      <Pop label="Needs you" icon={<Bell className="h-4 w-4" />} badge={bell} tone={failed.length && !waiting.length ? "err" : "wait"} wide>
        <div className="border-b border-border px-4 py-3"><p className="text-sm font-semibold">Needs you</p><p className="text-[11px] text-muted-foreground">Approvals and runs that stopped with a problem.</p></div>
        {bell === 0 ? <Empty title="All clear" text="Nothing is waiting for your approval." /> : <ul className="divide-y divide-border">{[...waiting, ...failed].map((j) => <Row key={`${j.studio}-${j.id}`} it={j} onGo={close} />)}</ul>}
      </Pop>
      <Pop label="Models" icon={<Cpu className="h-4 w-4" />}>
        <div className="border-b border-border px-4 py-3"><p className="text-sm font-semibold">What is ready</p></div>
        <ul className="space-y-2 px-4 py-3 text-sm">
          <li className="flex items-center gap-2">{dot(c?.ai_video)}AI video{c ? (c.ai_video ? "" : " · no fal.ai credit") : ""}</li>
          <li className="flex items-center gap-2">{dot(c?.voice)}Narration voice</li>
          <li className="flex items-center gap-2">{dot(c?.music)}Music</li>
          <li className="flex items-center gap-2">{dot(c?.blender)}3D scenes (Blender)</li>
        </ul>
        {c?.hint && <p className="px-4 pb-2 text-[11px] leading-relaxed text-muted-foreground">{c.hint}</p>}
        <div className="flex gap-2 border-t border-border px-4 py-3 text-xs"><Link href="/models" className="rounded-full border border-border px-3 py-1.5 hover:text-foreground">Models</Link><Link href="/settings" className="rounded-full border border-border px-3 py-1.5 hover:text-foreground">Settings</Link><Link href="/gpu" className="rounded-full border border-border px-3 py-1.5 hover:text-foreground">GPU</Link></div>
      </Pop>
      {palette && <Palette items={[...a.jobs, ...a.recent]} onClose={() => setPalette(false)} />}
    </div>
  );
}
