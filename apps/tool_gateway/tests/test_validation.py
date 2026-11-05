import pytest

from tool_gateway.registry import ToolRegistry
from tool_gateway.schemas import ToolSchema
from tool_gateway.validation import (
    ToolValidationError,
    validate_tool_call,
)


def make_echo_tool() -> ToolSchema:
    return ToolSchema(
        name="echo_tool",
        description="Development echo tool",
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
        permission="development",
        timeout=5,
    )


def make_ping_tool() -> ToolSchema:
    return ToolSchema(
        name="ping_tool",
        description="Development test tool",
        schema={},
        permission="development",
        timeout=5,
    )


def test_valid_ping_tool_call_is_accepted():
    registry = ToolRegistry()

    registry.register(make_ping_tool())

    result = validate_tool_call(
        registry,
        "ping_tool",
        {},
    )

    assert result == {}


def test_valid_tool_call_is_accepted():
    registry = ToolRegistry()

    registry.register(make_echo_tool())

    result = validate_tool_call(
        registry,
        "echo_tool",
        {
            "message": "hello",
        },
    )

    assert result == {
        "message": "hello",
    }


def test_missing_required_field_is_rejected():
    registry = ToolRegistry()

    registry.register(make_echo_tool())

    with pytest.raises(ToolValidationError) as exc_info:
        validate_tool_call(
            registry,
            "echo_tool",
            {},
        )

    assert "message" in str(exc_info.value)


def test_extra_field_is_rejected():
    registry = ToolRegistry()

    registry.register(make_echo_tool())

    with pytest.raises(ToolValidationError):
        validate_tool_call(
            registry,
            "echo_tool",
            {
                "message": "hello",
                "unexpected": "value",
            },
        )


def test_invalid_type_is_rejected():
    registry = ToolRegistry()

    registry.register(make_echo_tool())

    with pytest.raises(ToolValidationError):
        validate_tool_call(
            registry,
            "echo_tool",
            {
                "message": 123,
            },
        )


def test_unknown_tool_is_rejected():
    registry = ToolRegistry()

    with pytest.raises(ToolValidationError):
        validate_tool_call(
            registry,
            "unknown_tool",
            {},
        )


def test_ping_tool_rejects_extra_input():
    registry = ToolRegistry()

    registry.register(make_ping_tool())

    with pytest.raises(ToolValidationError):
        validate_tool_call(
            registry,
            "ping_tool",
            {
                "unexpected": "value",
            },
        )


def test_invalid_input_returns_schema_validation_error():
    registry = ToolRegistry()
    registry.register(make_echo_tool())

    with pytest.raises(ToolValidationError) as exc_info:
        validate_tool_call(
            registry,
            "echo_tool",
            {},
        )

    error = exc_info.value

    assert error.code == "SCHEMA_VALIDATION_ERROR"
    assert error.tool_name == "echo_tool"


def test_extra_field_returns_schema_validation_error():
    registry = ToolRegistry()
    registry.register(make_echo_tool())

    with pytest.raises(ToolValidationError) as exc_info:
        validate_tool_call(
            registry,
            "echo_tool",
            {
                "message": "hello",
                "unexpected": "value",
            },
        )

    assert exc_info.value.code == "SCHEMA_VALIDATION_ERROR"
    assert exc_info.value.tool_name == "echo_tool"
