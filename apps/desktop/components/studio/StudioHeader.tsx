import Link from "next/link";
import { ChevronLeft, DollarSign, Film } from "lucide-react";
import { StatusBadge } from "@/components/projects/StatusBadge";
import { PipelineSteps } from "@/components/projects/PipelineSteps";
import type { Project } from "@/types";

export function StudioHeader({
  project,
  connected,
  hasVideo = false,
}: {
  project: Project;
  connected: boolean;
  hasVideo?: boolean;
}) {
  return (
    <header className="border-b border-border bg-card/40">
      <div className="flex h-14 items-center justify-between gap-4 px-4">
        <div className="flex min-w-0 items-center gap-3">
          <Link
            href={`/project/${project.id}`}
            aria-label="Back to project"
            className="rounded-lg p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <ChevronLeft className="h-5 w-5" />
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold text-foreground">{project.name}</h1>
            <p className="truncate text-xs text-muted-foreground">{project.topic}</p>
          </div>
          <StatusBadge status={project.status} />
        </div>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          {hasVideo && (
            <Link
              href={`/project/${project.id}`}
              className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 px-3 py-1.5 font-medium text-white hover:from-amber-600 hover:to-orange-600"
            >
              <Film className="h-3.5 w-3.5" /> Watch video
            </Link>
          )}
          <span className="hidden items-center gap-1 sm:flex">
            <DollarSign className="h-3.5 w-3.5" />
            {project.budget_spent.toFixed(2)}
            {project.budget_limit ? ` / ${project.budget_limit.toFixed(2)}` : ""}
          </span>
          <span className="flex items-center gap-1.5" data-testid="live-indicator">
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-slate-600"}`} />
            {connected ? "Live" : "Offline"}
          </span>
        </div>
      </div>
      <div className="border-t border-border/60 px-4 py-2.5">
        <PipelineSteps status={project.status} />
      </div>
    </header>
  );
}
