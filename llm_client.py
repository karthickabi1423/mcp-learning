import os
import json

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("GROQ_API_KEY is not set in the .env file.")

client = Groq(api_key=api_key)


def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"The weather in {city} is sunny and 30°C."


tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the city."
                    }
                },
                "required": ["city"]
            }
        }
    }
]


# --------------------------------------------------
# 1. Create the initial conversation
# --------------------------------------------------

messages = [
    {
        "role": "user",
        "content": "What is the weather in Chennai?"
    }
]


# --------------------------------------------------
# 2. First LLM call
# --------------------------------------------------

response = client.chat.completions.create(
    model="openai/gpt-oss-20b",
    messages=messages,
    tools=tools
)

message = response.choices[0].message


print("\n=== LLM RESPONSE ===")
print(message)


# --------------------------------------------------
# 3. Check whether the LLM requested a tool
# --------------------------------------------------

if message.tool_calls:

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

    for tool_call in message.tool_calls:

        tool_name = tool_call.function.name
        tool_arguments = tool_call.function.arguments

        print("\n=== TOOL REQUEST ===")
        print("Tool:", tool_name)
        print("Arguments:", tool_arguments)


        # --------------------------------------------------
        # 4. Execute the requested tool
        # --------------------------------------------------

        if tool_name == "get_weather":

            arguments = json.loads(tool_arguments)

            result = get_weather(
                arguments["city"]
            )

            print("\n=== TOOL RESULT ===")
            print(result)


            # --------------------------------------------------
            # 5. Send the tool result back to the LLM
            # --------------------------------------------------

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": result
                }
            )


    
    # 6. Call the LLM again with the tool result

    final_response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=messages,
        tools=tools
    )



    # 7. Get the final answer

    final_message = final_response.choices[0].message

    print("\n=== FINAL LLM RESPONSE ===")
    print(final_message.content)