"use client";

import Link from "next/link";
import { ArrowRight, Clock, Film, Monitor } from "lucide-react";
import type { Project } from "@/types";
import { StatusBadge } from "./StatusBadge";
import { formatDuration, statusStyle, timeAgo } from "./status";

export function ProjectCard({ project }: { project: Project }) {
  const s = statusStyle(project.status);
  const StatusIcon = s.icon;

  return (
    <Link
      href={`/project/${project.id}`}
      data-testid="project-card"
      className="group flex flex-col overflow-hidden rounded-2xl border border-border bg-card/50 transition-all duration-300 hover:border-amber-500/30 hover:shadow-xl hover:shadow-amber-500/10"
    >
      <div className="relative flex aspect-video items-center justify-center bg-gradient-to-br from-slate-800 via-slate-900 to-slate-950">
        <div className={`flex h-16 w-16 items-center justify-center rounded-full border ${s.bg} ${s.border}`}>
          {project.status === "planning" ? (
            <Film className="h-8 w-8 text-muted-foreground" />
          ) : (
            <StatusIcon className={`h-8 w-8 ${s.text} ${s.active ? "animate-pulse" : ""}`} />
          )}
        </div>
        <div className="absolute right-3 top-3">
          <StatusBadge status={project.status} className="backdrop-blur-sm" />
        </div>
        {s.progress > 0 && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-muted/50">
            <div className={`h-full ${s.bar} transition-all duration-500`} style={{ width: `${s.progress}%` }} />
          </div>
        )}
      </div>

      <div className="flex flex-1 flex-col gap-3 p-5">
        <div>
          <h3 className="line-clamp-1 text-lg font-semibold text-foreground transition-colors group-hover:text-amber-300">
            {project.name}
          </h3>
          <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{project.topic}</p>
        </div>

        <p className={`text-xs ${s.text}`}>{s.description}</p>

        <div className="mt-auto flex items-center justify-between border-t border-border pt-3 text-xs text-muted-foreground">
          <span className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" /> {formatDuration(project.duration_seconds)}
            </span>
            <span className="flex items-center gap-1">
              <Monitor className="h-3.5 w-3.5" /> {project.aspect_ratio}
            </span>
          </span>
          <span className="flex items-center gap-1 text-muted-foreground group-hover:text-amber-300">
            {timeAgo(project.updated_at)} <ArrowRight className="h-3.5 w-3.5" />
          </span>
        </div>
      </div>
    </Link>
  );
}
