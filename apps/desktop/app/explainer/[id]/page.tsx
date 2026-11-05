"use client";

import { use } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { ProjectView } from "@/components/explainer/ProjectView";

export default function ExplainerProject({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AppShell header={<span className="text-lg font-semibold">Explainer Studio</span>}>
      <ProjectView id={id} />
    </AppShell>
  );
}
