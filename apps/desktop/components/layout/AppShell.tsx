"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Clapperboard, Home, Landmark, Library, Scissors, Settings2, Sparkles, Send, Wand2 } from "lucide-react";
import type { ReactNode } from "react";
import { Mark } from "@/components/layout/Mark";
import { ThemeToggle } from "@/components/layout/ThemeToggle";
import { TopBar } from "@/components/layout/TopBar";

// Eight rooms. Pages that belong together share one tab and switch with a strip under the top bar:
// Explainer (make, skills, prompts), Channels (posting, accounts) and Settings (studio, GPU, usage and cost).
const NAV = [
  { href: "/", label: "Home", hint: "Start something, see what is running", icon: Home, match: (p: string) => p === "/" },
  { href: "/explainer", label: "Explainer", hint: "Idea to finished video, crew skills and prompts", icon: Sparkles, match: (p: string) => p.startsWith("/explainer") },
  { href: "/skills", label: "Video skills", hint: "Ready-made videos: company story, mechanical toy, cartoon shorts", icon: Wand2, match: (p: string) => p.startsWith("/skills") },
  { href: "/stickman", label: "Stickman", hint: "Stickman videos, 13 looks", icon: Landmark, match: (p: string) => p.startsWith("/stickman") },
  { href: "/animations", label: "Animations", hint: "Films, series, video style", icon: Clapperboard, match: (p: string) => p.startsWith("/animations") },
  { href: "/autoclip", label: "Auto Clip", hint: "Long video to Shorts", icon: Scissors, match: (p: string) => p.startsWith("/autoclip") },
  { href: "/youtube", label: "Channels", hint: "Post, schedule, connect accounts", icon: Send, match: (p: string) => p.startsWith("/youtube") || p.startsWith("/connections") },
  { href: "/library", label: "Library", hint: "Everything you have made", icon: Library, match: (p: string) => p.startsWith("/library") },
  { href: "/settings", label: "Settings", hint: "Keys, models, GPU, usage and cost", icon: Settings2, match: (p: string) => p.startsWith("/settings") || p.startsWith("/gpu") || p.startsWith("/analytics") || p.startsWith("/models") },
];

/** Tabs inside a room. A page listed here gets the strip instead of its own title. */
const ROOMS: { title: string; tabs: [string, string][] }[] = [
  { title: "Explainer", tabs: [["/explainer", "Make"], ["/explainer/skills", "Crew skills"], ["/explainer/prompts", "Prompts"]] },
  { title: "Channels", tabs: [["/youtube", "Posting"], ["/connections", "Accounts"]] },
  { title: "Settings", tabs: [["/settings", "Studio"], ["/gpu", "GPU"], ["/analytics", "Usage and cost"]] },
];

interface AppShellProps {
  children: ReactNode;
  header?: ReactNode;
}

const GROUPS: [string, string[]][] = [
  ["Make", ["/", "/explainer", "/skills", "/stickman", "/animations", "/autoclip"]],
  ["Publish", ["/youtube", "/library"]],
];

const ring = "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring";

/** The frame every page sits in: one grid, cut by hairlines. Rail on the left, a thin bar on top, the page in the big cell. */
export function AppShell({ children, header }: AppShellProps) {
  const pathname = usePathname();
  const byHref = Object.fromEntries(NAV.map((n) => [n.href, n]));
  const room = ROOMS.find((r) => r.tabs.some(([h]) => h === pathname));
  const hue = NAV.find((n) => n.match(pathname))?.href ?? "/";
  const settings = byHref["/settings"];
  const setOn = settings.match(pathname);

  return (
    <div data-room={hue} className="app-frame grid grid-cols-1 grid-rows-[auto_3.5rem_minmax(0,1fr)] gap-px bg-border text-foreground md:grid-cols-[15rem_minmax(0,1fr)] md:grid-rows-[3.5rem_minmax(0,1fr)]">
      {/* corner: the mark */}
      <Link href="/" className={`hidden items-center gap-2.5 bg-sidebar px-5 md:flex ${ring}`} aria-label="AVOS Studio home">
        <Mark className="h-6 w-6" />
        <span className="font-[family-name:var(--font-display)] text-[17px] font-semibold tracking-[-0.02em]">AVOS Studio</span>
      </Link>

      {/* mobile: one scrolling strip */}
      <nav className="flex gap-px overflow-x-auto bg-sidebar md:hidden" aria-label="Main">
        {NAV.map((item) => {
          const on = item.match(pathname);
          return (
            <Link key={item.href} href={item.href} aria-current={on ? "page" : undefined}
              className={`flex shrink-0 items-center gap-2 border-b-2 px-3.5 py-3 text-[13px] ${ring} ${on ? "border-signal text-foreground" : "border-transparent text-muted-foreground"}`}>
              <item.icon className="h-4 w-4" strokeWidth={1.6} />{item.label}
            </Link>
          );
        })}
      </nav>

      {/* top bar */}
      <header className="flex min-w-0 items-center justify-between gap-3 bg-background px-4 md:px-6">
        <div className="flex min-w-0 flex-1 items-center gap-3 self-stretch text-[13px]">{room ? <RoomTabs room={room} pathname={pathname} /> : header}</div>
        <TopBar />
        <ThemeToggle />
      </header>

      {/* rail */}
      <aside className="hidden min-h-0 flex-col overflow-y-auto bg-sidebar md:flex">
        <nav className="flex-1 px-2 pb-4 pt-2" aria-label="Main">
          {GROUPS.map(([group, hrefs]) => (
            <div key={group} className="pt-4 first:pt-2">
              <p className="px-3 pb-2 text-[12px] text-muted-foreground">{group}</p>
              <ul className="space-y-0.5">
                {hrefs.map((h) => byHref[h]).filter(Boolean).map((item) => <RailLink key={item.href} item={item} on={item.match(pathname)} />)}
              </ul>
            </div>
          ))}
        </nav>
        <div className="border-t border-border px-2 py-2">
          <ul><RailLink item={settings} on={setOn} /></ul>
        </div>
      </aside>

      {/* the page */}
      <main className="room-wash min-h-0 min-w-0 overflow-auto overscroll-contain bg-background" data-scroll-root>{children}</main>
    </div>
  );
}

type Item = (typeof NAV)[number];

/** One row of the rail: 36 tall, the icon in one 16px column, a 2px key-blue edge when it is the room you are in. */
function RailLink({ item, on }: { item: Item; on: boolean }) {
  return (
    <li>
      <Link href={item.href} title={item.hint} aria-current={on ? "page" : undefined}
        className={`group relative flex h-9 items-center gap-2.5 px-3 text-[13.5px] transition-colors duration-150 ${ring} ${on ? "bg-[color-mix(in_oklab,var(--room)_12%,var(--background))] text-foreground" : "text-muted-foreground hover:bg-background/70 hover:text-foreground"}`}>
        <span aria-hidden className={`absolute inset-y-1.5 left-0 w-[2px] transition-colors ${on ? "bg-[var(--room)]" : "bg-transparent"}`} />
        <item.icon data-room={item.href} className={`rail-ico h-4 w-4 shrink-0 transition-colors ${on ? "on" : ""}`} strokeWidth={1.5} />
        {item.label}
      </Link>
    </li>
  );
}

/** The strip of tabs for a room that holds several pages. */
function RoomTabs({ room, pathname }: { room: (typeof ROOMS)[number]; pathname: string }) {
  return (
    <div className="flex min-w-0 items-stretch gap-6 self-stretch">
      <span className="flex items-center gap-2 font-[family-name:var(--font-display)] text-[15px] text-foreground"><span aria-hidden className="h-2 w-2 bg-[var(--room)]" />{room.title}</span>
      <nav className="flex min-w-0 items-stretch gap-1 overflow-x-auto" aria-label={`${room.title} pages`}>
        {room.tabs.map(([href, label]) => {
          const on = pathname === href;
          return (
            <Link key={href} href={href} aria-current={on ? "page" : undefined}
              className={`relative flex shrink-0 items-center px-3 text-[13px] transition-colors ${ring} ${on ? "text-foreground" : "text-muted-foreground hover:text-foreground"}`}>
              {label}
              <span aria-hidden className={`absolute inset-x-3 bottom-0 h-[2px] transition-colors ${on ? "bg-[var(--room)]" : "bg-transparent"}`} />
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
