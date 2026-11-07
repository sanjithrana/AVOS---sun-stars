"use client";

import { Check, Loader2 } from "lucide-react";

/** "Saving…" while a change is on its way, then "Saved". */
export function SaveState({ saving, error }: { saving: boolean; error?: string | null }) {
  if (error) return <span className="text-xs text-red-400" role="alert">Not saved: {error}</span>;
  return saving ? <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving…</span>
    : <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground"><Check className="h-3.5 w-3.5 text-emerald-400" />Saved</span>;
}
