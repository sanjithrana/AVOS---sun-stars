"use client";

import { useQuery } from "@tanstack/react-query";
import { BookOpen, ChevronRight } from "lucide-react";
import { useState } from "react";

interface AgentSkill { name: string; description: string; used_by: string; path: string; chars: number }

/** The SKILL.md files in apps/skills: the instructions AVOS's writers and directors read. They are not runs you can start
 *  here - they shape what the skills above produce - so they live in a panel of their own, folded away. */
export function AgentSkills() {
  const [open, setOpen] = useState(false);
  const q = useQuery({
    queryKey: ["agent-skills"],
    queryFn: async () => {
      const r = await fetch("/studio-api/series/skills");
      if (!r.ok) throw new Error("Could not read apps/skills");
      return (await r.json()) as { dir: string | null; skills: AgentSkill[] };
    },
    enabled: open,
    staleTime: 60_000,
  });
  const items = q.data?.skills ?? [];
  return (
    <section data-testid="agent-skills">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open}
        className="flex w-full items-center gap-2 rounded-2xl border border-border px-4 py-3 text-left hover:bg-accent">
        <BookOpen className="h-4 w-4 text-amber-500" />
        <span className="text-sm font-semibold">Instruction files {items.length ? `(${items.length})` : ""}</span>
        <span className="ml-1 text-xs text-muted-foreground">what the writers and directors read, in apps/skills</span>
        <ChevronRight className={`ml-auto h-4 w-4 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>
      {open && (
        <div className="mt-3 rounded-2xl border border-border p-4">
          {q.isLoading && <p className="text-sm text-muted-foreground">Reading…</p>}
          {q.isError && <p className="text-sm text-muted-foreground">{(q.error as Error).message}</p>}
          {!!items.length && (
            <>
              <p className="mb-3 text-xs text-muted-foreground">
                These are not runs. Each one is a Markdown file AVOS reads before it writes or directs; edit the file and the next run
                follows it, no restart needed. Folder: <code className="text-amber-700 dark:text-amber-300">{q.data?.dir ?? "apps/skills"}</code>
              </p>
              <ul className="space-y-2">
                {items.map((k) => (
                  <li key={k.name} className="rounded-xl border border-border p-3">
                    <p className="text-sm font-semibold"><code className="text-amber-700 dark:text-amber-300">{k.name}</code>
                      <span className="ml-2 font-normal text-xs text-muted-foreground">{(k.chars / 1000).toFixed(1)}k</span></p>
                    <p className="mt-0.5 text-xs text-muted-foreground">{k.description}</p>
                    {k.used_by && <p className="mt-1 text-[11px] text-muted-foreground">Used by: {k.used_by}</p>}
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}
    </section>
  );
}
