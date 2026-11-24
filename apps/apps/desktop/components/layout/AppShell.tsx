"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, Clapperboard, Cpu, Home, Landmark, Settings2, Sparkles } from "lucide-react";
import type { ReactNode } from "react";
import { Mark } from "@/components/layout/Mark";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

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
    hint: "History in stickman clips",
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

/** Sidebar + header frame shared by every page: hairline borders, no fills, one amber mark for where you are. */
export function AppShell({ children, header }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen text-foreground">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-border md:flex">
        <Link href="/" className={`flex items-center gap-3 px-6 py-6 ${ring}`} aria-label="AVOS Studio home">
          <Mark className="h-7 w-7" />
          <span className="leading-none">
            <span className="block text-xl font-light tracking-wide">AVOS</span>
            <span className="mt-1 block text-[11px] text-muted-foreground">Studio</span>
          </span>
        </Link>
        <nav className="flex-1 space-y-0.5 px-3 py-2" aria-label="Main">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={`relative flex items-center gap-3 rounded-full px-3 py-2.5 text-sm transition-colors ${ring} ${
                  active ? "bg-gradient-to-r from-[var(--signal)]/15 to-transparent text-foreground" : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                {active && <span className="absolute inset-y-2 left-0 w-0.5 rounded-full bg-[var(--signal)] shadow-[0_0_12px_2px_var(--signal)]" aria-hidden />}
                <item.icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.5} />
                <span className="flex flex-col leading-tight">
                  {item.label}
                  <span className="text-[11px] font-normal text-muted-foreground">{item.hint}</span>
                </span>
              </Link>
            );
          })}
        </nav>
        <p className="px-6 py-5 text-[11px] text-muted-foreground/70">AI video operating system</p>
      </aside>

      <main className="flex flex-1 flex-col overflow-hidden">
        <nav className="flex gap-1 overflow-x-auto border-b border-border p-2 md:hidden" aria-label="Main">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={item.match(pathname) ? "page" : undefined}
              className={`flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm ${ring} ${
                item.match(pathname) ? "bg-accent text-foreground" : "text-muted-foreground"
              }`}
            >
              <item.icon className="h-4 w-4" strokeWidth={1.5} />
              {item.label}
            </Link>
          ))}
        </nav>
        <header className="flex items-center justify-between gap-4 border-b border-border px-4 py-3.5 md:px-8">
          <div className="flex flex-1 items-center gap-4">{header}</div>
          <ThemeToggle />
        </header>
        <div className="flex-1 overflow-auto">{children}</div>
      </main>
    </div>
  );
}
