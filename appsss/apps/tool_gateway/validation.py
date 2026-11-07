from typing import Any

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate
from pydantic import BaseModel, ConfigDict

from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema


class ToolValidationError(ValueError):
    """
    Typed Tool Gateway validation error.

    The `code` identifies the machine-readable failure category.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "SCHEMA_VALIDATION_ERROR",
        tool_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.tool_name = tool_name

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": str(self),
            "tool_name": self.tool_name,
        }


class ToolCall(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    tool_name: str
    input: dict[str, Any]


def validate_tool(tool: ToolSchema) -> ToolSchema:
    return ToolSchema.model_validate(tool)


def validate_registry(registry: ToolRegistry) -> None:
    for tool in registry.list():
        validate_tool(tool)


def validate_tool_call(
    registry: ToolRegistry,
    tool_name: str,
    tool_input: dict[str, Any],
) -> dict[str, Any]:
    """
    Validate an Agent tool call against the registered tool schema.
    """

    try:
        tool = registry.get(tool_name)
    except KeyError as exc:
        raise ToolValidationError(
            f"Unknown tool: {tool_name}",
            tool_name=tool_name,
        ) from exc

    schema = tool.schema

    if not schema:
        if tool_input:
            raise ToolValidationError(
                f"Tool '{tool_name}' does not accept input.",
                tool_name=tool_name,
            )

        return {}

    try:
        validate(
            instance=tool_input,
            schema=schema,
        )
    except JSONSchemaValidationError as exc:
        raise ToolValidationError(
            f"Invalid input for tool '{tool_name}': {exc.message}",
            code="SCHEMA_VALIDATION_ERROR",
            tool_name=tool_name,
        ) from exc

    return tool_input
