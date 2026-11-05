"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  DollarSign,
  Film,
  FolderX,
  Hourglass,
  Loader2,
  Monitor,
  Play,
  RefreshCw,
  Terminal,
  XCircle,
  Zap,
} from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { FinalVideoCard } from "@/components/projects/FinalVideoCard";
import { PipelineSteps } from "@/components/projects/PipelineSteps";
import { ProjectDetailSkeleton } from "@/components/projects/ProjectDetailSkeleton";
import { StatusBadge } from "@/components/projects/StatusBadge";
import { formatDuration, statusStyle, timeAgo } from "@/components/projects/status";
import { queryKeys, useProject, useProjectJobs } from "@/hooks/queries";
import { useLiveProject } from "@/hooks/useLiveProject";
import { ApiError, assetsApi, projectsApi } from "@/lib/api";
import { VIDEO_PROVIDERS, type Job } from "@/types";

const JOB_BADGE: Record<string, { label: string; cls: string; icon: typeof Loader2 }> = {
  queued: { label: "QUEUED", cls: "bg-slate-500/20 text-foreground/90 border-slate-500/30", icon: Clock },
  running: { label: "RUNNING", cls: "bg-amber-500/20 text-amber-300 border-amber-500/30", icon: Loader2 },
  completed: { label: "COMPLETED", cls: "bg-green-500/20 text-green-300 border-green-500/30", icon: CheckCircle2 },
  cancelled: { label: "STOPPED", cls: "bg-orange-500/20 text-orange-300 border-orange-500/30", icon: XCircle },
  failed: { label: "FAILED", cls: "bg-red-500/20 text-red-300 border-red-500/30", icon: AlertCircle },
};

function JobCard({ job }: { job: Job }) {
  const badge = JOB_BADGE[job.status] ?? JOB_BADGE.queued;
  const BadgeIcon = badge.icon;
  const audio = job.output?.audio;

  return (
    <div className="rounded-2xl border border-border bg-card/50 p-6" data-testid="job-card">
      <div className="mb-4 flex items-center justify-between">
        <h3 className="flex items-center gap-2 text-lg font-semibold text-foreground">
          <Terminal className="h-5 w-5 text-amber-500" /> Generation job
        </h3>
        <span
          data-testid="job-status"
          className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${badge.cls}`}
        >
          <BadgeIcon className={`h-3 w-3 ${job.status === "running" ? "animate-spin" : ""}`} />
          {badge.label}
        </span>
      </div>

      <dl className="space-y-2 rounded-xl border border-border bg-muted/50 p-4 text-sm">
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Job ID</dt>
          <dd className="truncate font-mono text-foreground">{job.id}</dd>
        </div>
        {job.workflow_id && (
          <div className="flex justify-between gap-4">
            <dt className="text-muted-foreground">Temporal workflow</dt>
            <dd className="truncate font-mono text-blue-400">{job.workflow_id}</dd>
          </div>
        )}
        <div className="flex justify-between gap-4">
          <dt className="text-muted-foreground">Started</dt>
          <dd className="text-foreground/90">{timeAgo(job.started_at ?? job.created_at)}</dd>
        </div>
        {job.error_message && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-2 text-xs text-red-300">
            {job.error_message}
          </div>
        )}
      </dl>

      {audio && (
        <div className="mt-4 space-y-3 rounded-xl border border-green-500/20 bg-green-500/5 p-4">
          <p className="text-sm font-medium text-green-300">
            Narration ready · {formatDuration(audio.duration_seconds)} · {audio.word_count} words ·{" "}
            {audio.beats.length} beats
          </p>
          <audio controls src={assetsApi.contentUrl(audio.asset_id)} className="w-full" />
        </div>
      )}
    </div>
  );
}

export default function ProjectDetailPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const queryClient = useQueryClient();

  const { data: project, isLoading, isError, error, refetch } = useProject(projectId);
  const { data: jobs } = useProjectJobs(projectId);
  const { connected } = useLiveProject(projectId);

  const generate = useMutation({
    mutationFn: () => projectsApi.generate(projectId),
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.jobs(projectId) });
      queryClient.invalidateQueries({ queryKey: queryKeys.job(res.job_id) });
      queryClient.invalidateQueries({ queryKey: queryKeys.project(projectId) });
    },
  });

  if (isLoading) return <ProjectDetailSkeleton />;

  if (isError || !project) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <AppShell>
        <div className="flex min-h-full items-center justify-center p-8">
          <div className="max-w-md text-center">
            {notFound ? (
              <FolderX className="mx-auto mb-4 h-12 w-12 text-amber-500" />
            ) : (
              <AlertCircle className="mx-auto mb-4 h-12 w-12 text-red-500" />
            )}
            <h2 className="mb-2 text-xl font-bold text-foreground">
              {notFound ? "Project not found" : "Unable to load project"}
            </h2>
            {!notFound && error instanceof Error && <p className="mb-4 text-sm text-muted-foreground">{error.message}</p>}
            <div className="flex justify-center gap-3">
              {!notFound && (
                <button
                  onClick={() => refetch()}
                  className="flex items-center gap-2 rounded-xl border border-border bg-muted px-5 py-2.5 font-medium text-foreground hover:bg-accent"
                >
                  <RefreshCw className="h-4 w-4" /> Retry
                </button>
              )}
              <Link href="/facts" className="rounded-xl bg-amber-500 px-5 py-2.5 font-medium text-white">
                Back to Facts
              </Link>
            </div>
          </div>
        </div>
      </AppShell>
    );
  }

  const latestJob = jobs?.[0];
  const s = statusStyle(project.status);
  const busy = s.active || generate.isPending;
  const canGenerate = !busy;
  const generateLabel =
    project.status === "planning" ? "Generate Video" : project.status === "complete" ? "Generate again" : "Retry";

  return (
    <AppShell
      header={
        <>
          <Link href="/facts" className="flex items-center gap-2 text-muted-foreground transition-colors hover:text-foreground">
            <ArrowLeft className="h-4 w-4" />
            <span className="text-sm font-medium">Facts</span>
          </Link>
          <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
            <span className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-slate-600"}`} />
            {connected ? "Live" : "Offline"}
          </span>
        </>
      }
    >
      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-6 p-4 md:p-8 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <div className="rounded-2xl border border-border bg-card/50 p-8">
            <div className="mb-2 flex flex-wrap items-start justify-between gap-3">
              <h1 className="text-3xl font-bold text-foreground" data-testid="project-name">
                {project.name}
              </h1>
              <StatusBadge status={project.status} />
            </div>
            <p className="mb-6 text-lg text-muted-foreground">{project.topic}</p>

            <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="flex items-center gap-3">
                <Clock className="h-5 w-5 text-muted-foreground" />
                <span className="text-foreground/90">{formatDuration(project.duration_seconds)}</span>
              </div>
              <div className="flex items-center gap-3">
                <Monitor className="h-5 w-5 text-muted-foreground" />
                <span className="text-foreground/90">{project.aspect_ratio}</span>
              </div>
              <div className="flex items-center gap-3">
                <DollarSign className="h-5 w-5 text-muted-foreground" />
                <span className="text-foreground/90">
                  ${project.budget_spent.toFixed(2)}
                  {project.budget_limit ? ` / $${project.budget_limit.toFixed(2)}` : " spent"}
                </span>
              </div>
              <div className="flex items-center gap-3 sm:col-span-3">
                <Film className="h-5 w-5 text-muted-foreground" />
                <span className="text-sm text-foreground/90">
                  {VIDEO_PROVIDERS.find((p) => p.value === (project.video_provider ?? ""))?.label ??
                    project.video_provider}
                </span>
              </div>
            </div>

            <div className="border-t border-border pt-6">
              <p className={`mb-4 text-sm ${s.text}`}>{s.description}</p>

              {project.status === "awaiting_review" && (
                <Link
                  href={`/studio/${project.id}`}
                  className="mb-4 flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-200 transition-colors hover:bg-amber-500/20"
                >
                  <span className="flex items-center gap-2 text-sm font-medium">
                    <Hourglass className="h-4 w-4" /> The shots are ready for your review
                  </span>
                  <span className="text-sm font-semibold">Review in Studio →</span>
                </Link>
              )}
              {project.status === "awaiting_approval" && (
                <Link
                  href={`/studio/${project.id}`}
                  className="mb-4 flex items-center justify-between rounded-xl border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-amber-200 transition-colors hover:bg-amber-500/20"
                >
                  <span className="flex items-center gap-2 text-sm font-medium">
                    <Hourglass className="h-4 w-4" /> The script is ready for your review
                  </span>
                  <span className="text-sm font-semibold">Review in Studio →</span>
                </Link>
              )}

              <div className="flex flex-wrap gap-3">
                <button
                  onClick={() => generate.mutate()}
                  disabled={!canGenerate}
                  data-testid="generate-button"
                  className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-6 py-3 font-medium text-white shadow-lg shadow-amber-500/25 transition-all hover:from-amber-600 hover:to-orange-600 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {busy ? <Loader2 className="h-5 w-5 animate-spin" /> : <Zap className="h-5 w-5" />}
                  {generate.isPending ? "Starting..." : busy ? "In progress" : generateLabel}
                </button>
                <Link
                  href={`/studio/${project.id}`}
                  className="flex items-center gap-2 rounded-xl border border-border bg-muted px-6 py-3 font-medium text-foreground transition-all hover:bg-accent"
                >
                  <Play className="h-5 w-5" /> Open Studio
                </Link>
              </div>

              {generate.isError && (
                <p className="mt-3 flex items-center gap-2 text-sm text-red-400" role="alert">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  {generate.error instanceof Error ? generate.error.message : "Failed to start generation."}
                </p>
              )}
            </div>
          </div>

          {latestJob?.output?.final_video && (
            <FinalVideoCard
              video={latestJob.output.final_video}
              projectName={project.name}
              warnings={latestJob.output.warnings ?? []}
            />
          )}

          {latestJob?.status === "completed" && !latestJob.output?.final_video && (
            <div className="rounded-2xl border border-sky-500/30 bg-sky-500/5 p-5 text-sm text-sky-200">
              This project was generated before video rendering was added, so it has no video file.
              Click <span className="font-semibold">Generate again</span> to make the full video with real
              narration.
            </div>
          )}

          {latestJob && <JobCard job={latestJob} />}
        </div>

        <div className="lg:col-span-1">
          <div className="sticky top-8 rounded-2xl border border-border bg-card/50 p-6">
            <h2 className="mb-6 text-lg font-semibold text-foreground">Production</h2>
            <PipelineSteps status={project.status} orientation="vertical" />
          </div>
        </div>
      </div>
    </AppShell>
  );
}

