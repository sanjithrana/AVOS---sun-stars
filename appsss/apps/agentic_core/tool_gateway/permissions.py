from enum import StrEnum

from tool_gateway.registry import ToolRegistry


class AgentRole(StrEnum):
    DIRECTOR = "director"
    RESEARCH_AGENT = "research_agent"
    NARRATIVE_AGENT = "narrative_agent"
    PHYSICS_AGENT = "physics_agent"
    VIDEO_AGENT = "video_agent"
    AUDIO_AGENT = "audio_agent"
    QA_AGENT = "qa_agent"
    REPAIR_AGENT = "repair_agent"
    LEARNING_AGENT = "learning_agent"


class PermissionResult(StrEnum):
    AUTHORIZED = "AUTHORIZED"
    PERMISSION_DENIED = "PERMISSION_DENIED"


ROLE_TOOL_SCOPES: dict[AgentRole, frozenset[str]] = {
    AgentRole.DIRECTOR: frozenset(
        {
            "memory",
            "planning",
            "scheduling",
            "approval",
        }
    ),
    AgentRole.RESEARCH_AGENT: frozenset({"research"}),
    AgentRole.NARRATIVE_AGENT: frozenset({"script"}),
    AgentRole.PHYSICS_AGENT: frozenset({"blender"}),
    AgentRole.VIDEO_AGENT: frozenset({"comfyui"}),
    AgentRole.AUDIO_AGENT: frozenset({"audio"}),
    AgentRole.QA_AGENT: frozenset({"qa"}),
    AgentRole.REPAIR_AGENT: frozenset({"repair"}),
    AgentRole.LEARNING_AGENT: frozenset(
        {
            "analytics",
            "memory",
        }
    ),
}


def get_tool_scopes(role: AgentRole) -> frozenset[str]:
    return ROLE_TOOL_SCOPES.get(role, frozenset())


def has_tool_scope(
    role: AgentRole,
    scope: str,
) -> bool:
    return scope in get_tool_scopes(role)


def check_permission(
    registry: ToolRegistry,
    role: AgentRole,
    tool_name: str,
) -> PermissionResult:
    try:
        tool = registry.get(tool_name)
    except KeyError:
        return PermissionResult.PERMISSION_DENIED

    if has_tool_scope(role, tool.permission):
        return PermissionResult.AUTHORIZED

    return PermissionResult.PERMISSION_DENIED
