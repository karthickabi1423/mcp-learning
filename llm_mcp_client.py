import asyncio
import json
import os
import re

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
            fields[name] = (field_type | None, None)

    model = create_model(
        f"{tool.name}Arguments",
        **fields
    )

    try:
        validated = model.model_validate(arguments)

        validated_arguments = validated.model_dump(
            exclude_none=True
        )

        return True, validated_arguments

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

        error_details = "Unknown MCP tool error."

        if result.content:

            error_parts = []

            for content in result.content:

                if hasattr(content, "text"):
                    error_parts.append(content.text)

                else:
                    error_parts.append(str(content))

            if error_parts:
                error_details = "\n".join(error_parts)

        error_message = (
            f"MCP tool execution failed.\n"
            f"Tool: {tool_name}\n"
            f"Error: {error_details}"
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
# MCP RESOURCE HELPERS
# ==================================================

async def get_customer_resource(session, customer_id):
    """Read customer information from an MCP Resource."""

    resource = await session.read_resource(
        f"customer://{customer_id}"
    )

    return resource.contents[0].text


async def get_customer_prompt(session, customer_id):
    """Retrieve the customer analysis prompt from the MCP server."""

    prompt_result = await session.get_prompt(
        "analyze_customer",
        arguments={
            "customer_id": customer_id
        }
    )

    return prompt_result.messages[0].content.text


def extract_customer_id(text):

    match = re.search(
        r'\bcustomer\s+(\d+)\b',
        text,
        re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


async def prepare_resource_context(session, user_query):
    """Retrieve MCP Resource data when a customer ID is present."""

    customer_id = extract_customer_id(user_query)

    if not customer_id:
        return None

    print(
        f"\n[RESOURCE] Customer ID detected: {customer_id}"
    )

    customer_data = await get_customer_resource(
        session,
        customer_id
    )

    print("\n[RESOURCE] Customer data retrieved:")
    print(customer_data)

    return customer_data


async def enrich_with_customer_resources(
    session,
    tool_result
):
    """
    Find customer IDs in an MCP tool result and
    retrieve the corresponding customer Resources.
    """

    customer_ids = re.findall(
        r"Customer ID:\s*(\d+)",
        tool_result
    )

    for customer_id in customer_ids:

        print(f"[RESOURCE] Retrieving customer://{customer_id}")

        customer_resource = await get_customer_resource(
            session,
            customer_id
        )

        print(f"[RESOURCE] Retrieved customer://{customer_id}")

        tool_result += (
            f"\n\n=== MCP RESOURCE: customer://{customer_id} ===\n"
            f"{customer_resource}"
        )

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
            # DISCOVER MCP RESOURCE TEMPLATES
            # ------------------------------------------

            resource_templates = await session.list_resource_templates()

            print("\n=== MCP RESOURCE TEMPLATES ===")

            for template in resource_templates.resource_templates:

                print(f"Name: {template.name}")
                print(
                    f"URI Template: {template.uri_template}"
                )
                print(
                    f"Description: {template.description}"
                )

            # ------------------------------------------
            # DISCOVER MCP PROMPTS
            # ------------------------------------------

            prompts_result = await session.list_prompts()

            print("\n=== MCP PROMPTS ===")

            for prompt in prompts_result.prompts:

                print(f"\nPrompt: {prompt.name}")
                print(
                    f"Description: {prompt.description}"
                )

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
                print(
                    f"Description: {tool.description}"
                )
                print(
                    f"Input Schema: {tool.input_schema}"
                )

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

            prompt_text = None

            customer_id = extract_customer_id(
                user_query
            )

            if customer_id:

                prompt_text = await get_customer_prompt(
                    session,
                    customer_id
                )

                print(
                    "\n[PROMPT] Retrieved MCP Prompt:"
                )
                print(prompt_text)

            customer_data = await prepare_resource_context(
                session,
                user_query
            )

            # ------------------------------------------
            # SYSTEM PROMPT
            # ------------------------------------------

            system_prompt = """
You are an assistant connected to an MCP server.

You have access to tools, resources, and prompts
provided by the MCP server.

Rules:

1. Use MCP tools whenever they are relevant to the user's request.

2. For any arithmetic calculation, ALWAYS use the
   appropriate MCP calculation tool.

3. Do not perform arithmetic calculations yourself
   when an MCP calculation tool is available.

4. For customer-related information, ONLY use facts
   explicitly provided by MCP tools or MCP resources.

5. NEVER invent, assume, or infer customer facts
   that are not provided by MCP.

6. If information about a customer is not available
   from MCP, clearly say that the information is
   not available.

7. You may provide business recommendations or
   suggestions, but clearly distinguish recommendations
   from verified customer facts.

8. Do not treat a company name, customer name,
   industry, or status as evidence for additional facts.

9. Always use MCP results when providing
   customer-related information.

10. If an MCP tool returns an error, report the error
    accurately and continue processing the remaining
    parts of the user's request when possible.

11. When an MCP prompt is provided, follow its
    instructions while respecting all of the rules above.

12. Never use words such as "likely", "probably",
    "indicates", "represents", or similar language
    to turn missing customer data into implied facts.

13. When analyzing a customer, clearly separate:

    - Verified Facts: information directly provided by MCP.
    - Analysis: general observations about the customer's industry.
    - Recommendations: possible actions or opportunities.

14. Do not describe general industry characteristics
    as facts about the specific customer.

15. If a specific customer fact is not present in MCP data,
    say:

    "This information is not available in the MCP customer record."
16. Separate verified facts, inferences, and recommendations clearly.
17. Inferences must be based only on verified MCP data.
18. Recommendations may be general, but must not claim that a specific
    customer has a problem, need, event, or business situation unless
    that information exists in the MCP data.
19. Do not invent customer-specific opportunities, product needs,
    renewal status, business problems, or upcoming events.
20. When customer information is insufficient, explicitly say:
    "Not enough MCP data to determine this."

21. Inferences must be directly supported by verified MCP data.
22. Do not treat general industry knowledge as a customer-specific inference.
23. If a conclusion cannot be directly supported by MCP data, do not include it as an inference.
24. Recommendations should be based only on verified facts and clearly stated limitations.
25. Do not invent customer-specific needs, problems, opportunities, events, or business activities.
26. When the MCP data is insufficient, say: "Not enough MCP data to determine this."
"""

            messages = [
                {
                    "role": "system",
                    "content": system_prompt
                },
            ]

            if prompt_text:

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "MCP Prompt instructions "
                            "retrieved for this request:\n\n"
                            + prompt_text
                        ),
                    }
                )

            if customer_data:

                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "=== VERIFIED MCP CUSTOMER DATA ===\n\n"
                            + customer_data
                            + "\n\n"
                            "=== END VERIFIED MCP CUSTOMER DATA ===\n\n"
                            "GROUNDING REQUIREMENTS:\n"
                            "1. Treat only the fields explicitly present above "
                            "as verified customer facts.\n"
                            "2. Do not infer relationships between fields.\n"
                            "3. Do not infer facts from names, company names, "
                            "industry, or status values.\n"
                            "4. If requested customer information is not present "
                            "above, say that it is not available in the MCP "
                            "customer record.\n"
                            "5. General industry knowledge is allowed only when "
                            "clearly labelled as general industry analysis.\n"
                            "6. Business opportunities and next actions are "
                            "suggestions, not verified customer facts.\n"
                            "7. Never present assumptions or general industry "
                            "knowledge as facts about this specific customer."
                        ),
                    }
                )

            messages.append(
                {
                    "role": "user",
                    "content": user_query
                }
            )

            # ------------------------------------------
            # 5. AGENT CONFIGURATION
            # ------------------------------------------

            MAX_ITERATIONS = 10

            iteration = 0

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
                                    "name": (
                                        tool_call.function.name.split(
                                            "<|channel|>",
                                            1
                                        )[0]
                                        if "<|channel|>"
                                        in tool_call.function.name
                                        else tool_call.function.name
                                    ),
                                    "arguments":
                                        tool_call.function.arguments
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

                    if "<|channel|>" in tool_name:

                        tool_name = tool_name.split(
                            "<|channel|>",
                            1
                        )[0]

                    # ----------------------------------
                    # Parse arguments for duplicate check
                    # ----------------------------------

                    try:

                        arguments = json.loads(
                            tool_call.function.arguments
                        )

                    except json.JSONDecodeError:

                        arguments = (
                            tool_call.function.arguments
                        )

                    log_agent_event(
                        "LLM",
                        f"Requested tool '{tool_name}' "
                        f"with arguments: {arguments}"
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
                    # Generic Resource Enrichment
                    # ----------------------------------

                    tool_result = await enrich_with_customer_resources(
                        session,
                        tool_result
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
# RAW MCP ERROR TEST
# ==================================================

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

            print("\n=== RAW RESULT ===")
            print("is_error:", result.is_error)
            print("content:", result.content)
            print(
                "structured_content:",
                result.structured_content
            )


if __name__ == "__main__":
    asyncio.run(main())