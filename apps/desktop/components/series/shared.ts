import type { SeriesSnapshot } from "./types";

export const field = "w-full rounded-xl border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-amber-500/40";

/** Run an API call; a returned snapshot replaces the page's data, errors show above the page. */
export type Act = (label: string, fn: () => Promise<SeriesSnapshot | unknown>) => Promise<void>;
