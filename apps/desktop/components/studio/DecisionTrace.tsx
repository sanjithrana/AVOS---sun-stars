import { Brain, Wrench, CheckCircle2, AlertTriangle } from "lucide-react";
import { DecisionTraceEntry } from "@/types/trace";

interface DecisionTraceProps {
  entries: DecisionTraceEntry[];
}

/**
 * Renders one row per audit_records entry:
 *   🧠 <agent_decision>
 *   🔧 <tool_name>  (duration, cost)
 *   ✓ / ⚠ <status>
 * matching the AVOS-11 §5 decision-trace format.
 */
export function DecisionTrace({ entries }: DecisionTraceProps) {
  if (entries.length === 0) {
    return (
      <p className="text-xs text-muted-foreground px-1 py-4 text-center">
        No agent activity yet.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {entries.map((entry) => (
        <div
          key={entry.id}
          className="rounded-lg border border-border bg-muted/60 p-3 text-xs"
        >
          <div className="flex items-start gap-2 mb-1.5">
            <Brain className="h-3.5 w-3.5 text-purple-400 shrink-0 mt-0.5" />
            <span className="text-foreground leading-relaxed">
              {entry.agent_decision}
            </span>
          </div>
          <div className="flex items-start gap-2 mb-1.5">
            <Wrench className="h-3.5 w-3.5 text-blue-400 shrink-0 mt-0.5" />
            <span className="text-muted-foreground">
              {entry.tool_name}
              <span className="text-muted-foreground/60">
                {" "}
                · {entry.duration_ms}ms · ${entry.cost.toFixed(3)} · {entry.model}
              </span>
            </span>
          </div>
          <div className="flex items-center gap-2">
            {entry.status === "success" ? (
              <>
                <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
                <span className="text-green-400">Success</span>
              </>
            ) : (
              <>
                <AlertTriangle className="h-3.5 w-3.5 text-red-400 shrink-0" />
                <span className="text-red-400">{entry.error ?? "Failed"}</span>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
