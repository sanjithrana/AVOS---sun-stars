"use client";
/* eslint-disable @next/next/no-img-element -- pictures come from the Animation Studio service */
// Your character library: approved characters saved once (sheet + voice) and cast in any film or series.
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookUser, Check, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { seriesApi } from "./api";
import type { Act } from "./shared";
import type { LibraryCharacter } from "./types";

export function useLibrary() {
  return useQuery({ queryKey: ["series", "library"], queryFn: seriesApi.library, retry: false, staleTime: 5_000 });
}

function Card({ c, picked, onClick, children }: { c: LibraryCharacter; picked?: boolean; onClick?: () => void; children?: React.ReactNode }) {
  return (
    <div className={`w-44 shrink-0 overflow-hidden rounded-xl border bg-card/40 ${picked ? "border-amber-500 ring-2 ring-amber-500/40" : "border-border"}`} data-testid={`lib-${c.id}`}>
      <button type="button" className="relative block aspect-video w-full bg-muted/40" onClick={onClick} disabled={!onClick}>
        <img src={seriesApi.libFile(c.sheetUrl, c.savedAt)} alt={c.name} className="h-full w-full object-cover" />
        {picked && <Check className="absolute right-1 top-1 h-5 w-5 rounded-full bg-amber-500 p-0.5 text-black" />}
      </button>
      <div className="space-y-1 p-2">
        <b className="block truncate text-sm text-foreground">{c.name}</b>
        <p className="line-clamp-2 text-[11px] text-muted-foreground">{c.look}</p>
        {c.voiceUrl && <audio controls src={seriesApi.libFile(c.voiceUrl, c.savedAt)} className="h-7 w-full" />}
        {children}
      </div>
    </div>
  );
}

/** Pick library characters for a new film (their sheets and voices are reused, already approved). */
export function LibraryPicker({ value, onChange }: { value: string[]; onChange: (ids: string[]) => void }) {
  const lib = useLibrary();
  const items = lib.data ?? [];
  if (!items.length) return <p className="text-xs text-muted-foreground">Your library is empty: approve a character in a film or series and press “Save to library”.</p>;
  return (
    <div className="flex gap-3 overflow-x-auto pb-1" data-testid="library-picker">
      {items.map((c) => <Card key={c.id} c={c} picked={value.includes(c.id)} onClick={() => onChange(value.includes(c.id) ? value.filter((x) => x !== c.id) : [...value, c.id])} />)}
    </div>
  );
}

/** Cast a library character into this film / series, and manage the library. */
export function LibraryAdd({ sid, act, have }: { sid: string; act: Act; have: string[] }) {
  const [open, setOpen] = useState(false);
  const lib = useLibrary();
  const qc = useQueryClient();
  const items = lib.data ?? [];
  if (!open) return (
    <button className="flex min-h-40 items-center justify-center gap-2 rounded-xl border border-dashed border-border text-sm text-muted-foreground hover:border-amber-500" onClick={() => setOpen(true)} data-testid="open-library">
      <BookUser className="h-4 w-4" />From your library{items.length ? ` (${items.length})` : ""}
    </button>
  );
  return (
    <div className="space-y-2 rounded-xl border border-border bg-card/40 p-4 lg:col-span-2" data-testid="library">
      <div className="flex items-center gap-2"><BookUser className="h-4 w-4 text-amber-500" /><b className="text-sm text-foreground">Your character library</b><span className="grow" />
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Close</Button></div>
      {!items.length && <p className="text-xs text-muted-foreground">Empty: approve a character and press “Save to library”.</p>}
      <div className="flex gap-3 overflow-x-auto pb-1">
        {items.map((c) => (
          <Card key={c.id} c={c}>
            <div className="flex gap-1">
              <Button size="sm" variant="outline" disabled={have.includes(c.id)} onClick={() => act(`lib-${c.id}`, () => seriesApi.addFromLibrary(sid, c.id))} data-testid="lib-add">
                <Plus />{have.includes(c.id) ? "In the cast" : "Cast"}
              </Button>
              <Button size="sm" variant="ghost" title="Remove from the library" onClick={async () => { await seriesApi.deleteLibrary(c.id); await qc.invalidateQueries({ queryKey: ["series", "library"] }); }}><Trash2 /></Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}
