from typing import Any


class GraphRuntime:
    """
    LangGraph execution boundary.

    LangGraph owns agent reasoning/state transitions.
    Temporal owns durable long-running execution.
    """

    def __init__(self, graph: Any):
        self.graph = graph

    async def run(
        self,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Run the LangGraph.

        The graph produces a decision/result that can be
        handed to the execution layer.
        """
        result = await self.graph.ainvoke(input_data)

        return result
