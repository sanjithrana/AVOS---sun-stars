"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { AlertCircle, FolderX } from "lucide-react";
import { ProjectDetailSkeleton } from "@/components/projects/ProjectDetailSkeleton";
import { StudioShell } from "@/components/studio/StudioShell";
import { useProject } from "@/hooks/queries";
import { ApiError } from "@/lib/api";

export default function StudioPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { data: project, isLoading, isError, error } = useProject(projectId);

  if (isLoading) return <ProjectDetailSkeleton />;

  if (isError || !project) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="flex min-h-screen items-center justify-center bg-background p-8 text-foreground">
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
          <Link href="/facts" className="inline-block rounded-xl bg-amber-500 px-6 py-2.5 font-medium text-white">
            Back to Projects
          </Link>
        </div>
      </div>
    );
  }

  return <StudioShell project={project} />;
}
