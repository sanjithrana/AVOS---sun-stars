from typing import Any


class AgentRuntime:
    """
    Runtime boundary for agent execution.

    The agent decides what should happen.
    Execution of infrastructure remains outside the agent runtime.
    """

    def __init__(self, graph_runtime: Any):
        self.graph_runtime = graph_runtime

    async def run(
        self,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute agent reasoning through LangGraph.

        Infrastructure execution must not happen directly here.
        """
        return await self.graph_runtime.run(input_data)
