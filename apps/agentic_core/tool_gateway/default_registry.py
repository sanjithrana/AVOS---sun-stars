from agentic_core.tool_gateway.tools.generate_audio import GenerateAudioTool
from agentic_core.tool_gateway.tools.generate_script import GenerateScriptTool
from agentic_core.tool_gateway.tools.qa_tools import APPROVE_SHOT, REPAIR_SHOT, RUN_QA_COMMITTEE
from agentic_core.tool_gateway.tools.research_topic import ResearchTopicTool
from agentic_core.tool_gateway.tools.search_memory import SearchMemoryTool
from agentic_core.tool_gateway.tools.shotspec_tools import (
    ASSEMBLE_VIDEO,
    CREATE_SHOT_SPEC,
    GENERATE_VIDEO_SHOT,
    GET_WORLD_STATE,
    RUN_BLENDER_PROXY,
    VALIDATE_SHOT_SPEC,
)
from agentic_core.tool_gateway.tools.submit_video_generation import (
    SubmitVideoGenerationTool,
)
from tool_gateway.builtin_tools import ping_tool
from tool_gateway.registry import ToolRegistry


def create_default_registry() -> ToolRegistry:
    """Every tool an agent may dispatch (Weeks 1-3)."""
    registry = ToolRegistry()

    registry.register(ping_tool())
    registry.register(SubmitVideoGenerationTool.schema)
    registry.register(SearchMemoryTool.schema)
    registry.register(ResearchTopicTool.schema)
    registry.register(GenerateScriptTool.schema)
    registry.register(GenerateAudioTool.schema)
    registry.register(CREATE_SHOT_SPEC)
    registry.register(VALIDATE_SHOT_SPEC)
    registry.register(GET_WORLD_STATE)
    registry.register(RUN_BLENDER_PROXY)
    registry.register(GENERATE_VIDEO_SHOT)
    registry.register(RUN_QA_COMMITTEE)
    registry.register(REPAIR_SHOT)
    registry.register(APPROVE_SHOT)
    registry.register(ASSEMBLE_VIDEO)

    return registry
