"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Boxes, Clapperboard, Cpu, Lightbulb, Settings2, Star } from "lucide-react";
import type { ReactNode } from "react";
import { ThemeToggle } from "@/components/layout/ThemeToggle";

// Two studios: Facts (topic -> narrated facts video) and Animations
// (ReelMimic: reference video -> new animation in the same style), plus the
// Models page (which open model does which job, and what is set up).
const NAV = [
  {
    href: "/facts",
    label: "Facts",
    hint: "Narrated fact videos",
    icon: Lightbulb,
    match: (p: string) => p.startsWith("/facts") || p.startsWith("/project") || p.startsWith("/studio"),
  },
  {
    href: "/animations",
    label: "Animations",
    hint: "Copy a video's style",
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

/** Sidebar + header frame shared by the Facts, Animations and project pages. */
export function AppShell({ children, header }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="flex h-screen bg-background text-foreground">
      <aside className="hidden md:flex w-60 shrink-0 flex-col border-r border-border bg-card/30">
        <Link href="/facts" className="flex items-center gap-2 px-6 py-6 border-b border-border">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-amber-400 to-orange-500 shadow-lg shadow-amber-500/20">
            <Star className="h-6 w-6 fill-white text-white" />
          </div>
          <div>
            <p className="text-xl font-bold text-foreground leading-none">AVOS</p>
            <p className="text-[10px] uppercase tracking-widest text-muted-foreground">Studio</p>
          </div>
        </Link>
        <nav className="flex-1 space-y-1 p-4">
          {NAV.map((item) => {
            const active = item.match(pathname);
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all ${
                  active
                    ? "border border-amber-500/30 bg-gradient-to-r from-amber-500/20 to-orange-500/20 text-amber-700 dark:text-amber-300"
                    : "text-muted-foreground hover:bg-accent hover:text-foreground"
                }`}
              >
                <item.icon className="h-5 w-5 shrink-0" />
                <span className="flex flex-col leading-tight">
                  {item.label}
                  <span className="text-[11px] font-normal text-muted-foreground">{item.hint}</span>
                </span>
              </Link>
            );
          })}
        </nav>
        <p className="px-6 py-4 text-[11px] text-muted-foreground/60">AI Video Operating System</p>
      </aside>

      <main className="flex flex-1 flex-col overflow-hidden">
        <nav className="flex gap-1 border-b border-border bg-card/30 p-2 md:hidden">
          {NAV.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`flex flex-1 items-center justify-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
                item.match(pathname) ? "bg-amber-500/15 text-amber-700 dark:text-amber-300" : "text-muted-foreground"
              }`}
            >
              <item.icon className="h-4 w-4" />
              {item.label}
            </Link>
          ))}
        </nav>
        <header className="flex items-center justify-between gap-4 border-b border-border bg-card/20 px-4 py-4 md:px-8">
          <div className="flex flex-1 items-center gap-4">{header}</div>
          <ThemeToggle />
        </header>
        <div className="flex-1 overflow-auto">{children}</div>
      </main>
    </div>
  );
}
