import { autoclip, type YtPost, type YtTab } from "@/lib/autoclip";

export const thumbUrl = (t: YtPost["thumb"] | { jid?: string; name?: string; upload?: string } | undefined) =>
  !t ? undefined : t.upload ? autoclip.uploadCover(t.upload) : t.jid && t.name ? autoclip.file(t.jid, t.name) : undefined;

/** "Tue 17 Nov, 14:00" in the studio's clock (the posting-hours time zone), not the browser's. */
export function when(iso: string | null | undefined, tzMin: number) {
  if (!iso) return "as soon as possible";
  const d = new Date(Date.parse(iso) + tzMin * 60_000);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("en-GB", { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" });
}

export const num = (n: number | undefined | null) => (n == null ? "–" : n >= 1_000_000 ? `${(n / 1e6).toFixed(1)}M` : n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n));
export const chanName = (tab: YtTab, id: string) => tab.channels.find((c) => c.id === id)?.title ?? "(removed)";
