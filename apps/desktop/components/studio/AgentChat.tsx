"use client";

import { Bot } from "lucide-react";
import { DecisionTrace } from "@/components/studio/DecisionTrace";
import { useTrace } from "@/hooks/queries";

/**
 * Live agent decision trace (Day 9). Initial rows come from
 * GET /agents/trace; new rows are appended by useLiveProject from
 * AGENT_ACTION_RECORDED SSE events - no polling, no refresh.
 */
export function AgentChat({ projectId }: { projectId: string }) {
  const { data: entries, isLoading, isError } = useTrace(projectId);

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-12 shrink-0 items-center gap-2 border-b border-border px-4">
        <Bot className="h-4 w-4 text-amber-400" />
        <h2 className="text-sm font-semibold text-foreground">Agent Activity</h2>
        {entries && entries.length > 0 && (
          <span className="ml-auto rounded-full bg-muted px-2 py-0.5 text-[10px] text-muted-foreground">
            {entries.length}
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4" data-testid="agent-trace">
        {isLoading ? (
          <p className="py-4 text-center text-xs text-muted-foreground">Loading…</p>
        ) : isError ? (
          <p className="py-4 text-center text-xs text-red-400">Could not load the decision trace.</p>
        ) : (
          <DecisionTrace entries={entries ?? []} />
        )}
      </div>
    </div>
  );
}
