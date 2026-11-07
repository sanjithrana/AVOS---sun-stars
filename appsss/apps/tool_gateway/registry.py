from collections.abc import Iterable

from tool_gateway.schemas import ToolSchema


class ToolRegistry:
    """
    In-memory registry of tools available to the Agentic Core.

    The registry stores tool declarations only.
    It does not execute tools or access infrastructure.
    """

    def __init__(
        self,
        tools: Iterable[ToolSchema] | None = None,
    ) -> None:
        self._tools: dict[str, ToolSchema] = {}

        if tools is not None:
            for tool in tools:
                self.register(tool)

    def register(self, tool: ToolSchema) -> None:
        """
        Register a tool by its unique name.

        Raises:
            ValueError: if a tool with the same name already exists.
        """
        if tool.name in self._tools:
            raise ValueError(
                f"Tool already registered: {tool.name}"
            )

        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolSchema:
        """
        Retrieve a registered tool.

        Raises:
            KeyError: if the tool does not exist.
        """
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(
                f"Tool not registered: {name}"
            ) from None

    def list(self) -> list[ToolSchema]:
        """Return all registered tools."""
        return list(self._tools.values())

    def exists(self, name: str) -> bool:
        """Return whether a tool is registered."""
        return name in self._tools
