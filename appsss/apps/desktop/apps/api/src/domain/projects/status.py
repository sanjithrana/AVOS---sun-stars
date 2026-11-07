from enum import Enum


class ProjectStatus(str, Enum):
    """
    Project lifecycle for the Week 2 production pipeline.

        planning -> researching -> awaiting_approval -> generating_audio
                 -> planning_shots (ShotSpecs + Blender stage, Week 3)
                 -> generating_visuals (image + clip per shot)
                 -> rendering_video (final MP4) -> complete
                         \\-> rejected        (human rejected the script)
        any step --------> failed           (unrecoverable error)

    Kept as plain strings in the DB (projects.status) so adding stages in
    Week 3 (characters, world, shots...) needs no migration.
    """

    PLANNING = "planning"
    RESEARCHING = "researching"
    AWAITING_APPROVAL = "awaiting_approval"
    GENERATING_AUDIO = "generating_audio"
    PLANNING_SHOTS = "planning_shots"
    GENERATING_VISUALS = "generating_visuals"
    AWAITING_REVIEW = "awaiting_review"      # shots ready, waiting for a person before the final render (optional)
    RENDERING_VIDEO = "rendering_video"
    COMPLETE = "complete"
    REJECTED = "rejected"
    FAILED = "failed"


ACTIVE_STATUSES = frozenset(
    {
        ProjectStatus.RESEARCHING.value,
        ProjectStatus.AWAITING_APPROVAL.value,
        ProjectStatus.GENERATING_AUDIO.value,
        ProjectStatus.PLANNING_SHOTS.value,
        ProjectStatus.GENERATING_VISUALS.value,
        ProjectStatus.AWAITING_REVIEW.value,
        ProjectStatus.RENDERING_VIDEO.value,
    }
)
