"use client";

import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { GenerationMonitor } from "./GenerationMonitor";
import { QADashboard } from "./QADashboard";
import { ScriptApproval } from "./ScriptApproval";
import { ShotsReview } from "./ShotsReview";
import { ShotEditor } from "./ShotEditor";
import { ShotInfo } from "./ShotInfo";
import { Storyboard } from "./Storyboard";
import { StudioHeader } from "./StudioHeader";
import { Timeline } from "./Timeline";
import { queryKeys, useProjectGates, useProjectJobs, useProjectShots } from "@/hooks/queries";
import { useLiveProject } from "@/hooks/useLiveProject";
import { shotsApi } from "@/lib/api";
import type { Project, ScriptPayload } from "@/types";

const EMPTY_TEXT: Record<string, string> = {
  planning: "Start generation from the project page to create a script.",
  researching: "Agents are researching and writing the script…",
  planning_shots: "Planning shots and building physics proxies…",
  generating_visuals: "Generating an image and clip for every shot…",
  rendering_video: "Rendering the final video…",
  failed: "The last run failed. Retry from the project page.",
};

type Selection = { kind: "shot"; id: string } | { kind: "scene"; index: number } | null;

/**
 * Project Workspace: Storyboard + Timeline | Shot Editor (view, edit and regenerate a shot).
 * Week 3: the storyboard lists ShotSpecs (GET /projects/{id}/shots) once
 * they exist; the right panel shows the selected shot's ShotEditor, or
 * the script scene info before shots are planned.
 */
export function StudioShell({ project }: { project: Project }) {
  const { connected, notices } = useLiveProject(project.id);
  const { data: gates } = useProjectGates(project.id);
  const { data: jobs } = useProjectJobs(project.id);
  const { data: shotsData } = useProjectShots(project.id);
  const queryClient = useQueryClient();
  const [selection, setSelection] = useState<Selection>(null);

  const scriptGate = gates?.find((g) => g.gate_type === "script_approval");
  const reviewGate = gates?.find((g) => g.gate_type === "final_approval" && g.status === "pending");
  const script = scriptGate?.payload as ScriptPayload | undefined;
  const scenes = script?.scenes ?? [];
  const shots = shotsData ?? [];
  const latestJob = jobs?.[0];
  const audio = latestJob?.output?.audio;

  // Default selection: first shot once shots exist, else first scene.
  const selectedShot =
    selection?.kind === "shot" ? shots.find((s) => s.id === selection.id) : selection === null ? shots[0] : undefined;
  const selectedScene =
    selection?.kind === "scene" ? scenes.find((s) => s.index === selection.index) ?? scenes[0] : scenes[0];

  const plan = useMutation({
    mutationFn: () => shotsApi.plan(project.id),
    onSuccess: (planned) => {
      queryClient.setQueryData(queryKeys.shots(project.id), planned);
      if (planned[0]) setSelection({ kind: "shot", id: planned[0].id });
    },
  });
  const canPlan =
    shots.length === 0 && scriptGate?.status === "approved" && Boolean(audio?.beats?.length) &&
    project.status !== "planning_shots";

  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <StudioHeader project={project} connected={connected} hasVideo={Boolean(latestJob?.output?.final_video)} />

      {notices.length > 0 && (
        <div className="space-y-1 border-b border-amber-500/20 bg-amber-500/10 px-4 py-2">
          {notices.map((n) => (
            <p key={n.id} className="flex items-center gap-2 text-xs text-amber-200">
              <AlertTriangle className="h-3.5 w-3.5" /> {n.text}
            </p>
          ))}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <main className="flex min-w-0 flex-1 flex-col overflow-y-auto">
          {scriptGate && scriptGate.status === "pending" && (
            <div className="border-b border-border p-4">
              <ScriptApproval gate={scriptGate} />
            </div>
          )}
          {reviewGate && (
            <div className="border-b border-border p-4">
              <ShotsReview gate={reviewGate} onSelectShot={(id) => setSelection({ kind: "shot", id })} />
            </div>
          )}
          <Storyboard
            shots={shots}
            scenes={scenes}
            selectedShotId={selectedShot?.id ?? null}
            selectedSceneIndex={selectedShot ? null : selectedScene?.index ?? null}
            onSelectShot={(id) => setSelection({ kind: "shot", id })}
            onSelectScene={(index) => setSelection({ kind: "scene", index })}
            canPlan={canPlan}
            planning={plan.isPending}
            planError={plan.error ? plan.error.message : null}
            onPlan={() => plan.mutate()}
            emptyText={EMPTY_TEXT[project.status] ?? "No script yet."}
          />
          <GenerationMonitor projectId={project.id} shots={shots} />
          {selectedShot && <QADashboard key={selectedShot.id} shot={selectedShot} />}
          <Timeline audio={audio} />
        </main>

        <aside className="hidden w-96 shrink-0 border-l border-border bg-card/30 lg:block">
          {selectedShot ? (
            <ShotEditor key={selectedShot.id} shotId={selectedShot.id} />
          ) : (
            <ShotInfo
              scene={selectedScene}
              scenes={scenes}
              audio={audio}
              researchNotes={latestJob?.output?.research_notes}
            />
          )}
        </aside>
      </div>
    </div>
  );
}
