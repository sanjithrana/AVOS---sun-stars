import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";

const STEPS = [
  { key: "research", label: "Research" },
  { key: "script", label: "Script" },
  { key: "approval", label: "Your approval" },
  { key: "audio", label: "Audio + timing" },
  { key: "shots", label: "Shots + physics" },
  { key: "visuals", label: "Visuals" },
  { key: "render", label: "Final video" },
] as const;

type StepState = "done" | "active" | "pending" | "failed";

/** Derive each pipeline step's state from the backend project status. */
export function stepStates(status: string): StepState[] {
  switch (status) {
    case "researching":
      return ["active", "active", "pending", "pending", "pending", "pending", "pending"];
    case "awaiting_approval":
      return ["done", "done", "active", "pending", "pending", "pending", "pending"];
    case "generating_audio":
      return ["done", "done", "done", "active", "pending", "pending", "pending"];
    case "planning_shots":
      return ["done", "done", "done", "done", "active", "pending", "pending"];
    case "generating_visuals":
      return ["done", "done", "done", "done", "done", "active", "pending"];
    case "awaiting_review":
      return ["done", "done", "done", "done", "done", "done", "active"];
    case "rendering_video":
      return ["done", "done", "done", "done", "done", "done", "active"];
    case "complete":
      return ["done", "done", "done", "done", "done", "done", "done"];
    case "rejected":
      return ["done", "done", "failed", "pending", "pending", "pending", "pending"];
    case "failed":
      return ["failed", "pending", "pending", "pending", "pending", "pending", "pending"];
    default:
      return ["pending", "pending", "pending", "pending", "pending", "pending", "pending"];
  }
}

export function PipelineSteps({
  status,
  orientation = "horizontal",
}: {
  status: string;
  orientation?: "horizontal" | "vertical";
}) {
  const states = stepStates(status);
  const vertical = orientation === "vertical";

  return (
    <ol className={vertical ? "space-y-4" : "flex flex-wrap items-center gap-x-2 gap-y-2"}>
      {STEPS.map((step, i) => {
        const state = states[i];
        return (
          <li key={step.key} className="flex items-center gap-2" data-step={step.key} data-state={state}>
            {state === "done" && <CheckCircle2 className="h-4 w-4 text-green-400" />}
            {state === "active" && <Loader2 className="h-4 w-4 animate-spin text-amber-400" />}
            {state === "failed" && <XCircle className="h-4 w-4 text-red-400" />}
            {state === "pending" && <Circle className="h-4 w-4 text-muted-foreground/60" />}
            <span
              className={`text-sm font-medium ${
                state === "active"
                  ? "text-amber-300"
                  : state === "done"
                    ? "text-foreground"
                    : state === "failed"
                      ? "text-red-300"
                      : "text-muted-foreground"
              }`}
            >
              {step.label}
            </span>
            {!vertical && i < STEPS.length - 1 && <span className="mx-1 h-px w-6 bg-muted" />}
          </li>
        );
      })}
    </ol>
  );
}
