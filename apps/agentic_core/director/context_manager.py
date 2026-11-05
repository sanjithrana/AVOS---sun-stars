from pydantic import BaseModel, ConfigDict, Field


class ProjectSummary(BaseModel):
    """
    Compact summary of a project's current state, assembled for the
    Director before it makes a decision.

    Deliberately DB-agnostic: agentic_core has no SQLAlchemy/session
    dependency, so the api layer (src/services/director_service.py)
    reads the ORM Project and calls build_project_summary() with plain
    data. This keeps the agent logic unit-testable without a database.
    """

    model_config = ConfigDict(extra="forbid")

    project_id: str
    topic: str
    duration_seconds: int
    aspect_ratio: str
    status: str
    budget_limit: float | None = None
    budget_spent: float = 0
    prior_memory: list[str] = Field(default_factory=list)


def build_project_summary(
    *,
    project_id: str,
    topic: str,
    duration_seconds: int,
    aspect_ratio: str,
    status: str,
    budget_limit: float | None = None,
    budget_spent: float = 0,
    prior_memory: list[str] | None = None,
) -> ProjectSummary:
    return ProjectSummary(
        project_id=project_id,
        topic=topic,
        duration_seconds=duration_seconds,
        aspect_ratio=aspect_ratio,
        status=status,
        budget_limit=budget_limit,
        budget_spent=budget_spent,
        prior_memory=prior_memory or [],
    )
