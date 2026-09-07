import asyncio
import json
from unittest import result
import pytest

from mcp import ClientSession, StdioServerParameters, stdio_client
from llm_mcp_client import execute_mcp_tool

server_params = StdioServerParameters(
    command="python",
    args=["server.py"],
)

# ==================================================
# DUPLICATE TOOL CALL TEST
# ==================================================

def test_duplicate_detection():

    executed_tool_calls = set()

    tool_name = "calculate"

    arguments = {
        "a": 10,
        "b": 10,
        "operation": "multiply"
    }

    tool_call_key = (
        tool_name,
        json.dumps(
            arguments,
            sort_keys=True
        )
    )

    # First call should be accepted
    assert tool_call_key not in executed_tool_calls

    executed_tool_calls.add(tool_call_key)

    # Second identical call should be detected as duplicate
    assert tool_call_key in executed_tool_calls

    # Different call should be accepted
    different_arguments = {
        "a": 20,
        "b": 5,
        "operation": "multiply"
    }

    different_tool_call_key = (
        tool_name,
        json.dumps(
            different_arguments,
            sort_keys=True
        )
    )

    assert different_tool_call_key not in executed_tool_calls

@pytest.mark.asyncio
async def test_unknown_tool():
    tool_map = {
        "add_numbers": "dummy",
        "calculate": "dummy",
        "search_customers": "dummy"
    }

    fake_tool_call = type(
        "FakeToolCall",
        (),
        {
            "function": type(
                "FakeFunction",
                (),
                {
                    "name": "unknown_tool",
                    "arguments": "{}"
                }
            )()
        }
    )()

    result = await execute_mcp_tool(
        session=None,
        tool_call=fake_tool_call,
        available_tools=[],
        tool_map=tool_map
    )

    assert result == "Unknown MCP tool: unknown_tool"

@pytest.mark.asyncio
async def test_invalid_json():
    print("\n=== INVALID JSON TEST ===")

    fake_tool_call = type(
        "FakeToolCall",
        (),
        {
            "function": type(
                "FakeFunction",
                (),
                {
                    "name": "calculate",
                    "arguments": '{"a": 10, "b": 5, "operation": "multiply"'
                }
            )()
        }
    )()

    result = await execute_mcp_tool(
        session=None,
        tool_call=fake_tool_call,
        available_tools=["calculate"],
        tool_map={}
    )

    assert result == "Invalid JSON arguments for tool: calculate"

@pytest.mark.asyncio
async def test_missing_required_argument():
    print("\n=== MISSING REQUIRED ARGUMENT TEST ===")

    fake_tool_call = type(
        "FakeToolCall",
        (),
        {
            "function": type(
                "FakeFunction",
                (),
                {
                    "name": "calculate",
                    "arguments": '{"a": 10, "operation": "multiply"}'
                }
            )()
        }
    )()

    fake_tool = type(
        "FakeTool",
        (),
        {
            "name": "calculate",
            "input_schema": {
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                    "operation": {
                        "type": "string",
                        "enum": [
                            "add",
                            "subtract",
                            "multiply",
                            "divide"
                        ]
                    }
                },
                "required": ["a", "b", "operation"]
            }
        }
    )()

    result = await execute_mcp_tool(
        session=None,
        tool_call=fake_tool_call,
        available_tools=["calculate"],
        tool_map={"calculate": fake_tool}
    )

    assert result.startswith("Invalid arguments for tool 'calculate':")
    assert "Field required" in result
    assert "\nb\n" in result

@pytest.mark.asyncio
async def test_wrong_argument_type():
    print("\n=== WRONG ARGUMENT TYPE TEST ===")

    fake_tool_call = type(
        "FakeToolCall",
        (),
        {
            "function": type(
                "FakeFunction",
                (),
                {
                    "name": "calculate",
                    "arguments": '{"a": "ten", "b": 5, "operation": "multiply"}'
                }
            )()
        }
    )()

    fake_tool = type(
        "FakeTool",
        (),
        {
            "name": "calculate",
            "input_schema": {
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                    "operation": {
                        "type": "string",
                        "enum": [
                            "add",
                            "subtract",
                            "multiply",
                            "divide"
                        ]
                    }
                },
                "required": ["a", "b", "operation"]
            }
        }
    )()

    result = await execute_mcp_tool(
        session=None,
        tool_call=fake_tool_call,
        available_tools=["calculate"],
        tool_map={"calculate": fake_tool}
    )

    assert result.startswith("Invalid arguments for tool 'calculate':")
    assert "a" in result
    assert "valid number" in result

@pytest.mark.asyncio  
async def test_raw_mcp_error():
    print("\n=== RAW MCP ERROR TEST ===")

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:

            await session.initialize()

            result = await session.call_tool(
                "calculate",
                arguments={
                    "a": 20,
                    "b": 0,
                    "operation": "divide"
                }
            )

            assert result.is_error is False
            assert result.structured_content == {
                "result": "Error: Cannot divide by zero."
            }
            assert result.content[0].text == "Error: Cannot divide by zero."
