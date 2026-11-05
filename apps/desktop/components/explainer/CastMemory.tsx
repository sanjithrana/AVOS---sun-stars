"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { explainer } from "@/lib/explainer";

/** The characters the studio remembers. Use a name from here in your idea and the same character comes back. */
export function CastMemory() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["cast-memory"], queryFn: explainer.memory, retry: false });
  const forget = useMutation({ mutationFn: (mid: string) => explainer.forget(mid), onSuccess: (d) => qc.setQueryData(["cast-memory"], d) });
  const cast = q.data?.cast ?? [];
  if (q.isError || !cast.length) return null;
  return (
    <section data-testid="cast-memory">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-lg font-semibold">Cast memory</h2>
        <p className="text-sm text-muted-foreground">Use a name in your idea and the same character comes back.</p>
      </div>
      <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5 2xl:grid-cols-6">
        {cast.map((m) => (
          <li key={m.id} className="group overflow-hidden rounded-2xl border border-border bg-card">
            <div className="aspect-[3/4] bg-muted">
              {m.portrait && /* eslint-disable-next-line @next/next/no-img-element */ <img src={explainer.memoryFile(m.id, m.portrait, m.updated)} alt={`${m.name} portrait`} className="h-full w-full object-cover" />}
            </div>
            <div className="p-3">
              <p className="truncate text-sm font-medium">{m.name}</p>
              <p className="mt-0.5 line-clamp-2 text-[11px] text-muted-foreground">{m.look}</p>
              <div className="mt-2 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>{m.projects.length} {m.projects.length === 1 ? "video" : "videos"}{m.approved ? "" : " · not approved yet"}</span>
                <button type="button" onClick={() => { if (window.confirm(`Forget ${m.name}? The next video draws a new character.`)) forget.mutate(m.id); }}
                  className="rounded-full p-1.5 hover:bg-secondary" aria-label={`Forget ${m.name}`}><Trash2 className="h-3.5 w-3.5" /></button>
              </div>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
