import asyncio
import json
import os

from dotenv import load_dotenv
from groq import Groq

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from pydantic import create_model, ValidationError


# ==================================================
# GROQ SETUP
# ==================================================

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is not set in the .env file.")

groq_client = Groq(api_key=api_key)


# ==================================================
# TOOL ARGUMENT VALIDATION
# ==================================================

def validate_tool_arguments(tool, arguments):
    schema = tool.input_schema

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # --------------------------------------------------
    # ENUM VALIDATION
    # --------------------------------------------------

    for name, definition in properties.items():
        allowed_values = definition.get("enum")

        if allowed_values and name in arguments:
            if arguments[name] not in allowed_values:
                return (
                    False,
                    f"Argument '{name}' must be one of "
                    f"{allowed_values}. Received: {arguments[name]!r}"
                )

    # --------------------------------------------------
    # PYDANTIC TYPE VALIDATION
    # --------------------------------------------------

    fields = {}

    for name, definition in properties.items():

        field_type = str

        if definition.get("type") == "integer":
            field_type = int

        elif definition.get("type") == "number":
            field_type = float

        elif definition.get("type") == "string":
            field_type = str

        if name in required:
            fields[name] = (field_type, ...)
        else:
            fields[name] = (field_type, None)

    model = create_model(
        f"{tool.name}Arguments",
        **fields
    )

    try:
        validated = model.model_validate(arguments)

        return True, validated.model_dump()

    except ValidationError as error:
        return False, str(error)

# ==================================================
# AGENT LOGGING
# ==================================================

def log_agent_event(event, message):
    print(f"\n[{event}] {message}")


# ==================================================
# MCP TOOL EXECUTION
# ==================================================

async def execute_mcp_tool(
    session,
    tool_call,
    available_tools,
    tool_map
):

    tool_name = tool_call.function.name

    # --------------------------------------------------
    # 1. TOOL NAME VALIDATION
    # --------------------------------------------------

    if tool_name not in available_tools:

        error_message = f"Unknown MCP tool: {tool_name}"

        print("\n=== MCP TOOL ERROR ===")
        print(error_message)

        return error_message

    # --------------------------------------------------
    # 2. JSON VALIDATION
    # --------------------------------------------------

    try:

        arguments = json.loads(
            tool_call.function.arguments
        )

    except json.JSONDecodeError:

        error_message = (
            f"Invalid JSON arguments for tool: {tool_name}"
        )

        print("\n=== MCP TOOL ERROR ===")
        print(error_message)

        return error_message

    # --------------------------------------------------
    # 3. SCHEMA VALIDATION
    # --------------------------------------------------

    tool = tool_map[tool_name]

    is_valid, validation_result = validate_tool_arguments(
        tool,
        arguments
    )

    if not is_valid:

        error_message = (
            f"Invalid arguments for tool '{tool_name}':\n"
            f"{validation_result}"
        )

        print("\n=== MCP TOOL VALIDATION ERROR ===")
        print(error_message)

        return error_message

    arguments = validation_result

    # --------------------------------------------------
    # 4. MCP TOOL EXECUTION
    # --------------------------------------------------

    log_agent_event(
        "MCP",
        f"Executing tool '{tool_name}' with arguments: {arguments}"
    )
    try:

        result = await session.call_tool(
            tool_name,
            arguments=arguments
        )

    except Exception as error:

        error_message = (
            f"MCP tool '{tool_name}' failed during execution: "
            f"{error}"
        )

        print("\n=== MCP TOOL EXECUTION ERROR ===")
        print("Tool:", tool_name)
        print("Error:", error_message)

        return error_message

    # --------------------------------------------------
    # 5. MCP-REPORTED TOOL ERROR
    # --------------------------------------------------

    if result.is_error:

        error_message = (
            f"MCP tool '{tool_name}' returned an error."
        )

        if result.content:

            first_content = result.content[0]

            if hasattr(first_content, "text"):

                error_message = (
                    f"MCP tool '{tool_name}' returned an error: "
                    f"{first_content.text}"
                )

        print("\n=== MCP TOOL ERROR ===")
        print("Tool:", tool_name)
        print("Error:", error_message)

        return error_message

    # --------------------------------------------------
    # 6. HANDLE SUCCESSFUL RESULT
    # --------------------------------------------------

    try:

        if result.structured_content:

            if "result" in result.structured_content:

                tool_result = str(
                    result.structured_content["result"]
                )

            else:

                tool_result = str(
                    result.structured_content
                )

        elif result.content:

            first_content = result.content[0]

            if hasattr(first_content, "text"):

                tool_result = first_content.text

            else:

                tool_result = str(first_content)

        else:

            tool_result = "MCP tool returned no result."

    except Exception as error:

        error_message = (
            f"Unable to process the result from MCP tool "
            f"'{tool_name}': {error}"
        )

        print("\n=== MCP RESULT PROCESSING ERROR ===")
        print("Tool:", tool_name)
        print("Error:", error_message)

        return error_message

    log_agent_event(
        "MCP",
        f"Tool '{tool_name}' completed successfully"
    )

    print("Result:")
    print(tool_result)

    return tool_result


# ==================================================
# MCP SERVER SETUP
# ==================================================

server_params = StdioServerParameters(
    command="python",
    args=["server.py"],
)


# ==================================================
# MAIN AGENT
# ==================================================

async def main():

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # ------------------------------------------
            # 1. INITIALIZE MCP CONNECTION
            # ------------------------------------------

            await session.initialize()

            print("\n=== MCP CONNECTION ===")
            print("Connected to MCP server successfully!")

            # ------------------------------------------
            # 2. DISCOVER MCP TOOLS
            # ------------------------------------------

            tools_result = await session.list_tools()

            available_tools = {
                tool.name
                for tool in tools_result.tools
            }

            tool_map = {
                tool.name: tool
                for tool in tools_result.tools
            }

            print("\n=== MCP TOOLS ===")

            for tool in tools_result.tools:

                print(f"\nTool: {tool.name}")
                print(f"Description: {tool.description}")
                print(f"Input Schema: {tool.input_schema}")

            # ------------------------------------------
            # 3. CONVERT MCP TOOLS TO GROQ TOOLS
            # ------------------------------------------

            groq_tools = []

            for tool in tools_result.tools:

                groq_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                )

            print("\n=== GROQ TOOLS ===")

            for tool in groq_tools:
                print(tool)

            # ------------------------------------------
            # 4. USER MESSAGE
            # ------------------------------------------

            user_query = input("\nYou: ")

            system_prompt = """
You are an assistant connected to an MCP server.

You have access to tools provided by the MCP server.

When a user's request can be answered using an available tool,
prefer using the tool instead of calculating or guessing the result yourself.

Use MCP tools whenever they are relevant to the user's request.

Do not invent customer information.

Always use the MCP tool results when providing customer-related information.
"""

            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_query
                }
            ]

            # ------------------------------------------
            # 5. AGENT CONFIGURATION
            # ------------------------------------------

            MAX_ITERATIONS = 10

            iteration = 0

            # Remember previously executed tool calls
            executed_tool_calls = set()

            # ------------------------------------------
            # 6. AGENT LOOP
            # ------------------------------------------

            while iteration < MAX_ITERATIONS:

                iteration += 1

                print(
                    f"\n=== AGENT ITERATION {iteration} ==="
                )

                response = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=messages,
                    tools=groq_tools
                )

                message = response.choices[0].message

                log_agent_event(
                    "LLM",
                    f"Response received in iteration {iteration}"
                )

                # --------------------------------------
                # 7. CHECK FOR TOOL CALL
                # --------------------------------------

                if not message.tool_calls:

                    print("\n=== FINAL ANSWER ===")
                    print(message.content)

                    break

                # --------------------------------------
                # 8. SAVE LLM TOOL-CALL MESSAGE
                # --------------------------------------

                messages.append(
                    {
                        "role": "assistant",
                        "content": message.content,
                        "tool_calls": [
                            {
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments
                                }
                            }
                            for tool_call in message.tool_calls
                        ]
                    }
                )

                # --------------------------------------
                # 9. EXECUTE MCP TOOLS
                # --------------------------------------

                for tool_call in message.tool_calls:

                    tool_name = tool_call.function.name

                    # ----------------------------------
                    # Parse arguments for duplicate check
                    # ----------------------------------

                    try:

                        arguments = json.loads(
                            tool_call.function.arguments
                        )

                    except json.JSONDecodeError:

                        arguments = tool_call.function.arguments

                    log_agent_event(
                        "LLM",
                        f"Requested tool '{tool_name}' with arguments: {arguments}"
                    )

                    # ----------------------------------
                    # Create unique tool-call key
                    # ----------------------------------

                    if isinstance(arguments, dict):

                        tool_call_key = (
                            tool_name,
                            json.dumps(
                                arguments,
                                sort_keys=True
                            )
                        )

                    else:

                        tool_call_key = (
                            tool_name,
                            str(arguments)
                        )

                    # ----------------------------------
                    # DUPLICATE TOOL CALL DETECTION
                    # ----------------------------------

                    if tool_call_key in executed_tool_calls:

                        print(
                            "\n=== DUPLICATE TOOL CALL DETECTED ==="
                        )

                        print(
                            "Tool:",
                            tool_name
                        )

                        print(
                            "Arguments:",
                            arguments
                        )

                        duplicate_message = (
                            f"Duplicate tool call detected for "
                            f"'{tool_name}'. "
                            "The same tool with the same arguments "
                            "was already executed."
                        )

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "content": duplicate_message
                            }
                        )

                        continue

                    # ----------------------------------
                    # Remember this tool call
                    # ----------------------------------

                    executed_tool_calls.add(
                        tool_call_key
                    )

                    # ----------------------------------
                    # Execute MCP tool
                    # ----------------------------------

                    tool_result = await execute_mcp_tool(
                        session,
                        tool_call,
                        available_tools,
                        tool_map
                    )

                    # ----------------------------------
                    # Send result back to LLM
                    # ----------------------------------

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        }
                    )

            # ------------------------------------------
            # 10. AGENT ITERATION LIMIT
            # ------------------------------------------

            if iteration >= MAX_ITERATIONS:

                print("\n=== AGENT STOPPED ===")
                print(
                    "Maximum agent iterations reached."
                )



# ==================================================
# DUPLICATE TOOL CALL TEST
# ==================================================

def test_duplicate_detection():

    print("\n=== DUPLICATE TOOL CALL TEST ===")

    executed_tool_calls = set()

    # ------------------------------------------
    # First tool call
    # ------------------------------------------

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

    print("\nFirst tool call:")
    print("Tool:", tool_name)
    print("Arguments:", arguments)

    if tool_call_key in executed_tool_calls:

        print("❌ Duplicate detected")

    else:

        executed_tool_calls.add(tool_call_key)

        print("✅ First call accepted")
        print("Tool would be executed.")


    # ------------------------------------------
    # Second identical tool call
    # ------------------------------------------

    print("\nSecond tool call:")
    print("Tool:", tool_name)
    print("Arguments:", arguments)

    if tool_call_key in executed_tool_calls:

        print("⚠️ Duplicate tool call detected!")
        print("MCP tool will NOT be executed again.")

    else:

        executed_tool_calls.add(tool_call_key)

        print("✅ Call accepted")
        print("Tool would be executed.")


    # ------------------------------------------
    # Third different tool call
    # ------------------------------------------

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

    print("\nThird tool call:")
    print("Tool:", tool_name)
    print("Arguments:", different_arguments)

    if different_tool_call_key in executed_tool_calls:

        print("⚠️ Duplicate detected")

    else:

        executed_tool_calls.add(
            different_tool_call_key
        )

        print("✅ Different call accepted")
        print("Tool would be executed.")


        
# ==================================================
# PROGRAM ENTRY POINT
# ==================================================

async def test_unknown_tool():
    print("\n=== UNKNOWN TOOL TEST ===")

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

    print("\n=== TEST RESULT ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(test_unknown_tool())