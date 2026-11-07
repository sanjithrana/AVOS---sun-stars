from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agentic_core.tool_gateway.gateway import dispatch
from agentic_core.tool_gateway.permissions import AgentRole
from agentic_core.tool_gateway.tools.submit_video_generation import (
    SubmitVideoGenerationTool,
)
from tool_gateway.registry import ToolRegistry


class DirectorState(TypedDict, total=False):
    intent: str
    role: AgentRole
    tool_name: str
    arguments: dict[str, Any]
    agent_result: dict[str, Any]


def analyze_intent(state: DirectorState) -> DirectorState:
    return {
        **state,
        "intent": state.get("intent", ""),
    }


def decide_action(state: DirectorState) -> DirectorState:
    if state.get("intent") == "generate project":
        return {
            **state,
            "tool_name": "submit_video_generation",
        }

    return {
        **state,
        "tool_name": "",
    }


async def tool_gateway_node(
    state: DirectorState,
) -> DirectorState:
    registry = ToolRegistry()

    tool = SubmitVideoGenerationTool()

    registry.register(tool.schema)

    async def executor(
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        return await tool.execute(arguments)

    result = await dispatch(
        registry=registry,
        role=state["role"],
        tool_name=state["tool_name"],
        tool_input=state["arguments"],
        executor=executor,
    )

    return {
        **state,
        "agent_result": {
            "success": result.status == "SUCCESS",
            "tool_name": result.tool_name,
            **result.result,
        },
    }


def build_director_graph():
    graph = StateGraph(DirectorState)

    graph.add_node("analyze_intent", analyze_intent)
    graph.add_node("decide_action", decide_action)
    graph.add_node("tool_gateway", tool_gateway_node)

    graph.add_edge(START, "analyze_intent")
    graph.add_edge("analyze_intent", "decide_action")
    graph.add_edge("decide_action", "tool_gateway")
    graph.add_edge("tool_gateway", END)

    return graph.compile()
