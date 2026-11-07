"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, Clapperboard, Cpu, Home, Landmark, Settings2, Sparkles, Wand2 } from "lucide-react";
import type { ReactNode } from "react";
import { Mark } from "@/components/layout/Mark";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { TopBar } from "@/components/layout/TopBar";

// Studios: Explainer (one idea -> a finished explainer video; characters, 3D, AI video and voice chosen per shot)
// and Animations (films, series, video style), plus the Models page (which open model does which job).
const NAV = [
  {
    href: "/",
    label: "Home",
    hint: "Production assistant",
    icon: Home,
    match: (p: string) => p === "/",
  },
  {
    href: "/explainer",
    label: "Explainer",
    hint: "Idea to finished video",
    icon: Sparkles,
    match: (p: string) => p.startsWith("/explainer"),
  },
  {
    href: "/stickman",
    label: "Stickman",
    hint: "Stickman videos, 13 looks",
    icon: Landmark,
    match: (p: string) => p.startsWith("/stickman"),
  },
  {
    href: "/animations",
    label: "Animations",
    hint: "Films, series, video style",
    icon: Clapperboard,
    match: (p: string) => p.startsWith("/animations"),
  },
  {
    href: "/skills",
    label: "Skills",
    hint: "One-subject skills, e.g. toys",
    icon: Wand2,
    match: (p: string) => p.startsWith("/skills"),
  },
  {
    href: "/models",
    label: "Models",
    hint: "Open AI models in use",
    icon: Boxes,
    match: (p: string) => p.startsWith("/models"),
  },
  {
    href: "/gpu",
    label: "GPU",
    hint: "Workers, router, runs",
    icon: Cpu,
    match: (p: string) => p.startsWith("/gpu"),
  },
  {
    href: "/settings",
    label: "Settings",
    hint: "Keys, GPU, your models",
    icon: Settings2,
    match: (p: string) => p.startsWith("/settings"),
  },
];

interface AppShellProps {
  children: ReactNode;
  header?: ReactNode;
}

const ring = "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring";

/** Sidebar + header frame shared by every page: frosted glass over the indigo scene, the current page lit in violet. */
export function AppShell({ children, header }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="app-frame flex h-dvh overflow-hidden text-foreground">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
        <Link href="/" className={`flex h-20 items-center gap-3 px-6 ${ring}`} aria-label="AVOS Studio home">
          <Mark className="h-7 w-7" />
          <span className="leading-none">
            <span className="block text-lg font-semibold tracking-wide">AVOS</span>
            <span className="mt-1 block text-[11px] text-muted-foreground">Studio</span>
          </span>
        </Link>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-2" aria-label="Main">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`flex min-h-[46px] items-center gap-3 rounded-2xl px-3.5 py-2 text-[13px] font-medium transition-all ${ring} ${
                  active
                    ? "border border-[rgba(150,130,255,0.35)] bg-[rgba(124,92,255,0.10)] text-foreground"
                    : "border border-transparent text-muted-foreground hover:bg-[rgba(124,92,255,0.10)] hover:text-foreground hover:shadow-[0_0_22px_-2px_rgba(124,92,255,0.9)] hover:border-[rgba(185,172,255,0.4)]"
                }`}
              >
                <item.icon className={`h-[18px] w-[18px] shrink-0 ${active ? "text-[var(--signal)]" : ""}`} strokeWidth={1.5} />
                <span className="flex flex-col leading-tight">
                  {item.label}
                  <span className="text-[11px] font-normal text-muted-foreground">{item.hint}</span>
                </span>
              </Link>
            );
          })}
        </nav>
        <p className="px-6 py-5 text-[11px] text-muted-foreground">AI video operating system</p>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <nav className="flex gap-1 overflow-x-auto border-b border-border bg-sidebar p-2 md:hidden" aria-label="Main">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={item.match(pathname) ? "page" : undefined}
              className={`flex shrink-0 items-center gap-2 rounded-full px-3.5 py-2 text-sm ${ring} ${
                item.match(pathname) ? "bg-[rgba(109,76,255,0.22)] text-foreground" : "text-muted-foreground"
              }`}
            >
              <item.icon className="h-4 w-4" strokeWidth={1.5} />
              {item.label}
            </Link>
          ))}
        </nav>
        <header className="flex h-16 shrink-0 items-center justify-between gap-4 border-b border-border px-4 md:h-20 md:px-10">
          <div className="flex min-w-0 flex-1 items-center gap-4">{header}</div>
          <TopBar />
          <ThemeToggle />
        </header>
        <div className="min-h-0 flex-1 overflow-auto overscroll-contain" data-scroll-root>{children}</div>
      </main>
    </div>
  );
}
