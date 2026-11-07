from typing import Any


class ConstitutionViolationError(RuntimeError):
    """Raised when a tool call violates a hard AVOS constitutional rule."""

    code = "CONSTITUTION_VIOLATION"

    def __init__(self, message: str, *, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(message)

    def to_dict(self) -> dict[str, str]:
        return {
            "code": self.code,
            "message": str(self),
            "tool_name": self.tool_name,
        }


class MissingDependencyError(ConstitutionViolationError):
    """
    A tool was called before the stage it depends on completed
    (AVOS-03 v1.1 s9.3, physics-before-pixels): e.g. generate_video_shot
    before the Blender stage produced a physics proxy for that shot.
    """

    code = "MISSING_DEPENDENCY"

    def __init__(self, message: str, *, tool_name: str, dependency: str) -> None:
        self.dependency = dependency
        super().__init__(f"[MISSING_DEPENDENCY] {message}", tool_name=tool_name)

    def to_dict(self) -> dict[str, str]:
        return {**super().to_dict(), "dependency": self.dependency}


# Pixel-generating tools that must be grounded by a Blender physics proxy.
PHYSICS_GATED_TOOLS = frozenset({"generate_video_shot"})


def check_constitution(
    tool_name: str,
    tool_input: dict[str, Any],
) -> None:
    """
    Stateless hard rules (no database access).

    Physics-before-pixels, part 1: a pixel-generating call must *name*
    the physics proxy it is grounded on. Part 2 - that the proxy really
    exists, belongs to the shot, and is for the shot's current ShotSpec
    version - needs the database and lives in the api
    (src/services/physics_gate.py), which runs this check first.
    """
    if tool_name in PHYSICS_GATED_TOOLS:
        if not tool_input.get("physics_proxy_asset_id"):
            raise MissingDependencyError(
                f"'{tool_name}' requires a physics_proxy_asset_id: the Blender stage "
                "(run_blender_proxy) must complete for this shot before any pixels "
                "are generated.",
                tool_name=tool_name,
                dependency="run_blender_proxy",
            )
