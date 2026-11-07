"use client";

import { use } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { ProjectView } from "@/components/stickman/ProjectView";

export default function StickmanProject({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  return (
    <AppShell header={<span className="text-lg font-semibold">Stickman Studio</span>}>
      <ProjectView id={id} />
    </AppShell>
  );
}
