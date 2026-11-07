import { apiBaseUrl } from "@/lib/api/core";
import { LIVE_EVENT_TYPES, type AVOSEvent } from "@/types/event";

export type { AVOSEvent };
export type EventHandler = (event: AVOSEvent) => void;

/**
 * Open a live SSE connection to GET /events/stream (optionally scoped to
 * one project). Returns a cleanup function. The browser's EventSource
 * reconnects automatically after transient drops.
 */
export function subscribeToEvents(
  onEvent: EventHandler,
  options: { projectId?: string; onOpen?: () => void; onError?: (err: Event) => void } = {}
): () => void {
  const url = new URL(`${apiBaseUrl()}/events/stream`);
  if (options.projectId) url.searchParams.set("project_id", options.projectId);

  const source = new EventSource(url.toString());

  // The backend sends named SSE events (event: <EVENT_TYPE>), which only
  // reach listeners registered for that exact name.
  const listener = (e: MessageEvent) => {
    try {
      onEvent(JSON.parse(e.data) as AVOSEvent);
    } catch {
      // Ignore malformed events rather than crashing the subscriber.
    }
  };
  for (const type of LIVE_EVENT_TYPES) source.addEventListener(type, listener);

  source.onopen = () => options.onOpen?.();
  source.onerror = (err) => options.onError?.(err);

  return () => {
    for (const type of LIVE_EVENT_TYPES) source.removeEventListener(type, listener);
    source.close();
  };
}
