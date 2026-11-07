import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from src.temporal.activities.audio import AudioInput, generate_audio_activity
    from src.temporal.activities.blender import BlenderInput, blender_activity
    from src.temporal.activities.lifecycle import FinalizeInput, finalize_job_activity
    from src.temporal.activities.render import (
        FinalRenderInput,
        ShotVisualInput,
        VisualsInput,
        generate_shot_visual_activity,
        render_final_video_activity,
        start_visuals_activity,
        visual_concurrency_activity,
    )
    from src.temporal.activities.qa import (
        QASettingsInput,
        ShotQAInput,
        ShotsReviewInput,
        qa_repair_activity,
        qa_settings_activity,
        shots_review_gate_activity,
    )
    from src.temporal.activities.research import ResearchInput, research_activity
    from src.temporal.activities.script import ScriptInput, generate_script_activity
    from src.temporal.activities.shots import PlanShotsInput, plan_shots_activity


@dataclass
class CreateVideoInput:
    job_id: str
    project_id: str


@dataclass
class CreateVideoProgress:
    stage: str = "starting"
    gate_id: str | None = None
    decision: str | None = None  # "approved" | "rejected"
    errors: list[str] = field(default_factory=list)
    shots_total: int = 0
    shots_done: int = 0
    warnings: list[str] = field(default_factory=list)


RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(seconds=20),
    maximum_attempts=3,
)


@workflow.defn
class CreateVideoWorkflow:
    """
    Week 2 production pipeline (Day 8, replaces HelloWorkflow):

        Research -> Script -> (wait for human gate) -> Audio
                 -> Shot planning (ShotSpecs per beat) -> Blender stage
                 -> Visuals (image + clip per shot) -> Final render (MP4) -> finalize

    Physics before pixels (Week 3 Day 12): the Blender stage runs for
    every planned shot before any pixel stage may start; the Tool Gateway
    enforces it independently (MISSING_DEPENDENCY).

    The pause is genuine (AVOS-03 v1.1 s5/s7): after the script activity
    opens the gate, workflow.wait_condition() blocks with no polling and
    no timers until the `gate_decided` signal arrives from
    POST /gates/{id}/approve|reject. Every exit path finalizes the Job
    (completed / cancelled-on-reject / failed), so a job can never be
    left RUNNING forever.
    """

    def __init__(self) -> None:
        self._progress = CreateVideoProgress()
        self._approved: bool | None = None
        self._decisions: list[bool] = []

    @workflow.signal
    def gate_decided(self, approved: bool) -> None:
        # One signal per gate, in order: [script approval, shots review]. For the script, only the first counts.
        self._decisions.append(approved)
        if self._approved is None:
            self._approved = approved

    @workflow.query
    def progress(self) -> CreateVideoProgress:
        return self._progress

    @workflow.run
    async def run(self, inp: CreateVideoInput) -> dict[str, Any]:
        info = workflow.info()

        try:
            self._progress.stage = "research"
            notes: list[str] = await workflow.execute_activity(
                research_activity,
                ResearchInput(job_id=inp.job_id, project_id=inp.project_id),
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RETRY,
            )

            self._progress.stage = "script"
            gate_id: str = await workflow.execute_activity(
                generate_script_activity,
                ScriptInput(
                    project_id=inp.project_id,
                    research_notes=notes,
                    workflow_id=info.workflow_id,
                ),
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RETRY,
            )
            self._progress.gate_id = gate_id

            self._progress.stage = "awaiting_approval"
            await workflow.wait_condition(lambda: self._approved is not None)
            self._progress.decision = "approved" if self._approved else "rejected"

            if not self._approved:
                output = {"status": "REJECTED", "gate_id": gate_id}
                await self._finalize(inp, "rejected", output)
                self._progress.stage = "rejected"
                return output

            self._progress.stage = "audio"
            audio: dict[str, Any] = await workflow.execute_activity(
                generate_audio_activity,
                AudioInput(project_id=inp.project_id, gate_id=gate_id),
                start_to_close_timeout=timedelta(minutes=10),
                retry_policy=RETRY,
            )

            self._progress.stage = "shots"
            shots: list[dict[str, Any]] = await workflow.execute_activity(
                plan_shots_activity,
                PlanShotsInput(project_id=inp.project_id, audio=audio),
                start_to_close_timeout=timedelta(minutes=3),
                retry_policy=RETRY,
            )

            self._progress.stage = "blender"
            physics: list[dict[str, Any]] = await workflow.execute_activity(
                blender_activity,
                BlenderInput(project_id=inp.project_id),
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RETRY,
            )

            self._progress.stage = "visuals"
            pending: list[str] = await workflow.execute_activity(
                start_visuals_activity,
                VisualsInput(project_id=inp.project_id),
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RETRY,
            )
            self._progress.shots_total = len(pending)
            visuals: list[dict[str, Any]] = []
            if workflow.patched("parallel-visuals-v12"):
                # GPU Scheduler: several shots at once (spread over the GPUs), in shot order in the output.
                limit: int = await workflow.execute_activity(
                    visual_concurrency_activity,
                    VisualsInput(project_id=inp.project_id),
                    start_to_close_timeout=timedelta(seconds=30),
                    retry_policy=RETRY,
                )
                visuals = await self._visuals_parallel(inp, pending, max(1, limit))
            else:
                for number, shot_id in enumerate(pending, start=1):
                    result = await self._one_visual(inp, number, shot_id)
                    if result is not None:
                        visuals.append(result)
                    self._progress.shots_done = number

            qa_results: list[dict[str, Any]] = []
            if workflow.patched("qa-repair-v12"):
                qa_cfg: dict[str, Any] = await workflow.execute_activity(
                    qa_settings_activity, QASettingsInput(project_id=inp.project_id),
                    start_to_close_timeout=timedelta(seconds=30), retry_policy=RETRY,
                )
                if qa_cfg.get("auto_qa"):
                    # QA agent → PASS, or FAIL → repair agent → GPU → QA again (bounded by the generation limit)
                    self._progress.stage = "qa"
                    qa_results = await self._qa_parallel(inp, [v["shot_id"] for v in visuals if v.get("shot_id")])
                    for r in qa_results:
                        if r.get("status") == "NEEDS_REVIEW":
                            self._progress.warnings.append(
                                f"Shot {int(r.get('shot_index', 0)) + 1}: QA still failing after {r.get('repairs', 0)} "
                                "repair(s); its last version is used. Review it in the Studio."
                            )
                if qa_cfg.get("review_shots"):
                    self._progress.stage = "awaiting_shots_review"
                    review_gate: str = await workflow.execute_activity(
                        shots_review_gate_activity,
                        ShotsReviewInput(project_id=inp.project_id, workflow_id=info.workflow_id, results=qa_results),
                        start_to_close_timeout=timedelta(minutes=2), retry_policy=RETRY,
                    )
                    await workflow.wait_condition(lambda: len(self._decisions) >= 2)
                    if not self._decisions[1]:
                        output = {"status": "REJECTED", "gate_id": review_gate, "stage": "shots_review",
                                  "visuals": visuals, "qa": qa_results, "warnings": self._progress.warnings}
                        await self._finalize(inp, "rejected", output)
                        self._progress.stage = "rejected"
                        return output

            self._progress.stage = "render"
            final_video: dict[str, Any] = await workflow.execute_activity(
                render_final_video_activity,
                FinalRenderInput(project_id=inp.project_id, audio=audio),
                start_to_close_timeout=timedelta(minutes=30),
                retry_policy=RETRY,
            )

            output = {
                "status": "COMPLETED",
                "gate_id": gate_id,
                "research_notes": notes,
                "audio": audio,
                "shots": shots,
                "physics": physics,
                "visuals": visuals,
                "qa": qa_results,
                "final_video": final_video,
                "warnings": self._progress.warnings,
            }
            await self._finalize(inp, "completed", output)
            self._progress.stage = "complete"
            return output

        except ActivityError as exc:
            cause = exc.cause
            message = str(cause.message if isinstance(cause, ApplicationError) else cause or exc)
            failed_stage = self._progress.stage
            self._progress.errors.append(message)
            self._progress.stage = "failed"
            await self._finalize(inp, "failed", {"stage_failed": failed_stage}, message)
            raise ApplicationError(f"CreateVideoWorkflow failed: {message}", non_retryable=True) from exc

    async def _one_visual(self, inp: CreateVideoInput, number: int, shot_id: str) -> dict[str, Any] | None:
        try:
            return await workflow.execute_activity(
                generate_shot_visual_activity,
                ShotVisualInput(project_id=inp.project_id, shot_id=shot_id),
                start_to_close_timeout=timedelta(minutes=35),
                retry_policy=RETRY,
            )
        except ActivityError as exc:
            cause = exc.cause
            if isinstance(cause, ApplicationError) and cause.non_retryable:
                raise  # misconfiguration: every shot would fail the same way
            # A provider hiccup on one shot shouldn't cost the
            # whole video: that shot falls back to its still
            # (animated), and the warning is shown on the project.
            message = str(cause.message if isinstance(cause, ApplicationError) else cause or exc)
            self._progress.warnings.append(
                f"Shot {number}: visual generation failed ({message}); used an animated still instead."
            )
            return None

    async def _visuals_parallel(self, inp: CreateVideoInput, pending: list[str], limit: int) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(limit)
        results: list[dict[str, Any] | None] = [None] * len(pending)

        async def run(i: int, shot_id: str) -> None:
            async with sem:
                results[i] = await self._one_visual(inp, i + 1, shot_id)
                self._progress.shots_done += 1

        tasks = [asyncio.ensure_future(run(i, sid)) for i, sid in enumerate(pending)]
        try:
            await asyncio.gather(*tasks)
        except BaseException:
            for t in tasks:
                t.cancel()
            raise
        return [r for r in results if r is not None]

    async def _qa_parallel(self, inp: CreateVideoInput, shot_ids: list[str], limit: int = 4) -> list[dict[str, Any]]:
        sem = asyncio.Semaphore(limit)
        out: list[dict[str, Any] | None] = [None] * len(shot_ids)

        async def run(i: int, shot_id: str) -> None:
            async with sem:
                try:
                    out[i] = await workflow.execute_activity(
                        qa_repair_activity, ShotQAInput(project_id=inp.project_id, shot_id=shot_id),
                        start_to_close_timeout=timedelta(minutes=120), retry_policy=RETRY,
                    )
                except ActivityError as exc:      # QA trouble never blocks the video
                    out[i] = {"shot_id": shot_id, "shot_index": i, "status": "SKIPPED", "reason": str(exc.cause or exc)}

        await asyncio.gather(*(run(i, sid) for i, sid in enumerate(shot_ids)))
        return [r for r in out if r is not None]

    async def _finalize(
        self,
        inp: CreateVideoInput,
        outcome: str,
        output: dict[str, Any],
        error: str | None = None,
    ) -> None:
        await workflow.execute_activity(
            finalize_job_activity,
            FinalizeInput(
                job_id=inp.job_id,
                project_id=inp.project_id,
                outcome=outcome,
                output=output,
                error=error,
            ),
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5),
        )
