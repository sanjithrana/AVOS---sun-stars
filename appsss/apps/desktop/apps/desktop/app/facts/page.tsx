"use client";

import { useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  FolderOpen,
  FolderPlus,
  Hourglass,
  Loader2,
  Plus,
  RefreshCw,
  Search,
  Sparkles,
  Wand2,
} from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { FactsComposer, type FactsComposerHandle } from "@/components/projects/FactsComposer";
import { ProjectCard } from "@/components/projects/ProjectCard";
import { queryKeys, useProjects } from "@/hooks/queries";
import { useLiveProject } from "@/hooks/useLiveProject";
import { ApiError, projectsApi } from "@/lib/api";
import { ACTIVE_PROJECT_STATUSES, type ProjectCreate } from "@/types";

function CardSkeleton() {
  return (
    <div className="animate-pulse overflow-hidden rounded-2xl border border-border bg-card/50">
      <div className="aspect-video bg-muted" />
      <div className="space-y-3 p-5">
        <div className="h-5 w-3/4 rounded bg-muted" />
        <div className="h-4 w-full rounded bg-muted" />
        <div className="h-4 w-1/2 rounded bg-muted" />
      </div>
    </div>
  );
}

export default function FactsPage() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [search, setSearch] = useState("");
  const composer = useRef<FactsComposerHandle>(null);

  const { data: projects, isLoading, isError, error, refetch, isFetching } = useProjects();
  const { connected } = useLiveProject(); // all projects: live status updates

  const createProject = useMutation({
    mutationFn: (data: ProjectCreate) => projectsApi.create(data),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.projects });
      router.push(`/project/${project.id}`);
    },
  });

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!projects) return [];
    if (!q) return projects;
    return projects.filter((p) => p.name.toLowerCase().includes(q) || p.topic.toLowerCase().includes(q));
  }, [projects, search]);

  const stats = [
    { label: "Total projects", value: projects?.length ?? 0, icon: FolderOpen, color: "from-blue-500 to-cyan-500" },
    {
      label: "In progress",
      value: projects?.filter((p) => ACTIVE_PROJECT_STATUSES.includes(p.status)).length ?? 0,
      icon: Loader2,
      color: "from-amber-500 to-orange-500",
    },
    {
      label: "Awaiting approval",
      value: projects?.filter((p) => p.status === "awaiting_approval" || p.status === "awaiting_review").length ?? 0,
      icon: Hourglass,
      color: "from-purple-500 to-pink-500",
    },
    {
      label: "Completed",
      value: projects?.filter((p) => p.status === "complete").length ?? 0,
      icon: CheckCircle2,
      color: "from-green-500 to-emerald-500",
    },
  ];

  const openForm = () => composer.current?.focus();

  const header = (
    <>
      <div className="relative hidden max-w-md flex-1 sm:block">
        <Search className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search projects..."
          className="w-full rounded-xl border border-border bg-muted/50 py-2.5 pl-11 pr-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-amber-500/50"
        />
      </div>
      <div className="flex items-center gap-3">
        <span className="hidden items-center gap-1.5 text-xs text-muted-foreground md:flex" title="Live updates">
          <span className={`h-2 w-2 rounded-full ${connected ? "bg-green-500" : "bg-slate-600"}`} />
          {connected ? "Live" : "Offline"}
        </span>
        <button
          onClick={openForm}
          className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2.5 text-sm font-medium text-white shadow-lg shadow-amber-500/25 transition-all hover:from-amber-600 hover:to-orange-600"
        >
          <Plus className="h-4 w-4" />
          <span className="hidden sm:inline">New Project</span>
        </button>
      </div>
    </>
  );

  return (
    <AppShell header={header}>
      <div className="mx-auto max-w-7xl space-y-8 p-4 md:p-8">
        <div>
          <h1 className="mb-2 text-2xl font-bold text-foreground md:text-3xl">Facts</h1>
          <p className="text-muted-foreground">Narrated fact videos: topic, script, voice, shots and the final video</p>
        </div>

        {isError ? (
          <div className="flex flex-col items-center gap-4 rounded-2xl border border-red-500/20 bg-red-500/5 p-10 text-center">
            <AlertCircle className="h-10 w-10 text-red-400" />
            <div>
              <h2 className="text-lg font-semibold text-foreground">Unable to load projects</h2>
              <p className="mt-1 max-w-lg text-sm text-muted-foreground">
                {error instanceof ApiError ? error.message : "Unexpected error."}
              </p>
            </div>
            <button
              onClick={() => refetch()}
              className="flex items-center gap-2 rounded-lg border border-border bg-muted px-4 py-2 text-sm font-medium text-foreground hover:bg-accent"
            >
              <RefreshCw className={`h-4 w-4 ${isFetching ? "animate-spin" : ""}`} /> Retry
            </button>
          </div>
        ) : (
          <>
            <section className="grid grid-cols-2 gap-4 md:gap-6 lg:grid-cols-4">
              {stats.map((stat) => (
                <div key={stat.label} className="rounded-2xl border border-border bg-card/50 p-4 md:p-6">
                  <div
                    className={`mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br md:h-12 md:w-12 ${stat.color} shadow-lg`}
                  >
                    <stat.icon className="h-5 w-5 text-white md:h-6 md:w-6" />
                  </div>
                  <p className="mb-1 text-2xl font-bold text-foreground md:text-3xl">{isLoading ? "–" : stat.value}</p>
                  <p className="text-xs text-muted-foreground md:text-sm">{stat.label}</p>
                </div>
              ))}
            </section>

            <section>
              <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold text-foreground md:text-xl">
                <Wand2 className="h-5 w-5 text-amber-400" />
                New video
              </h2>
              <FactsComposer
                ref={composer}
                onSubmit={(data) => createProject.mutate(data)}
                isSubmitting={createProject.isPending}
                error={createProject.error instanceof Error ? createProject.error.message : null}
              />
            </section>

            <section>
              <h2 className="mb-5 flex items-center gap-2 text-lg font-semibold text-foreground md:text-xl">
                <Sparkles className="h-5 w-5 text-amber-400" />
                Your Projects
              </h2>

              {isLoading ? (
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                  {[1, 2, 3].map((i) => (
                    <CardSkeleton key={i} />
                  ))}
                </div>
              ) : projects && projects.length === 0 ? (
                <div className="flex flex-col items-center gap-5 rounded-2xl border border-dashed border-border p-12 text-center">
                  <div className="flex h-16 w-16 items-center justify-center rounded-full bg-amber-500/10">
                    <FolderPlus className="h-8 w-8 text-amber-500" />
                  </div>
                  <div>
                    <h3 className="text-xl font-bold text-foreground">No projects yet</h3>
                    <p className="text-muted-foreground">Create your first AI production.</p>
                  </div>
                  <button
                    onClick={openForm}
                    className="flex items-center gap-2 rounded-xl bg-gradient-to-r from-amber-500 to-orange-500 px-4 py-2.5 text-sm font-medium text-white"
                  >
                    <Plus className="h-4 w-4" /> New Project
                  </button>
                </div>
              ) : filtered.length === 0 ? (
                <p className="py-10 text-center text-muted-foreground">No projects match &ldquo;{search}&rdquo;.</p>
              ) : (
                <div className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
                  {filtered.map((project) => (
                    <ProjectCard key={project.id} project={project} />
                  ))}
                </div>
              )}
            </section>
          </>
        )}
      </div>

    </AppShell>
  );
}
