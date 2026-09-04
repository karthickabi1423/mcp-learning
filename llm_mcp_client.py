import asyncio
import json
import os

from dotenv import load_dotenv
from groq import Groq

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# --------------------------------------------------
# GROQ SETUP
# --------------------------------------------------

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is not set in the .env file.")

groq_client = Groq(api_key=api_key)


# --------------------------------------------------
# MCP SERVER SETUP
# --------------------------------------------------

server_params = StdioServerParameters(
    command="python",
    args=["server.py"],
)


# --------------------------------------------------
# MAIN
# --------------------------------------------------

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

            messages = [
                {
                    "role": "user",
                    "content": user_query
                }
            ]


            # ------------------------------------------
            # 5. SEND USER QUESTION TO LLM
            # ------------------------------------------

            while True:

                response = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=messages,
                    tools=groq_tools
                )

                message = response.choices[0].message

                print("\n=== LLM RESPONSE ===")
                print(message)

                # No tool call means the model has finished
                if not message.tool_calls:
                    print("\n=== FINAL ANSWER ===")
                    print(message.content)
                    break

                # Add assistant tool-call message
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

                # Execute every requested tool
                for tool_call in message.tool_calls:

                    tool_name = tool_call.function.name

                    arguments = json.loads(
                        tool_call.function.arguments
                    )

                    print("\n=== MCP TOOL CALL ===")
                    print("Tool:", tool_name)
                    print("Arguments:", arguments)

                    result = await session.call_tool(
                        tool_name,
                        arguments=arguments
                    )

                    if result.is_error:

                        tool_result = result.content[0].text

                        print("\n=== MCP TOOL ERROR ===")
                        print(tool_result)

                    else:

                        tool_result = str(
                            result.structured_content["result"]
                        )

                        print("\n=== MCP TOOL RESULT ===")
                        print(tool_result)

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result
                        }
                    )


            # ------------------------------------------
            # 6. CHECK WHETHER LLM REQUESTED A TOOL
            # ------------------------------------------

            if message.tool_calls:

                # --------------------------------------
                # 7. SAVE LLM TOOL-CALL MESSAGE
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
                                    "arguments": tool_call.function.arguments,
                                },
                            }
                            for tool_call in message.tool_calls
                        ],
                    }
                )


                # --------------------------------------
                # 8. EXECUTE MCP TOOL
                # --------------------------------------

                for tool_call in message.tool_calls:

                    tool_name = tool_call.function.name
                    tool_arguments = tool_call.function.arguments

                    print("\n=== MCP TOOL REQUEST ===")
                    print("Tool:", tool_name)
                    print("Arguments:", tool_arguments)


                    # Convert JSON string → Python dictionary

                    arguments = json.loads(tool_arguments)

                    print("\n=== PARSED ARGUMENTS ===")
                    print(arguments)


                    # Call MCP server

                    result = await session.call_tool(
                        tool_name,
                        arguments=arguments
                    )


                    print("\n=== MCP TOOL RESULT ===")
                    print(result)


                    # ----------------------------------
                    # 9. EXTRACT MCP RESULT
                    # ----------------------------------

                    if result.is_error:
                        tool_result = result.content[0].text

                        print("\n=== MCP TOOL ERROR ===")
                        print(tool_result)

                    else:
                        tool_result = str(result.structured_content["result"])

                        print("\n=== EXTRACTED TOOL RESULT ===")
                        print(tool_result)


                    # ----------------------------------
                    # 10. SEND MCP RESULT TO LLM
                    # ----------------------------------

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": tool_result,
                        }
                    )


                # --------------------------------------
                # 11. CALL LLM AGAIN
                # --------------------------------------

                final_response = groq_client.chat.completions.create(
                    model="openai/gpt-oss-20b",
                    messages=messages,
                    tools=groq_tools,
                )


                final_message = final_response.choices[0].message


                # --------------------------------------
                # 12. FINAL ANSWER
                # --------------------------------------

                print("\n=== FINAL LLM RESPONSE ===")
                print(final_message)


            else:

                print("\nLLM did not request any tool.")


# --------------------------------------------------
# PROGRAM ENTRY POINT
# --------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())