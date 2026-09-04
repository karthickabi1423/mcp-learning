import asyncio

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


server_params = StdioServerParameters(
    command="python",
    args=["server.py"],
)



async def run_client():

    async with stdio_client(server_params) as (read, write):

        async with ClientSession(read, write) as session:

            # Initialize connection
            await session.initialize()

            print("\nConnected to MCP server successfully!\n")

            # Discover tools
            tools = await session.list_tools()

            result = await session.call_tool(
                "add_numbers",
                arguments={
                    "a": 10,
                    "b": 20
                }
            )

            print("\n=== ADD NUMBERS RESULT ===")
            print(result)


                        # Call calculate tool
            result = await session.call_tool(
                "calculate",
                arguments={
                    "a": 20,
                    "b": 5,
                    "operation": "multiply"
                }
            )

            print("\n=== CALCULATE RESULT ===")
            print(result)


            # Call search_customers tool
            result = await session.call_tool(
                "search_customers",
                arguments={
                    "industry": "Software",
                    "status": "Active"
                }
            )

            print("\n=== SEARCH CUSTOMERS RESULT ===")
            print(result)


            # Read customer resource
            result = await session.read_resource(
                "customer://1001"
            )

            print("\n=== CUSTOMER RESOURCE ===")
            print(result)


            # Get customer analysis prompt
            result = await session.get_prompt(
                "analyze_customer",
                arguments={
                    "customer_id": "1001"
                }
            )

            print("\n=== CUSTOMER ANALYSIS PROMPT ===")
            print(result)

            print("=== TOOLS ===")

            for tool in tools.tools:
                print(f"- {tool.name}")
                print(f"  Description: {tool.description}")
                print(f"Input Schema: {tool.input_schema}")

            # Discover resources
            resources = await session.list_resources()

            print("\n=== RESOURCES ===")

            for resource in resources.resources:
                print(f"- {resource.uri}")
                print(f"  Name: {resource.name}")

            # Discover resource templates
            resource_templates = await session.list_resource_templates()


            for template in resource_templates.resource_templates:
                print(f"- {template.uri_template}")
                print(f"  Name: {template.name}")

            # Discover prompts
            prompts = await session.list_prompts()

            print("\n=== PROMPTS ===")

            for prompt in prompts.prompts:
                print(f"- {prompt.name}")
                print(f"  Description: {prompt.description}")


if __name__ == "__main__":
    asyncio.run(run_client())