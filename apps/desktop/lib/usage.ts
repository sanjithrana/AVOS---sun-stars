// What each run spent, from the ledger in animation_studio/studio/usage.py, through the Next rewrite.
export interface Bucket { name: string; calls: number; units: number; cost: number; unpriced: number; failed: number }
export interface Row { at: string; kind: string; model: string; units: number; unit: string; cost: number; priced: boolean; ok: boolean; run: string; skill: string; note: string }
export interface UsageSummary {
  days: number;
  total: { cost: number; calls: number; unpriced: number; free: number; failed: number };
  by_kind: Bucket[]; by_model: Bucket[]; by_skill: Bucket[];
  by_day: { day: string; cost: number; calls: number }[];
  recent: Row[]; note: string;
}

export const usage = {
  async summary(days = 30): Promise<UsageSummary> {
    const r = await fetch(`/studio-api/usage?days=${days}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`Usage is not available (${r.status}). The studio may still be starting.`);
    return r.json();
  },
};

/** Money, written the way a bill is: cents when it is cents, so "$0.0031" does not read as three dollars. */
export function money(n: number): string {
  if (!n) return "$0";
  if (n < 0.01) return `$${n.toFixed(4)}`;
  if (n < 1) return `$${n.toFixed(3)}`;
  return `$${n.toFixed(2)}`;
}
