import pytest

from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema
from tool_gateway.validation import (
    ToolValidationError,
    validate_tool_call,
)


def test_valid_ping_input_is_accepted():
    registry = ToolRegistry()
    registry.register(
        ToolSchema(
            name="ping_tool",
            description="Development test tool",
            schema={},
            permission="memory",
            timeout=5,
        )
    )

    result = validate_tool_call(
        registry,
        "ping_tool",
        {},
    )

    assert result == {}


def test_invalid_schema_input_is_rejected():
    registry = ToolRegistry()

    registry.register(
        ToolSchema(
            name="echo_tool",
            description="Validation test tool",
            schema={
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                    },
                },
                "required": ["message"],
                "additionalProperties": False,
            },
            permission="memory",
            timeout=5,
        )
    )

    with pytest.raises(ToolValidationError) as exc_info:
        validate_tool_call(
            registry,
            "echo_tool",
            {
                "unexpected": "value",
            },
        )

    assert exc_info.value.code == "SCHEMA_VALIDATION_ERROR"
